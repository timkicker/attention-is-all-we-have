<script lang="ts">
  /// Theme: System follows the device, Light and Dark stay.
  import { SegmentedControl } from "@arlen/ui-kit/components/ui/segmented-control";
  import { setMode, theme, type Mode } from "$lib/theme.svelte";

  const OPTIONS = [
    { value: "system", label: "System" },
    { value: "light", label: "Light" },
    { value: "dark", label: "Dark" },
  ];
</script>

<div class="theme" data-testid="theme">
  <SegmentedControl options={OPTIONS} value={theme.mode} ariaLabel="Theme" id="theme-mode" onchange={(v) => setMode(v as Mode)} />
</div>

<style>
  .theme {
    display: flex;
  }
</style>
