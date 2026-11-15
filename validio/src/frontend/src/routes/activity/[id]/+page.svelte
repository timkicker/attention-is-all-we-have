<script lang="ts">
  /// One request or standing order, read top to bottom: what the agent asked,
  /// what Validio checked at Valio (with the options it compared, when the
  /// backend has them), the rule that decided, the result, and the proof folded
  /// away. On the desk "How this was checked" stands in the margin: the order
  /// against the limits, what Valio was asked, the sealed record. While it
  /// waits, the owner answers here: Approve asks for the approval code under
  /// the buttons, Reject needs none.
  ///
  /// Motion (plans/003, 007, 010, 011, 021): the title arrives from the clicked row; Approve
  /// opens the code in place and the answer lands as one wave; Proof draws as a chain; the
  /// margin's scale shows where this order landed; Replay walks the whole story once.
  import { tick, untrack } from "svelte";
  import { page } from "$app/state";
  import { ChevronRight, Play, Square } from "@lucide/svelte";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { agentApi } from "$lib/api/agent";
  import { api, ApiError } from "$lib/api/client";
  import type { ActivityDetail } from "$lib/api/types";
  import { bump } from "$lib/chrome.svelte";
  import { owner, isCode } from "$lib/owner.svelte";
  import VCode from "$lib/v/VCode.svelte";
  import { blurSwap, buzz, collapse, DUR, fadeOut, reduced, rise } from "$lib/motion";
  import { morph, peek } from "$lib/peek.svelte";
  import type { ActivityItem } from "$lib/api/types";
  import { BusyLabel, Current, dayHead, dayTime, Empty, Explain, hm, LimitScale, live, Loading, LoadError, money, nb, PageHead, pillOf, Ticker } from "$lib/v2";
  import Options from "./Options.svelte";

  const id = $derived(page.params.id ?? "");
  const detail = live(() => api.activityItem(id), 2000, () => `item:${id}`);
  const d = $derived(detail.data?.item.id === id ? detail.data : undefined);
  // The title the list already knew, while the detail's own answer is on its way (plans/003).
  const head = $derived(d?.item ?? peek.get(id));
  const missing = $derived(!d && detail.status === 404);
  // The rules this request was decided under can be older than today's: then the link says which they are now.
  const rules = live(() => agentApi.rules().catch(() => null), 2000, () => "rules-raw");
  const later = $derived(d && rules.data && rules.data.passVersion !== d.rule.version ? rules.data.passVersion : null);
  // The options Validio compared: the backend's request view; none for a standing order or in the fixture.
  const req = live(() => (id.startsWith("S-") ? Promise.resolve(null) : api.request(id).catch(() => null)), 2000, () => `request:${id}`);
  const r = $derived(d?.item.kind === "request" && req.data?.id === id ? req.data : undefined);
  const chosen = $derived(r?.lines[0] ? [...r.lines[0].options, ...(r.lines[0].substitutes ?? []), ...(r.lines[0].beyondList ?? [])].find((o) => o.verdict === "chosen") : undefined);
  const planted = $derived(
    r?.lines.flatMap((l) => [...l.options, ...(l.substitutes ?? []), ...(l.beyondList ?? [])]).find((o) => o.supplierText?.planted || o.supplierText?.reader?.flags.some((f) => f.code === "addresses_agents")),
  );
  let options = $state<Options>();

  const pill = $derived(d ? pillOf(d.item) : undefined);
  // The order against the limits it was decided under (plans/025, P3): the version's own limits from the
  // server; without them, today's rules while they are still the ones it was decided under.
  const limits = $derived.by(() => {
    if (!d || d.item.kind !== "request" || d.item.totalCents == null) return null;
    const l =
      d.rule.limits ??
      (rules.data?.saved && !later ? { aloneUpToCents: rules.data.aloneUpToCents, approvalUpToCents: rules.data.approvalUpToCents } : null);
    return l ? { total: d.item.totalCents, alone: l.aloneUpToCents, most: l.approvalUpToCents } : null;
  });
  type Zone = "alone" | "wait" | "blocked";
  const zone = (total: number, alone: number, most: number): Zone => (total <= alone ? "alone" : total <= most ? "wait" : "blocked");
  const ZONE_WORDS: Record<Zone, string> = { alone: "be ordered alone", wait: "wait for you", blocked: "be blocked" };
  // The Rules changed since: what today's would do with the same order, when that is different.
  const today = $derived.by(() => {
    if (!limits || !later || !rules.data?.saved) return null;
    const then = zone(limits.total, limits.alone, limits.most);
    const now = zone(limits.total, rules.data.aloneUpToCents, rules.data.approvalUpToCents);
    return now === then ? null : `Under today's Rules (version ${later}) it would ${ZONE_WORDS[now]}.`;
  });

  // ---------- the decision's spine (plans/025, P1) ----------
  // A petrol line down the left of the five parts with a node at each heading. It is lit as far as
  // the decision went; a step reached while the page is open (an approval, here or elsewhere) runs
  // the current on to it. Each item draws its spine once per visit; after that it stands.
  type NodeId = "asked" | "checks" | "rule" | "result" | "proof";
  let partsEl = $state<HTMLElement>();
  let nodeY = $state<Partial<Record<NodeId, number>>>({});
  function measure() {
    if (!partsEl) return;
    const top = partsEl.getBoundingClientRect().top;
    const out: Partial<Record<NodeId, number>> = {};
    for (const n of partsEl.querySelectorAll<HTMLElement>("[data-node]")) {
      const r = n.getBoundingClientRect();
      out[n.dataset.node as NodeId] = r.top + r.height / 2 - top;
    }
    nodeY = out;
  }
  $effect(() => {
    if (!partsEl) return;
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(partsEl);
    return () => ro.disconnect();
  });
  const ORDER: NodeId[] = ["asked", "checks", "rule", "result", "proof"];
  const present = $derived(ORDER.filter((n) => nodeY[n] !== undefined));
  /** How far the decision went: the last node the line reaches. */
  const reach = $derived.by((): NodeId => {
    if (!d) return "asked";
    return d.result ? "proof" : "rule";
  });
  const first = $derived(present.length ? nodeY[present[0]]! : 0);
  const span = $derived(present.length > 1 ? nodeY[present[present.length - 1]]! - first : 0);
  const levelOf = (n: NodeId) => (span > 0 && nodeY[n] !== undefined ? (nodeY[n]! - first) / span : 0);
  /** The node each part shows: reached in petrol, the outcome in its colour, what waits hollow. */
  const nodeTone = (n: NodeId): "done" | "ok" | "bad" | "wait" | "off" => {
    if (!d) return "off";
    const at = ORDER.indexOf(n);
    const upTo = ORDER.indexOf(reach);
    if (n === "rule" && d.item.status === "blocked") return "bad";
    if (n === "result") return d.result ? "ok" : d.item.status === "waiting" ? "wait" : "off";
    return at <= upTo ? "done" : "off";
  };
  const seenSpines = ((globalThis as { __validioSpines?: Set<string> }).__validioSpines ??= new Set<string>());
  let spine = $state({ mode: "lit" as "lit" | "run", from: 0, level: 0, key: 0 });
  let lastReach: { id: string; at: number } | null = null;
  // Nodes past this one wait for the current to arrive before they take their colour.
  let litTo = $state<number>(99);
  $effect(() => {
    if (!d || span <= 0 || replaying) return;
    const at = ORDER.indexOf(reach);
    const level = levelOf(reach);
    const cur = untrack(() => spine);
    if (!lastReach || lastReach.id !== id) {
      if (!seenSpines.has(id) && !reduced()) {
        seenSpines.add(id);
        litTo = 0;
        spine = { mode: "run", from: 0, level, key: cur.key + 1 };
      } else {
        litTo = 99;
        spine = { mode: "lit", from: 0, level, key: cur.key };
      }
    } else if (at > lastReach.at) {
      litTo = lastReach.at;
      spine = { mode: "run", from: levelOf(ORDER[lastReach.at]), level, key: cur.key + 1 };
    } else if (cur.mode === "lit" && Math.abs(cur.level - level) > 0.001) spine = { ...cur, level };
    lastReach = { id, at };
  });
  let replayAt: NodeId | null = null;
  function arrived() {
    litTo = replaying && replayAt ? ORDER.indexOf(replayAt) : 99;
    spine = { ...spine, mode: "lit" };
  }

  // ---------- the answer's ending (plans/025, P2) ----------
  // After Approve or Reject: the next thing that waits, or that nothing does.
  let ending = $state<{ kind: "approved" | "rejected"; next: ActivityItem | null } | null>(null);
  let endingEl = $state<HTMLElement>();
  async function after(kind: "approved" | "rejected") {
    let next: ActivityItem | null = null;
    try {
      next = (await api.home()).needsYou.find((i) => i.id !== id) ?? null;
    } catch {
      // the ending still stands, without a next item
    }
    ending = { kind, next };
    await tick();
    endingEl?.focus({ preventScroll: true });
  }
  // A new item: no ending from the last one.
  $effect(() => {
    void id;
    ending = null;
  });

  // Opened from Home, a toast or the palette to approve: the code is open at once (plans/025, S4).
  let askedByLink = "";
  $effect(() => {
    if (d?.approval && page.url.searchParams.get("approve") === "1" && askedByLink !== id) {
      askedByLink = id;
      asking = true;
    }
  });

  // ---------- Verify the chain (plans/025, P4) ----------
  let verify = $state<{ state: "idle" | "running" | "done" | "failed"; step: number; ok: boolean[]; text: string }>({
    state: "idle",
    step: -1,
    ok: [],
    text: "",
  });
  async function runVerify() {
    if (!d || verify.state === "running") return;
    const proof = d.proof;
    verify = { state: "running", step: -1, ok: [], text: "" };
    try {
      const res = await api.verifyProof(proof);
      const gap = reduced() ? 0 : Math.max(60, Math.min(DUR.chain, 1600 / Math.max(1, proof.length)));
      for (let i = 0; i < proof.length; i++) {
        verify.step = i;
        verify.ok = [...verify.ok, res.links[i]];
        if (gap) await new Promise((r) => setTimeout(r, gap));
        if (!res.links[i]) break;
      }
      const broken = res.links.findIndex((x) => !x);
      verify.state = res.ok ? "done" : "failed";
      verify.text = res.ok
        ? `Sealed. These ${proof.length} ${proof.length === 1 ? "entry links" : "entries link"} to the one before, and all ${res.count} entries of your ledger check out${res.head ? `, the newest at ${hm(res.head)}` : ""}.`
        : broken >= 0
          ? `Entry ${broken + 1} does not match the one before it. Something changed after it was written.`
          : "Your ledger does not check out as a whole. Something changed after it was written.";
    } catch (e) {
      verify = { state: "failed", step: -1, ok: [], text: `Couldn't reach Validio to check: ${e instanceof Error ? e.message : String(e)}` };
    }
  }
  const longDay = (iso: string) =>
    new Intl.DateTimeFormat("en-GB", { weekday: "long", day: "numeric", month: "long", timeZone: "Europe/Helsinki" }).format(new Date(iso)).replace(",", "");

  const HELSINKI = "Europe/Helsinki";
  const date = (ymd: string) =>
    nb(new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: HELSINKI }).format(new Date(`${ymd}T12:00:00Z`)));
  /** "15:00 today" or "Mon 16 Nov, 15:00". */
  const until = (iso: string) => (dayHead(iso).startsWith("Today") ? `${hm(iso)} today` : dayTime(iso));
  const secs = (iso: string) =>
    new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: HELSINKI }).format(new Date(iso));

  let proofOpen = $state(false);
  async function toProof(e: MouseEvent) {
    e.preventDefault();
    proofOpen = true;
    await tick();
    document.getElementById("proof")?.scrollIntoView({ block: "start", behavior: reduced() ? "auto" : "smooth" });
    glow(document.querySelector("#proof > summary"));
  }
  /** A brief petrol tint on where a link landed (plans/011). */
  function glow(el: Element | null) {
    if (!el) return;
    el.classList.remove("v-glow");
    void (el as HTMLElement).offsetWidth;
    el.classList.add("v-glow");
    setTimeout(() => el.classList.remove("v-glow"), 1600);
  }

  // A hash copies on a click; "Copied" stands in for it a moment (plans/011).
  let copiedHash = $state("");
  let copyTimer: ReturnType<typeof setTimeout> | undefined;
  async function copyHash(h: string) {
    try {
      await navigator.clipboard.writeText(h);
    } catch {
      return;
    }
    copiedHash = h;
    clearTimeout(copyTimer);
    copyTimer = setTimeout(() => (copiedHash = ""), 1600);
  }

  // The result arrived while the page was open: its check draws itself (plans/007).
  let hadResult: boolean | null = null;
  let justDone = $state(false);
  $effect(() => {
    if (!d) return;
    if (hadResult === false && d.result) justDone = true;
    hadResult = !!d.result;
  });

  // Replay (plans/021): the page walks its own story once, step by step; any input stops it.
  let replaying = $state(false);
  let step = $state(0);
  let beat = $state(0); // re-keys the result and the scale's marker so they play again
  let mkBeat = $state(0);
  let replaySaid = $state("");
  let ctl: AbortController | null = null;
  const sleepFor = (ms: number, sig: AbortSignal) =>
    new Promise<void>((res, rej) => {
      const t = setTimeout(res, ms);
      sig.addEventListener("abort", () => (clearTimeout(t), rej(new Error("stopped"))), { once: true });
    });
  function into(sel: string) {
    const el = document.querySelector(sel);
    if (!el) return;
    const r = el.getBoundingClientRect();
    if (r.top < 72 || r.bottom > innerHeight) el.scrollIntoView({ block: "nearest", behavior: reduced() ? "auto" : "smooth" });
  }
  async function replay() {
    if (replaying) return stopReplay();
    ctl = new AbortController();
    const sig = ctl.signal;
    const calm = reduced();
    const hold = calm ? 1200 : 900;
    proofOpen = false;
    replaying = true;
    step = 0;
    replaySaid = "Replaying the decision";
    try {
      await sleepFor(calm ? 0 : 300, sig);
      const steps: [number, string, NodeId][] = [
        [1, "#h-asked", "asked"],
        [2, "#h-checks", "checks"],
        [3, "#h-rule", "rule"],
        [4, "#h-result", "result"],
        [5, "#proof", "proof"],
      ];
      // The spine empties, then the current walks it part by part (plans/025, P5).
      let lvl = 0;
      litTo = -1;
      spine = { mode: "lit", from: 0, level: 0, key: spine.key + 1 };
      for (const [n, sel, node] of steps) {
        if (!document.querySelector(sel)) continue;
        step = n;
        replayAt = node;
        const to = levelOf(node);
        litTo = ORDER.indexOf(node) - 1;
        spine = { mode: "run", from: lvl, level: to, key: spine.key + 1 };
        lvl = to;
        if (n === 3) mkBeat += 1;
        if (n === 4) beat += 1;
        if (n === 5) proofOpen = true;
        into(sel);
        await sleepFor((n === 2 ? 900 : 300) + hold, sig);
      }
      replaySaid = "Replay finished";
    } catch {
      replaySaid = "Replay stopped";
    } finally {
      replaying = false;
      replayAt = null;
      step = 0;
      ctl = null;
      litTo = 99;
      spine = { mode: "lit", from: 0, level: levelOf(reach), key: spine.key + 1 };
    }
  }
  function stopReplay() {
    ctl?.abort();
  }
  function interrupt(e: Event) {
    if (!replaying) return;
    if (e.type === "pointerdown" && (e.target as Element | null)?.closest?.("#replay")) return;
    stopReplay();
  }

  const NOT_ORDERED: Record<ActivityDetail["item"]["status"], string> = {
    waiting: "Not ordered yet",
    blocked: "Nothing ordered",
    standing: "No run yet",
    ordered: "Ordered",
  };

  // The answer: Approve opens the code field, Confirm sends it, Reject goes at once.
  let asking = $state(false);
  let code = $state("");
  let problem = $state("");
  let busy = $state(false);
  let said = $state("");

  // Another item, or the answer came from somewhere else: the field closes.
  $effect(() => {
    if (!d?.approval) {
      asking = false;
      code = "";
      problem = "";
    }
  });

  function why(e: unknown): string {
    if (e instanceof ApiError && e.status === 403) return "That code is not right";
    if (e instanceof ApiError && e.status === 409) return "Someone already answered this";
    return e instanceof Error ? e.message : String(e);
  }

  async function confirm() {
    if (!d?.approval || busy) return;
    if (!isCode(code.trim())) {
      problem = "The code has 6 digits";
      return;
    }
    busy = true;
    problem = "";
    owner.code = code.trim();
    try {
      await api.approve(d.approval.orderId);
      said = "Approved. Valio places the order";
      buzz();
      bump();
      void after("approved");
    } catch (e) {
      problem = why(e);
      // Answered elsewhere meanwhile: close the code and read the request again.
      if (e instanceof ApiError && e.status === 409) {
        asking = false;
        code = "";
        bump();
      }
    } finally {
      busy = false;
    }
  }

  async function reject() {
    if (!d?.approval || busy) return;
    busy = true;
    problem = "";
    try {
      await api.reject(d.approval.orderId);
      said = "Rejected. Nothing is ordered";
      bump();
      void after("rejected");
    } catch (e) {
      problem = why(e);
    } finally {
      busy = false;
    }
  }
