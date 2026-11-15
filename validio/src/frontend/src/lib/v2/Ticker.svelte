<script lang="ts">
  /// A figure that, when it changes, rolls the new text in from the side it moved to (plans/009).
  /// At rest the DOM holds one text node, so text checks read it as before.
  import { easeOut, reduced } from "$lib/motion";

  let { text, value }: { text: string; value: number } = $props();
  let dir = $state(1);
  let last: number | undefined;
  $effect.pre(() => {
    if (last !== undefined && value !== last) dir = value > last ? 1 : -1;
    last = value;
  });
  const enter = (_n: Element) =>
    reduced()
      ? { duration: 120, css: (t: number) => `opacity:${t}` }
      : { duration: 260, easing: easeOut, css: (t: number, u: number) => `opacity:${t};transform:translateY(${u * 8 * dir}px);filter:blur(${u * 2}px)` };
  const leave = (_n: Element) =>
    reduced()
      ? { duration: 120, css: (t: number) => `opacity:${t}` }
      : { duration: 160, easing: easeOut, css: (t: number, u: number) => `opacity:${t};transform:translateY(${-u * 8 * dir}px)` };
</script>

<span class="tk">{#key text}<span class="tk-v" in:enter out:leave>{text}</span>{/key}</span>

<style>
  .tk {
    display: inline-grid;
    overflow-x: visible;
    overflow-y: clip;
    vertical-align: bottom;
  }
  .tk-v {
    grid-area: 1 / 1;
    white-space: nowrap;
  }
</style>
