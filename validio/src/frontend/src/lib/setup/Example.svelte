<script lang="ts">
  /// Demo kitchens only: the demo agent sends the challenge's sentence, and
  /// what became of it stands under it as one muted line that leads to the
  /// request (or the ledger, for a refusal). The Inbox holds only what waits,
  /// so a finished result is no row of its own; a request still open is
  /// already in the Inbox's list, so it is not shown twice.
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { api, ApiError } from "$lib/api/client";
  import { askRow, notRecorded, type AskRow } from "$lib/ask";
  import { bump } from "$lib/chrome.svelte";
  import { nb } from "$lib/format";
  import { session } from "$lib/owner.svelte";
  import { settingsApi } from "$lib/settings";
  import { requestPill } from "$lib/v";

  let { listed = [] }: { listed?: string[] } = $props();

  const a = $derived(session.account);
  const show = $derived(!!a?.isDemo && (a.agent.state === "active" || a.agent.state === "paused"));
  let busy = $state(false);
  let row = $state<AskRow | null>(null);
  let refused = $state("");
  let problem = $state("");

  async function send() {
    if (busy) return;
    busy = true;
    row = null;
    refused = problem = "";
    try {
      const out = await settingsApi.example();
      if (out.requestId) {
        const [r, inbox] = await Promise.all([api.request(out.requestId), api.inbox().catch(() => [])]);
        row = askRow(r, inbox.find((i) => i.id === r.id));
      } else refused = [out.final, ...out.lines].some((l) => /paused this agent/i.test(l)) ? "Agent paused" : notRecorded(out.final);
      bump();
    } catch (err) {
      problem = err instanceof ApiError && err.status === 409 ? "Connect the demo agent first." : err instanceof Error ? err.message : String(err);
    } finally {
      busy = false;
    }
  }
</script>

{#if show}
  <section class="sec" aria-label="Example request" data-testid="example">
    <Section class="v-card">
      <div class="v-row ex">
        <span class="v-row-main">
          <span class="v-row-title">{nb("1,000 l lactose-free milk by Monday, budget 1,200.00 €")}</span>
          {#if busy}
            <span class="v-row-sub">Sending…</span>
          {:else if row && !listed.includes(row.id)}
            <a class="v-row-sub last" href="/requests/{row.id}" data-testid="example-result">{nb(`${requestPill(row.status).label}${row.end ? `, ${row.end}` : ""}`)} ›</a>
          {:else if refused}
            <a class="v-row-sub last" href="/ledger" data-testid="example-result">Refused: {refused.charAt(0).toLowerCase() + refused.slice(1)} ›</a>
          {/if}
        </span>
        <span class="v-row-end"><Button data-testid="example-send" disabled={busy} onclick={send}>Send example request</Button></span>
      </div>
    </Section>
    {#if problem}<p class="problem" role="alert" data-testid="example-problem">{problem}</p>{/if}
  </section>
{/if}

<style>
  /* No status column: the result is a line under the sentence, not a pill. */
  .ex {
    grid-template-columns: minmax(0, 1fr) auto;
  }
  .last {
    display: block;
    text-decoration: none;
  }
  .last:hover {
    color: var(--v-fg);
  }
  /* On the phone the sentence first, then the button over the full width. */
  @media (max-width: 760px) {
    .ex .v-row-main {
      grid-row: 1;
    }
    .ex .v-row-end {
      grid-row: 2;
      grid-column: 1 / -1;
      margin-top: 8px;
    }
    .ex .v-row-end :global([data-slot="button"]) {
      width: 100%;
    }
  }
  .problem {
    margin: 8px 0 0;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-bad-text);
  }
</style>
