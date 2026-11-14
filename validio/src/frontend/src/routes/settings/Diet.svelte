<script lang="ts">
  /// Diet and allergens: one switch per diet. Saving signs the agent's pass
  /// again, so it asks for the approval code first.
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { Switch } from "@arlen/ui-kit/components/ui/switch";
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
    <div class="sw-line">
      <span class="lbl" id="diet-{d.id}">{d.label}</span>
      <span class="sw"><Switch ariaLabel={d.label} bind:value={on[d.id]} disabled={asking} /></span>
    </div>
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
    min-height: 56px;
    padding: 12px 16px;
  }
  .lbl {
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    font-weight: 500;
  }
  /* The kit Switch, on in Valio blue, as on the Spend Pass. */
  .sw {
    --color-accent: var(--valio);
    --color-accent-foreground: var(--v-on-valio);
    display: inline-flex;
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
