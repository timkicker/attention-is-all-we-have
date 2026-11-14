<script lang="ts">
  /// The small form under a Settings row: its fields, a problem that belongs
  /// to no one field, then Save and Cancel.
  import type { Snippet } from "svelte";
  import { Button } from "@arlen/ui-kit/components/ui/button";

  let {
    id,
    problem = "",
    busy = false,
    onsave,
    oncancel,
    children,
  }: { id: string; problem?: string; busy?: boolean; onsave: () => void; oncancel: () => void; children: Snippet } = $props();
</script>

<form
  class="sf"
  data-testid="{id}-form"
  novalidate
  onsubmit={(e) => {
    e.preventDefault();
    onsave();
  }}
>
  {@render children()}
  {#if problem}<p class="sf-problem" role="alert" data-testid="{id}-problem">{problem}</p>{/if}
  <div class="sf-acts">
    <Button variant="ghost" id="{id}-cancel" onclick={oncancel}>Cancel</Button>
    <Button type="submit" id="{id}-save" data-testid="{id}-save" disabled={busy}>Save</Button>
  </div>
</form>

<style>
  .sf {
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-width: 360px;
    padding-top: 4px;
  }
  /* A field label here sits under the row's own label, so it is no bigger. */
  .sf :global(.vf label) {
    font-size: var(--fs-meta);
  }
  .sf-problem {
    margin: 0;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-bad-text);
  }
  .sf-acts {
    display: flex;
    gap: 8px;
  }
</style>
