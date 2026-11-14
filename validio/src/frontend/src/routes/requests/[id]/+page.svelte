<script lang="ts">
  /// A request as a halbat record: crumbs, h1, facts, the lead (or the
  /// question), two lanes with plots, a card of value rows, then tabs of option rows.
  import { tick } from "svelte";
  import { page } from "$app/state";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { ChevronRight } from "@lucide/svelte";
  import { api } from "$lib/api/client";
  import type { RankedOption } from "$lib/api/types";
  import { live } from "$lib/live.svelte";
  import { day, fieldWord, money, nb, valueWord } from "$lib/format";
  import { optionLine, optionPill, requestPill, turnedDownGroups } from "$lib/v";
  import VHead from "$lib/v/VHead.svelte";
  import VLane from "$lib/v/VLane.svelte";
  import VPill from "$lib/v/VPill.svelte";
  import VPlotOptions from "$lib/v/VPlotOptions.svelte";
  import VPlotTotal from "$lib/v/VPlotTotal.svelte";
  import VState from "$lib/v/VState.svelte";
  import VTabs from "$lib/v/VTabs.svelte";
  import VValueRow from "$lib/v/VValueRow.svelte";

  const id = $derived(page.params.id ?? "");
  const req = live(() => api.request(id));
  const pass = live(() => api.spendPass("M-1"));

  const r = $derived(req.data?.id === id ? req.data : undefined);
  const line = $derived(r?.lines[0]);
  const asked = $derived(line?.need.productId);
  const swap = $derived(!!line?.substitutes?.length);
  const all = $derived(line ? [...line.options, ...(line.substitutes ?? []), ...(line.beyondList ?? [])] : []);
  const counted = $derived(all.filter((o) => o.productId !== asked));
  const possible = $derived(counted.filter((o) => o.verdict === "chosen" || o.verdict === "ranked"));
  const down = $derived(counted.filter((o) => o.verdict !== "chosen" && o.verdict !== "ranked"));
  const chosen = $derived(all.find((o) => o.verdict === "chosen"));
  const prices = $derived(counted.map((o) => o.totalCents).filter((c): c is number => c !== undefined));
  const sim = $derived(r?.simulated?.[0]);
  const planted = $derived(all.find((o) => o.supplierText?.planted || o.supplierText?.reader?.flags.some((f) => f.code === "addresses_agents")));
  const pill = $derived(requestPill(r?.status));
  const rule = $derived(r?.decision.ruleIds[0]);

  // Without a swap: Possible and Turned down. With a swap: Valio's list and Beyond the list.
  const valioList = $derived(line ? [...line.options, ...(line.substitutes ?? [])] : []);
  const beyond = $derived(line?.beyondList ?? []);
  const beyondPossible = $derived(beyond.filter((o) => o.verdict === "chosen" || o.verdict === "ranked"));
  const beyondDown = $derived(beyond.filter((o) => o.verdict !== "chosen" && o.verdict !== "ranked"));
  let tab = $state("");
  $effect(() => {
    void id;
    tab = "";
  });
  const tabs = $derived(
    swap
      ? [
          { id: "list", label: "Valio's list", count: valioList.length },
          { id: "beyond", label: "Beyond the list", count: beyond.length },
        ]
      : [
          { id: "possible", label: "Possible", count: possible.length },
          { id: "down", label: "Turned down", count: down.length },
        ],
  );
  const selected = $derived(tab || (swap ? "beyond" : "possible"));

  async function toIgnored(e: MouseEvent) {
    e.preventDefault();
    if (!planted) return;
    tab = swap ? (beyond.includes(planted) ? "beyond" : "list") : "down";
    await tick();
    document.getElementById(`supplier-${planted.productId}`)?.scrollIntoView({ block: "center" });
  }
  const rank = (list: RankedOption[], o: RankedOption) => String(list.indexOf(o) + 1);

  const rejected = $derived(r?.status === "rejected");
  // The facts Validio confirmed, for the chosen row's fold.
  const CHECKED = new Set(["attested", "attested_until", "consistent"]);
  function checkedLine(o: RankedOption): string {
    const f = o.facts.filter((x) => CHECKED.has(x.grade) && !/^(description|key_ingredients)$/.test(x.field) && (x.valueText ?? x.value) != null);
    return f.length ? `Checked: ${f.map((x) => `${fieldWord(x.field)} ${x.valueText ?? valueWord(x.field, x.value)}`).join(", ")}.` : "";
  }
  // The owner's states carry the rule in the chosen row's fold, not in the head.
  const ruleInFold = $derived(["waiting", "ordered", "approved", "rejected"].includes(r?.status ?? ""));
  const priced = $derived(prices.length);
  // "Lactose-free mozzarella 125 g is out of stock (simulated)." from askedFor.
  const askedLine = $derived.by(() => {
    const a = r?.askedFor;
    if (!a) return "";
    const state = a.stateText.replace(/\s*\(.*\)\s*$/, "").replace(/ at Valio$/i, "");
    const simulated = /simulated/i.test(a.stateText) ? " (simulated)" : "";
    return `${a.displayName} is ${state.charAt(0).toLowerCase()}${state.slice(1)}${simulated}.`;
  });
  const askedSub = $derived(/Valio really has [^)]+/.exec(r?.askedFor?.stateText ?? "")?.[0]);
