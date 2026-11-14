<script lang="ts">
  /// Demo kitchens only: the demo agent sends the challenge's sentence, and
  /// what became of it stands under it as one row. A request still open is
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
  import VPill from "$lib/v/VPill.svelte";
  import VStatusRow from "$lib/v/VStatusRow.svelte";

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
        <span class="v-row-lead">{#if busy}<VPill label="Working" tone="neutral" />{/if}</span>
        <span class="v-row-main"><span class="v-row-title">{nb("1,000 l lactose-free milk by Monday, budget 1,200.00 €")}</span></span>
        <span class="v-row-end"><Button data-testid="example-send" disabled={busy} onclick={send}>Send example request</Button></span>
      </div>
      {#if row && !listed.includes(row.id)}
        <VStatusRow href="/requests/{row.id}" testid="example-result" pill={requestPill(row.status)} title={row.title} sub={row.sub} end={row.end} />
      {:else if refused}
        <VStatusRow testid="example-result" pill={{ label: "Refused", tone: "bad" }} title={refused} />
      {/if}
    </Section>
    {#if problem}<p class="problem" role="alert" data-testid="example-problem">{problem}</p>{/if}
  </section>
{/if}

<style>
  /* On the phone the sentence first, then the button over the full width. */
  @media (max-width: 760px) {
    .ex .v-row-main {
      grid-row: 2;
    }
    .ex .v-row-end {
      grid-row: 3;
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
