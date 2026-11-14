<script lang="ts">
  /// A request as a halbat record: crumbs, h1, facts, the lead (or the
  /// question), two lanes with plots, the ignored line, then tabs of option rows.
  import { tick } from "svelte";
  import { page } from "$app/state";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { ChevronRight } from "@lucide/svelte";
  import { api } from "$lib/api/client";
  import type { RankedOption } from "$lib/api/types";
  import { live } from "$lib/live.svelte";
  import { day, money, nb } from "$lib/format";
  import { optionLine, optionPill, requestPill, turnedDownGroups, weekLine } from "$lib/v";
  import VHead from "$lib/v/VHead.svelte";
  import VLane from "$lib/v/VLane.svelte";
  import VPill from "$lib/v/VPill.svelte";
  import VPlotOptions from "$lib/v/VPlotOptions.svelte";
  import VPlotTotal from "$lib/v/VPlotTotal.svelte";
  import VState from "$lib/v/VState.svelte";
  import VTabs from "$lib/v/VTabs.svelte";

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

  // Without a swap: Possible and Turned down. With a swap: Valio's list and Beyond the list.
  const valioList = $derived(line ? [...line.options, ...(line.substitutes ?? [])] : []);
  const beyond = $derived(line?.beyondList ?? []);
  const beyondPossible = $derived(beyond.filter((o) => o.verdict === "chosen" || o.verdict === "ranked"));
  const beyondDown = $derived(beyond.filter((o) => o.verdict !== "chosen" && o.verdict !== "ranked"));
  // One name for the fold: every group here is about delivery, or it is plainly "Not orderable".
  const downLabel = $derived(beyondDown.every((o) => /cut-off|deliver/i.test(o.groupText ?? "")) ? "Can't arrive in time" : "Not orderable");
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
    const el = document.getElementById(`supplier-${planted.productId}`) as HTMLDetailsElement | null;
    if (el) el.open = true;
    el?.scrollIntoView({ block: "center" });
  }
  const rank = (list: RankedOption[], o: RankedOption) => String(list.indexOf(o) + 1);

  const rejected = $derived(r?.status === "rejected");
  // When Validio read Valio live: the API's liveAt, else the request's own time.
  const liveTime = $derived(r?.liveAt ?? r?.timeText);
  // The asked-for product's live count goes into the chosen row's fold, once.
  const liveCount = $derived(r?.liveCountText);
  /** A ranked row's short text is its price over the chosen one ("+90.00 €"): it goes to the amount column. */
  const over = (o: RankedOption): string | undefined => (o.shortText?.startsWith("+") ? o.shortText : undefined);
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
      {#if !over(o)}<span class="ev-sub">{optionLine(o)}</span>{/if}
      {#if o.verdict === "chosen"}
        <details class="fold">
          <summary data-testid="why-{o.productId}"><ChevronRight class="chev" aria-hidden="true" />Why this product</summary>
          <ul class="fold-body why-facts" data-testid="why-body-{o.productId}">
            {#each o.checks ?? [] as f (f)}<li data-testid="why-check">{nb(f)}</li>{/each}
            {#if liveCount}<li data-testid="asked-for" id="asked-for">{nb(liveCount)}</li>{/if}
          </ul>
        </details>
      {/if}
      {#if o.supplierText && (o.supplierText.planted || o.supplierText.reader)}
        <details class="fold" data-testid="supplier-{o.productId}" id="supplier-{o.productId}">
          <summary><ChevronRight class="chev" aria-hidden="true" />{o.supplierText.planted ? "Written to steer AI agents" : "Written by the supplier"}</summary>
          <span class="fold-body rc-diff">
            <span class="top">
              <span>{o.supplierText.planted ? "Planted by the team for the demo." : "Written by the supplier."}</span>
              <VPill label="Untrusted" tone="neutral" />
            </span>
            <q class="quote">{o.supplierText.text}</q>
            {#if o.supplierText.reader}
              <span class="reader" data-testid="reader-{o.productId}" id="reader-{o.productId}">{nb(o.supplierText.reader.summary)}</span>
            {/if}
          </span>
        </details>
      {/if}
    </span>
    <span class="ev-amt" class:none={!amt}>{amt || "No price"}{#if over(o)}<span class="ev-over num">{over(o)}</span>{/if}</span>
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
    <VHead title="Request {id}" crumbs={[{ href: "/orders", label: "Orders" }]} here={id} back={{ href: "/orders", label: "Orders" }} />
    <VState kind="error" title={/404|not found/i.test(req.error) ? `No request ${id}.` : "Validio is not reachable."} detail={req.error} onretry={() => location.reload()} />
  {:else}
    <VState kind="loading" rows={4} />
  {/if}
{:else}
  <VHead
    title={r.titleText ?? r.displayName ?? r.title ?? r.text}
    titleId="request-title"
    crumbs={[{ href: "/orders", label: "Orders" }]}
    here={r.id}
    back={{ href: "/orders", label: "Orders" }}
  >
    {#snippet facts()}
      <VPill label={pill.label} tone={pill.tone} testid="request-status" id="request-status" />
      <b class="num">{r.moneyText ?? money(r.totalCents)}</b>
      <span>Deliver by {day(r.deliverBy)}</span>
      {#if liveTime}<span data-testid="live-checked" id="live-checked">Live {liveTime}</span>{/if}
    {/snippet}
    {#if r.status === "waiting"}
      <p class="question">{nb(r.question)}</p>
      <!-- The one place on the page that names the stock-out. -->
      <p class="q-sub" id="request-why">{nb(r.leadText ?? "")}</p>
      <div class="head-btn">
        <Button href="/approve/{r.id}" data-testid="open-approve" id="open-approve">Open approval</Button>
      </div>
    {:else if r.status === "ordered" || r.status === "approved"}
      <p class="question">Ordered after you approved.</p>
      <p class="q-sub">Price and delivery confirmed again.</p>
    {:else if r.status === "rejected"}
      <p class="question">You rejected it.</p>
      <p class="q-sub">Nothing was ordered.</p>
    {/if}
  </VHead>

  <div class="blocks">
    <div class="lanes">
      <VLane
        name={rejected ? "Proposed" : "Total"}
        testid="lane-total"
        value={r.moneyText ?? money(r.totalCents)}
        sub={rejected ? "Nothing added" : weekLine((r.usedBeforeCents ?? 0) + (r.totalCents ?? 0), pass.data?.weekCapCents)}
      >
        {#snippet plot()}
          <VPlotTotal amount={rejected ? 0 : (r.totalCents ?? 0)} auto={pass.data?.autoLimitCents} cap={pass.data?.hardCapCents} />
        {/snippet}
      </VLane>
      <VLane name="Options" testid="lane-options" value={String(counted.length)}>
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

    {#if planted}
      <a class="ignored" href="#supplier-{planted.productId}" onclick={toIgnored} data-testid="ignored-note" id="ignored-note">1 ignored: written to steer AI agents ›</a>
    {/if}

    {#snippet optionTabs()}
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
          {#if beyondDown.length}
            <!-- The options that cannot be ordered wait behind one fold, as on Approve. -->
            <details class="fold later" data-testid="not-orderable" id="not-orderable">
              <summary><ChevronRight class="chev" aria-hidden="true" />{downLabel} <span class="num">{beyondDown.length}</span></summary>
              {@render groups(beyondDown)}
            </details>
          {/if}
        </div>
      {:else}
        <div class="pane" role="tabpanel" id="panel-possible" aria-labelledby="tab-possible" hidden={selected !== "possible"}>
          <ul class="rc-ev">
            {#each possible as o (o.productId)}{@render optionRow(o, rank(possible, o))}{/each}
          </ul>
        </div>
        <div class="pane" role="tabpanel" id="panel-down" aria-labelledby="tab-down" hidden={selected !== "down"}>
          {@render groups(down)}
        </div>
      {/if}
    </div>
    {/snippet}
    {#if rejected}
      <!-- Nothing was ordered: the options wait behind one fold. -->
      <details class="fold" data-testid="options-fold" id="options-fold">
        <summary><ChevronRight class="chev" aria-hidden="true" />Options <span class="num">{counted.length}</span></summary>
        {@render optionTabs()}
      </details>
    {:else}
      {@render optionTabs()}
    {/if}
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
  .pane > .rc-ev:first-child > :global(li:first-child) {
    padding-top: 0;
  }
  .pane :global(.day:first-child) {
    padding-top: 0;
  }
  .why-facts { margin: 0; list-style: none; }
  .ev-over { display: block; font-size: var(--fs-meta); color: var(--v-muted); }
  .ignored { color: var(--v-muted); text-decoration: none; }
  .ignored:hover { color: var(--v-fg); }
  .later { margin-top: 24px; }
</style>
