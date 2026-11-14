<script lang="ts">
  /// One steady order as halbat's admin overview: "Open", "Not ordered" and
  /// "Renewed" cards of status rows; before renewal one "This week" card.
  /// The blocked mozzarella line is halbat's alert row with a spark.
  import { tick } from "svelte";
  import { page } from "$app/state";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { ChevronRight } from "@lucide/svelte";
  import { ApiError, api } from "$lib/api/client";
  import type { SteadyLine, SteadyOrder } from "$lib/api/types";
  import { bump, chrome } from "$lib/chrome.svelte";
  import { money } from "$lib/format";
  import { live } from "$lib/live.svelte";
  import { isCode, owner } from "$lib/owner.svelte";
  import type { Pill } from "$lib/v";
  import VCode from "$lib/v/VCode.svelte";
  import VHead from "$lib/v/VHead.svelte";
  import VSpark from "$lib/v/VSpark.svelte";
  import VState from "$lib/v/VState.svelte";
  import VStatusRow from "$lib/v/VStatusRow.svelte";

  const id = $derived(page.params.id ?? "");
  const steady = live(() => api.steadyOrder(id));
  const demo = live(() => api.demoState());
  const s = $derived(steady.data?.id === id ? steady.data : undefined);

  // A write that waits for the code: which one, and what it runs.
  let asking = $state<null | { key: string; label: string; run: () => Promise<SteadyOrder> }>(null);
  let code = $state("");
  let wrong = $state("");
  let busy = $state("");
  let problem = $state("");

  async function write(key: string, label: string, run: () => Promise<SteadyOrder>) {
    problem = "";
    if (demo.data?.codeRequired && !isCode(owner.code)) {
      wrong = "";
      asking = { key, label, run };
      return;
    }
    busy = key;
    try {
      steady.data = await run();
      asking = null;
      bump();
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) {
        owner.code = "";
        wrong = "Wrong code. Try again.";
        asking = { key, label, run };
      } else problem = e instanceof Error ? e.message : String(e);
    } finally {
      busy = "";
    }
  }
  async function submitCode() {
    if (!asking) return;
    if (!isCode(code)) {
      wrong = "Wrong code. Try again.";
      return;
    }
    owner.code = code;
    const a = asking;
    await write(a.key, a.label, a.run);
    await tick();
  }

  const pending = $derived(!!s && s.lines.every((l) => l.result === "pending"));
  const open = $derived((s?.lines ?? []).filter((l) => l.result === "waiting" || l.result === "flagged"));
  const notOrdered = $derived((s?.lines ?? []).filter((l) => l.result === "blocked"));
  const renewed = $derived((s?.lines ?? []).filter((l) => ["renewed", "split_renewed", "accepted"].includes(l.result)));

  const pillOf = (l: SteadyLine): Pill =>
    l.result === "waiting" || l.result === "flagged"
      ? { label: "Short", tone: "wait" }
      : l.result === "blocked"
        ? { label: "Blocked", tone: "neutral" }
        : l.result === "accepted"
          ? { label: "Accepted", tone: "ok" }
          : { label: "Renewed", tone: "ok" };
</script>

