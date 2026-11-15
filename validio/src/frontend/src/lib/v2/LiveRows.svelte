<script lang="ts" generics="T extends { id: string }">
  /// A list the server can add to while it is on screen (plans/005). Rows that arrive slide
  /// open and glow; rows that leave fold away; rows that move travel. Transitions are local,
  /// so the first render never animates. Put it inside a ListSection.
  import type { Snippet } from "svelte";
  import { flip } from "svelte/animate";
  import { collapse, easeInOut, reduced } from "$lib/motion";

  let { items, row }: { items: T[]; row: Snippet<[T]> } = $props();
  const move = () => ({ duration: reduced() ? 0 : 260, easing: easeInOut });
</script>

{#each items as it (it.id)}
  <div
    class="lr"
    animate:flip={move()}
    in:collapse
    out:collapse={{ duration: 200 }}
    onintrostart={(e) => (e.currentTarget as HTMLElement).classList.add("v-glow")}
  >
    {@render row(it)}
  </div>
{/each}
