<script lang="ts">
  /// The small form under a Settings row: its fields, a problem that belongs
  /// to no one field, then Save and Cancel.
  import { tick, type Snippet } from "svelte";
  import { beforeNavigate, goto } from "$app/navigation";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { collapse } from "$lib/motion";
  import BusyLabel from "$lib/v2/BusyLabel.svelte";

  let {
    id,
    problem = "",
    busy = false,
    onsave,
    oncancel,
    children,
  }: { id: string; problem?: string; busy?: boolean; onsave: () => void; oncancel: () => void; children: Snippet } = $props();

  // Escape cancels, ⌘ or Ctrl with Enter saves; typing then leaving the page asks first (plans/025).
  let touched = $state(false);
  let leaveTo = $state<URL | null>(null);
  let leaving = false;
  beforeNavigate((nav) => {
    if (leaving || busy || !touched || !nav.to || nav.type === "leave") return;
    nav.cancel();
    leaveTo = nav.to.url;
    tick().then(() => document.getElementById(`${id}-stay`)?.focus());
  });
  function keys(e: KeyboardEvent) {
    if (e.key === "Escape") {
      e.preventDefault();
      oncancel();
    } else if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      onsave();
    }
  }
</script>

<!-- It opens under its row (plans/016). It leaves at once: another row's form may open in the
     same moment, and two forms must never hold the same field ids. -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions (Escape and ⌘↵ for the fields inside; Save and Cancel are the buttons) -->
<form
  in:collapse
  class="sf"
  data-testid="{id}-form"
  novalidate
  oninput={() => (touched = true)}
  onkeydown={keys}
  onsubmit={(e) => {
    e.preventDefault();
    onsave();
  }}
>
  {@render children()}
  {#if leaveTo}
    <p class="sf-leave" role="alert" data-testid="{id}-leave" in:collapse={{ duration: 200 }}>
      Leave without saving?
      <button type="button" class="link" id="{id}-stay" onclick={() => (leaveTo = null)}>Stay</button>
      <button
        type="button"
        class="link bad"
        onclick={() => {
          const to = leaveTo;
          leaveTo = null;
          leaving = true;
          if (to) void goto(to.pathname + to.search);
        }}>Leave</button
      >
    </p>
  {/if}
  {#if problem}<p class="sf-problem" role="alert" data-testid="{id}-problem" in:collapse={{ duration: 200 }} out:collapse={{ duration: 140 }}>{problem}</p>{/if}
  <div class="sf-acts">
    <Button variant="ghost" id="{id}-cancel" onclick={oncancel}>Cancel</Button>
    <Button type="submit" id="{id}-save" data-testid="{id}-save" disabled={busy}><BusyLabel {busy} idle="Save" working="Saving" /></Button>
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
  .sf-leave {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 14px;
    margin: 0;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
  }
  .sf-leave button {
    padding: 0;
    border: 0;
    background: none;
    font: inherit;
  }
  .sf-leave .bad {
    color: var(--v-bad-text);
  }
  .sf-acts {
    display: flex;
    gap: 8px;
  }
</style>
