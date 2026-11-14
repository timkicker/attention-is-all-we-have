<script lang="ts">
  /// "Ask as the kitchen's agent": the owner's own words go through the same
  /// agent loop as `make agent`. Each ask lands as one inbox-style row, newest
  /// on top, so the three endings can stand side by side; the agent's steps
  /// sit in one quiet fold underneath.
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Chip } from "@arlen/ui-kit/components/ui/chip";
  import { Dialog } from "@arlen/ui-kit/components/ui/dialog";
  import { IconAction } from "@arlen/ui-kit/components/ui/icon-action";
  import { Input } from "@arlen/ui-kit/components/ui/input";
  import { Notice } from "@arlen/ui-kit/components/ui/notice";
  import { ChevronRight, X } from "@lucide/svelte";
  import { api, needsToken } from "$lib/api/client";
  import { askLog, askRow, notRecorded, type AskRow, type AskStep } from "$lib/ask";
  import { bump, chrome } from "$lib/chrome.svelte";
  import { requestPill } from "$lib/v";
  import VStatusRow from "./VStatusRow.svelte";

  let { open, onClose }: { open: boolean; onClose: () => void } = $props();

  // One recorded example for each ending: ordered alone, waits for you, blocked.
  const EXAMPLES = [
    { label: "100 l whipping cream", text: "100 litres of whipping cream by Monday" },
    { label: "50 kg quark, budget 100 €", text: "50 kg of quark by Monday, budget 100 euro" },
    { label: "20 kg parmesan", text: "20 kg of parmesan by Monday" },
  ];

  type Entry =
    | { key: number; kind: "working"; label: string }
    | { key: number; kind: "row"; row: AskRow }
    | { key: number; kind: "none"; line: string };

  let text = $state("");
  let entries = $state<Entry[]>([]);
  let log = $state<AskStep[]>([]); // the latest ask only
  let problem = $state("");
  let next = 0;
  const busy = $derived(entries.some((e) => e.kind === "working"));

  async function send(words: string, label = words) {
    const t = words.trim();
    if (!t || busy) return;
    problem = "";
    text = "";
    const key = next++;
    entries = [{ key, kind: "working", label }, ...entries];
    const put = (e: Entry | null) => (entries = entries.flatMap((x) => (x.key === key ? (e ? [e] : []) : [x])));
    try {
      const a = await api.ask(t);
      log = askLog(a.lines);
      if (a.requestId) {
        const [r, inbox] = await Promise.all([api.request(a.requestId), api.inbox().catch(() => [])]);
        put({ key, kind: "row", row: askRow(r, inbox.find((i) => i.id === r.id)) });
      } else put({ key, kind: "none", line: notRecorded(a.final) });
      bump();
    } catch (err) {
      put(null);
      if (!needsToken(err)) problem = err instanceof Error ? err.message : String(err);
    }
  }

  function submit(e: SubmitEvent) {
    e.preventDefault();
    void send(text);
  }
</script>

<Dialog {open} {onClose} labelledby="ask-title" size="md">
  <div class="ask" class:phone={chrome.phone} data-testid="ask-dialog">
    <header>
      <h2 id="ask-title">Ask as the kitchen's agent</h2>
      <IconAction label="Close" size="control" onclick={onClose}><X size={16} strokeWidth={1.75} /></IconAction>
    </header>
    <form class="send" onsubmit={submit}>
      <Input
        id="ask-input"
        data-testid="ask-input"
        aria-label="What the kitchen needs"
        bind:value={text}
        maxlength={300}
        autocomplete="off"
        placeholder="e.g. 50 kg of quark by Monday"
      />
      <Button type="submit" data-testid="ask-send" disabled={busy || !text.trim()}>Send</Button>
    </form>
    <div class="chips" role="group" aria-label="Recorded examples">
      {#each EXAMPLES as x, i (x.text)}
        <Chip id="ask-chip-{i + 1}" label={x.label} tooltip={x.text} actionLabel="Send: {x.text}" onclick={() => void send(x.text, x.label)} />
      {/each}
    </div>

    {#if problem}<Notice tone="error" text={problem} />{/if}
    {#if entries.length}
      <ul class="results" data-testid="ask-results" aria-live="polite">
        {#each entries as e (e.key)}
          <li data-testid="ask-entry">
            {#if e.kind === "working"}
              <VStatusRow pill={{ label: "Working", tone: "neutral" }} title={e.label} end="…" testid="ask-working" />
            {:else if e.kind === "row"}
              <VStatusRow href="/requests/{e.row.id}" testid="ask-row-{e.row.id}" pill={requestPill(e.row.status)} title={e.row.title} sub={e.row.sub} end={e.row.end} />
            {:else}
              <p class="none" data-testid="ask-none">{e.line}</p>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}
    {#if log.length}
      <details class="fold log" data-testid="ask-log">
        <summary><ChevronRight class="chev" aria-hidden="true" />Agent log</summary>
        <ol>
          {#each log as l, i (i)}<li><span class="who">{l.who}</span><span>{l.what}</span></li>{/each}
        </ol>
      </details>
    {/if}
  </div>
</Dialog>

<style>
  .ask {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 16px 20px 20px;
  }
  .ask.phone {
    padding-bottom: calc(20px + env(safe-area-inset-bottom));
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  h2 {
    margin: 0;
    font-size: 15px;
    line-height: 22px;
    font-weight: 600;
  }
  .send {
    display: flex;
    gap: 8px;
  }
  .send :global(input) {
    flex: 1;
    min-width: 0;
  }
  .send :global([data-slot="button"]:disabled) {
    opacity: 0.4;
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .results {
    margin: 4px 0 0;
    padding: 0;
    list-style: none;
    max-height: 264px;
    overflow-y: auto;
    border-top: 1px solid var(--v-line);
  }
  .results li {
    border-bottom: 1px solid var(--v-line);
  }
  /* The phone's row at every width: the pill above the title, flush with the input. */
  .results :global(.v-row) {
    grid-template-columns: minmax(0, 1fr) auto;
    row-gap: 4px;
    padding-inline: 0;
    border-radius: 0;
  }
  .results :global(.v-row-lead) {
    grid-row: 1;
    grid-column: 1;
  }
  .results :global(.v-row-end) {
    grid-row: 1;
    grid-column: 2;
  }
  .results :global(.v-row-main) {
    grid-row: 2;
    grid-column: 1 / -1;
  }
  .none {
    margin: 0;
    padding: 12px 0;
    font-size: 13px;
    line-height: 20px;
    color: var(--v-muted);
  }
  .log ol {
    margin: 8px 0 0;
    padding: 8px 0;
    list-style: none;
    max-height: 240px;
    overflow: auto;
    border-top: 1px solid var(--v-line);
    border-bottom: 1px solid var(--v-line);
    font-size: 13px;
    line-height: 20px;
    color: var(--v-fg);
  }
  .log li {
    display: grid;
    grid-template-columns: 64px minmax(0, 1fr);
    column-gap: 8px;
  }
  .log li + li {
    margin-top: 2px;
  }
  .log .who {
    color: var(--v-muted);
  }
  :global(.dialog-card:has(.ask)) {
    max-width: 520px;
  }
  :global(.dialog-backdrop:has(.ask:not(.phone))) {
    align-items: flex-start;
    padding-top: 15vh;
  }
  :global(.dialog-backdrop:has(.ask.phone)) {
    align-items: flex-end;
    padding: 0;
  }
  :global(.dialog-card:has(.ask.phone)) {
    max-width: none;
    border-radius: var(--radius-modal) var(--radius-modal) 0 0;
  }
</style>
