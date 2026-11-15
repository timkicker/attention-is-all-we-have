<script lang="ts">
  /// The agent's connection, drawn (plans/025, Agent): your agent, Validio, Valio Aimo, and the
  /// current between them. Not connected: a dashed line. Pairing: a spark leaves the agent now and
  /// then, listening for its first call. The code asked: the spark reaches Validio and Validio
  /// waits for you. Active: the line is lit and every call the agent makes runs through to Valio.
  /// Paused: dashed and grey again.
  import type { AgentState } from "$lib/api/types";
  import { chrome } from "$lib/chrome.svelte";
  import { DUR } from "$lib/motion";
  import Current from "./Current.svelte";

  let { phase, name = "Your agent", pulse = 0 }: { phase: AgentState["state"]; name?: string; pulse?: number } = $props();

  // A call through: the first leg runs, then the second, as the first spark arrives.
  let second = $state(0);
  let relay = $state(0);
  $effect(() => {
    const p = pulse;
    const t = setTimeout(() => (relay = p), DUR.spark);
    return () => clearTimeout(t);
  });
  const firstMode = $derived(phase === "pairing" ? "listen" : phase === "consent" ? "run" : phase === "active" ? "lit" : "dim");
  const WORDS: Record<AgentState["state"], string> = {
    none: "Not connected",
    pairing: "Waiting for its first call",
    consent: "Called. Check the code",
    active: "Connected",
    paused: "Paused",
  };
</script>

<figure class="alink" data-state={phase} data-testid="agent-link" aria-label="{name}: {WORDS[phase]}">
  <span class="nd agent" class:on={phase === "active" || phase === "consent"} class:off={phase === "paused" || phase === "none"}>
    <span class="nd-name">{name}</span>
    <span class="nd-sub">{WORDS[phase]}</span>
  </span>
  <span class="ln">
    <Current axis={chrome.phone ? "v" : "h"} mode={firstMode} base={phase === "pairing" ? "dim" : "idle"} pause={2600} {pulse} onarrive={() => (second += 1)} />
  </span>
  <span class="nd validio" class:wait={phase === "consent"}>
    <span class="nd-name wm">Validio</span>
    <span class="nd-sub">{phase === "consent" ? "Waits for you" : "Checks every order"}</span>
  </span>
  <span class="ln">
    <Current axis={chrome.phone ? "v" : "h"} mode="lit" pulse={relay + second} />
  </span>
  <span class="nd valio">
    <span class="nd-name">Valio Aimo</span>
    <span class="nd-sub">Price and stock</span>
  </span>
</figure>

<style>
  .alink {
    display: grid;
    grid-template-columns: auto minmax(32px, 1fr) auto minmax(32px, 1fr) auto;
    align-items: center;
    margin: 0;
    padding: 20px 0;
  }
  .ln {
    display: block;
    min-width: 0;
  }
  .nd {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 10px 14px;
    border: 1px solid var(--v-line-strong);
    border-radius: var(--radius-button);
    background: var(--v-surface);
    transition:
      border-color var(--v-dur-ui) var(--v-ease-out),
      background-color var(--v-dur-ui) var(--v-ease-out),
      opacity var(--v-dur-ui) var(--v-ease-out);
  }
  .nd-name {
    font-size: var(--fs-head);
    line-height: var(--lh-head);
    font-weight: 600;
    white-space: nowrap;
  }
  .nd-name.wm {
    font-family: var(--v-script);
    font-weight: 400;
    font-size: 18px;
    color: var(--valio);
  }
  .nd-sub {
    font-size: var(--fs-cap);
    line-height: 16px;
    color: var(--v-muted);
    white-space: nowrap;
  }
  .nd.agent.on {
    border-color: var(--valio);
  }
  .nd.agent.off {
    border-style: dashed;
  }
  [data-state="paused"] .nd.agent {
    opacity: 0.6;
  }
  .nd.validio {
    border-color: var(--valio);
    background: var(--valio-tint);
  }
  .nd.validio.wait {
    box-shadow: inset 0 0 0 1px var(--valio);
  }
  .nd.validio.wait .nd-sub {
    color: var(--valio);
    font-weight: 600;
  }
  @media (max-width: 760px) {
    .alink {
      grid-template-columns: minmax(0, 1fr);
      justify-items: start;
      padding: 12px 0;
    }
    .ln {
      width: 2px;
      height: 24px;
      margin-left: 22px;
    }
  }
</style>
