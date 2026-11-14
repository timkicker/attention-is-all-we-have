<script lang="ts">
  /// Agent: connect it once, check the code on its first call, then pause or
  /// disconnect it. The state comes from GET /api/agent every two seconds, so
  /// the code appears here while the person is still in their agent. In the
  /// fixture, validioMcpCall() in the console plays the agent's first call.
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { ConfirmDialog } from "@arlen/ui-kit/components/ui/confirm-dialog";
  import { Row } from "@arlen/ui-kit/components/ui/row";
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { ChevronRight } from "@lucide/svelte";
  import { agentApi, type AgentState } from "$lib/api/agent";
  import { bump, chrome } from "$lib/chrome.svelte";
  import { ListRow, ListSection, LoadError, Loading, PageHead, dayTime, hm, live } from "$lib/v2";
  import VPill from "$lib/v/VPill.svelte";
  import type { PillTone } from "$lib/v";

  const ag = live(() => agentApi.agent());
  const a = $derived(ag.data);
  const connected = $derived(a?.state === "active" || a?.state === "paused");

  const PILL: Record<AgentState["state"], { label: string; tone: PillTone } | null> = {
    none: null,
    pairing: { label: "Connecting", tone: "neutral" },
    consent: { label: "Check the code", tone: "wait" },
    active: { label: "Active", tone: "ok" },
    paused: { label: "Paused", tone: "neutral" },
  };
  const pill = $derived(a ? PILL[a.state] : null);

  let busy = $state(false);
  let problem = $state("");
  async function act(run: () => Promise<AgentState>) {
    busy = true;
    problem = "";
    try {
      ag.data = await run();
      // Home and the sidebar read the agent too.
      bump();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      problem = msg.charAt(0).toUpperCase() + msg.slice(1);
    } finally {
      busy = false;
    }
  }

  let copied = $state("");
  let copyTimer: ReturnType<typeof setTimeout> | undefined;
  async function copy(what: string, text: string) {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // No clipboard (an insecure origin): select the text so Ctrl+C takes it.
      const el = document.getElementById(`${what}-text`);
      if (el) getSelection()?.selectAllChildren(el);
      return;
    }
    copied = what;
    clearTimeout(copyTimer);
    copyTimer = setTimeout(() => (copied = ""), 2000);
  }

  let confirmOff = $state(false);
</script>

