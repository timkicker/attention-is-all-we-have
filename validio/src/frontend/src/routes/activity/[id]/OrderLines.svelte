<script lang="ts">
  /// A request with several lines as one order table: Item | Quantity | Unit price | Total | Arrives, a row
  /// a line and the total under them. A row opens to what Validio checked for it at Valio (price, stock,
  /// allergens, diet). A line that was not ordered keeps its row, its reason in the outcome colour, and the
  /// order that brought it after all when the agent asked again. On the phone a row folds into its name, the
  /// quantity times the unit price, and the total.
  import { ChevronRight } from "@lucide/svelte";
  import type { ActivityLine } from "$lib/api/types";
  import { money, nb } from "$lib/format";

  let { lines, date, proposed = false }: { lines: ActivityLine[]; date: (ymd: string) => string; /** Nothing ordered (yet): no line is "left out". */ proposed?: boolean } = $props();

  let open = $state<Record<string, boolean>>({});
  const inOrder = $derived(lines.filter((l) => l.ordered !== false));
  const sum = $derived(inOrder.reduce((n, l) => n + (l.totalCents ?? 0), 0));
  const unit = (l: ActivityLine) => (l.unitPriceCents != null ? money(l.unitPriceCents) : "");
  const phoneMeta = (l: ActivityLine) =>
    [l.qtyText && (unit(l) ? `${l.qtyText} at ${unit(l)}` : l.qtyText), l.ordered !== false && l.delivery && `arrives ${date(l.delivery)}`].filter(Boolean).join(", ");
</script>