{#snippet codeFor(key: string)}
  {#if asking?.key === key}
    <div class="code-slot"><VCode bind:value={code} error={wrong} onsubmit={submitCode} submitLabel={asking.label} oncancel={() => (asking = null)} /></div>
  {/if}
{/snippet}

{#snippet acceptBtn(l: SteadyLine)}
  <Button variant="outline" data-testid="accept-{l.productId}" id="accept-{l.productId}" disabled={!!busy} onclick={() => write(`accept-${l.productId}`, l.acceptLabel ?? "Order now", () => api.acceptLine(id, l.productId))}>
    {l.acceptLabel ?? `Order ${l.thisWeekQuantity ?? ""} now`}
  </Button>
{/snippet}

{#snippet amountAct(l: SteadyLine, act: boolean)}
  <span class="amt num">{l.moneyText ?? money(l.totalCents)}</span>
  <span class="act">{#if act && !chrome.phone}{@render acceptBtn(l)}{/if}</span>
{/snippet}

{#if !s}
  {#if steady.error}
    <VHead title="Steady order" crumbs={[{ href: "/steady", label: "Steady orders" }]} here={id} back={{ href: "/steady", label: "Steady orders" }} />
    <VState kind="error" title={/404|not found/i.test(steady.error) ? `No Steady Order ${id}.` : "Validio is not reachable."} detail={steady.error} onretry={() => location.reload()} />
  {:else}
    <VState kind="loading" rows={4} />
  {/if}
{:else}
  <VHead title={s.name} crumbs={[{ href: "/steady", label: "Steady orders" }]} here={s.id} back={{ href: "/steady", label: "Steady orders" }}>
    {#snippet actions()}
      {#if pending}
        <Button data-testid="renew" id="renew" disabled={!!busy} onclick={() => write("renew", "Renew now", () => api.renew(id))}>Renew now</Button>
      {/if}
    {/snippet}
    {#snippet facts()}
      {#if !pending && s.steadyPass}<span><b class="num">{money(s.steadyPass.usedCents)}</b> ordered</span>{/if}
      <span>{s.guestsPerWeek} guests a week</span>
      {#if pending}<span>{s.lines.length} lines</span>{/if}
      {#if s.simulatedHistory}<span data-testid="simulated-history" id="simulated-history">History of {s.weeksLearned} weeks, simulated</span>{/if}
    {/snippet}
  </VHead>
  <div class="renew-code">{@render codeFor("renew")}</div>
  {#if problem}<p class="q-sub" role="alert">{problem}</p>{/if}

  <div class="blocks">
    {#if pending}
      <section class="sec" aria-labelledby="h-week">
        <h2 class="v-h" id="h-week">This week <em>{s.lines.length}</em></h2>
        <Section class="v-card">
          {#each s.lines as l (l.productId)}
            <VStatusRow testid="line-{l.productId}" id="line-{l.productId}" title={l.displayName ?? l.name} end="usual {l.usualQtyText ?? l.usualQuantity}" />
          {/each}
        </Section>
      </section>
    {:else}
      {#if open.length}
        <section class="sec" aria-labelledby="h-open">
          <h2 class="v-h" id="h-open">Open <em>{open.length}</em></h2>
          <Section class="v-card">
            {#each open as l (l.productId)}
              <div class="line" data-testid="line-{l.productId}" id="line-{l.productId}">
                <VStatusRow pill={pillOf(l)} title={l.displayName ?? l.name} sub={l.flags[0]?.sentence ?? l.sentence}>
                  {#snippet middle()}
                    {#if l.history?.length}<VSpark values={l.history} usual={l.usualQuantity} unit={l.unit} />{/if}
                  {/snippet}
                  {#snippet more()}
                    <details class="fold">
                      <summary><ChevronRight class="chev" aria-hidden="true" />Why no substitute</summary>
                      <div class="fold-body"><p>{l.fullName ?? l.name}, product {l.productId}.</p><p>{l.sentence}</p></div>
                    </details>
                  {/snippet}
                  {#snippet right()}{@render amountAct(l, true)}{/snippet}
                </VStatusRow>
                {#if chrome.phone}<div class="phone-act">{@render acceptBtn(l)}</div>{/if}
                {@render codeFor(`accept-${l.productId}`)}
              </div>
            {/each}
          </Section>
        </section>
      {/if}
      {#if notOrdered.length}
        <section class="sec" aria-labelledby="h-not">
          <h2 class="v-h" id="h-not">Not ordered <em>{notOrdered.length}</em></h2>
          <Section class="v-card">
            {#each notOrdered as l (l.productId)}
              <div class="line" data-testid="line-{l.productId}" id="line-{l.productId}">
                <VStatusRow pill={pillOf(l)} title={l.displayName ?? l.name} sub={l.sentence}>
                  {#snippet middle()}
                    {#if l.history?.length}<VSpark values={l.history} usual={l.usualQuantity} unit={l.unit} />{/if}
                  {/snippet}
                  {#snippet more()}<span class="v-row-sub">Order it from Valio directly or wait for next Monday.</span>{/snippet}
                  {#snippet right()}<span class="act"></span>{/snippet}
                </VStatusRow>
              </div>
            {/each}
          </Section>
        </section>
      {/if}
      {#if renewed.length}
        <section class="sec" aria-labelledby="h-renewed">
          <h2 class="v-h" id="h-renewed">Ordered <em>{renewed.length}</em></h2>
          <Section class="v-card">
            {#each renewed as l (l.productId)}
              <div class="line" data-testid="line-{l.productId}" id="line-{l.productId}">
                <VStatusRow pill={pillOf(l)} title={l.displayName ?? l.name} sub={l.split ? l.flags[0]?.sentence : undefined}>
                  {#snippet middle()}<span class="qty num">{l.qtyText}</span>{/snippet}
                  {#snippet more()}
                    {#if l.split}
                      <details class="fold">
                        <summary><ChevronRight class="chev" aria-hidden="true" />Swap</summary>
                        <div class="fold-body">
                          {#each l.split.parts as p (p.productId)}<p>{p.qtyText} {p.fullName ?? p.name}, product {p.productId}, {p.moneyText}.</p>{/each}
                          <p>{money(l.split.extraCostCents)} ({l.split.extraCostPct} %) more than the usual line.</p>
                        </div>
                      </details>
                    {/if}
                  {/snippet}
                  {#snippet right()}{@render amountAct(l, false)}{/snippet}
                </VStatusRow>
              </div>
            {/each}
          </Section>
        </section>
      {/if}
    {/if}
  </div>
{/if}

<style>
  .act {
    display: inline-flex;
    justify-content: flex-end;
    width: 144px;
  }
  .qty {
    display: inline-block;
    min-width: 120px;
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    color: var(--v-muted);
  }
  .code-slot {
    padding: 0 16px 16px 172px;
  }
  .renew-code .code-slot {
    padding: 16px 0 0;
  }
  .line :global(.v-row-mid) {
    margin-right: 24px;
  }
  @media (max-width: 760px) {
    .act {
      width: auto;
    }
    .act:empty {
      display: none;
    }
    .code-slot {
      padding: 0 16px 16px;
    }
    .phone-act {
      padding: 0 16px 16px;
    }
    .phone-act :global([data-slot="button"]) {
      width: 100%;
      height: 44px;
    }
    .line :global(.v-row-end) {
      flex-wrap: wrap;
    }
  }
</style>
