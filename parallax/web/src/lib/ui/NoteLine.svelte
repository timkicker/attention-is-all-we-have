<script lang="ts">
  // wf .note: the line under a statement; strong parts (edition names) in <b>.
  import type { Note } from '../model'

  let { parts }: { parts: Note } = $props()
</script>

<p class="note">{#each parts as p, i (i)}{#if p.strong}<b>{p.text}</b>{:else}{p.text}{/if}{/each}</p>
