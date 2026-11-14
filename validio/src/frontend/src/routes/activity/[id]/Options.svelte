<script lang="ts">
  /// The options Validio compared at Valio for one request, as a ruled table:
  /// Product | Per unit | Total | Arrives | Delivered in full. The chosen row
  /// is tinted with a petrol rule on the left, a small-caps "Chosen" and its
  /// why sentence; the turned-down ones wait in a fold under their reasons.
  /// Everything comes from the backend's request view (api.request).
  import { tick } from "svelte";
  import { ChevronRight } from "@lucide/svelte";
  import type { RankedOption, SupplyRequest } from "$lib/api/types";
  import { money, nb } from "$lib/format";

  let { req, proposed = false }: { req: SupplyRequest; /** Nothing was ordered: the chosen row is only proposed. */ proposed?: boolean } = $props();

  const line = $derived(req.lines[0]);
  const asked = $derived(line?.need.productId);
  const all = $derived(line ? [...line.options, ...(line.substitutes ?? []), ...(line.beyondList ?? [])] : []);
  const counted = $derived(all.filter((o) => o.productId !== asked));
  const suitable = $derived(
    counted
      .filter((o) => o.verdict === "chosen" || o.verdict === "ranked")
      .sort((a, b) => (a.verdict === "chosen" ? -1 : b.verdict === "chosen" ? 1 : (a.totalCents ?? 0) - (b.totalCents ?? 0))),
  );
  const unsuitable = $derived(counted.filter((o) => o.verdict !== "chosen" && o.verdict !== "ranked"));

  const optionLine = (o: RankedOption) => nb(o.shortText ?? o.sentence);
  const arrives = (o: RankedOption) => (o.deliveryText ? o.deliveryText.replace(/^Arrives /, "") : "");
  const reliability = (o: RankedOption) => {
    const t = o.reliabilityText ?? "";
    if (/every time/i.test(t)) return "Every time";
    const m = /(\d+) of (\d+)/.exec(t);
    if (m) return `${m[1]} of ${m[2]}`;
    if (/no record/i.test(t)) return "No record yet";
    return t;
  };
  /** Under a suitable option that lost: why not, short ("Costs 90.00 € more"). */
  const whyNot = (o: RankedOption) => (o.whyNotText ? o.whyNotText.split(/:\s/)[0].replace(/\.$/, "") : optionLine(o));
  /** Under a turned-down option: the reason without the group's own words. */
  const notReason = (o: RankedOption) => (o.whyNotText ?? optionLine(o)).replace(/^Not suitable:\s*/i, "").replace(/^./, (c) => c.toUpperCase());
  function groups(list: RankedOption[]) {
    const out = new Map<string, { name: string; order: number; items: RankedOption[] }>();
    for (const o of list) {
      const name = o.groupText ?? "Turned down";
      const g = out.get(name) ?? { name, order: o.groupOrder ?? 99, items: [] };
      g.items.push(o);
      out.set(name, g);
    }
    return [...out.values()].sort((a, b) => a.order - b.order || a.name.localeCompare(b.name));
  }

  // Every suitable option priced per litre: the head says "Per litre" and the cells hold the price alone.
  const UNIT_WORD: Record<string, string> = { l: "litre", kg: "kilo" };
  const perUnit = $derived.by(() => {
    const units = new Set(suitable.map((o) => /per (\S+)$/.exec(o.unitPriceText ?? "")?.[1]).filter(Boolean));
    return units.size === 1 ? [...units][0]! : "";
  });
  const unitHead = $derived(perUnit ? `Per ${UNIT_WORD[perUnit] ?? perUnit}` : "Per unit");
  const unitPrice = (o: RankedOption) => (perUnit ? (o.unitPriceText ?? "").replace(/ per \S+$/, "") : nb(o.unitPriceText ?? ""));
  // A column only when some option has it.
  const hasUnit = $derived(suitable.some((o) => o.unitPriceText));
  const hasArrive = $derived(suitable.some((o) => o.deliveryText));
  const hasRecord = $derived(suitable.some((o) => o.reliabilityText));
  const cols = $derived(2 + (hasUnit ? 1 : 0) + (hasArrive ? 1 : 0) + (hasRecord ? 1 : 0));
  /** On the phone the columns fold into one line under the name. */
  const phoneMeta = (o: RankedOption) =>
    [o.unitPriceText, arrives(o) && `arrives ${arrives(o)}`, reliability(o) && `in full ${reliability(o).toLowerCase()}`].filter(Boolean).join(", ");

  let openDown = $state(false);
  /** The supplier text Validio ignored: open the fold and show its row. */
  export async function show(productId: string) {
    openDown = true;
    await tick();
    const row = document.getElementById(`option-${productId}`);
    row?.scrollIntoView({ block: "center" });
    row?.classList.add("flash");
    setTimeout(() => row?.classList.remove("flash"), 1600);
  }
