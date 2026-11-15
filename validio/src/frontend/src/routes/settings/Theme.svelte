<script lang="ts">
  /// Theme: System follows the device, Light and Dark stay. The new theme reveals itself in a
  /// circle growing from the segment that was pressed (plans/016).
  import { tick } from "svelte";
  import { SegmentedControl } from "@arlen/ui-kit/components/ui/segmented-control";
  import { ListRow, ListSection } from "$lib/v2";
  import { setMode, theme, type Mode } from "$lib/theme.svelte";

  const MODES: { value: Mode; label: string }[] = [
    { value: "system", label: "System" },
    { value: "light", label: "Light" },
    { value: "dark", label: "Dark" },
  ];

  let at: { x: number; y: number; t: number } | null = null;
  async function change(v: string) {
    let origin = at && Date.now() - at.t < 1000 ? { x: at.x, y: at.y } : undefined;
    if (!origin) {
      // A key press: from the middle of the segment that is now chosen.
      await tick();
      const r = document.querySelector('#theme [role="radio"][aria-checked="true"]')?.getBoundingClientRect();
      if (r) origin = { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    }
    at = null;
    setMode(v as Mode, origin);
  }
</script>

<ListSection id="theme" title="Theme">
  <ListRow id="row-theme" label="Look">
    {#snippet control()}
      <!-- svelte-ignore a11y_no_static_element_interactions (only notes where the press was; the control inside is the radiogroup) -->
      <span class="th" onpointerdown={(e) => (at = { x: e.clientX, y: e.clientY, t: Date.now() })}>
        <SegmentedControl id="theme" ariaLabel="Theme" options={MODES} value={theme.mode} onchange={change} />
      </span>
    {/snippet}
  </ListRow>
</ListSection>

<style>
  .th {
    display: inline-flex;
  }
</style>
