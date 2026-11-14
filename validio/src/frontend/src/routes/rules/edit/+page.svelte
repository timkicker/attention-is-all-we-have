<script lang="ts">
  /// Edit rules: one form for Money, Diet and allergens and Substitutes, then
  /// one Save that asks the approval code once. A save is one new pass
  /// version; the Rules page then says the agent follows it.
  import { onMount, tick, type Snippet } from "svelte";
  import { goto } from "$app/navigation";
  import { Chip } from "@arlen/ui-kit/components/ui/chip";
  import { SegmentedControl } from "@arlen/ui-kit/components/ui/segmented-control";
  import { agentApi, type Rules } from "$lib/api/agent";
  import { ApiError } from "$lib/api/error";
  import { bump, chrome } from "$lib/chrome.svelte";
  import { ListRow, ListSection, Loading, LoadError, money, PageHead } from "$lib/v2";
  import VCode from "$lib/v/VCode.svelte";
  import UnitField from "../UnitField.svelte";
  import { ALLOWED, type Allowed, allowedOf, amountText, extraText, parseAmount, parsePct, word } from "../rules";

  let r = $state<Rules | undefined>();
  let loadError = $state("");
  const options = $derived(r?.diet?.options ?? { mustBe: [], never: [] });
  // The form, as typed.
  const f = $state({ alone: "", waiting: "", week: "", allowed: "listed" as Allowed, extra: "0", mustBe: [] as string[], never: [] as string[] });
  type Key = "alone" | "waiting" | "week" | "extra";
  let bad = $state<Partial<Record<Key, string>>>({});
  let formProblem = $state("");
  let code = $state("");
  let codeError = $state("");
  let busy = $state(false);

  function fill(v: Rules) {
    r = v;
    f.alone = v.saved ? amountText(v.aloneUpToCents) : "";
    f.waiting = v.saved ? amountText(v.approvalUpToCents) : "";
    f.week = v.saved && v.perWeekCents != null ? amountText(v.perWeekCents) : "";
    f.allowed = v.saved ? allowedOf(v) : "listed";
    f.extra = String(v.maxExtraPct);
    f.mustBe = [...(v.diet?.mustBe ?? [])];
    f.never = [...(v.diet?.never ?? [])];
  }
  const load = () =>
    agentApi.rules().then(
      (v) => ((loadError = ""), fill(v)),
      (e) => (loadError = e instanceof Error ? e.message : String(e)),
    );
  onMount(load);

  // Each field read as far as it reads; a field that does not parse is left out of the comparison.
  const cents = (s: string) => {
    const p = parseAmount(s);
    return "cents" in p ? p.cents : null;
  };
  const pct = $derived.by(() => {
    const p = parsePct(f.extra);
    return "pct" in p ? p.pct : null;
  });
  const sameSet = (a: string[], b: string[]) => a.length === b.length && a.every((x) => b.includes(x));

  /** The blocks with a change, in page order. */
  const changed = $derived.by(() => {
    if (!r) return [] as { block: string; n: number }[];
    const was = r;
    const money = [
      !was.saved || cents(f.alone) !== was.aloneUpToCents,
      !was.saved || cents(f.waiting) !== was.approvalUpToCents,
      (f.week.trim() ? cents(f.week) : null) !== (was.saved ? was.perWeekCents : null),
    ].filter(Boolean).length;
    const diet = [!sameSet(f.mustBe, was.diet?.mustBe ?? []), !sameSet(f.never, was.diet?.never ?? [])].filter(Boolean).length;
    const subs = [
      !was.saved || f.allowed !== allowedOf(was),
      f.allowed === "listed" && pct !== (was.substitutes === "extra" ? was.maxExtraPct : 0),
    ].filter(Boolean).length;
    return [
      { block: "Money", n: money },
      { block: "Diet", n: diet },
      { block: "Substitutes", n: subs },
    ].filter((x) => x.n > 0);
  });
  const changeLine = $derived.by(() => {
    const n = changed.reduce((s, x) => s + x.n, 0);
    if (!n) return "No changes yet";
    const blocks = changed.map((x) => x.block);
    const where = blocks.length < 2 ? blocks[0] : `${blocks.slice(0, -1).join(", ")} and ${blocks[blocks.length - 1]}`;
    return `${n} ${n === 1 ? "change" : "changes"}, in ${where}`;
  });

  /** A field's place in its row: right of the label on the desk, under it on the phone. */
  const place = (field: Snippet) => (chrome.phone ? { below: field } : { control: field });

  /** "Was 1,200.00 €" under a money row whose value moved. */
  function was(key: "alone" | "waiting" | "week"): string | undefined {
    if (!r?.saved) return undefined;
    const before = key === "alone" ? r.aloneUpToCents : key === "waiting" ? r.approvalUpToCents : r.perWeekCents;
    const empty = key === "week" && !f.week.trim();
    const now = empty ? null : cents(f[key]);
    if (now === null && !empty) return undefined;
    if (now === before) return undefined;
    return `Was ${before == null ? "no limit" : money(before)}`;
  }

  /** On leaving a money field: the amount in its one shape, 1,500.00. */
  function tidy(key: "alone" | "waiting" | "week") {
    const c = cents(f[key]);
    if (c !== null) f[key] = amountText(c);
  }

  function toggle(listKey: "mustBe" | "never", w: string) {
    const l = f[listKey];
    f[listKey] = l.includes(w) ? l.filter((x) => x !== w) : [...l, w];
  }

  // The problems clear as soon as the field is typed in again.
  let seen = { ...f };
  $effect(() => {
    const next = { ...bad };
    for (const k of ["alone", "waiting", "week", "extra"] as Key[]) if (f[k] !== seen[k]) delete next[k];
    seen = { ...f };
    if (Object.keys(next).length !== Object.keys(bad).length) bad = next;
  });

  function check(): Partial<Record<Key, string>> {
    const out: Partial<Record<Key, string>> = {};
    const a = parseAmount(f.alone);
    const w = parseAmount(f.waiting);
    const wk = f.week.trim() ? parseAmount(f.week) : null;
    if ("problem" in a) out.alone = a.problem;
    if ("problem" in w) out.waiting = w.problem;
    if (wk && "problem" in wk) out.week = wk.problem;
    if ("cents" in a && "cents" in w && a.cents > w.cents) out.alone = "Must not be above Waiting for you.";
    if (wk && "cents" in wk && "cents" in w && wk.cents < w.cents) out.week = `At least ${money(w.cents)}, the Waiting for you limit.`;
    if (f.allowed === "listed") {
      const p = parsePct(f.extra);
      if ("problem" in p) out.extra = p.problem;
    }
    return out;
  }

  async function save() {
    if (!r || busy) return;
    formProblem = "";
    codeError = "";
    bad = check();
    const first = (["alone", "waiting", "week", "extra"] as Key[]).find((k) => bad[k]);
    if (first) {
      await tick();
      document.getElementById(`f-${first}`)?.focus();
      return;
    }
    if (!changed.length) {
      formProblem = "Nothing changed yet.";
      return;
    }
    if (!/^\d{6}$/.test(code)) {
      codeError = "Type the 6-digit approval code.";
      return;
    }
    const extra = f.allowed === "listed" ? (pct ?? 0) : 0;
    busy = true;
    try {
      await agentApi.saveRules({
        aloneUpToCents: cents(f.alone)!,
        approvalUpToCents: cents(f.waiting)!,
        perWeekCents: f.week.trim() ? cents(f.week) : null,
        substitutes: f.allowed === "off" ? "off" : extra > 0 ? "extra" : "listed",
        maxExtraPct: extra,
        diet: { mustBe: [...f.mustBe], never: [...f.never] },
        code,
      });
      bump();
      await goto("/rules?saved", { replaceState: true });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      const status = e instanceof ApiError ? e.status : 0;
      if (status === 403) codeError = "That code is not right.";
      else if (status === 429) codeError = "Too many wrong codes. Try again in 15 minutes.";
      else if (status === 422 && /alone/i.test(msg)) bad = { alone: "Must not be above Waiting for you." };
      else if (status === 422 && /per week/i.test(msg)) bad = { week: "At least the Waiting for you limit." };
      else formProblem = msg;
    } finally {
      busy = false;
    }
  }
