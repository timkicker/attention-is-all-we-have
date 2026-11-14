<script lang="ts">
  /// The open ledger as halbat's feed: entries in chain order under the
  /// request or steady order they belong to. Each entry is a closed fold
  /// holding the backend's sentence, the rules, the disclosed fields and the hashes.
  import { page } from "$app/state";
  import { replaceState } from "$app/navigation";
  import { Chip } from "@arlen/ui-kit/components/ui/chip";
  import { api } from "$lib/api/client";
  import { live } from "$lib/live.svelte";
  import { ACTOR, ledgerGroups } from "$lib/v";
  import { nb } from "$lib/format";
  import VHead from "$lib/v/VHead.svelte";
  import VPill from "$lib/v/VPill.svelte";
  import VState from "$lib/v/VState.svelte";

  const ledger = live(() => api.ledger());
  const inbox = live(() => api.inbox());
  const steady = live(() => api.steadyList());

  const titleOf = (id: string) =>
    ledger.data?.groups?.find((g) => g.requestId === id)?.titleText ??
    inbox.data?.find((i) => i.id === id)?.displayName ??
    steady.data?.find((s) => s.id === id)?.name ??
    "Other entries";
  // "See in ledger" on the Agent page lands here with ?pass=<passId>: that agent's entries only.
  const passId = page.url.searchParams.get("pass");
  let onlyPass = $state(!!passId);
  function pick(only: boolean) {
    onlyPass = only;
    const url = new URL(page.url);
    if (only && passId) url.searchParams.set("pass", passId);
    else url.searchParams.delete("pass");
    replaceState(url, {});
  }
  const entries = $derived((ledger.data?.entries ?? []).filter((e) => !onlyPass || e.spendPassId === passId));
  const groups = $derived(ledgerGroups(entries));
  const chain = $derived(ledger.data?.chain);
</script>

<VHead title="Ledger">
  {#snippet facts()}
    {#if chain}
      <span class="chain" data-testid="chain-status" id="chain-status">
        <VPill label={chain.ok ? "Verified" : `Broken at ${chain.brokenAt}`} tone={chain.ok ? "ok" : "bad"} />
        <span class="num" title="Every entry signs the one before it">{chain.count} entries</span>
      </span>
    {/if}
  {/snippet}
</VHead>

<div class="blocks">
  {#if ledger.error && !ledger.data}
    <VState kind="error" title="Validio is not reachable." detail={ledger.error} onretry={() => location.reload()} />
  {:else if !ledger.loaded}
    <VState kind="loading" rows={4} />
  {:else if !ledger.data?.entries?.length}
    <VState kind="empty" title="Nothing recorded yet." />
  {:else}
    {#if passId}
      <div class="chips" role="group" aria-label="Show">
        <Chip id="ledger-all" label="All" pressed={!onlyPass} onclick={() => pick(false)} />
        <Chip id="ledger-agent" label="Agent" pressed={onlyPass} onclick={() => pick(true)} />
      </div>
    {/if}
    {#if !groups.length}<VState kind="empty" title="None." />{/if}
    <div data-testid="ledger" id="ledger">
      {#each groups as g (g.id)}
        <!-- The id once after the title ("Spend Pass M-1"); the demo's own group has no id to show. -->
        <div class="day" data-testid="ledger-group-{g.id}"><b>{nb(titleOf(g.id))}</b>{#if g.id !== "demo" && !titleOf(g.id).endsWith(g.id)}<span>{g.id}</span>{/if}</div>
        <ul class="rc-ev led">
          {#each g.entries as e (e.seq)}
            <li data-testid="ledger-entry" class:broken={chain && !chain.ok && chain.brokenAt === e.seq}>
              <details>
                <summary>
                  <span class="ev-left"><span class="t num">{nb(e.timeText)}</span><span class="who">{ACTOR[e.kind] ?? e.actorText ?? e.actor}</span></span>
                  <span class="ev-main">
                    <span class="sent">{nb(e.displayText ?? e.summary ?? e.sentence)}</span>
                    {#if chain && !chain.ok && chain.brokenAt === e.seq}<span class="ev-sub">Hash does not match the entry before.</span>{/if}
                  </span>
                  <span class="oid num">{e.kind === "order" && e.orderId && !(e.displayText ?? "").includes(e.orderId) ? e.orderId : ""}</span>
                </summary>
                <div class="body" data-raw>
                  <p>{e.sentence}</p>
                  <p>By {e.actor}</p>
                  {#if e.ruleIds.length}<p>Rules: {e.ruleIds.join(", ")}</p>{/if}
                  {#if e.disclosedText?.length}<p>Shown to the agent: {e.disclosedText.join(", ")}</p>{/if}
                  <p class="hash mono">Hash {e.hash}</p>
                  <p class="hash mono">Before {e.prevHash}</p>
                </div>
              </details>
            </li>
          {/each}
        </ul>
      {/each}
    </div>
  {/if}
</div>

<style>
  .chips {
    display: flex;
    gap: 8px;
    margin-bottom: 12px;
  }
  .chips :global(.chip) {
    height: 28px;
  }
  @media (max-width: 760px) {
    .chips :global(.chip) {
      height: 44px;
    }
  }
  .chain {
    display: inline-flex;
    align-items: center;
    gap: 24px;
  }
  .led > li {
    display: block;
    padding: 0;
    position: relative;
  }
  .led > li.broken::before {
    content: "";
    position: absolute;
    left: -4px;
    top: 0;
    bottom: 0;
    width: 2px;
    background: var(--v-bad);
  }
  summary {
    display: grid;
    grid-template-columns: 176px minmax(0, 1fr) auto;
    column-gap: 24px;
    align-items: baseline;
    min-height: 50px;
    padding: 14px 0;
    list-style: none;
    cursor: pointer;
  }
  summary::-webkit-details-marker {
    display: none;
  }
  .ev-left {
    display: flex;
    gap: 12px;
  }
  .who {
    color: var(--v-fg);
    font-weight: 500;
  }
  .ev-main {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .sent {
    font-size: var(--fs-body);
    line-height: var(--lh-body);
  }
  .oid {
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  /* The row hover of a.v-row, reaching 8 px past the text on both sides. */
  summary {
    margin-inline: -8px;
    padding-inline: 8px;
    border-radius: var(--radius-button);
    transition: background-color var(--duration-fast) ease;
  }
  summary:hover {
    background: var(--v-tint-hover);
  }
  .body {
    padding: 0 0 16px 200px;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  .body p {
    margin: 0;
  }
  .body p + p {
    margin-top: 4px;
  }
  .hash {
    font-size: 12px;
    line-height: 16px;
    color: var(--v-faint);
    overflow-wrap: anywhere;
  }
  @media (max-width: 760px) {
    summary {
      grid-template-columns: minmax(0, 1fr) auto;
      row-gap: 4px;
      padding-block: 12px;
      min-height: 72px;
    }
    .ev-left {
      grid-row: 1;
      grid-column: 1;
      font-size: 14px;
    }
    .who {
      color: var(--v-muted);
      font-weight: 400;
    }
    .oid {
      grid-row: 1;
      grid-column: 2;
    }
    .ev-main {
      grid-row: 2;
      grid-column: 1 / -1;
    }
    .body {
      padding-left: 0;
    }
  }
</style>
