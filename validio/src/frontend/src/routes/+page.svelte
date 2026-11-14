<script lang="ts">
  /// Inbox: only what is still open (working or waiting for you), one card of
  /// status rows. Handled requests live on the Orders page.
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { api } from "$lib/api/client";
  import type { SupplyRequest } from "$lib/api/types";
  import { live } from "$lib/live.svelte";
  import { money } from "$lib/format";
  import { isFinal, requestPill } from "$lib/v";
  import VHead from "$lib/v/VHead.svelte";
  import Checklist from "$lib/setup/Checklist.svelte";
  import Example from "$lib/setup/Example.svelte";
  import VState from "$lib/v/VState.svelte";
  import VStatusRow from "$lib/v/VStatusRow.svelte";
  import { shortReason } from "$lib/ask";

  const inbox = live(() => api.inbox());
  const pass = live(() => api.spendPass("M-1"));
  // The rows' simulated lines come with each request.
  const reqs = live(async () => {
    const items = await api.inbox();
    const out: Record<string, SupplyRequest> = {};
    for (const i of items) out[i.id] = await api.request(i.id);
    return out;
  });

  const items = $derived(inbox.data ?? []);
  // Grouped by the same state the pill shows: open until the state is final.
  const open = $derived(items.filter((i) => !isFinal(i.status)));
  const simulated = (id: string) => reqs.data?.[id]?.simulated?.[0]?.sentence;
</script>

<VHead title="Inbox">
  {#snippet facts()}
    {#if pass.data}
      <a href="/agent#rules" data-testid="spend-pass">
        Orders alone up to <span data-testid="pass-auto" id="pass-auto">{money(pass.data.autoLimitCents)}</span>, never above
        <span data-testid="pass-cap" id="pass-cap">{money(pass.data.hardCapCents)}</span> ›
      </a>
    {/if}
  {/snippet}
</VHead>

<div class="blocks">
  <Checklist />
  <Example listed={open.map((i) => i.id)} />
  {#if inbox.error && !inbox.data}
    <VState kind="error" title="Validio is not reachable." detail={inbox.error} onretry={() => location.reload()} />
  {:else if !inbox.loaded}
    <VState kind="loading" />
  {:else if !open.length}
    <VState kind="empty" title="Nothing waits for you." />
  {:else}
    {#each [{ name: "Open", list: open }] as sec (sec.name)}
      {#if sec.list.length}
        <section class="sec" aria-labelledby="h-{sec.name}">
          <h2 class="v-h" id="h-{sec.name}">{sec.name} <em>{sec.list.length}</em></h2>
          <Section class="v-card">
            {#each sec.list as i (i.id)}
              <VStatusRow
                href="/requests/{i.id}"
                testid="inbox-{i.id}"
                id="inbox-{i.id}"
                pill={requestPill(i.status)}
                title={i.titleText ?? i.displayName ?? i.title ?? i.text}
                sub={i.status === "waiting" ? (i.summary ? shortReason(i.summary) : simulated(i.id)) : undefined}
                subTestid={i.status === "waiting" ? `inbox-summary-${i.id}` : undefined}
                end={i.moneyText ?? money(i.totalCents)}
              />
            {/each}
          </Section>
        </section>
      {/if}
    {/each}
  {/if}
</div>
