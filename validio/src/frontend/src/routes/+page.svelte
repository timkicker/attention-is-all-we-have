<script lang="ts">
  /// Inbox: halbat's admin overview. One facts link to the Spend Pass, then
  /// "Open" (waiting for you) and "Handled", each a card of status rows.
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { api } from "$lib/api/client";
  import type { SupplyRequest } from "$lib/api/types";
  import { live } from "$lib/live.svelte";
  import { money } from "$lib/format";
  import { requestPill } from "$lib/v";
  import VHead from "$lib/v/VHead.svelte";
  import VState from "$lib/v/VState.svelte";
  import VStatusRow from "$lib/v/VStatusRow.svelte";

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
  const open = $derived(items.filter((i) => i.status === "waiting"));
  const handled = $derived(items.filter((i) => i.status !== "waiting"));
  const simulated = (id: string) => reqs.data?.[id]?.simulated?.[0]?.sentence;
</script>

<VHead title="Inbox">
  {#snippet facts()}
    {#if pass.data}
      <a href="/spend-pass" data-testid="spend-pass">
        Orders alone up to <span data-testid="pass-auto" id="pass-auto">{money(pass.data.autoLimitCents)}</span>, never above
        <span data-testid="pass-cap" id="pass-cap">{money(pass.data.hardCapCents)}</span> ›
      </a>
    {/if}
  {/snippet}
</VHead>

<div class="blocks">
  {#if inbox.error && !inbox.data}
    <VState kind="error" title="Validio is not reachable." detail={inbox.error} onretry={() => location.reload()} />
  {:else if !inbox.loaded}
    <VState kind="loading" />
  {:else if !items.length}
    <VState kind="empty" title="No requests yet." detail="The kitchen's agent sends its requests here." />
  {:else}
    {#each [{ name: "Open", list: open }, { name: "Handled", list: handled }] as sec (sec.name)}
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
                sub={i.status === "waiting" ? (i.summary ?? simulated(i.id)) : undefined}
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