</script>

{#snippet optionRow(o: RankedOption, left: string | null, grouped = false)}
  {@const p = grouped
    ? null
    : o.productId === asked
      ? { label: "Asked for", tone: "neutral" as const }
      : o.verdict === "chosen" && rejected
        ? { label: "Proposed", tone: "neutral" as const }
        : optionPill(o)}
  {@const amt = o.moneyText ?? money(o.totalCents)}
  <li data-testid="option-{o.productId}" id="option-{o.productId}">
    <span class="ev-left">{#if p}<VPill label={p.label} tone={p.tone} />{:else if left}{left}{/if}</span>
    <span class="ev-main">
      <span class="ev-name">{nb(o.displayName ?? o.name)}</span>
      <span class="ev-sub">{optionLine(o)}</span>
      {#if o.verdict === "chosen"}
        <details class="fold">
          <summary data-testid="why-{o.productId}"><ChevronRight class="chev" aria-hidden="true" />Why this product</summary>
          <div class="fold-body" data-testid="why-body-{o.productId}">
            <p>{o.fullName ?? o.name}, product {o.productId}.</p>
            {#each o.reasons?.length ? o.reasons : [o.sentence] as why (why)}<p>{nb(why)}</p>{/each}
            {#if checkedLine(o)}<p>{nb(checkedLine(o))}</p>{/if}
            {#if ruleInFold}<p data-testid="request-rule" id="request-rule">Rule: {rule}</p>{/if}
          </div>
        </details>
      {/if}
      {#if o.supplierText && (o.supplierText.planted || o.supplierText.reader)}
        <span class="rc-diff" data-testid="supplier-{o.productId}" id="supplier-{o.productId}">
          <span class="top">
            <span>{o.supplierText.planted ? "Planted by the team for the demo." : "Written by the supplier."}</span>
            <VPill label="Untrusted" tone="neutral" />
          </span>
          <q class="quote">{o.supplierText.text}</q>
          {#if o.supplierText.reader}
            <span class="reader" data-testid="reader-{o.productId}" id="reader-{o.productId}">{nb(o.supplierText.reader.summary)}</span>
          {/if}
        </span>
      {/if}
    </span>
    <span class="ev-amt" class:none={!amt}>{amt || "No price"}</span>
  </li>
{/snippet}

{#snippet groups(list: RankedOption[])}
  {#each turnedDownGroups(list) as g (g.name)}
    <div class="day"><b>{g.name}</b><span>{g.items.length}</span></div>
    <ul class="rc-ev">
      {#each g.items as o (o.productId)}{@render optionRow(o, null, true)}{/each}
    </ul>
  {/each}
{/snippet}

{#if !r}
  {#if req.error}
    <VHead title="Request {id}" crumbs={[{ href: "/", label: "Inbox" }]} here={id} back={{ href: "/", label: "Inbox" }} />
    <VState kind="error" title={/404|not found/i.test(req.error) ? `No request ${id}.` : "Validio is not reachable."} detail={req.error} onretry={() => location.reload()} />
  {:else}
    <VState kind="loading" rows={4} />
  {/if}
{:else}
  <VHead
    title={r.titleText ?? r.displayName ?? r.title ?? r.text}
    titleId="request-title"
    crumbs={[{ href: "/", label: "Inbox" }]}
    here={r.id}
    back={{ href: "/", label: "Inbox" }}
  >
    {#snippet facts()}
      <VPill label={pill.label} tone={pill.tone} testid="request-status" id="request-status" />
      <b class="num">{r.moneyText ?? money(r.totalCents)}</b>
      <span>Deliver by {day(r.deliverBy)}</span>
      {#if r.orderId && r.status !== "waiting" && r.status !== "rejected"}<a href="/ledger">Order {r.orderId} ›</a>{/if}
    {/snippet}
    {#if r.status === "waiting"}
      <p class="question">{nb(r.question)}</p>
      <p class="q-sub" id="request-why">
        {#if r.askedFor}{nb(askedLine)}{:else if sim}{nb(sim.sentence)}{/if}
        {#if chosen?.isSubstitute && !chosen.onValioList}The swap is not on Valio's list.{/if}
      </p>
      <div class="head-btn">
        <Button href="/approve/{r.id}" data-testid="open-approve" id="open-approve">Open approval</Button>
      </div>
    {:else if r.status === "ordered" || r.status === "approved"}
      <p class="question">Placed after you approved.</p>
      <p class="q-sub">Price and delivery confirmed again.</p>
    {:else if r.status === "rejected"}
      <p class="question">You rejected it.</p>
      <p class="q-sub">Nothing was ordered.</p>
    {:else}
      <p class="lead" id="decision-sentence">
        {nb(r.decision.summary ?? r.decision.sentence)}
        <span class="rule" data-testid="request-rule" id="request-rule">Rule: {rule}</span>
      </p>
    {/if}
  </VHead>

  <div class="blocks">
    <div class="lanes">
      <VLane
        name="Total"
        value={r.moneyText ?? money(r.totalCents)}
        sub={rejected ? "Nothing added" : r.usedBeforeCents ? `${money(r.usedBeforeCents)} ordered before` : undefined}
      >
        {#snippet plot()}
          <VPlotTotal before={r.usedBeforeCents ?? 0} amount={rejected ? 0 : (r.totalCents ?? 0)} auto={pass.data?.autoLimitCents} cap={pass.data?.hardCapCents} />
        {/snippet}
      </VLane>
      <VLane name="Options" testid="lane-options" value={String(counted.length)} sub="{priced} with a price, {counted.length - priced} without">
        {#snippet plot()}
          <VPlotOptions
            {prices}
            chosen={chosen?.totalCents}
            word={rejected ? "Proposed" : "Chosen"}
            said="{prices.length} priced options from {money(Math.min(...prices))} to {money(Math.max(...prices))}{chosen?.totalCents !== undefined ? `, ${rejected ? "proposed" : "chosen"} ${money(chosen.totalCents)}` : ''}."
          />
        {/snippet}
      </VLane>
    </div>

    <Section class="v-card">
      {#if r.askedFor}
        <VValueRow label="Asked for" value={r.askedFor.displayName} sub={askedSub ? `${askedSub}.` : r.askedFor.stateText} testid="asked-for" />
      {/if}
      <VValueRow label="Checked live" value="Read live from Valio at {r.timeText ?? '10:00'}" sub="Stock, price and delivery" testid="live-checked" />
      {#if planted}
        <VValueRow label="Ignored" value="Written to steer AI agents" sub={planted.supplierText?.planted ? "Planted by the team for the demo." : undefined} href="#supplier-{planted.productId}" onclick={toIgnored} testid="ignored-note" />
      {/if}
    </Section>

    <div class="tabbed">
      <VTabs {tabs} bind:selected={() => selected, (v) => (tab = v)} label="Options" />
      {#if swap}
        <div class="pane" role="tabpanel" id="panel-list" aria-labelledby="tab-list" hidden={selected !== "list"}>
          <ul class="rc-ev">
            {#each valioList as o (o.productId)}{@render optionRow(o, null)}{/each}
          </ul>
        </div>
        <div class="pane" role="tabpanel" id="panel-beyond" aria-labelledby="tab-beyond" hidden={selected !== "beyond"}>
          <ul class="rc-ev">
            {#each beyondPossible as o (o.productId)}{@render optionRow(o, rank(beyondPossible, o))}{/each}
          </ul>
          {@render groups(beyondDown)}
        </div>
      {:else}
        <div class="pane" role="tabpanel" id="panel-possible" aria-labelledby="tab-possible" hidden={selected !== "possible"}>
          <ul class="rc-ev">
            {#each possible as o (o.productId)}{@render optionRow(o, rank(possible, o))}{/each}
          </ul>
          {#if line?.note}<p class="cap note">{nb(line.note)}</p>{/if}
        </div>
        <div class="pane" role="tabpanel" id="panel-down" aria-labelledby="tab-down" hidden={selected !== "down"}>
          {@render groups(down)}
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .lanes {
    display: flex;
    flex-direction: column;
  }
  .ev-main {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .ev-main :global(details.fold) {
    margin-top: 4px;
  }
  .rc-diff {
    display: flex;
    flex-direction: column;
    gap: 4px;
    color: var(--v-fg);
  }
  .quote {
    quotes: "\201C" "\201D";
  }
  .reader {
    color: var(--v-muted);
  }
  .note {
    margin: 12px 0 0;
  }
  .pane > .rc-ev:first-child > :global(li:first-child) {
    padding-top: 0;
  }
  .pane :global(.day:first-child) {
    padding-top: 0;
  }
</style>
