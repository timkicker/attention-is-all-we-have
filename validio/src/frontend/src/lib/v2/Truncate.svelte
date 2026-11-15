<script lang="ts">
  /// Text cut with an ellipsis that shows itself in full in a tooltip, only when it is cut (plans/023).
  import Tip from "./Tip.svelte";

  let { text, class: cls = "" }: { text: string; class?: string } = $props();
  let el = $state<HTMLElement>();
  let cut = $state(false);
  const measure = () => {
    if (el) cut = el.scrollWidth > el.clientWidth + 1;
  };
  $effect(() => {
    void text;
    if (!el) return;
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  });
</script>

<Tip {text} disabled={!cut}>
  {#snippet children(props)}<span {...props} class="tr {cls}" bind:this={el}>{text}</span>{/snippet}
</Tip>

<style>
  .tr {
    display: block;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
