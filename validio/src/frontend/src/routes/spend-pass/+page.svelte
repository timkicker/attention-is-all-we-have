<script lang="ts">
  /// The Spend Pass as a halbat record: facts, one Limits lane, a card of
  /// value rows; what the agent sees is one item in the facts line.
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import * as Popover from "@arlen/ui-kit/components/ui/popover";
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { Info } from "@lucide/svelte";
  import { Input } from "@arlen/ui-kit/components/ui/input";
  import { ApiError, api } from "$lib/api/client";
  import type { SpendPassIn } from "$lib/api/types";
  import { bump } from "$lib/chrome.svelte";
  import { isCode, owner } from "$lib/owner.svelte";
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

  // "Change limits": the owner signs M-1 again. Same id, so the week's spend
  // still counts; the agent's older copy is refused from then on.
  const demo = live(() => api.demoState());
  const codeRequired = $derived(!!demo.data?.codeRequired);
  let editing = $state(false);
  let saving = $state(false);
  let formProblem = $state("");
  const f = $state({ auto: "", hard: "", lactose: true, deliverBy: "2026-11-16", substitutes: true, code: "" });
  const euros = (c: number) => (c / 100).toFixed(2);
  const cents = (t: string) => Math.round(Number(t.replace(/[^\d.]/g, "")) * 100);
  function startEdit() {
    if (!p) return;
    f.auto = euros(p.autoLimitCents ?? 0);
    f.hard = euros(p.hardCapCents ?? 0);
    f.lactose = p.diet?.some((d) => /lactose/i.test(d)) ?? true;
    f.deliverBy = p.deliverBy?.slice(0, 10) ?? "2026-11-16";
    f.substitutes = p.substitutes !== "never";
    f.code = owner.code;
    formProblem = "";
    editing = true;
  }
  async function save(e: SubmitEvent) {
    e.preventDefault();
    const body: SpendPassIn = {
      autoLimitCents: cents(f.auto),
      hardCapCents: cents(f.hard),
      diet: f.lactose ? ["FREE_FROM_LACTOSE"] : [],
      deliverBy: f.deliverBy,
      substitutes: f.substitutes,
    };
    if (!(body.autoLimitCents > 0) || !(body.hardCapCents > 0)) {
      formProblem = "Type both limits in euros, for example 1200.";
      return;
    }
    if (codeRequired) {
      if (!isCode(f.code)) {
        formProblem = "Type the 6 digit approval code.";
        return;
      }
      owner.code = f.code;
    }
    saving = true;
    formProblem = "";
    try {
      await api.signPass(body);
      editing = false;
      bump();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      formProblem = err instanceof ApiError && err.status === 403 ? "That approval code is not right." : err instanceof ApiError && err.status === 422 ? `${cap(msg)}.` : msg;
      if (err instanceof ApiError && err.status === 403) owner.code = "";
    } finally {
      saving = false;
    }
  }
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
    {#snippet actions()}
      {#if !editing}<Button variant="outline" data-testid="change-limits" id="change-limits" onclick={startEdit}>Change limits</Button>{/if}
    {/snippet}
    {#snippet facts()}
      <VPill label={valid ? "Valid" : "Expired"} tone={valid ? "ok" : "neutral"} />
      <span>Signed by you</span>
      <span data-testid="pass-approvers" id="pass-approvers">Agent sees limits and diet, not approvers</span>
      <span>{day(p.validFrom)} to <span data-testid="pass-valid-to" id="pass-valid-to">{day(p.validTo)}</span></span>
    {/snippet}
  </VHead>

  <div class="blocks">
    {#if editing}
      <form class="limits" data-testid="limits-form" onsubmit={save}>
        <Section class="v-card">
          <div class="field">
            <label for="f-auto">Orders alone up to, €</label>
            <Input id="f-auto" data-testid="f-auto" inputmode="decimal" bind:value={f.auto} autocomplete="off" />
          </div>
          <div class="field">
            <label for="f-hard">Never above, €</label>
            <Input id="f-hard" data-testid="f-hard" inputmode="decimal" bind:value={f.hard} autocomplete="off" />
          </div>
          <div class="field">
            <label class="check"><input type="checkbox" id="f-lactose" bind:checked={f.lactose} /> Lactose free</label>
            <p class="hint">Valio's answers are recorded for lactose-free only.</p>
          </div>
          <div class="field">
            <label for="f-deliver">Deliver by</label>
            <Input id="f-deliver" type="date" bind:value={f.deliverBy} />
            <p class="hint">Recorded for 16 Nov only.</p>
          </div>
          <div class="field">
            <label class="check"><input type="checkbox" id="f-subs" bind:checked={f.substitutes} /> Substitutes from Valio's list</label>
          </div>
          {#if codeRequired}
            <div class="field">
              <label for="f-code">Approval code</label>
              <Input id="f-code" data-testid="f-code" inputmode="numeric" maxlength={6} bind:value={f.code} autocomplete="one-time-code" />
            </div>
          {/if}
        </Section>
        {#if formProblem}<p class="problem" role="alert" data-testid="limits-problem">{formProblem}</p>{/if}
        <div class="form-buttons">
          <Button variant="outline" onclick={() => (editing = false)}>Cancel</Button>
          <Button type="submit" data-testid="limits-save" disabled={saving}>Sign again</Button>
        </div>
      </form>
    {/if}
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
  .limits {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 12px 16px;
    border-bottom: 1px solid var(--v-line);
  }
  .field:last-child {
    border-bottom: 0;
  }
  .field label {
    font-size: var(--fs-meta);
    color: var(--v-fg);
  }
  .field :global(input:not([type="checkbox"])) {
    max-width: 320px;
  }
  .field .check {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: var(--fs-body);
  }
  .field :global(input[type="checkbox"]) {
    width: 18px;
    height: 18px;
    accent-color: var(--v-fg);
  }
  .hint,
  .problem {
    margin: 0;
    font-size: var(--fs-meta);
    color: var(--v-muted);
  }
  .problem {
    color: var(--v-bad-text);
  }
  .form-buttons {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
  }
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