</script>

{#snippet optionRow(o: RankedOption)}
  {@const isChosen = o.verdict === "chosen"}
  <tr class:chosen={isChosen} data-testid="option-{o.productId}" id="option-{o.productId}">
    <td class="prod">
      {#if isChosen}<span class="smallcaps pick">{proposed ? "Proposed" : "Chosen"}</span>{/if}
      <span class="p-name">{nb(o.displayName ?? o.name)}</span>
      <span class="p-sub">{nb(isChosen ? (o.qtyText ?? "") : whyNot(o))}</span>
      <span class="p-meta">{nb(phoneMeta(o))}</span>
    </td>
    {#if hasUnit}<td class="r num">{nb(unitPrice(o))}</td>{/if}
    <td class="r num total">{o.moneyText ?? money(o.totalCents)}</td>
    {#if hasArrive}<td class="num">{nb(arrives(o))}</td>{/if}
    {#if hasRecord}<td>{reliability(o)}</td>{/if}
  </tr>
  {#if isChosen && (o.whyText || o.checks?.length)}
    <tr class="chosen why-row">
      <td class="why-cell" colspan={cols}>
        {#if o.whyText}<p class="why-text">{nb(o.whyText)}</p>{/if}
        {#if o.checks?.length}
          <details class="fold">
            <summary data-testid="why-{o.productId}"><ChevronRight class="chev" aria-hidden="true" />What Validio confirmed</summary>
            <ul class="fold-body why-facts">
              {#each o.checks as f (f)}<li>{nb(f)}</li>{/each}
            </ul>
          </details>
        {/if}
      </td>
    </tr>
  {/if}
{/snippet}

<div class="options" data-testid="options">
  <h3 class="o-h">{proposed ? "What Validio compared" : "Suitable options"} <em class="num">{suitable.length}</em></h3>
  {#if suitable.length}
    <table class="opts">
      <thead>
        <tr>
          <th class="v-th">Product</th>
          {#if hasUnit}<th class="v-th r">{unitHead}</th>{/if}
          <th class="v-th r">Total</th>
          {#if hasArrive}<th class="v-th">Arrives</th>{/if}
          {#if hasRecord}<th class="v-th">Delivered in full</th>{/if}
        </tr>
      </thead>
      <tbody>
        {#each suitable as o (o.productId)}{@render optionRow(o)}{/each}
      </tbody>
    </table>
  {:else}
    <p class="notice quiet">No product fitted every rule.</p>
  {/if}

  {#if unsuitable.length}
    <details class="fold unsuitable" data-testid="not-suitable" bind:open={openDown}>
      <summary><ChevronRight class="chev" aria-hidden="true" />Not suitable <span class="num">({unsuitable.length})</span></summary>
      {#each groups(unsuitable) as g (g.name)}
        <div class="day"><b>{g.name}</b><span class="num">{g.items.length}</span></div>
        <ul class="rc-ev">
          {#each g.items as o (o.productId)}
            <li data-testid="option-{o.productId}" id="option-{o.productId}">
              <span class="ev-main">
                <span class="ev-name">{nb(o.displayName ?? o.name)}</span>
                <span class="ev-sub">{nb(notReason(o))}{#if o.supplierText?.planted || o.supplierText?.reader} Its description talks to AI agents and was ignored.{/if}</span>
              </span>
              <span class="ev-amt" class:none={!o.moneyText && o.totalCents === undefined}>{o.moneyText ?? (money(o.totalCents) || "No price")}</span>
            </li>
          {/each}
        </ul>
      {/each}
    </details>
  {/if}
</div>

<style>
  .options {
    margin-top: 28px;
  }
  .o-h {
    display: flex;
    align-items: baseline;
    gap: 8px;
    margin: 0 0 10px;
    font-size: var(--fs-head);
    line-height: var(--lh-head);
    font-weight: 600;
  }
  .o-h em {
    font-style: normal;
    font-weight: 400;
    font-size: var(--fs-meta);
    color: var(--v-faint);
  }
  .opts {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--fs-head);
    line-height: var(--lh-head);
  }
  .opts th {
    padding: 0 10px 10px;
    text-align: left;
    vertical-align: bottom;
    border-bottom: 1px solid var(--v-fg);
    white-space: nowrap;
  }
  .opts th.r,
  .opts td.r {
    text-align: right;
  }
  .opts td {
    padding: 14px 10px;
    vertical-align: top;
    border-bottom: 1px solid var(--v-line);
    white-space: nowrap;
  }
  .opts td.prod {
    width: 46%;
    white-space: normal;
  }
  .p-name {
    display: block;
    font-weight: 500;
  }
  .p-meta {
    display: none;
  }
  .p-sub {
    display: block;
    margin-top: 2px;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  .pick {
    display: block;
    margin-bottom: 2px;
    color: var(--valio);
  }
  tr.chosen td {
    background: var(--valio-tint);
  }
  tr.chosen td:first-child {
    box-shadow: inset 3px 0 0 var(--valio);
  }
  tr.chosen:not(.why-row) td {
    border-bottom-color: transparent;
  }
  tr.why-row td {
    padding-top: 0;
    padding-bottom: 14px;
    white-space: normal;
  }
  .why-text {
    margin: 0 0 4px;
    max-width: 560px;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--valio-why);
  }
  .why-facts {
    margin: 6px 0 0;
    padding: 0;
    list-style: none;
  }
  .why-facts li + li {
    margin-top: 2px;
  }
  .opts tbody tr:not(.chosen):hover td {
    background: var(--v-tint-hover);
  }
  :global(.flash) {
    animation: flash var(--duration-slow) ease;
  }
  @keyframes flash {
    from {
      background: var(--valio-tint-strong);
    }
  }
  .unsuitable {
    margin-top: 20px;
  }
  .unsuitable .day:first-of-type {
    padding-top: 16px;
  }
  .unsuitable .rc-ev > li {
    grid-template-columns: minmax(0, 1fr) auto;
  }

  @media (max-width: 760px) {
    .opts thead {
      display: none;
    }
    .opts,
    .opts tbody {
      display: block;
    }
    .opts tr {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      column-gap: 12px;
      padding: 12px 0;
      border-bottom: 1px solid var(--v-line);
    }
    .opts tr.chosen {
      padding: 12px 12px 12px 14px;
      background: var(--valio-tint);
      box-shadow: inset 3px 0 0 var(--valio);
      border-bottom: 0;
    }
    .opts tr.chosen td,
    .opts tr.chosen td:first-child {
      background: none;
      box-shadow: none;
      padding-left: 0;
    }
    .opts td {
      display: block;
      padding: 0;
      border: 0;
      white-space: normal;
    }
    .opts td.prod {
      width: auto;
    }
    .opts td.total {
      grid-column: 2;
      grid-row: 1;
    }
    .opts td:not(.prod):not(.total) {
      display: none;
    }
    .opts tr.why-row td.why-cell {
      display: block;
    }
    .p-meta {
      display: block;
      margin-top: 2px;
      font-size: var(--fs-meta);
      line-height: var(--lh-meta);
      color: var(--v-faint);
    }
    .opts tr.why-row {
      padding-top: 0;
      display: block;
      border-bottom: 1px solid var(--v-line);
    }
  }
</style>
