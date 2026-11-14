<script lang="ts">
  /// Theme: System follows the device, Light and Dark stay. One row each,
  /// as the theme choice in the page menu's sheet.
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { Check } from "@lucide/svelte";
  import { setMode, theme, type Mode } from "$lib/theme.svelte";

  const MODES: { id: Mode; label: string }[] = [
    { id: "system", label: "System" },
    { id: "light", label: "Light" },
    { id: "dark", label: "Dark" },
  ];

  // A radio group is one tab stop; the arrows move the choice (WAI-ARIA radio).
  function arrows(e: KeyboardEvent) {
    const step = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[e.key];
    if (step === undefined) return;
    e.preventDefault();
    const next = (MODES.findIndex((m) => m.id === theme.mode) + step + MODES.length) % MODES.length;
    setMode(MODES[next].id);
    (e.currentTarget as HTMLElement).querySelectorAll<HTMLElement>('[role="radio"]')[next]?.focus();
  }
</script>

<Section class="v-card">
  <div class="group" role="radiogroup" aria-label="Theme" tabindex="-1" onkeydown={arrows} data-testid="theme">
    {#each MODES as m (m.id)}
      <button
        type="button"
        class="opt"
        role="radio"
        aria-checked={theme.mode === m.id}
        tabindex={theme.mode === m.id ? 0 : -1}
        data-testid="theme-{m.id}"
        onclick={() => setMode(m.id)}
      >
        <span>{m.label}</span>
        {#if theme.mode === m.id}<Check size={16} strokeWidth={1.75} aria-hidden="true" />{/if}
      </button>
    {/each}
  </div>
</Section>

<style>
  .group {
    display: flex;
    flex-direction: column;
  }
  .opt {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    min-height: 56px;
    padding: 12px 16px;
    margin: 0;
    border: 0;
    background: none;
    font: inherit;
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    font-weight: 500;
    color: var(--v-fg);
    text-align: left;
    cursor: pointer;
    transition: background-color var(--duration-fast) ease;
  }
  .opt + .opt {
    border-top: 1px solid var(--v-line);
  }
  .opt:hover {
    background: var(--v-tint-hover);
  }
  .opt:first-child {
    border-start-start-radius: max(0px, calc(var(--radius-card) - 1px));
    border-start-end-radius: max(0px, calc(var(--radius-card) - 1px));
  }
  .opt:last-child {
    border-end-start-radius: max(0px, calc(var(--radius-card) - 1px));
    border-end-end-radius: max(0px, calc(var(--radius-card) - 1px));
  }
  .opt :global(svg) {
    color: var(--v-muted);
  }
</style>
