<script lang="ts">
  // The authority the kitchen gave its agent, laid out as Arlen settings lays
  // out an app's access: what it may do, the value, and whether the agent
  // showed it to Validio. One chart: where each request fell on the scale.
  import { Page } from "@arlen/ui-kit/components/ui/page";
  import { Row } from "@arlen/ui-kit/components/ui/row";
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { SectionGrid } from "@arlen/ui-kit/components/ui/section-grid";
  import { api } from "$lib/api/client";
  import { setChrome } from "$lib/chrome.svelte";
  import { day, dayTime, money } from "$lib/format";
  import { live } from "$lib/live.svelte";
  import Info from "$lib/components/Info.svelte";
  import State from "$lib/components/State.svelte";

  setChrome("Spend Pass");
  const pass = live(() => api.spendPass("M-1"));
  const inbox = live(() => api.inbox());

  const SUBSTITUTES: Record<string, string> = {
    listed_and_rules_kept: "Valio's listed ones, when every rule holds",
    none: "None",
    any_rules_kept: "Any, when every rule holds",
  };
  const HIDDEN: Record<string, string> = {
    approvers: "Who approves",
    preferLabels: "Preferred labels",
  };

  const shown = (f: string) => !!pass.data?.disclosed.includes(f);
  const requests = $derived((inbox.data ?? []).filter((i) => i.totalCents !== undefined));
</script>