<div class="lines" data-testid="order-lines">
  <table class="ot">
    <thead>
      <tr>
        <th class="v-th">Item</th>
        <th class="v-th">Quantity</th>
        <th class="v-th r">Unit price</th>
        <th class="v-th r">Total</th>
        <th class="v-th">Arrives</th>
      </tr>
    </thead>
    <tbody>
      {#each lines as l (l.lineId)}
        {@const out = l.ordered === false || (proposed && !!l.reason)}
        {@const shown = !!open[l.lineId]}
        <tr class="row" class:out class:shown data-testid="line-{l.lineId}" data-ordered={l.ordered}>
          <td class="item">
            <button
              type="button"
              class="row-btn"
              aria-expanded={shown}
              aria-controls="checks-{l.lineId}"
              disabled={!l.checks.length}
              onclick={() => (open[l.lineId] = !shown)}
            >
              <ChevronRight class="chev" aria-hidden="true" />
              <span class="name">{nb(l.name)}</span>
            </button>
            {#if l.product && l.product.toLowerCase() !== l.name.toLowerCase()}<span class="sub">{nb(l.product)}</span>{/if}
            {#if out && l.reason}
              <span class="why" data-testid="line-reason">
                {nb(l.reason)}.{#if l.replacedBy}{" "}<a class="link" href="/activity/{l.replacedBy.requestId}" data-testid="line-replaced">Ordered later as {l.replacedBy.orderId}</a>{/if}
              </span>
            {/if}
            <span class="meta">{nb(phoneMeta(l))}</span>
          </td>
          <td class="num">{nb(l.qtyText ?? "")}</td>
          <td class="r num">{nb(unit(l))}</td>
          <td class="r num total">{#if out}<span class="none">Not ordered</span>{:else}{nb(money(l.totalCents ?? undefined))}{/if}</td>
          <td class="num arr">{#if !out && l.delivery}{nb(date(l.delivery))}{/if}</td>
        </tr>
        <tr class="fold-row" class:out id="checks-{l.lineId}" hidden={!shown}>
          <td colspan="5">
            <dl class="lc">
              {#each l.checks as c, n (n)}
                <div class="lc-row" data-ok={c.ok}>
                  <dt>{c.label}</dt>
                  <dd class:ok={c.ok === true} class:bad={c.ok === false}>
                    {#if c.ok === true}<span class="sr-only">Passed:</span>{:else if c.ok === false}<span class="sr-only">Failed:</span>{/if}
                    <span class="lc-v">{nb(c.value)}</span>
                    {#if c.note}<span class="lc-n">{nb(c.note)}</span>{/if}
                  </dd>
                </div>
              {/each}
            </dl>
          </td>
        </tr>
      {/each}
    </tbody>
    <tfoot>
      <tr class="sum" data-testid="lines-total">
        <th scope="row" class="item">Total<span class="count">{inOrder.length} of {lines.length} items</span></th>
        <td class="r num total" colspan="3">{nb(money(sum))}</td>
        <td class="arr"></td>
      </tr>
    </tfoot>
  </table>
</div>

<style>
  .ot {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--fs-head);
    line-height: var(--lh-head);
  }
  .ot th.v-th {
    padding: 0 10px 10px;
    text-align: left;
    vertical-align: bottom;
    border-bottom: 1px solid var(--v-fg);
    white-space: nowrap;
  }
  .ot th.r,
  .ot td.r {
    text-align: right;
  }
  .ot td {
    padding: 12px 10px;
    vertical-align: top;
    border-bottom: 1px solid var(--v-line);
    white-space: nowrap;
  }
  .ot td.item {
    width: 46%;
    white-space: normal;
  }
  /* The whole row opens its checks: the button's hit area covers the row. */
  .row {
    position: relative;
  }
  .row-btn {
    display: inline-flex;
    align-items: baseline;
    gap: 4px;
    margin: 0;
    padding: 0;
    border: 0;
    background: none;
    font: inherit;
    color: inherit;
    text-align: left;
    cursor: pointer;
  }
  .row-btn::after {
    content: "";
    position: absolute;
    inset: 0;
  }
  .row-btn:disabled {
    cursor: default;
  }
  .row-btn:disabled :global(.chev) {
    visibility: hidden;
  }
  .row-btn :global(.chev) {
    flex: none;
    align-self: center;
    width: 14px;
    height: 14px;
    color: var(--v-faint);
    transition: transform var(--duration-fast) ease;
  }
  .row.shown .row-btn :global(.chev) {
    transform: rotate(90deg);
  }
  .row:hover td {
    background: var(--v-tint-hover);
  }
  .row:hover .name {
    color: var(--valio);
  }
  .row.out:hover .name {
    color: var(--v-bad-text);
  }
  .row-btn:focus-visible {
    outline: none;
  }
  .row:has(.row-btn:focus-visible) td {
    box-shadow: inset 0 0 0 2px var(--valio);
  }
  .name {
    font-weight: 500;
  }
  .sub,
  .why,
  .meta {
    display: block;
    margin-top: 2px;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  .sub,
  .why,
  .meta,
  .lc {
    padding-left: 18px;
  }
  .meta {
    display: none;
  }
  .row.shown td {
    border-bottom-color: transparent;
  }

  /* A line left out of the order: its name and reason in the outcome colour, a thin rule on the left. */
  .row.out td.item {
    box-shadow: inset 2px 0 0 var(--v-bad);
  }
  .row.out .name,
  .row.out .why,
  .none {
    color: var(--v-bad-text);
  }
  .none {
    font-size: var(--fs-meta);
  }
  .why .link {
    position: relative;
    z-index: 1;
    white-space: nowrap;
  }

  /* The checks under a row. */
  .fold-row td {
    padding: 0 10px 14px 10px;
    white-space: normal;
  }
  .fold-row.out td {
    box-shadow: inset 2px 0 0 var(--v-bad);
  }
  .lc {
    margin: 0;
    max-width: 640px;
  }
  .lc-row {
    display: grid;
    grid-template-columns: 96px minmax(0, 1fr);
    column-gap: 16px;
    align-items: baseline;
    padding: 4px 0;
  }
  .lc dt {
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  .lc dd {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    column-gap: 8px;
    min-width: 0;
    margin: 0;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
  }
  .lc dd.ok,
  .lc dd.bad {
    padding-left: 8px;
    border-left: 2px solid var(--v-ok);
  }
  .lc dd.bad {
    border-left-color: var(--v-bad);
  }
  .lc-v {
    font-weight: 500;
    color: var(--v-fg);
    overflow-wrap: anywhere;
  }
  .lc dd.bad .lc-v {
    color: var(--v-bad-text);
  }
  .lc-n {
    color: var(--v-muted);
  }

  /* The total: under an ink rule, the sum of what was ordered. */
  .sum th,
  .sum td {
    padding: 12px 10px;
    border-top: 1px solid var(--v-fg);
    border-bottom: 0;
    text-align: left;
    font-weight: 600;
  }
  .sum td.r {
    text-align: right;
  }
  .count {
    margin-left: 10px;
    font-size: var(--fs-meta);
    font-weight: 400;
    color: var(--v-muted);
  }

  @media (max-width: 760px) {
    .ot thead {
      display: none;
    }
    .ot,
    .ot tbody,
    .ot tfoot {
      display: block;
    }
    .ot tr {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      column-gap: 12px;
      padding: 12px 0;
      border-bottom: 1px solid var(--v-line);
    }
    .ot tr[hidden] {
      display: none;
    }
    .ot td {
      display: block;
      padding: 0;
      border: 0;
      white-space: normal;
    }
    .ot td.item {
      width: auto;
    }
    .ot td.total {
      grid-column: 2;
      grid-row: 1;
    }
    .ot tr.row td:not(.item):not(.total),
    .sum td.arr {
      display: none;
    }
    .meta {
      display: block;
      color: var(--v-faint);
    }
    .row.out td.item,
    .fold-row.out td {
      box-shadow: none;
    }
    .row.out,
    .fold-row.out {
      padding-left: 10px;
      box-shadow: inset 2px 0 0 var(--v-bad);
    }
    .row:hover td {
      background: none;
    }
    .row.shown {
      border-bottom: 0;
      padding-bottom: 4px;
    }
    .fold-row {
      padding-top: 0;
    }
    .fold-row td {
      grid-column: 1 / -1;
      padding: 0;
    }
    .lc-row {
      grid-template-columns: 80px minmax(0, 1fr);
      column-gap: 10px;
    }
    .sum {
      border-top: 1px solid var(--v-fg);
      border-bottom: 0;
    }
    .sum th,
    .sum td {
      padding: 0;
      border: 0;
    }
  }
</style>
