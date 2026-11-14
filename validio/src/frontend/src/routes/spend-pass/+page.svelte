<script lang="ts">
  /// The Spend Pass as a halbat record: facts, one Limits lane, a card of
  /// value rows; what the agent sees is one item in the facts line.
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import * as Popover from "@arlen/ui-kit/components/ui/popover";
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { Info } from "@lucide/svelte";
  import { api } from "$lib/api/client";
  import { CLOCK, day, money } from "$lib/format";
  import { live } from "$lib/live.svelte";
  import VHead from "$lib/v/VHead.svelte";
  import VLane from "$lib/v/VLane.svelte";
  import VPill from "$lib/v/VPill.svelte";
  import VPlotTotal from "$lib/v/VPlotTotal.svelte";
  import VState from "$lib/v/VState.svelte";
  import VValueRow from "$lib/v/VValueRow.svelte";

  const pass = live(() => api.spendPass("M-1"));
  const p = $derived(pass.data);
  const used = $derived(p?.usedCents ?? 0);
  const valid = $derived(!!p && new Date(p.validTo) > new Date(CLOCK) && new Date(p.validFrom) <= new Date(CLOCK));
  const left = $derived(p?.autoLimitCents !== undefined ? p.autoLimitCents - used : undefined);
  const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
</script>

{#if !p}
  <VHead title="Spend Pass" />
  {#if pass.error}
    <VState kind="error" title="Validio is not reachable." detail={pass.error} onretry={() => location.reload()} />
  {:else}
    <VState kind="loading" rows={3} />
  {/if}
{:else}
  <VHead title="Spend Pass">
    {#snippet facts()}
      <VPill label={valid ? "Valid" : "Expired"} tone={valid ? "ok" : "neutral"} />
      <span>Signed by you</span>
      <span data-testid="pass-approvers" id="pass-approvers">Agent sees limits and diet, not approvers</span>
      <span>{day(p.validFrom)} to <span data-testid="pass-valid-to" id="pass-valid-to">{day(p.validTo)}</span></span>
    {/snippet}
  </VHead>

  <div class="blocks">
    <div>
      <VLane
        name="Limits"
        value="{money(used)} used"
        sub={left === undefined ? undefined : left >= 0 ? `${money(left)} left to order alone` : "Over the alone limit, so Validio asks you"}
      >
        {#snippet plot()}
          <VPlotTotal pass amount={used} auto={p.autoLimitCents} cap={p.hardCapCents} />
        {/snippet}
      </VLane>
    </div>

    <Section class="v-card">
      {#if p.diet?.length}<VValueRow label="Diet" value={cap(p.diet.join(", "))} testid="pass-diet" />{/if}
      <VValueRow label="Deliver by" value={day(p.deliverBy)} testid="pass-deliver-by" />
      <VValueRow
        label="Substitutes"
        value="{p.split.allowListedSubstitutes ? "From Valio's list" : 'None'}, up to {p.split.maxExtraCostPct} % extra"
      />
      <VValueRow label="Product groups">
        {p.categories.length}
        <Popover.Root>
          <Popover.Trigger>
            {#snippet child({ props })}
              <Button {...props} variant="ghost" size="icon-sm" aria-label="Which product groups" class="info-btn"><Info /></Button>
            {/snippet}
          </Popover.Trigger>
          <Popover.Content class="v-pop">{p.categories.join(", ")}</Popover.Content>
        </Popover.Root>
      </VValueRow>
    </Section>
  </div>
{/if}

<style>
  :global(.info-btn) {
    vertical-align: middle;
    margin-left: 4px;
    color: var(--v-faint);
  }
  :global(.v-pop) {
    width: 260px;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
  }
  @media (max-width: 760px) {
    :global(.info-btn) {
      width: 44px;
      height: 44px;
    }
  }
</style>
