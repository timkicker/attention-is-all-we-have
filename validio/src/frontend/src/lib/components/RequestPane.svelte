<script lang="ts">
  /// One request, cut to what the owner needs now: the title, one line of
  /// figures with the state, one sentence, and the action when one waits.
  /// Everything behind it sits in one fold: why this product (the first few
  /// options, then all), the Spend Pass in one line, and a quiet footnote
  /// with the live check, the rule and any simulated fact. Every field the API
  /// may leave out is optional, so a half-finished request still renders.
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import * as Collapsible from "@arlen/ui-kit/components/ui/collapsible";
  import type { RankedOption, SpendPass, SupplyRequest } from "$lib/api/types";
  import { STATUS, amount, day, look, money, prose, requestTitle, sentences, stockOutLine } from "$lib/format";
  import OptionList from "./OptionList.svelte";
  import State from "./State.svelte";

  let { req, pass }: { req: SupplyRequest; pass?: SpendPass } = $props();

  const status = $derived(look(STATUS, req.status));
  const live = $derived(req.liveChecked);
  const title = $derived(requestTitle(req));
  const asking = $derived(req.status === "waiting" && !!req.orderId);
  // Waiting: the question's last sentence is the one sentence ("Order 10
  // packs of ... for 180.10 €?"), its reasons fold. Otherwise the decision's
  // first sentence, the rest folds.
  const asked = $derived(sentences(req.question));
  const said = $derived(sentences(req.decision?.sentence));
  const lead = $derived(asking && asked.length ? prose(asked.at(-1) ?? "") : said[0]);

  // A simulated stock-out changes the outcome, so it gets the one muted line:
  // "Gran Castelli ... is out of stock at Valio (simulated for the demo; Valio
  // really has 11,603 bags)."
  const switched = $derived(stockOutLine(req));
  const words = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
  // One list in Validio's order: what was asked, Valio's substitutes, then
  // what was found beyond Valio's list.
  const options = (l: SupplyRequest["lines"][number]): RankedOption[] => [...l.options, ...(l.substitutes ?? []), ...(l.beyondList ?? [])];
  // A supplier text that talked to AI agents and was set aside.
  const ignored = $derived(
    req.lines.flatMap(options).some((o) => o.supplierText && (o.supplierText.planted || (o.supplierText.reader?.flags ?? []).some((f) => f.code !== "mentions_claim"))),
  );
  // A request that named a product counts in that product's own unit (bags),
  // not the reader's generic "pieces".
  const needUnit = (l: SupplyRequest["lines"][number]) =>
    (l.need.productId && options(l).find((o) => o.productId === l.need.productId)?.unit) || l.need.unit;
</script>

<article class="pane" aria-labelledby="request-title">
  <header class="head">
    <h2 id="request-title">{title}</h2>
    <p class="facts">
      {#if req.totalCents !== undefined}<span class="num strong">{money(req.totalCents)}</span>{/if}
      {#if req.deliverBy}<span>deliver by {day(req.deliverBy)}</span>{/if}
      <span data-testid="request-status" id="request-status">
        {#if asking}<State label={status.label} tone="act" />{:else}<span class:t-bad={status.tone === "bad"}>{status.label}</span>{/if}
      </span>
      {#if req.orderId && !asking}<a href="/ledger">Order {req.orderId}</a>{/if}
    </p>
  </header>

  {#if lead}
    <p class="decision" id="decision-sentence">{lead}</p>
  {:else if !req.decision}
    <p class="decision t-quiet" id="decision-sentence">Validio is still checking this request.</p>
  {/if}
  {#if switched}
    <p class="aside t-quiet" id="simulated-stock-out" data-testid="stock-out-note">{switched}</p>
  {:else if ignored}
    <p class="aside t-quiet" id="ignored-note">Ignored a product description that told AI agents to buy it.</p>
  {/if}

  {#if asking}
    <div><Button href="/approve/{req.id}" id="open-approve" data-testid="open-approve">Open the approval</Button></div>
    <Collapsible.Root>
      <Collapsible.Trigger class="fold" id="fold-details">
        <Collapsible.Chevron />
        Why this product
      </Collapsible.Trigger>
      <Collapsible.Content forceMount>
        {#snippet child({ props, open })}
          <div {...props} hidden={!open} class="details" id="details">
            {@render why()}
          </div>
        {/snippet}
      </Collapsible.Content>
    </Collapsible.Root>
  {:else}
    <p class="aside"><a href="/ledger" id="see-record">See the record</a></p>
    <!-- A finished request shows no details; its options stay in the page,
         unseen, for the record link and the suites. -->
    <div hidden id="details">{@render why()}</div>
  {/if}

  <!-- What the record holds and the pane does not show: the live check, how
       the request was read, notes and the rule. Kept for the suites. -->
  <div hidden class="record">
    {#if live}<span id="live-checked" data-testid="live-checked">Checked {words(live.ids, "product", "products")} live at Valio.</span>{/if}
    {#each req.lines as l (l.lineId)}
      {#if l.need}<span>Read as {amount(l.need.quantity, needUnit(l))} of {l.need.what}{#if l.need.diet.length}, {l.need.diet.join(", ")}{/if}.</span>{/if}
      {#if l.note}<span>{prose(l.note)}</span>{/if}
    {/each}
    {#if req.decision?.ruleIds.length}<span>Rule <span data-testid="request-rule">{req.decision.ruleIds.join(", ")}</span>.</span>{/if}
  </div>
</article>

{#snippet why()}
  {#each req.lines as l (l.lineId)}
    {#if req.lines.length > 1}<h3 class="line-title">{prose(l.text)}</h3>{/if}
    <OptionList options={options(l)} label="Options for {prose(l.text)}" />
  {/each}
  {#if pass}
    <p class="pass" data-testid="spend-pass" id="spend-pass">
      Inside Spend Pass {pass.id}:
      {#if pass.autoLimitCents !== undefined}alone up to <span class="num" data-testid="pass-auto">{money(pass.autoLimitCents)}</span>{/if}{#if pass.hardCapCents !== undefined}, never above <span class="num" data-testid="pass-cap">{money(pass.hardCapCents)}</span>{/if}.
      <a href="/spend-pass">Open the Spend Pass</a>
    </p>
  {/if}
{/snippet}

<style>
  .pane {
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
    max-width: var(--frame-width);
    padding: var(--frame-pad-top) var(--frame-pad-x) 4rem;
  }
  .head {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  h2 {
    margin: 0;
    font-size: var(--text-xl);
    font-weight: 600;
    line-height: 1.25;
    letter-spacing: -0.01em;
    text-wrap: balance;
  }
  .facts {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.25rem 1.25rem;
    margin: 0;
    font-size: var(--text-sm);
    color: var(--color-fg-secondary);
  }
  .facts .strong {
    font-weight: 500;
    color: var(--color-fg-primary);
  }
  .facts a,
  .pass a {
    color: inherit;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .decision {
    margin: 0;
    max-width: 60ch;
    font-size: var(--text-base);
  }
  .pane :global(.fold#fold-details) {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    min-height: 2rem;
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--color-fg-secondary);
  }
  .details {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    padding: 0.75rem 0 0 1.25rem;
  }
  .aside {
    margin: 0;
    max-width: 62ch;
    font-size: var(--text-sm);
  }
  .aside a {
    color: inherit;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .line-title {
    margin: 0;
    font-size: var(--text-sm);
    font-weight: 600;
  }
  .pass {
    margin: 0;
    font-size: var(--text-sm);
  }
</style>
