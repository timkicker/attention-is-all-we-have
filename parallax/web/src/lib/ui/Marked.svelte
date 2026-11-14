<script lang="ts">
  // Text with spans: as="mark" (says it differently, ochre) or as="del" (removed, struck).
  import { segments } from '../marks'
  import type { MarkedText } from '../model'

  let { value, as = 'mark' }: { value: MarkedText; as?: 'mark' | 'del' } = $props()
</script>

{#each segments(value) as s, i (i)}{#if !s.on}{s.text}{:else if as === 'del'}<del>{s.text}</del>{:else}<mark>{s.text}</mark>{/if}{/each}