</script>

<PageHead title="Edit rules" crumbs={[{ href: "/rules", label: "Rules" }]} here="Edit" back={{ href: "/rules", label: "Rules" }}>
  {#snippet facts()}
    {#if r}<span>Saving makes version <b>{r.passVersion + 1}</b></span>{/if}
  {/snippet}
</PageHead>

<div class="blocks">
  {#if loadError && !r}
    <LoadError detail={loadError} onretry={load} />
  {:else if !r}
    <Loading rows={4} />
  {:else}
    {#snippet aloneF()}<UnitField id="f-alone" label="Ordered alone up to" unit="€" placeholder="1,200.00" start={chrome.phone} bind:value={f.alone} problem={bad.alone} onblur={() => tidy("alone")} />{/snippet}
    {#snippet waitingF()}<UnitField id="f-waiting" label="Waiting for you up to" unit="€" placeholder="5,000.00" start={chrome.phone} bind:value={f.waiting} problem={bad.waiting} onblur={() => tidy("waiting")} />{/snippet}
    {#snippet weekF()}<UnitField id="f-week" label="Per week" unit="€" placeholder="No limit" start={chrome.phone} bind:value={f.week} problem={bad.week} onblur={() => tidy("week")} />{/snippet}
    {#snippet allowedF()}<SegmentedControl id="f-allowed" ariaLabel="Substitutes allowed" options={ALLOWED} bind:value={f.allowed} />{/snippet}
    {#snippet extraF()}<UnitField id="f-extra" label="Extra cost up to" unit="%" narrow start={chrome.phone} bind:value={f.extra} problem={bad.extra} />{/snippet}

    <!-- On the desk a field sits on the right of its row; on the phone under its label. -->
    <ListSection id="money" title="Money">
      <ListRow id="row-alone" label="Ordered alone up to" description={was("alone")} {...place(aloneF)} />
      <ListRow id="row-waiting" label="Waiting for you up to" description={was("waiting") ?? "Above it, blocked"} {...place(waitingF)} />
      <ListRow id="row-week" label="Per week" description={was("week") ?? (f.week.trim() ? undefined : "Empty: no weekly limit")} {...place(weekF)} />
    </ListSection>

    <ListSection id="diet" title="Diet and allergens">
      <ListRow id="row-must" label="Must be">
        {#snippet below()}
          <div class="chips" role="group" aria-label="Must be">
            {#each options.mustBe as w (w)}
              <Chip id="must-{w}" label={word(w)} pressed={f.mustBe.includes(w)} onclick={() => toggle("mustBe", w)} />
            {/each}
          </div>
        {/snippet}
      </ListRow>
      <ListRow id="row-never" label="Never">
        {#snippet below()}
          <div class="chips" role="group" aria-label="Never">
            {#each options.never as w (w)}
              <Chip id="never-{w}" label={word(w)} pressed={f.never.includes(w)} onclick={() => toggle("never", w)} />
            {/each}
          </div>
        {/snippet}
      </ListRow>
    </ListSection>

    <ListSection id="substitutes" title="Substitutes">
      <ListRow id="row-allowed" label="Allowed" description={f.allowed === "off" ? "Each substitute waits for you" : "Not on the list: waits for you"} {...place(allowedF)} />
      {#if f.allowed === "listed"}
        <ListRow
          id="row-extra"
          label="Extra cost up to"
          description={r.saved && pct !== null && pct !== (r.substitutes === "extra" ? r.maxExtraPct : 0) ? `Was ${extraText(r.maxExtraPct).toLowerCase()}` : "Above it, waits for you"}
          {...place(extraF)}
        />
      {/if}
    </ListSection>

    <ListSection id="save">
      <div class="save">
        <p class="change" class:bad={!!formProblem} data-testid="rules-changes" role={formProblem ? "alert" : undefined}>{formProblem || changeLine}</p>
        <VCode bind:value={code} error={codeError} onsubmit={save} submitLabel="Save rules" oncancel={chrome.phone ? undefined : () => goto("/rules")} focus={false} {busy} />
      </div>
    </ListSection>
  {/if}
</div>

<style>
  .blocks {
    display: flex;
    flex-direction: column;
    gap: 32px;
  }
  .blocks > :global(*) {
    margin: 0;
  }
  /* The kit Chip paints a pressed chip's label in the foreground under the
     pointer, on a foreground fill: the label vanished. It keeps its colour here. */
  .chips :global(.chip.on button.chip-body:hover) {
    color: inherit;
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  /* A finger needs the phone's control height, not the desk's 24 px chip. */
  @media (max-width: 760px) {
    .chips :global(.chip) {
      height: var(--height-control);
    }
  }
  .save {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 16px 0 20px;
  }
  .change {
    margin: 0;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  .change.bad {
    color: var(--v-bad-text);
  }
</style>
