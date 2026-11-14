<script lang="ts">
  /// The Spend Pass as a halbat record: facts, one Limits lane, a card of
  /// value rows; what the agent sees is one item in the facts line.
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import * as Popover from "@arlen/ui-kit/components/ui/popover";
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { Switch } from "@arlen/ui-kit/components/ui/switch";
  import { Info } from "@lucide/svelte";
  import { Input } from "@arlen/ui-kit/components/ui/input";
  import { api, ApiError, LIVE, needsToken } from "$lib/api/client";
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
  // Problems sit on the field they belong to; `form` is for anything else.
  let bad = $state<{ auto?: string; hard?: string; code?: string; form?: string }>({});
  const f = $state({ auto: "", hard: "", substitutes: true, code: "" });
  const euros = (c: number) => (c / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const cents = (t: string) => (/^\s*[\d,]*\.?\d*\s*$/.test(t) && /\d/.test(t) ? Math.round(Number(t.replace(/[,\s]/g, "")) * 100) : NaN);
  const tidy = (k: "auto" | "hard") => {
    const c = cents(f[k]);
    if (c > 0) f[k] = euros(c);
  };
  function startEdit() {
    if (!p) return;
    f.auto = euros(p.autoLimitCents ?? 0);
    f.hard = euros(p.hardCapCents ?? 0);
    f.substitutes = p.substitutes !== "never";
    f.code = owner.code;
    bad = {};
    editing = true;
  }
  async function save(e: SubmitEvent) {
    e.preventDefault();
    if (!p) return;
    // Diet and date are fixed: Valio's answers are recorded for these only.
    const body: SpendPassIn = {
      autoLimitCents: cents(f.auto),
      hardCapCents: cents(f.hard),
      diet: p.diet?.some((d) => /lactose/i.test(d)) ? ["FREE_FROM_LACTOSE"] : [],
      deliverBy: p.deliverBy?.slice(0, 10) ?? "2026-11-16",
      substitutes: f.substitutes,
    };
    const next: typeof bad = {};
    if (!(body.autoLimitCents > 0)) next.auto = "Type an amount in euros.";
    if (!(body.hardCapCents > 0)) next.hard = "Type an amount in euros.";
    if (codeRequired && !isCode(f.code)) next.code = "Type the 6 digit code.";
    bad = next;
    if (Object.keys(next).length) return;
    if (codeRequired) owner.code = f.code;
    saving = true;
    try {
      await api.signPass(body);
      editing = false;
      bump();
    } catch (err) {
      if (needsToken(err)) return; // the presenter closed the token dialog
      const msg = err instanceof Error ? err.message : String(err);
      if (err instanceof ApiError && err.status === 403) {
        bad = { code: "That code is not right." };
        owner.code = "";
      } else if (err instanceof ApiError && err.status === 422 && /never above/i.test(msg)) bad = { auto: "Must be below never above." };
      else bad = { form: err instanceof ApiError && err.status === 422 ? `${cap(msg)}.` : msg };
    } finally {
      saving = false;
    }
  }
</script>

{#snippet money_field(k: "auto" | "hard", label: string)}
  <span class="money">
    <label for="f-{k}">{label}</label>
    <span class="euro">
      <Input
        id="f-{k}"
        data-testid="f-{k}"
        inputmode="decimal"
        bind:value={f[k]}
        onblur={() => tidy(k)}
        autocomplete="off"
        aria-invalid={bad[k] ? true : undefined}
        aria-describedby={bad[k] ? `f-${k}-problem` : undefined}
      />
      <span class="unit" aria-hidden="true">€</span>
    </span>
    {#if bad[k]}<span class="problem" id="f-{k}-problem" data-testid="f-{k}-problem" role="alert">{bad[k]}</span>{/if}
  </span>
{/snippet}

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
      <span>
        Signed by you
        <Popover.Root>
          <Popover.Trigger>
            {#snippet child({ props })}
              <Button {...props} variant="ghost" size="icon-sm" aria-label="What the agent sees" class="info-btn" id="pass-sees"><Info /></Button>
            {/snippet}
          </Popover.Trigger>
          <Popover.Content class="v-pop"><span data-testid="pass-approvers" id="pass-approvers">Agent sees limits and diet, not approvers.</span></Popover.Content>
        </Popover.Root>
      </span>
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

    {#if editing}
      <form class="limits" data-testid="limits-form" onsubmit={save} novalidate>
        <Section class="v-card">
          <VValueRow label="Limits">
            <span class="money-pair">
              {@render money_field("auto", "Alone up to")}
              {@render money_field("hard", "Never above")}
            </span>
          </VValueRow>
          {#if p.diet?.length}<VValueRow label="Diet" value={cap(p.diet.join(", "))} />{/if}
          <VValueRow label="Deliver by" value={day(p.deliverBy)} sub="Recorded for lactose free and 16 Nov only." />
          <VValueRow label="Substitutes">
            <span class="sw-row">
              <Switch ariaLabel="Substitutes" bind:value={f.substitutes} />
              <span>{f.substitutes ? `From Valio's list, up to ${p.split.maxExtraCostPct} % extra` : "None"}</span>
            </span>
          </VValueRow>
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
        {#if bad.form}<p class="problem" role="alert" data-testid="limits-problem">{bad.form}</p>{/if}
        <!-- The field before the action, labelled as on the approve page: code, Sign again, Cancel. -->
        <div class="sign" class:bad={!!bad.code}>
          {#if codeRequired}<label for="f-code">Approval code</label>{/if}
          <div class="form-buttons">
            {#if codeRequired}
              <Input
                id="f-code"
                data-testid="f-code"
                class="code mono"
                inputmode="numeric"
                maxlength={6}
                bind:value={f.code}
                autocomplete="one-time-code"
                aria-invalid={bad.code ? true : undefined}
                aria-describedby="f-code-help"
              />
            {/if}
            <Button type="submit" data-testid="limits-save" disabled={saving}>Sign again</Button>
            <Button variant="ghost" data-testid="limits-cancel" id="limits-cancel" onclick={() => (editing = false)}>Cancel</Button>
          </div>
          {#if codeRequired}
            {#if bad.code}
              <p class="help" id="f-code-help" data-testid="f-code-problem" role="alert">{bad.code}</p>
            {:else}
              <p class="help" id="f-code-help">{LIVE ? "The 6-digit code you set for approvals." : "Demo: any 6 digits"}</p>
            {/if}
          {/if}
        </div>
      </form>
    {:else}
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
    {/if}
  </div>
{/if}

<style>
  .limits {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .money-pair {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
  }
  .money {
    display: flex;
    flex-direction: column;
    gap: 4px;
    width: 140px;
  }
  .money label {
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  .euro {
    position: relative;
    display: block;
  }
  .euro :global(input) {
    width: 100%;
    text-align: right;
    padding-right: 26px;
    font-variant-numeric: tabular-nums;
  }
  .unit {
    position: absolute;
    right: 10px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--v-muted);
    pointer-events: none;
  }
  .money .problem {
    white-space: nowrap;
  }
  /* The kit Switch, on in Valio blue: its accent comes from the nearest wrapper. */
  .sw-row {
    --color-accent: var(--valio);
    --color-accent-foreground: var(--v-on-valio);
    display: inline-flex;
    align-items: center;
    gap: 10px;
  }
  .problem {
    margin: 0;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-bad-text);
  }
  .form-buttons {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    gap: 8px;
  }
  /* As VCode on the approve page: the same label, field, help line and control height. */
  .sign {
    --height-control: 44px;
    --height-control-prominent: 44px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .sign label {
    font-size: 14px;
    line-height: 20px;
    font-weight: 500;
  }
  .sign :global(.code) {
    max-width: 160px;
    font-size: 16px;
    line-height: 24px;
    font-variant-numeric: tabular-nums;
  }
  .help {
    margin: 0;
    font-size: 14px;
    line-height: 20px;
    color: var(--v-muted);
  }
  .sign.bad .help {
    color: var(--v-bad-text);
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
