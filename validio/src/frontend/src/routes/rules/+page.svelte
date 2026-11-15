<script lang="ts">
  /// Rules: Money, Diet and allergens, Substitutes, each value once, and Edit.
  /// No summary sentence on top: it said every value a second time. After a
  /// save (/rules?saved=alone,week) a quiet line says the agent follows them now,
  /// and the rows that changed glow once (plans/019). The money limits also show
  /// as a scale of zones (plans/010).
  import type { Snippet } from "svelte";
  import { page } from "$app/state";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Notice } from "@arlen/ui-kit/components/ui/notice";
  import { agentApi } from "$lib/api/agent";
  import { rise } from "$lib/motion";
  import { dayTime, Empty, Explain, LimitScale, ListRow, ListSection, live, Loading, LoadError, money, PageHead } from "$lib/v2";
  import { allowedOf, extraText, list, upTo } from "./rules";

  const data = live(
    async () => {
      const [rules, agent] = await Promise.all([agentApi.rules(), agentApi.agent().catch(() => null)]);
      // The version's date, when the agent's history knows it.
      const since = agent?.versions.find((v) => v.version === rules.passVersion)?.at ?? null;
      return { rules, since };
    },
    2000,
    () => "rules",
  );
  const r = $derived(data.data?.rules);
  const saved = $derived(page.url.searchParams.has("saved"));
  const changed = $derived(new Set((page.url.searchParams.get("saved") ?? "").split(",").filter(Boolean)));
</script>

{#snippet glow(key: string, row: Snippet)}<div class:v-glow={changed.has(key)}>{@render row()}</div>{/snippet}

<PageHead title="Rules">
  {#snippet facts()}
    {#if r?.saved}
      <span data-testid="rules-version">Version <b>{r.passVersion}</b>{#if data.data?.since}, since {dayTime(data.data.since)}{/if}</span>
    {/if}
  {/snippet}
  {#snippet actions()}
    {#if r}
      <Button variant="outline" href="/rules/edit" id="rules-edit" data-testid="rules-edit">{r.saved ? "Edit" : "Set rules"}</Button>
    {/if}
  {/snippet}
</PageHead>

<div class="blocks" class:v-arrive={data.arrive}>
  {#if data.error && !data.data}
    <LoadError detail={data.error} />
  {:else if !r}
    <Loading rows={4} />
  {:else if !r.saved}
    <Empty title="No rules yet" detail="Until you set them, every order waits for you." />
  {:else}
    {#snippet a()}<ListRow id="rule-alone" label="Ordered alone" value={upTo(r.aloneUpToCents)} />{/snippet}
    {#snippet w()}<ListRow id="rule-waiting" label="Waiting for you" value={upTo(r.approvalUpToCents)} />{/snippet}
    {#snippet wk()}<ListRow id="rule-week" label="Per week" value={r.perWeekCents == null ? "No limit" : upTo(r.perWeekCents)} />{/snippet}
    {#snippet must()}<ListRow id="rule-must" label="Must be" value={r.diet?.mustBe.length ? list(r.diet.mustBe) : "Anything"} />{/snippet}
    {#snippet never()}<ListRow id="rule-never" label="Never" value={r.diet?.never.length ? list(r.diet.never) : "None"} />{/snippet}
    {#snippet off()}<ListRow id="rule-allowed" label="Allowed" value="Never" />{/snippet}
    {#snippet listed()}<ListRow id="rule-allowed" label="Allowed" value="From Valio's list" />{/snippet}
    {#snippet extra()}<ListRow id="rule-extra" label="Extra cost" value={extraText(r.maxExtraPct)} />{/snippet}
    {#if saved}
      <div in:rise={{ y: 6, duration: 260 }}>
        <Notice id="rules-saved" text="Saved. Your agent follows these rules from its next order." />
      </div>
    {/if}
    <section class="money">
      <div class="m-head">
        <h2 class="v-h" id="h-money">Money, before VAT</h2>
        <Explain label="What before VAT means">Limits count Valio's catalog prices before VAT.</Explain>
      </div>
      <div class="scale"><LimitScale mode="read" alone={r.aloneUpToCents} waiting={r.approvalUpToCents} id="rules-scale" /></div>
      <ListSection id="money">
        
        {@render glow("alone", a)}
        {@render glow("waiting", w)}
        <ListRow id="rule-blocked" label="Blocked" value="Above {money(r.approvalUpToCents)}" />
        {@render glow("week", wk)}
      </ListSection>
    </section>
    <ListSection id="diet" title="Diet and allergens">
      
      {@render glow("must", must)}
      {@render glow("never", never)}
    </ListSection>
    <ListSection id="substitutes" title="Substitutes">
      {#if allowedOf(r) === "off"}
        {@render glow("allowed", off)}
        <ListRow id="rule-any" label="Any substitute" value="Waiting for you" />
      {:else}
        
        {@render glow("allowed", listed)}
        {@render glow("extra", extra)}
        <ListRow id="rule-unlisted" label="Not on the list" value="Waiting for you" />
      {/if}
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
  .money {
    display: flex;
    flex-direction: column;
  }
  .m-head {
    display: flex;
    align-items: baseline;
    gap: 4px;
  }
  .m-head .v-h {
    margin-bottom: 0;
  }
  .scale {
    padding: 4px 0 20px;
    max-width: 640px;
  }
</style>
