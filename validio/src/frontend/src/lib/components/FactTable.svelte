<script lang="ts">
  /// The evidence behind one option: each fact on its own line, what it says,
  /// how far it can be trusted, and where it comes from.
  import type { Fact } from "$lib/api/types";
  import { GRADE, fieldWord, look, valueWord } from "$lib/format";
  import State from "./State.svelte";

  let { facts }: { facts: Fact[] } = $props();
</script>

<table class="facts">
  <thead class="sr-only">
    <tr><th>Fact</th><th>Value</th><th>Trust</th><th>Source</th></tr>
  </thead>
  <tbody>
    {#each facts as f, i (i)}
      {@const g = look(GRADE, f.grade)}
      <tr>
        <th scope="row">{fieldWord(f.field)}</th>
        <td class="value">{valueWord(f.field, f.value)}</td>
        <td><State label={g.label} tone={g.tone} /></td>
        <td class="source">{f.source}{#if f.note}<span class="note">, {f.note}</span>{/if}</td>
      </tr>
    {/each}
  </tbody>
</table>

<style>
  .facts {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--text-xs);
  }
  th,
  td {
    padding: 0.3rem 0.75rem 0.3rem 0;
    text-align: start;
    vertical-align: top;
  }
  @media (min-width: 761px) {
    tbody tr + tr :is(th, td) {
      border-top: 1px solid color-mix(in srgb, var(--foreground) 7%, transparent);
    }
  }
  th {
    width: 9rem;
    font-weight: 500;
    color: var(--color-fg-secondary);
  }
  .value {
    max-width: 18rem;
    overflow-wrap: anywhere;
  }
  .source {
    color: var(--color-fg-secondary);
  }
  .note {
    color: color-mix(in srgb, var(--color-fg-secondary) 80%, transparent);
  }
  @media (max-width: 760px) {
    tr {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 0.15rem 0.5rem;
      padding-block: 0.4rem;
    }
    th,
    td {
      padding: 0;
    }
    th {
      width: auto;
    }
    .value {
      grid-column: 1 / -1;
      grid-row: 2;
    }
    .source {
      grid-column: 1 / -1;
    }
    tbody tr + tr {
      border-top: 1px solid color-mix(in srgb, var(--foreground) 7%, transparent);
    }
  }
</style>
