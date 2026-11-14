<script lang="ts">
  /// Diet and allergens: one switch per diet. Saving signs the agent's pass
  /// again, so it asks for the approval code first.
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { ApiError } from "$lib/api/client";
  import { bump } from "$lib/chrome.svelte";
  import { isCode, owner } from "$lib/owner.svelte";
  import { DIETS, settingsApi, type Diet, type Settings } from "$lib/settings";
  import VCode from "$lib/v/VCode.svelte";

  let { s, onsaved }: { s: Settings; onsaved: (s: Settings) => void } = $props();

  let on = $state<Record<Diet, boolean>>(Object.fromEntries(DIETS.map((d) => [d.id, s.diet.includes(d.id)])) as Record<Diet, boolean>);
  const picked = $derived(DIETS.filter((d) => on[d.id]).map((d) => d.id));
  const dirty = $derived(picked.join() !== DIETS.filter((d) => s.diet.includes(d.id)).map((d) => d.id).join());
  let asking = $state(false);
  let code = $state("");
  let problem = $state("");
  let form = $state("");
  let saved = $state(false);
  let saving = $state(false);

  function reset() {
    for (const d of DIETS) on[d.id] = s.diet.includes(d.id);
    asking = false;
    problem = form = "";
  }
  function ask() {
    code = owner.code;
    problem = form = "";
    asking = true;
  }
  async function save() {
    if (saving) return;
    if (!isCode(code)) {
      problem = "Type the 6 digit code.";
      return;
    }
    saving = true;
    try {
      const next = await settingsApi.diet(picked, code);
      owner.code = code;
      asking = false;
      saved = true;
      onsaved(next);
      bump();
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        problem = "That code is not right.";
        owner.code = "";
      } else if (err instanceof ApiError && err.status === 429) problem = "Too many wrong codes. Try later.";
      else form = err instanceof Error ? err.message : String(err);
    } finally {
      saving = false;
    }
  }
  $effect(() => {
    if (dirty) saved = false;
  });
</script>

<Section class="v-card">
  {#each DIETS as d (d.id)}
    <!-- The whole row is the switch, as the stock-out row in the page menu: 56 px to tap on the phone. -->
    <button type="button" class="sw-line" role="switch" aria-checked={on[d.id]} disabled={asking} data-testid="diet-{d.id}" onclick={() => (on[d.id] = !on[d.id])}>
      <span class="lbl">{d.label}</span>
      <span class="vsw" class:on={on[d.id]} aria-hidden="true"><span class="thumb"></span></span>
    </button>
  {/each}
</Section>

{#if form}<p class="problem" role="alert">{form}</p>{/if}
{#if asking}
  <div class="code"><VCode bind:value={code} error={problem} onsubmit={save} submitLabel="Save" oncancel={reset} /></div>
{:else if dirty}
  <div class="acts">
    <Button data-testid="diet-save" onclick={ask}>Save</Button>
    <Button variant="ghost" onclick={reset}>Cancel</Button>
  </div>
{:else if saved}
  <p class="saved" role="status" data-testid="diet-saved">Saved</p>
{/if}

<style>
  .sw-line {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    width: 100%;
    min-height: 56px;
    padding: 12px 16px;
    margin: 0;
    border: 0;
    background: none;
    font: inherit;
    color: var(--v-fg);
    text-align: left;
    cursor: pointer;
    transition: background-color var(--duration-fast) ease;
  }
  .sw-line + .sw-line {
    border-top: 1px solid var(--v-line);
  }
  .sw-line:hover:not(:disabled) {
    background: var(--v-tint-hover);
  }
  .sw-line:first-child {
    border-start-start-radius: max(0px, calc(var(--radius-card) - 1px));
    border-start-end-radius: max(0px, calc(var(--radius-card) - 1px));
  }
  .sw-line:last-child {
    border-end-start-radius: max(0px, calc(var(--radius-card) - 1px));
    border-end-end-radius: max(0px, calc(var(--radius-card) - 1px));
  }
  .sw-line:disabled {
    cursor: default;
  }
  .sw-line:disabled .vsw {
    opacity: 0.5;
  }
  .lbl {
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    font-weight: 500;
  }
  /* The kit Switch's look, on in Valio blue (as VMenu's stock-out row). */
  .vsw {
    position: relative;
    width: 32px;
    height: 18px;
    flex-shrink: 0;
    border-radius: var(--radius-input);
    border: 1px solid var(--control-border);
    background: var(--control-bg-strong);
  }
  .vsw .thumb {
    position: absolute;
    top: 1px;
    left: 1px;
    width: 14px;
    height: 14px;
    border-radius: max(0px, calc(var(--radius-input) - 2px));
    background: var(--foreground);
    box-shadow: var(--v-shadow-thumb);
    transition: transform var(--duration-fast) ease;
  }
  .vsw.on {
    background: var(--valio);
    border-color: var(--valio);
  }
  .vsw.on .thumb {
    background: var(--v-on-valio);
    transform: translateX(14px);
  }
  .acts {
    display: flex;
    gap: 8px;
    margin-top: 16px;
  }
  .code {
    margin-top: 16px;
  }
  .saved,
  .problem {
    margin: 16px 0 0;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  .problem {
    color: var(--v-bad-text);
  }
</style>