{#snippet copyButton(what: string, text: string, label: string)}
  <Button variant="outline" id="copy-{what}" data-testid="copy-{what}" aria-label={copied === what ? "Copied" : label} onclick={() => copy(what, text)}>
    {copied === what ? "Copied" : "Copy"}
  </Button>
{/snippet}

{#snippet apiText()}<code class="mono code-sm" id="api-text" data-testid="api-url" data-raw>{a?.pairing?.apiUrl}</code>{/snippet}
{#snippet apiCopy()}{@render copyButton("api", a?.pairing?.apiUrl ?? "", "Copy API address")}{/snippet}

{#snippet facts()}
  {#if pill}<VPill label={pill.label} tone={pill.tone} testid="agent-state" id="agent-state" />{/if}
  {#if a?.state === "consent" && a.consent}
    <span data-testid="consent-who">{a.consent.name}{#if a.consent.at} called at {hm(a.consent.at)}{/if}</span>
  {/if}
{/snippet}

<PageHead title="Agent" titleId="agent-title" facts={pill ? facts : undefined}>
  {#snippet actions()}
    {#if a?.state === "pairing"}
      <Button variant="ghost" id="pair-cancel" data-testid="pair-cancel" disabled={busy} onclick={() => act(agentApi.deny)}>Cancel</Button>
    {:else if connected}
      <Button variant="outline" id="agent-pause" data-testid="agent-pause" disabled={busy} onclick={() => act(() => agentApi.pause(a?.state === "active"))}>
        {a?.state === "active" ? "Pause" : "Resume"}
      </Button>
      <Button variant="outline" id="agent-disconnect" data-testid="agent-disconnect" disabled={busy} onclick={() => (confirmOff = true)}>Disconnect</Button>
    {/if}
  {/snippet}
</PageHead>

<div class="blocks">
  {#if !a}
    {#if ag.error}<LoadError detail={ag.error} />{:else}<Loading rows={3} />{/if}
  {:else if a.state === "none"}
    <Section class="v-card">
      <div class="none" data-testid="agent-none">
        <p class="none-title">No agent connected</p>
        <p class="none-text">Your purchasing agent orders from Valio through Validio, inside your Rules.</p>
        <Button id="agent-connect" data-testid="agent-connect" disabled={busy} onclick={() => act(agentApi.pair)}>Connect agent</Button>
      </div>
    </Section>
  {:else if a.state === "pairing" && a.pairing}
    <section class="pair" aria-labelledby="pair-h">
      <p class="pair-h" id="pair-h" data-testid="mcp-hint">Add this address to your agent as an MCP server, then ask it to order something.</p>
      <Section class="v-card">
        <div class="url-line">
          <code class="url-big mono" id="mcp-text" data-testid="mcp-url" data-raw>{a.pairing.mcpUrl}</code>
          {@render copyButton("mcp", a.pairing.mcpUrl, "Copy MCP address")}
        </div>
      </Section>
      <details class="fold" id="agent-nomcp" data-testid="agent-nomcp">
        <summary><ChevronRight class="chev" aria-hidden="true" />Agent without MCP</summary>
        <div class="fold-body nomcp">
          <Section class="v-card">
            <Row id="pair-code" label="Pairing code" description="Valid until {hm(a.pairing.expiresAt)}">
              {#snippet preview()}<code class="mono code-sm" id="code-text" data-testid="pair-code-text" data-raw>{a.pairing?.code}</code>{/snippet}
              {#snippet control()}{@render copyButton("code", a.pairing?.code ?? "", "Copy pairing code")}{/snippet}
            </Row>
            {#if chrome.phone}
              <!-- The address under its label: beside it, the label breaks inside a word. -->
              <Row id="api-url" label="API address" control={apiCopy} below={apiText} />
            {:else}
              <Row id="api-url" label="API address" preview={apiText} control={apiCopy} />
            {/if}
          </Section>
        </div>
      </details>
    </section>
  {:else if a.state === "consent" && a.consent}
    <section class="consent" aria-labelledby="consent-h" data-testid="consent">
      <Section class="v-card">
        <div class="verify">
          <h2 class="sr-only" id="consent-h">Check the code</h2>
          <p class="verify-code mono" id="verify-code" data-testid="verify-code" aria-label="Code {a.consent.verifyCode?.split('').join(' ')}">
            {a.consent.verifyCode ?? ""}
          </p>
          <p class="verify-text">Your agent shows this code too. Allow only if it matches.</p>
          <div class="verify-buttons">
            <Button id="consent-allow" data-testid="consent-allow" disabled={busy} onclick={() => act(agentApi.allow)}>Allow</Button>
            <Button variant="outline" id="consent-deny" data-testid="consent-deny" disabled={busy} onclick={() => act(agentApi.deny)}>Deny</Button>
          </div>
        </div>
      </Section>
      <div class="may">
        <h3 class="may-h" id="may-h">What it may do</h3>
        <ul aria-labelledby="may-h" data-testid="consent-may">
          {#each a.consent.may as m (m)}<li>{m}</li>{/each}
        </ul>
      </div>
    </section>
  {:else if connected && a.agent}
    <ListSection id="agent">
      <ListRow id="agent-name" label="Name" value={a.agent.name} />
      <ListRow id="agent-connected" label="Connected" value={dayTime(a.agent.connectedAt)} />
      <ListRow id="agent-used" label="Last used" value={a.agent.lastUsedAt ? dayTime(a.agent.lastUsedAt) : "Not yet"} />
      <a class="vr go-row" href="/activity" id="agent-activity" data-testid="agent-activity">
        <span>See its activity</span>
        <ChevronRight class="go" aria-hidden="true" />
      </a>
    </ListSection>
  {/if}
  {#if problem}<p class="problem" role="alert" data-testid="agent-problem">{problem}</p>{/if}
</div>

<ConfirmDialog
  open={confirmOff}
  title="Disconnect {a?.agent?.name ?? 'the agent'}?"
  message="It can no longer order. To use it again, connect it anew."
  confirmLabel="Disconnect"
  variant="destructive"
  onCancel={() => (confirmOff = false)}
  onConfirm={async () => {
    await act(agentApi.disconnect);
    confirmOff = false;
  }}
/>

<style>
  /* ---------- none ---------- */
  .none {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
    padding: 20px;
  }
  .none-title {
    margin: 0;
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    font-weight: 500;
  }
  .none-text {
    margin: 0 0 16px;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  /* ---------- pairing ---------- */
  .pair {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .pair-h {
    margin: 0;
    font-size: var(--fs-body);
    line-height: var(--lh-body);
  }
  .url-line {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 16px 16px 16px 20px;
  }
  .url-big {
    flex: 1 1 auto;
    min-width: 0;
    font-size: var(--fs-body);
    line-height: 24px;
    font-weight: 500;
    overflow-wrap: anywhere;
  }
  .pair .fold {
    margin-top: 4px;
  }
  /* The fold's body is muted for prose; these rows hold controls at full contrast. */
  .fold-body.nomcp {
    color: var(--v-fg);
  }
  .code-sm {
    display: block;
    overflow-wrap: anywhere;
    text-align: right;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-fg);
  }
  /* ---------- consent ---------- */
  .consent {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }
  .verify {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    padding: 32px 20px 24px;
    text-align: center;
  }
  .verify-code {
    margin: 0;
    font-size: 48px;
    line-height: 56px;
    font-weight: 500;
    letter-spacing: 0.08em;
    font-variant-numeric: tabular-nums;
    color: var(--v-fg);
  }
  .verify-text {
    margin: 0;
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    color: var(--v-muted);
  }
  .verify-buttons {
    display: flex;
    gap: 8px;
    margin-top: 16px;
  }
  .may-h {
    margin: 0 0 4px;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    font-weight: 500;
    color: var(--v-fg);
  }
  .may ul {
    max-width: 560px;
    margin: 0;
    padding: 0;
    list-style: none;
    columns: 2;
    column-gap: 24px;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  /* ---------- connected ---------- */
  .go-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    min-height: 44px;
    padding: 12px 16px;
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--v-fg);
    text-decoration: none;
  }
  .go-row :global(.go) {
    width: 16px;
    height: 16px;
    color: var(--v-faint);
  }
  .problem {
    margin: 12px 0 0;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-bad-text);
  }
  @media (max-width: 760px) {
    .url-line {
      flex-direction: column;
      align-items: stretch;
      padding: 16px;
    }
    .may ul {
      columns: 1;
    }
    .code-sm {
      text-align: left;
    }
    .verify-code {
      font-size: 40px;
      line-height: 48px;
    }
    .verify-buttons {
      align-self: stretch;
    }
    .verify-buttons :global([data-slot="button"]) {
      flex: 1;
    }
    .none :global([data-slot="button"]) {
      align-self: stretch;
    }
  }
</style>
