<script lang="ts">
  /// halbat's tabs: 14 px words, a count in faint, the selected one underlined in Valio blue.
  let {
    tabs,
    selected = $bindable(),
    label,
  }: { tabs: { id: string; label: string; count?: number }[]; selected: string; label: string } = $props();

  function key(e: KeyboardEvent, i: number) {
    const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!d) return;
    e.preventDefault();
    const t = tabs[(i + d + tabs.length) % tabs.length];
    selected = t.id;
    document.getElementById(`tab-${t.id}`)?.focus();
  }
</script>

<div class="tabs" role="tablist" aria-label={label}>
  {#each tabs as t, i (t.id)}
    <button
      type="button"
      role="tab"
      id="tab-{t.id}"
      aria-selected={selected === t.id}
      aria-controls="panel-{t.id}"
      tabindex={selected === t.id ? 0 : -1}
      onclick={() => (selected = t.id)}
      onkeydown={(e) => key(e, i)}
    >
      {t.label}{#if t.count !== undefined}<em>{t.count}</em>{/if}
    </button>
  {/each}
</div>
