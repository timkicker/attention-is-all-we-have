<script lang="ts">
  // wf .note: the line under a statement; strong parts (edition names) in <b>.
  // Groups are set apart by space (.parts); the separator is only read out, never drawn.
  import type { Note } from '../model'

  let { parts }: { parts: Note } = $props()
  const groups = $derived.by(() => {
    const out: Note[] = [[]]
    for (const p of parts) {
      if (p.sep) out.push([])
      else out[out.length - 1].push(p)
    }
    return out.filter((g) => g.length)
  })
</script>

<p class="note parts">{#each groups as g, i (i)}<span>{#if i}<span class="sr-only">, </span>{/if}{#each g as p, j (j)}{#if p.strong}<b>{p.text}</b>{:else}{p.text}{/if}{/each}</span>{/each}</p>
