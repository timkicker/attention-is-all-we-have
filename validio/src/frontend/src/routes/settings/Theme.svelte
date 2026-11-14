<script lang="ts">
  /// Theme: System follows the device, Light and Dark stay.
  import { SegmentedControl } from "@arlen/ui-kit/components/ui/segmented-control";
  import { ListRow, ListSection } from "$lib/v2";
  import { setMode, theme, type Mode } from "$lib/theme.svelte";

  const MODES: { value: Mode; label: string }[] = [
    { value: "system", label: "System" },
    { value: "light", label: "Light" },
    { value: "dark", label: "Dark" },
  ];
</script>

<ListSection id="theme" title="Theme">
  <ListRow id="row-theme" label="Look">
    {#snippet control()}
      <SegmentedControl id="theme" ariaLabel="Theme" options={MODES} value={theme.mode} onchange={(v) => setMode(v as Mode)} />
    {/snippet}
  </ListRow>
</ListSection>
