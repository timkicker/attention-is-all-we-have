<script lang="ts">
  /// Rules: Money, Diet and allergens, Substitutes, each value once, and Edit.
  /// No summary sentence on top: it said every value a second time. After a
  /// save (/rules?saved) a quiet line says the agent follows them now.
  import { page } from "$app/state";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Notice } from "@arlen/ui-kit/components/ui/notice";
  import { agentApi } from "$lib/api/agent";
  import { dayTime, Empty, ListRow, ListSection, live, Loading, LoadError, money, PageHead } from "$lib/v2";
  import { allowedOf, extraText, list, upTo } from "./rules";

  const data = live(async () => {
    const [rules, agent] = await Promise.all([agentApi.rules(), agentApi.agent().catch(() => null)]);
    // The version's date, when the agent's history knows it.
    const since = agent?.versions.find((v) => v.version === rules.passVersion)?.at ?? null;
    return { rules, since };
  });
  const r = $derived(data.data?.rules);
  const saved = $derived(page.url.searchParams.has("saved"));
</script>

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

<div class="blocks">
  {#if data.error && !data.data}
    <LoadError detail={data.error} />
  {:else if !r}
    <Loading rows={4} />
  {:else if !r.saved}
    <Empty title="No rules yet" detail="Until you set them, every order waits for you." />
  {:else}
    {#if saved}
      <Notice id="rules-saved" text="Saved. Your agent follows these rules from its next order." />
    {/if}
    <ListSection id="money" title="Money, before VAT">
      <ListRow id="rule-alone" label="Ordered automatically" value={upTo(r.aloneUpToCents)} />
      <ListRow id="rule-waiting" label="Waiting for you" value={upTo(r.approvalUpToCents)} />
      <ListRow id="rule-blocked" label="Blocked" value="Above {money(r.approvalUpToCents)}" />
      <ListRow id="rule-week" label="Per week" value={r.perWeekCents == null ? "No limit" : upTo(r.perWeekCents)} />
    </ListSection>
    <ListSection id="diet" title="Diet and allergens">
      <ListRow id="rule-must" label="Must be" value={r.diet?.mustBe.length ? list(r.diet.mustBe) : "Anything"} />
      <ListRow id="rule-never" label="Never" value={r.diet?.never.length ? list(r.diet.never) : "None"} />
    </ListSection>
    <ListSection id="substitutes" title="Substitutes">
      {#if allowedOf(r) === "off"}
        <ListRow id="rule-allowed" label="Allowed" value="Never" />
        <ListRow id="rule-any" label="Any substitute" value="Waiting for you" />
      {:else}
        <ListRow id="rule-allowed" label="Allowed" value="From Valio's list" />
        <ListRow id="rule-extra" label="Extra cost" value={extraText(r.maxExtraPct)} />
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
</style>