</script>

{#snippet lede()}
  {#if d && pill}
    {@const amount = d.item.totalCents != null ? nb(money(d.item.totalCents)) : ""}
    <p class="lead" data-testid="detail-lede">
      {#key pill.label}<span class="word tone-{pill.tone}-text" data-testid="detail-status" in:blurSwap={{ y: 4 }}>{pill.label}</span>{/key}.
      {#if d.item.status === "waiting"}
        {#if amount}<b class="num" data-testid="detail-total">{amount}</b> is ready to order once you approve.{:else}Ready to order once you approve.{/if}
      {:else if d.item.status === "ordered"}
        {#if amount}<b class="num" data-testid="detail-total">{amount}</b>{#if d.result?.delivery}, arriving {date(d.result.delivery)}{/if}.{/if}
      {:else if d.item.status === "blocked"}
        {#if amount}<b class="num" data-testid="detail-total">{amount}</b> was not ordered.{:else}Nothing was ordered.{/if}
      {:else}
        {nb(d.item.why)}.
      {/if}
    </p>
    <p class="facts">
      {#if d.item.kind === "standing" && amount}<b class="num" data-testid="detail-total">{amount}</b>{/if}
      <span>{d.item.kind === "standing" ? dayTime(d.item.at) : `Asked ${dayTime(d.item.at)}`}</span>
    </p>
  {/if}
{/snippet}

<svelte:window onkeydown={interrupt} onpointerdown={interrupt} onwheel={interrupt} ontouchstart={interrupt} />

<PageHead
  title={missing ? "Not found" : (head?.title ?? "")}
  crumbs={[{ href: "/activity", label: "Activity" }]}
  here={head ? nb(longDay(head.at)) : ""}
  back={{ href: "/activity", label: "Activity" }}
  titleTestid="detail-title"
  morphName={morph.id === id ? "v-title" : undefined}
>
  {#snippet actions()}
    {#if d && d.item.kind === "request" && !d.approval}
      <Button variant="ghost" id="replay" data-testid="replay" onclick={replay} aria-pressed={replaying}>
        {#if replaying}<Square size={13} aria-hidden="true" />Stop{:else}<Play size={13} aria-hidden="true" />Replay{/if}
      </Button>
    {/if}
  {/snippet}
  {@render lede()}
</PageHead>

{#snippet node(n: NodeId)}
  {@const tone = nodeTone(n)}
  <span class="node {ORDER.indexOf(n) <= litTo || tone === 'off' ? tone : 'pending'}" data-node={n} aria-hidden="true"></span>
{/snippet}

{#snippet fact(testid: string, label: string, value: string, note: string | null = null, ok: boolean | null = null)}
  <div class="check" data-testid={testid} data-ok={ok}>
    <dt class="ck-label">{label}</dt>
    <dd class="ck-val" class:ok={ok === true} class:bad={ok === false}>
      {#if ok === true}<span class="sr-only">Passed:</span>{:else if ok === false}<span class="sr-only">Failed:</span>{/if}
      <span class="ck-value">{nb(value)}</span>
      {#if note}<span class="ck-note">{nb(note)}</span>{/if}
    </dd>
  </div>
{/snippet}

<p class="sr-only" role="status">{said}</p>
<p class="sr-only" role="status" data-testid="replay-status">{replaySaid}</p>

{#if missing}
  <div class="parts"><Empty title="It may belong to another kitchen." detail="Activity lists everything your agent did." /></div>
{:else if detail.error && !d}
  <div class="parts"><LoadError detail={detail.error} /></div>
{:else if !d}
  <div class="parts"><Loading rows={4} /></div>
{:else}
  {#if d.approval}
    <div class="ask notice" data-testid="approval" out:collapse={{ duration: 220 }}>
      <p class="ask-q">Your agent waits for you. Valio holds this price until {until(d.approval.holdUntil)}.</p>
      <!-- While the code is asked, its own Approve and Cancel stand in for these two. -->
      {#if !asking}
        <div class="v-buttons" in:rise={{ y: 6, duration: 200 }}>
          <Button id="approve" data-testid="approve" aria-expanded={false} disabled={busy} onclick={() => (asking = true)}>Approve</Button>
          <Button id="reject" data-testid="reject" variant="outline" disabled={busy} onclick={reject}>Reject</Button>
        </div>
      {/if}
      {#if problem && !asking}<p class="ask-problem" role="alert" in:rise={{ y: 4, duration: 200 }} out:fadeOut>{problem}</p>{/if}
      {#if asking}
        <div in:rise={{ y: 6, duration: 200 }}>
        <VCode
          bind:value={code}
          error={problem}
          {busy}
          submitLabel="Approve"
          onsubmit={confirm}
          oncancel={() => {
            asking = false;
            code = "";
            problem = "";
            tick().then(() => document.getElementById("approve")?.focus());
          }}
        />
        </div>
      {/if}
    </div>
  {/if}
  {#if ending}
    <div class="ending notice" tabindex="-1" bind:this={endingEl} data-testid="ending" in:rise={{ y: 8, duration: DUR.enter, delay: 700 }}>
      {#if ending.next}
        <span>{ending.kind === "approved" ? "Approved." : "Rejected."} Next waiting: <b>{nb(ending.next.title)}</b>{#if ending.next.totalCents != null}, <span class="num">{nb(money(ending.next.totalCents))}</span>{/if}.</span>
        <a class="link" href="/activity/{encodeURIComponent(ending.next.id)}?approve=1" data-testid="ending-next">Review it</a>
      {:else}
        <span>{ending.kind === "approved" ? "Approved." : "Rejected."} Nothing else waits for you.</span>
        <a class="link" href="/" data-testid="ending-home">Back to Home</a>
      {/if}
    </div>
  {/if}

  <div class="doc" class:v-arrive={detail.arrive}>
    <div class="parts" class:replaying class:spined={span > 0} bind:this={partsEl}>
      {#if span > 0}
        <span class="spine" style:top="{first}px" style:height="{span}px" aria-hidden="true">
          {#key spine.key}
            <Current axis="v" mode={spine.mode} from={spine.from} level={spine.level} track="dashed" duration={replaying ? 520 : 760} onarrive={arrived} />
          {/key}
        </span>
      {/if}
      <section class="part" class:lit={step >= 1} aria-labelledby="h-asked">
        <h2 class="v-h" id="h-asked">{@render node("asked")}What your agent asked</h2>
        <figure class="asked" data-testid="asked">
          <blockquote>“{nb(d.asked.text)}”</blockquote>
          <figcaption>{d.asked.agentName}</figcaption>
        </figure>
      </section>

      <!-- A request blocked before Valio was asked has nothing checked: no empty section for it. -->
      {#if d.checks.length || r}
        <section class="part" class:lit={step >= 2} aria-labelledby="h-checks">
          <h2 class="v-h" id="h-checks">{@render node("checks")}What Validio checked at Valio</h2>
          {#if d.checks.length}
            <dl class="checks" class:stagger={replaying && step === 2}>
              {#each d.checks as c, n (n)}
                {@render fact(`check-${c.label.toLowerCase()}`, c.label, c.value, c.note, c.ok)}
              {/each}
            </dl>
          {/if}
          {#if r?.simulated?.length}
            <ul class="sim" data-testid="simulated">
              {#each r.simulated as m (m.what)}
                <li>{nb(m.sentence)} <Explain label="Why this is simulated">The demo shows this case on purpose. Valio's real answer was different.</Explain></li>
              {/each}
            </ul>
          {/if}
          {#if r}<Options bind:this={options} req={r} proposed={d.item.status === "blocked"} />{/if}
        </section>
      {/if}

      <section class="part" class:lit={step >= 3} aria-labelledby="h-rule">
        <div class="h-row">
          <h2 class="v-h" id="h-rule">{@render node("rule")}Which rule decided</h2>
          <Explain label="What a Rules version is">Every Rules save signs a new version. Orders show the version they were decided under.</Explain>
        </div>
        <a class="rule-row" href="/rules" id="rule-link" data-testid="rule">
          <span class="rule-text">{nb(d.rule.text)}</span>
          <span class="rule-ver" data-testid="rule-version">{later ? `Rules, version ${d.rule.version} (now ${later})` : `Rules, version ${d.rule.version}`}</span>
        </a>
      </section>

      <section class="part" class:lit={step >= 4} aria-labelledby="h-result">
        <h2 class="v-h" id="h-result">{@render node("result")}Result</h2>
        {#key beat}
          {#if d.result}
            {@const ids = d.result.orderIds.length ? d.result.orderIds : [d.result.orderId]}
            <dl class="checks" in:rise={{ y: 6, delay: 80 }}>
              <div class="check" data-testid="result-order" data-order={ids.join(", ")}>
                <dt class="ck-label">{ids.length > 1 ? "Orders" : "Order"}</dt>
                <dd class="ck-val ok">
                  <svg class="v-check done-mark" class:just={justDone || beat > 0} viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M20 6 9 17l-5-5" pathLength="1" /></svg>
                  <span class="ck-value">{ids.length > 1 ? `${ids.length} orders placed with Valio` : "Placed with Valio"}</span>
                </dd>
              </div>
              {#if d.result.delivery}{@render fact("result-delivery", "Delivery", date(d.result.delivery))}{/if}
            </dl>
          {:else}
            <p class="none" data-testid="result-none" in:blurSwap>{NOT_ORDERED[d.item.status]}</p>
          {/if}
        {/key}
      </section>

      <details class="fold proof" class:lit={step >= 5} id="proof" data-testid="proof" bind:open={proofOpen}>
        <summary id="proof-toggle">
          {@render node("proof")}
          <ChevronRight class="chev" aria-hidden="true" />
          <span class="proof-name">Proof</span>
          <span class="proof-n"><Ticker text="{d.proof.length} {d.proof.length === 1 ? 'entry' : 'entries'}" value={d.proof.length} />, sealed</span>
        </summary>
        <ol class="pes" class:verifying={verify.step >= 0} style:--vp={d.proof.length ? (verify.step + 1) / d.proof.length : 0}>
          {#each d.proof as p, i (p.hash)}
            <li class="pe" class:vok={verify.ok[i] === true} class:vbad={verify.ok[i] === false} data-raw>
              <span class="pe-time num">{secs(p.at)}</span>
              <span class="pe-actor smallcaps">{p.actor}</span>
              <span class="pe-main">
                <span class="pe-text">{p.text}</span>
                <button type="button" class="pe-hash mono" title={p.hash} aria-label="Copy hash" onclick={() => copyHash(p.hash)}>
                  {#key copiedHash === p.hash}<span class="ph" in:blurSwap={{ duration: 150 }}>{copiedHash === p.hash ? "Copied" : p.hash}</span>{/key}
                </button>
              </span>
            </li>
          {/each}
        </ol>
        <div class="verify">
          <Button variant="outline" size="sm" id="verify" data-testid="verify" disabled={verify.state === "running"} onclick={runVerify}>
            <BusyLabel busy={verify.state === "running"} idle={verify.state === "idle" ? "Verify the chain" : "Verify again"} working="Checking the chain" />
          </Button>
          {#if verify.text}
            {#key verify.text}<p class="v-res" class:bad={verify.state === "failed"} role="status" data-testid="verify-result" in:rise={{ y: 4 }}>{verify.text}</p>{/key}
          {/if}
        </div>
      </details>
    </div>

    <aside class="checked" aria-labelledby="h-how">
      <h2 class="v-h" id="h-how">How this was checked</h2>
      <dl>
        {#if limits}
          {@const over = limits.total > limits.alone}
          <div class="ck" class:lit={step === 3} data-testid="limits">
            <dt>{limits.total > limits.most ? "Over your limits" : over ? "Above what it orders alone" : "Within your limits"}</dt>
            <dd>
              {#key mkBeat}<LimitScale mode="order" alone={limits.alone} waiting={limits.most} order={limits.total} id="detail-scale" />{/key}
              {#if later}<p class="ck-then">Rules version {d.rule.version}, when this was decided.</p>{/if}
              {#if today}<p class="ck-today" data-testid="today-rules">{today}</p>{/if}
            </dd>
          </div>
        {/if}
        {#if r}
          <div class="ck" class:lit={step === 2}>
            <dt>Valio asked for price and stock</dt>
            <dd>{r.liveChecked.ids} products, prices and stock read before deciding.{#if r.valioText}{" "}{nb(r.valioText)}.{/if}</dd>
          </div>
          {#if chosen?.dietText}
            <div class="ck" class:lit={step === 2}>
              <dt>{chosen.dietText.split(":")[0]} confirmed</dt>
              <dd>{nb(chosen.dietText.split(/:\s*/)[1] ?? "").replace(/^./, (c) => c.toUpperCase())}.</dd>
            </div>
          {/if}
          {#if planted?.supplierText}
            <div class="ck" class:lit={step === 2}>
              <dt>One supplier text ignored</dt>
              <dd>
                <p>The description of <b>{nb(planted.displayName ?? planted.name)}</b> tried to instruct your agent. It never reached the agent.</p>
                <blockquote data-raw>{planted.supplierText.text}</blockquote>
                <a class="link" href="#option-{planted.productId}" onclick={(e) => { e.preventDefault(); options?.show(planted.productId); }}>Show this product</a>
              </dd>
            </div>
          {/if}
        {/if}
        <div class="ck" class:lit={step === 5}>
          <dt>Recorded in your activity <Explain label="What sealed means">Each entry carries the fingerprint of the one before. A changed entry breaks the chain.</Explain></dt>
          <dd>Sealed, nothing changed since. <a class="link" href="#proof" onclick={toProof}>See the proof</a></dd>
        </div>
      </dl>
    </aside>
  </div>
{/if}

<style>
  .doc {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 280px;
    gap: 56px;
    margin-top: 40px;
    align-items: start;
  }
  .parts {
    display: flex;
    flex-direction: column;
    gap: 40px;
    min-width: 0;
  }
  .part {
    display: flex;
    flex-direction: column;
  }

  /* The answer: a calm notice with the petrol rule, the buttons under it. */
  .ask {
    display: flex;
    flex-direction: column;
    gap: 14px;
    margin-top: 28px;
    padding: 4px 0 4px 18px;
  }
  .ask-q {
    margin: 0;
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    font-weight: 500;
  }
  .ask-problem {
    margin: 0;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-bad-text);
  }

  /* Asked: the agent's words as a quotation. */
  .asked {
    margin: 0;
    padding: 2px 0 2px 18px;
    border-left: 2px solid var(--v-line-strong);
  }
  .asked blockquote {
    margin: 0;
    font-family: var(--v-sans);
    font-size: 16px;
    line-height: 25px;
    font-style: normal;
  }
  .asked figcaption {
    margin-top: 6px;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }

  /* Checks and the result: label and value between hairlines; a passed or
     failed value carries a thin rule in its colour. */
  .checks {
    margin: 0;
    border-top: 1px solid var(--v-fg);
  }
  .check {
    display: grid;
    grid-template-columns: 152px minmax(0, 1fr);
    column-gap: 24px;
    align-items: baseline;
    padding: 12px 10px;
    border-bottom: 1px solid var(--v-line);
  }
  .ck-label {
    font-size: var(--fs-meta);
    line-height: var(--lh-body);
    color: var(--v-muted);
  }
  .ck-val {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    column-gap: 10px;
    min-width: 0;
    margin: 0;
  }
  .ck-val.ok,
  .ck-val.bad {
    padding-left: 10px;
    border-left: 2px solid var(--v-ok);
  }
  .ck-val.bad {
    border-left-color: var(--v-bad);
  }
  .ck-value {
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    font-weight: 500;
    overflow-wrap: anywhere;
  }
  .ck-val.bad .ck-value {
    color: var(--v-bad-text);
  }
  .ck-note {
    font-size: var(--fs-meta);
    line-height: var(--lh-body);
    color: var(--v-muted);
  }

  /* Rule: one ruled line, the whole line a link to Rules. */
  .rule-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: baseline;
    column-gap: 24px;
    padding: 14px 10px;
    border-top: 1px solid var(--v-fg);
    border-bottom: 1px solid var(--v-line);
    color: inherit;
    text-decoration: none;
  }
  .rule-text {
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    font-weight: 500;
    transition: color var(--duration-fast) ease;
  }
  @media (hover: hover) and (pointer: fine) {
    .rule-row:hover .rule-text {
      color: var(--valio);
    }
  }
  .rule-row {
    transition: background-color var(--duration-fast) ease;
  }
  .rule-row:active {
    background: var(--v-tint-fill);
    transition-duration: 0ms;
  }
  .rule-row:focus-visible {
    outline-offset: -2px;
    background: var(--v-tint-hover);
  }
  .rule-row:focus-visible .rule-text {
    color: var(--valio);
  }
  .h-row {
    display: flex;
    align-items: baseline;
    gap: 4px;
  }
  .rule-ver {
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--valio);
    white-space: nowrap;
  }

  .none {
    margin: 0;
    padding: 14px 10px;
    border-top: 1px solid var(--v-fg);
    border-bottom: 1px solid var(--v-line);
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    color: var(--v-muted);
  }

  /* Proof */
  .proof > summary {
    font-size: var(--fs-head);
  }
  .proof-name {
    font-family: var(--v-sans);
    font-size: var(--fs-section);
    line-height: var(--lh-section);
    font-weight: 600;
    color: var(--v-fg);
  }
  .proof-n {
    margin-left: 6px;
    font-size: var(--fs-meta);
    color: var(--v-faint);
  }
  .pes {
    margin: 12px 0 0;
    padding: 0;
    list-style: none;
    border-top: 1px solid var(--v-fg);
  }
  .pe {
    display: grid;
    grid-template-columns: 72px 112px minmax(0, 1fr);
    column-gap: 16px;
    align-items: baseline;
    padding: 12px 10px;
    border-bottom: 1px solid var(--v-line);
  }
  .pe-time {
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-faint);
  }
  .pe-main {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .pe-text {
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-fg);
  }
  .pe-hash {
    display: inline-grid;
    justify-items: start;
    padding: 0;
    border: 0;
    background: none;
    font: inherit;
    font-family: var(--font-mono);
    font-size: var(--fs-cap);
    line-height: 16px;
    text-align: left;
    color: var(--v-faint);
    overflow-wrap: anywhere;
    text-decoration: underline;
    text-decoration-color: transparent;
    text-underline-offset: 3px;
    transition:
      text-decoration-color var(--duration-fast) ease,
      color var(--duration-fast) ease;
  }
  .pe-hash .ph {
    grid-area: 1 / 1;
  }
  @media (hover: hover) and (pointer: fine) {
    .pe-hash:hover {
      color: var(--v-muted);
      text-decoration-color: currentColor;
    }
  }
  .pe-hash:focus-visible {
    border-radius: var(--radius-chip);
  }

  /* The chain (plans/011): a line through the entries, a node on each; on opening the line
     draws down while the entries fall into place just behind it. */
  .pes {
    position: relative;
    padding-left: 20px;
  }
  .pes::before {
    content: "";
    position: absolute;
    left: 3px;
    top: 20px;
    bottom: 20px;
    width: 1px;
    background: var(--v-line-strong);
    transform-origin: top;
  }
  .pe {
    position: relative;
  }
  .pe::before {
    content: "";
    position: absolute;
    left: -20px;
    top: 17px;
    width: 7px;
    height: 7px;
    border: 1.5px solid var(--valio);
    border-radius: var(--radius-chip);
    background: var(--v-ground);
  }
  details.proof[open] .pes::before {
    animation: v-chain 300ms var(--v-ease-out) both;
  }
  details.proof[open] .pe {
    animation: v-pe 220ms var(--v-ease-out) both;
    animation-delay: 90ms;
  }
  details.proof[open] .pe:nth-child(1) {
    animation-delay: 0ms;
  }
  details.proof[open] .pe:nth-child(2) {
    animation-delay: 30ms;
  }
  details.proof[open] .pe:nth-child(3) {
    animation-delay: 55ms;
  }
  details.proof[open] .pe:nth-child(4) {
    animation-delay: 75ms;
  }
  @keyframes v-chain {
    from {
      transform: scaleY(0);
    }
  }
  @keyframes v-pe {
    from {
      opacity: 0;
      transform: translateY(4px);
    }
  }

  /* The result's check (plans/007). */
  .done-mark {
    flex: none;
    align-self: center;
  }

  /* Replay (plans/021): everything not yet reached dims; a petrol line measures the way. */
  .parts {
    position: relative;
  }
  .parts > :is(.part, .proof),
  .checked .ck {
    transition: opacity 300ms var(--v-ease-out);
  }
  .parts.replaying > :is(.part, .proof):not(.lit),
  .parts.replaying ~ .checked .ck:not(.lit) {
    opacity: 0.32;
  }
  .checks.stagger > .check {
    animation: v-pe 220ms var(--v-ease-out) both;
  }
  .checks.stagger > .check:nth-child(2) {
    animation-delay: 120ms;
  }
  .checks.stagger > .check:nth-child(3) {
    animation-delay: 220ms;
  }
  .checks.stagger > .check:nth-child(4) {
    animation-delay: 310ms;
  }
  .checks.stagger > .check:nth-child(n + 5) {
    animation-delay: 390ms;
  }
  @media (prefers-reduced-motion: reduce) {
    details.proof[open] .pes::before {
      animation: none;
    }
    details.proof[open] .pe,
    .checks.stagger > .check {
      animation: v-fade-in 120ms linear both;
      animation-delay: 0ms;
    }
  }

  /* ---------- the decision's spine (plans/025, P1) ---------- */
  .parts.spined {
    --sx: 36px;
    padding-left: var(--sx);
  }
  .spine {
    position: absolute;
    left: 4px;
    width: 2px;
  }
  .part > .v-h,
  .h-row > .v-h,
  .proof > summary {
    position: relative;
  }
  .node {
    position: absolute;
    left: calc(-1 * var(--sx));
    top: 50%;
    width: 10px;
    height: 10px;
    margin-top: -5px;
    border: 2px solid var(--v-current-dim);
    border-radius: var(--radius-chip);
    background: var(--v-ground);
    transition:
      background-color var(--v-dur-ui) var(--v-ease-out),
      border-color var(--v-dur-ui) var(--v-ease-out),
      transform var(--v-dur-ui) var(--v-ease-out);
  }
  .parts:not(.spined) .node {
    visibility: hidden;
  }
  .node.done {
    border-color: var(--valio);
    background: var(--valio);
  }
  .node.ok {
    border-color: var(--v-ok);
    background: var(--v-ok);
  }
  .node.bad {
    border-color: var(--v-bad);
    background: var(--v-bad);
  }
  /* What waits for the owner: a hollow petrol node, the one place the line asks for a hand. */
  .node.wait {
    border-color: var(--valio);
  }
  .node.pending {
    transform: scale(0.8);
  }

  /* The answer's ending: what is next. */
  .ending {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 6px 16px;
    margin-top: 28px;
    padding-block: 6px;
    font-size: var(--fs-body);
    line-height: var(--lh-body);
  }
  .ending b {
    font-weight: 600;
  }
  .ending:focus-visible {
    outline-offset: 4px;
  }

  /* A value the demo simulates on purpose. */
  .sim {
    margin: 10px 0 0;
    padding: 0;
    list-style: none;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }

  /* Verify (plans/025, P4): a green line follows the check down the chain, node by node. */
  .verify {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px 16px;
    margin-top: 14px;
  }
  .v-res {
    margin: 0;
    max-width: 560px;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-ok-text);
  }
  .v-res.bad {
    color: var(--v-bad-text);
  }
  .pes::after {
    content: "";
    position: absolute;
    left: 3px;
    top: 20px;
    bottom: 20px;
    width: 1px;
    background: var(--v-ok);
    transform-origin: top;
    transform: scaleY(var(--vp, 0));
    transition: transform var(--v-dur-chain) linear;
  }
  .pe.vok::before {
    border-color: var(--v-ok);
    background: var(--v-ok);
  }
  .pe.vbad::before {
    border-color: var(--v-bad);
    background: var(--v-bad);
  }
  .pe::before {
    transition:
      background-color var(--v-dur-ui) var(--v-ease-out),
      border-color var(--v-dur-ui) var(--v-ease-out);
  }
  .ck-then,
  .ck-today {
    margin: 8px 0 0;
    font-size: var(--fs-cap);
    line-height: 16px;
  }
  .ck-today {
    margin-top: 4px;
    color: var(--valio);
  }

  /* How this was checked: the margin column. */
  .checked {
    position: sticky;
    top: 84px; /* below the sticky band */
    padding: 20px 24px 8px;
    background: var(--v-subtle);
  }
  .checked .v-h {
    font-size: 18px;
    line-height: 26px;
    margin-bottom: 4px;
  }
  .checked dl {
    margin: 0;
  }
  .ck {
    padding: 12px 0 14px;
    border-bottom: 1px solid var(--v-line);
  }
  .ck:last-child {
    border-bottom: 0;
  }
  .ck dt {
    margin-bottom: 2px;
    font-size: var(--fs-head);
    line-height: var(--lh-head);
    font-weight: 500;
  }
  .ck dd {
    margin: 0;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  .ck dd p {
    margin: 0;
  }
  .ck dd b {
    font-weight: 500;
    color: var(--v-fg);
  }
  .ck blockquote {
    margin: 10px 0 6px;
    padding: 0 0 0 12px;
    border-left: 2px solid var(--v-bad);
    font-family: var(--v-sans);
    font-size: 14px;
    line-height: 21px;
    font-style: normal;
    color: var(--v-fg);
  }
  @media (max-width: 1100px) {
    .doc {
      grid-template-columns: minmax(0, 1fr);
      gap: 40px;
    }
    .checked {
      position: static;
      padding: 16px 16px 4px;
    }
  }
  @media (max-width: 760px) {
    .doc {
      margin-top: 28px;
    }
    .parts.spined {
      --sx: 22px;
    }
    .checked {
      top: 64px;
    }
    .parts {
      gap: 32px;
    }
    .check {
      grid-template-columns: minmax(0, 1fr);
      row-gap: 2px;
      padding: 12px 0;
    }
    .ck-label {
      line-height: var(--lh-meta);
    }
    .rule-row {
      grid-template-columns: minmax(0, 1fr);
      row-gap: 4px;
      padding: 14px 0;
    }
    .none {
      padding: 14px 0;
    }
    .pe {
      grid-template-columns: auto minmax(0, 1fr);
      row-gap: 2px;
      padding: 12px 0;
    }
    .pe-main {
      grid-column: 1 / -1;
    }
  }
</style>