<Page title="Spend Pass" description="What the kitchen lets its agent buy. Validio checks every order against it.">
  <SectionGrid>
  {#if pass.data}
    {@const p = pass.data}
    <div class="who">
      <span class="mono">{p.id}</span>
      <span class="t-quiet">held by</span> <span class="mono">{p.holder}</span>
      <span class="t-quiet">issued by</span> <span class="mono">{p.issuer}</span>
    </div>

    {#if p.autoLimitCents !== undefined && p.hardCapCents !== undefined}
      {@const cap = p.hardCapCents}
      {@const top = cap * 1.15}
      {@const at = (c: number) => `${Math.min(c / top, 1) * 100}%`}
      <figure class="scale" id="spend-scale">
        <div class="track" role="img" aria-label="Requests on the Spend Pass scale: {requests.map((r) => `${r.id} ${money(r.totalCents)}`).join(', ')}">
          <span class="zone alone" style="width: {at(p.autoLimitCents)}"></span>
          <span class="zone ask" style="left: {at(p.autoLimitCents)}; width: calc({at(cap)} - {at(p.autoLimitCents)})"></span>
          <span class="zone over" style="left: {at(cap)}"></span>
          <span class="tick" style="left: {at(p.autoLimitCents)}"></span>
          <span class="tick cap" style="left: {at(cap)}"></span>
          {#each requests as r (r.id)}
            <span class="pin" style="left: {at(r.totalCents ?? 0)}" title="{r.id} {money(r.totalCents)}">
              <span class="pin-l mono">{r.id}</span>
            </span>
          {/each}
        </div>
        <figcaption class="legend">
          <span>Alone up to <b class="num">{money(p.autoLimitCents)}</b></span>
          <span>Asks you up to <b class="num">{money(cap)}</b></span>
          <span>Blocked above</span>
        </figcaption>
      </figure>
    {/if}

    <Section>
      {#if p.autoLimitCents !== undefined}
        <Row label="Orders alone up to" id="pass-auto">{#snippet control()}{@render value(money(p.autoLimitCents), "autoLimitCents")}{/snippet}</Row>
      {/if}
      {#if p.hardCapCents !== undefined}
        <Row label="Never orders above" id="pass-cap">{#snippet control()}{@render value(money(p.hardCapCents), "hardCapCents")}{/snippet}</Row>
      {/if}
      {#if p.diet?.length}
        <Row label="Diet">{#snippet control()}{@render value(p.diet!.join(", "), "diet")}{/snippet}</Row>
      {/if}
      <Row label="Product groups">{#snippet control()}{@render value(p.categories.join(", "))}{/snippet}</Row>
      {#if p.deliverBy}
        <Row label="Delivered by">{#snippet control()}{@render value(day(p.deliverBy!))}{/snippet}</Row>
      {/if}
      {#if p.substitutes}
        <Row label="Substitutes">{#snippet control()}{@render value(SUBSTITUTES[p.substitutes!] ?? p.substitutes!.replaceAll("_", " "))}{/snippet}</Row>
      {/if}
      <Row label="Splitting a line" description={p.split.allowListedSubstitutes ? "With Valio's listed substitutes" : "Same product only"}>
        {#snippet control()}{@render value(`up to ${p.split.maxExtraCostPct} % more`)}{/snippet}
      </Row>
      <Row label="Valid">{#snippet control()}{@render value(`${dayTime(p.validFrom)} to ${dayTime(p.validTo)}`)}{/snippet}</Row>
    </Section>

    {#if p.hidden.length}
      <div class="kept">
        <h2>
          Kept back from Validio
          <Info
            label="Why some fields stay hidden"
            text="The agent shows Validio only the fields a decision needs. The rest stay sealed in the pass: Validio can tell they exist, not what they say."
          />
        </h2>
        <Section>
          {#each p.hidden as h (h)}
            <Row label={HIDDEN[h] ?? h} id="hidden-{h}">{#snippet control()}<State label="Sealed" tone="quiet" />{/snippet}</Row>
          {/each}
        </Section>
      </div>
    {/if}
  {:else if pass.error}
    <p class="t-quiet">Cannot read the Spend Pass: {pass.error}</p>
  {/if}
  </SectionGrid>
</Page>

{#snippet value(v: string, field?: string)}
  <span class="ctl">
    <span class="v">{v}</span>
    {#if field}<State label={shown(field) ? "Shown" : "Not shown"} tone="quiet" />{/if}
  </span>
{/snippet}

<style>
  .who {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem 0.5rem;
    font-size: var(--text-xs);
  }
  .scale {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    margin: 0;
    padding-top: 1.4rem;
  }
  .track {
    position: relative;
    height: 0.5rem;
    border-radius: var(--radius-full);
    overflow: visible;
  }
  .zone {
    position: absolute;
    top: 0;
    bottom: 0;
  }
  .zone.alone {
    left: 0;
    border-radius: var(--radius-full) 0 0 var(--radius-full);
    background: color-mix(in srgb, var(--color-success) 55%, transparent);
  }
  .zone.ask {
    background: color-mix(in srgb, var(--color-fg-primary) 18%, transparent);
  }
  .zone.over {
    right: 0;
    border-radius: 0 var(--radius-full) var(--radius-full) 0;
    background: color-mix(in srgb, var(--destructive-on-tint) 45%, transparent);
  }
  .tick {
    position: absolute;
    top: -3px;
    bottom: -3px;
    width: 2px;
    margin-left: -1px;
    background: var(--color-fg-secondary);
  }
  .pin {
    position: absolute;
    top: 50%;
    width: 0.75rem;
    height: 0.75rem;
    margin: -0.375rem 0 0 -0.375rem;
    border-radius: 50%;
    background: var(--color-fg-primary);
    border: 2px solid var(--color-bg-app);
  }
  .pin-l {
    position: absolute;
    bottom: 100%;
    left: 50%;
    translate: -50% -0.2rem;
    white-space: nowrap;
    font-size: var(--text-2xs);
    color: var(--color-fg-secondary);
  }
  .legend {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    font-size: var(--text-xs);
    color: var(--color-fg-secondary);
  }
  .legend b {
    font-weight: 500;
    color: var(--color-fg-primary);
  }
  .ctl {
    display: inline-flex;
    align-items: center;
    gap: 0.75rem;
  }
  .v {
    font-size: var(--text-sm);
    font-weight: 500;
    text-align: end;
  }
  .kept {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }
  .kept h2 {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    margin: 0;
    font-size: var(--text-sm);
    font-weight: 600;
  }
  @media (max-width: 760px) {
    .legend {
      flex-direction: column;
      gap: 0.15rem;
    }
  }
</style>
