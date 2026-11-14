<script lang="ts">
  /// The kitchen's one agent: connect it (pairing code, or the demo agent),
  /// let it in on the consent card, then pause or disconnect it. Its Rules
  /// sit below in one card, edited in place and saved with the approval code.
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Dialog } from "@arlen/ui-kit/components/ui/dialog";
  import { Input } from "@arlen/ui-kit/components/ui/input";
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { SegmentedControl } from "@arlen/ui-kit/components/ui/segmented-control";
  import { ChevronRight } from "@lucide/svelte";
  import { api, ApiError } from "$lib/api/client";
  import { agentApi, type AgentState, type Rules, type Substitutes } from "$lib/api/agent";
  import { bump, chrome } from "$lib/chrome.svelte";
  import { dayTime, hm, money } from "$lib/format";
  import { live } from "$lib/live.svelte";
  import { owner, session } from "$lib/owner.svelte";
  import VCode from "$lib/v/VCode.svelte";
  import VHead from "$lib/v/VHead.svelte";
  import VPill from "$lib/v/VPill.svelte";
  import VState from "$lib/v/VState.svelte";
  import VValueRow from "$lib/v/VValueRow.svelte";

  const ag = live(() => agentApi.agent());
  const rl = live(() => agentApi.rules());
  const a = $derived(ag.data);
  const r = $derived(rl.data);
  const connected = $derived(a?.state === "active" || a?.state === "paused");
  const passId = $derived(a?.agent?.passId);
  const pass = live(() => (passId ? api.spendPass(passId) : Promise.resolve(undefined)), 10_000);

  let busy = $state(false);
  let problem = $state("");
  async function act(run: () => Promise<AgentState>) {
    busy = true;
    problem = "";
    try {
      const next = await run();
      ag.data = next;
      // The Inbox checklist and the example request read the agent from the session.
      const acc = session.account;
      if (acc) {
        const agent = next.state === "active" || next.state === "paused";
        const setup = { ...acc.setup, agent, done: acc.setup.kitchen && acc.setup.rules && agent };
        session.account = { ...acc, agent: next, setup };
      }
      bump();
    } catch (e) {
      problem = e instanceof Error ? e.message : String(e);
    } finally {
      busy = false;
    }
  }

  let copied = $state("");
  async function copy(what: string, text: string) {
    try {
      await navigator.clipboard.writeText(text);
      copied = what;
      setTimeout(() => (copied = ""), 2000);
    } catch {
      copied = "";
    }
  }

  let confirmOff = $state(false);

  // ---------- Rules, edited in place ----------
  const SUBS: { value: Substitutes; label: string }[] = [
    { value: "off", label: "Off" },
    { value: "listed", label: "Valio's list" },
    { value: "extra", label: "Extra cost" },
  ];
  const subsWord = (x: Rules) =>
    x.substitutes === "off" ? "Off" : x.substitutes === "listed" ? "Valio's list" : `Up to ${x.maxExtraPct} % extra`;

  let editing = $state(false);
  let saving = $state(false);
  const f = $state({ alone: "", approval: "", week: "", subs: "listed" as Substitutes, pct: "5", code: "" });
  let bad = $state<{ alone?: string; approval?: string; week?: string; pct?: string; code?: string; form?: string }>({});
  const euros = (c: number) => (c / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const cents = (t: string) => (/^\s*[\d,]*\.?\d*\s*$/.test(t) && /\d/.test(t) ? Math.round(Number(t.replace(/[,\s]/g, "")) * 100) : NaN);
  const tidy = (k: "alone" | "approval" | "week") => {
    const c = cents(f[k]);
    if (c >= 0) f[k] = euros(c);
  };
  const above = $derived(cents(f.approval) >= 0 ? money(cents(f.approval)) : "");

  function startEdit() {
    if (!r) return;
    f.alone = euros(r.aloneUpToCents);
    f.approval = euros(r.approvalUpToCents);
    f.week = r.perWeekCents == null ? "" : euros(r.perWeekCents);
    f.subs = r.substitutes;
    f.pct = String(r.maxExtraPct || 5);
    f.code = owner.code;
    bad = {};
    editing = true;
    queueMicrotask(() => document.getElementById("r-alone")?.focus());
  }

  async function save() {
    const alone = cents(f.alone);
    const approval = cents(f.approval);
    const pct = Number(f.pct);
    // An empty week field is no weekly limit.
    const week = f.week.trim() ? cents(f.week) : null;
    const next: typeof bad = {};
    if (!(alone >= 0)) next.alone = "Type an amount in euros.";
    if (!(approval >= 0)) next.approval = "Type an amount in euros.";
    else if (alone > approval) next.alone = "Above needs approval.";
    if (week !== null && !(week >= 0)) next.week = "Type an amount in euros.";
    else if (week !== null && approval >= 0 && week < approval) next.week = "Below needs approval.";
    if (f.subs === "extra" && !(Number.isInteger(pct) && pct >= 0 && pct <= 20)) next.pct = "0 to 20.";
    if (!/^\d{6}$/.test(f.code)) next.code = "Type the 6 digit code.";
    bad = next;
    if (Object.keys(next).length) return;
    saving = true;
    try {
      rl.data = await agentApi.saveRules({
        aloneUpToCents: alone,
        approvalUpToCents: approval,
        perWeekCents: week,
        substitutes: f.subs,
        maxExtraPct: f.subs === "extra" ? pct : (r?.maxExtraPct ?? 5),
        code: f.code,
      });
      owner.code = f.code;
      editing = false;
      const acc = session.account;
      if (acc && !acc.setup.rules) session.account = { ...acc, setup: { ...acc.setup, rules: true, done: acc.setup.kitchen && acc.setup.agent } };
      bump();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (e instanceof ApiError && e.status === 403) {
        bad = { code: "That code is not right." };
        owner.code = "";
      } else if (e instanceof ApiError && e.status === 429) bad = { code: "Too many tries. Wait 15 minutes." };
      else bad = { form: msg.charAt(0).toUpperCase() + msg.slice(1) };
    } finally {
      saving = false;
    }
  }
</script>

{#snippet money_field(k: "alone" | "approval" | "week", label: string)}
  <span class="money">
    <span class="euro">
      <Input
        id="r-{k}"
        data-testid="r-{k}"
        inputmode="decimal"
        bind:value={f[k]}
        onblur={() => tidy(k)}
        autocomplete="off"
        aria-label="{label}, in euros"
        aria-invalid={bad[k] ? true : undefined}
        aria-describedby={bad[k] ? `r-${k}-problem` : undefined}
      />
      <span class="unit" aria-hidden="true">€</span>
    </span>
    {#if bad[k]}<span class="problem" id="r-{k}-problem" role="alert">{bad[k]}</span>{/if}
  </span>
{/snippet}

{#snippet controls()}
  <Button variant="outline" data-testid="agent-pause" disabled={busy} onclick={() => act(() => agentApi.pause(a?.state === "active"))}>
    {a?.state === "active" ? "Pause" : "Resume"}
  </Button>
  <Button variant="ghost" data-testid="agent-disconnect" disabled={busy} onclick={() => (confirmOff = true)}>Disconnect</Button>
{/snippet}

{#snippet copy_button(what: string, text: string, label: string)}
  <Button variant="outline" data-testid="copy-{what}" aria-label={copied === what ? "Copied" : label} onclick={() => copy(what, text)}>
    {copied === what ? "Copied" : "Copy"}
  </Button>
{/snippet}

{#if !a}
  <VHead title="Agent" />
  {#if ag.error}
    <VState kind="error" title="Validio is not reachable." detail={ag.error} onretry={() => location.reload()} />
  {:else}
    <VState kind="loading" rows={3} />
  {/if}
{:else}
  <VHead title="Agent" titleId="agent-title">
    {#snippet facts()}
      {#if a.state === "active"}
        <VPill label="Active" tone="ok" testid="agent-state" />
      {:else if a.state === "paused"}
        <VPill label="Paused" tone="neutral" testid="agent-state" />
      {:else}
        <VPill label={a.state === "pairing" ? "Waiting for your agent" : a.state === "consent" ? "Waiting for you" : "Not connected"} tone="neutral" testid="agent-state" />
      {/if}
      {#if a.agent}
        <span data-testid="agent-name">{a.agent.name}</span>
        <span data-testid="agent-used">{a.agent.lastUsedAt ? `Used ${dayTime(a.agent.lastUsedAt)}` : "Not used yet"}</span>
        {#if pass.data?.usedCents !== undefined}<span class="num" data-testid="agent-week">{money(pass.data.usedCents)} this week</span>{/if}
        <a href="/ledger?pass={encodeURIComponent(a.agent.passId)}" data-testid="agent-ledger" id="agent-ledger">See in ledger</a>
      {/if}
    {/snippet}
    {#snippet actions()}
      {#if connected && !chrome.phone}{@render controls()}{/if}
    {/snippet}
  </VHead>

  <div class="blocks">
    {#if connected && chrome.phone}
      <div class="row-buttons">{@render controls()}</div>
    {:else if a.state === "none"}
      <div class="row-buttons">
        <Button data-testid="agent-connect" disabled={busy} onclick={() => act(agentApi.pair)}>Connect agent</Button>
        {#if session.account?.isDemo}
          <Button variant="outline" data-testid="agent-demo" disabled={busy} onclick={() => act(agentApi.demo)}>Connect the demo agent</Button>
        {/if}
      </div>
    {:else if a.state === "pairing" && a.pairing}
      <section class="sec" aria-labelledby="h-pair">
        <h2 class="v-h" id="h-pair">Connect your agent</h2>
        <Section class="v-card">
          <div class="pair">
            <code class="url big" data-testid="mcp-url" id="mcp-url">{a.pairing.mcpUrl}</code>
            {@render copy_button("mcp", a.pairing.mcpUrl, "Copy MCP URL")}
          </div>
          <p class="steps" data-testid="mcp-hint">Add this URL to your agent as an MCP server. Allow appears here on its first call.</p>
        </Section>
        <details class="fold vendor">
          <summary data-testid="vendor-fold"><ChevronRight class="chev" aria-hidden="true" />Agent without MCP</summary>
          <div class="fold-body urls">
            <span class="url-label">Code</span>
            <code class="url" data-testid="pair-code" id="pair-code" data-raw>{a.pairing.code}</code>
            {@render copy_button("code", a.pairing.code, "Copy pairing code")}
            <span class="hint">Valid until {hm(a.pairing.expiresAt)}</span>
            <span class="url-label">API</span>
            <code class="url">{a.pairing.apiUrl}</code>
            {@render copy_button("api", a.pairing.apiUrl, "Copy API URL")}
          </div>
        </details>
        <div class="row-buttons">
          {#if session.account?.isDemo}
            <Button variant="outline" data-testid="agent-demo" disabled={busy} onclick={() => act(agentApi.demo)}>Connect the demo agent</Button>
          {/if}
          <Button variant="ghost" data-testid="pair-cancel" disabled={busy} onclick={() => act(agentApi.deny)}>Cancel</Button>
        </div>
      </section>
    {:else if a.state === "consent" && a.consent}
      <section class="sec" aria-labelledby="h-consent" data-testid="consent">
        <h2 class="v-h" id="h-consent">{a.consent.name} wants to order for {session.account?.name ?? "your kitchen"} within your Rules</h2>
        <Section class="v-card">
          <ul class="may" aria-label="What it may do">
            {#each a.consent.may as m (m)}<li>{m}</li>{/each}
          </ul>
        </Section>
        <div class="row-buttons">
          <Button data-testid="consent-allow" disabled={busy} onclick={() => act(agentApi.allow)}>Allow</Button>
          <Button variant="outline" data-testid="consent-deny" disabled={busy} onclick={() => act(agentApi.deny)}>Deny</Button>
        </div>
      </section>
    {/if}
    {#if problem}<p class="problem" role="alert" data-testid="agent-problem">{problem}</p>{/if}

    <!-- While an agent pairs or asks, that is the page's one job; the consent card names the Rules. -->
    {#if a.state !== "pairing" && a.state !== "consent"}
    <section class="sec" aria-labelledby="h-rules" id="rules">
      <h2 class="v-h" id="h-rules">
        Rules
        <span class="grow"></span>
        {#if r && !editing}
          <Button variant="outline" data-testid="rules-edit" id="rules-edit" onclick={startEdit}>{r.saved ? "Edit" : "Set rules"}</Button>
        {/if}
      </h2>
      {#if !r}
        {#if rl.error}<VState kind="error" title="Rules are not reachable." detail={rl.error} onretry={() => location.reload()} />{:else}<VState kind="loading" rows={3} />{/if}
      {:else if editing}
        <div class="rules-form" data-testid="rules-form">
          <Section class="v-card">
            <VValueRow label="Orders alone">{@render money_field("alone", "Orders alone")}</VValueRow>
            <VValueRow label="Needs approval">{@render money_field("approval", "Needs approval")}</VValueRow>
            <VValueRow label="Blocked above" value={above || "—"} testid="r-blocked" />
            <VValueRow label="Per week">{@render money_field("week", "Per week")}</VValueRow>
            <VValueRow label="Substitutes">
              <span class="subs">
                <SegmentedControl ariaLabel="Substitutes" options={SUBS} bind:value={f.subs} id="r-subs" />
                {#if f.subs === "extra"}
                  <span class="pct">
                    <span class="euro">
                      <Input
                        id="r-pct"
                        data-testid="r-pct"
                        inputmode="numeric"
                        bind:value={f.pct}
                        autocomplete="off"
                        aria-label="Up to this percent extra"
                        aria-invalid={bad.pct ? true : undefined}
                      />
                      <span class="unit" aria-hidden="true">%</span>
                    </span>
                    {#if bad.pct}<span class="problem" role="alert">{bad.pct}</span>{/if}
                  </span>
                {/if}
              </span>
            </VValueRow>
          </Section>
          {#if bad.form}<p class="problem" role="alert" data-testid="rules-problem">{bad.form}</p>{/if}
          <VCode bind:value={f.code} error={bad.code} focus={false} busy={saving} submitLabel="Save" onsubmit={save} oncancel={() => (editing = false)} />
        </div>
      {:else}
        <Section class="v-card">
          {#if r.saved}
            <VValueRow label="Orders alone" value="Up to {money(r.aloneUpToCents)}" testid="rules-alone" />
            <VValueRow label="Needs approval" value="Up to {money(r.approvalUpToCents)}" testid="rules-approval" />
            <VValueRow label="Blocked above" value={money(r.approvalUpToCents)} testid="rules-blocked" />
            <VValueRow label="Per week" value={r.perWeekCents == null ? "No limit" : `Up to ${money(r.perWeekCents)}`} testid="rules-week" />
            <VValueRow label="Substitutes" value={subsWord(r)} testid="rules-subs" />
          {:else}
            <VValueRow label="Every order" value="Needs approval" testid="rules-unset" />
          {/if}
        </Section>
      {/if}
    </section>
    {/if}

    {#if connected && a.agent}
      <details class="fold" data-testid="tech-fold" id="tech-fold">
        <summary><ChevronRight class="chev" aria-hidden="true" />Technical</summary>
        <div class="fold-body tech">
          <dl>
            <dt>Pass</dt>
            <dd class="mono">{a.agent.passId}</dd>
            <dt>Key</dt>
            <dd class="mono">{a.agent.keyId}</dd>
          </dl>
          {#if a.versions.length}
            <ol class="versions" aria-label="Versions">
              {#each a.versions as v (v.version)}
                <li><span class="mono">v{v.version}</span><span>{v.why}</span><span class="when">{dayTime(v.at)}</span></li>
              {/each}
            </ol>
          {/if}
          {#if pass.data}<pre class="raw mono" data-testid="raw-pass" data-raw>{JSON.stringify(pass.data, null, 2)}</pre>{/if}
        </div>
      </details>
    {/if}
  </div>

  <Dialog open={confirmOff} onClose={() => (confirmOff = false)} labelledby="off-title">
    <div class="confirm">
      <h2 id="off-title">Disconnect {a.agent?.name ?? "the agent"}?</h2>
      <div class="confirm-buttons">
        <Button variant="ghost" onclick={() => (confirmOff = false)}>Cancel</Button>
        <Button
          variant="destructive"
          data-testid="disconnect-confirm"
          onclick={() => {
            confirmOff = false;
            void act(agentApi.disconnect);
          }}>Disconnect</Button
        >
      </div>
    </div>
  </Dialog>
{/if}

<style>
  .row-buttons {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 16px;
  }
  .sec > .row-buttons:first-child,
  .blocks > .row-buttons:first-child {
    margin-top: 0;
  }
  .grow {
    flex: 1;
  }
  .pair {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 16px;
  }
  .pair .big {
    font-size: var(--fs-body);
    line-height: 24px;
    font-weight: 600;
    overflow-wrap: anywhere;
    min-width: 0;
  }
  .steps {
    margin: 0;
    padding: 0 16px 16px;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
    overflow-wrap: anywhere;
  }
  .vendor {
    margin-top: 12px;
  }
  .urls {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: 8px 12px;
  }
  .url-label {
    font-size: var(--fs-meta);
    color: var(--v-muted);
  }
  .url {
    font-size: var(--fs-meta);
    overflow-wrap: anywhere;
  }
  .hint {
    grid-column: 2 / -1;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
    overflow-wrap: anywhere;
  }
  .may {
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .may li {
    padding: 12px 16px;
    font-size: var(--fs-body);
    line-height: var(--lh-body);
  }
  .may li + li {
    border-top: 1px solid var(--v-line);
  }
  .rules-form {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .money,
  .pct {
    display: flex;
    flex-direction: column;
    gap: 4px;
    width: 160px;
  }
  .pct {
    width: 96px;
  }
  .subs {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    gap: 12px;
  }
  .euro {
    position: relative;
    display: block;
  }
  .euro :global(input) {
    width: 100%;
    text-align: right;
    padding-right: 26px;
    font-variant-numeric: tabular-nums;
  }
  .unit {
    position: absolute;
    right: 10px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--v-muted);
    pointer-events: none;
  }
  .problem {
    margin: 0;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-bad-text);
  }
  .tech dl {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 4px 16px;
    margin: 0;
  }
  .tech dt {
    color: var(--v-muted);
  }
  .tech dd {
    margin: 0;
  }
  .versions {
    max-width: 480px;
    margin: 12px 0 0;
    padding: 0;
    list-style: none;
  }
  .versions li {
    display: grid;
    grid-template-columns: 40px minmax(0, 1fr) auto;
    gap: 12px;
    padding: 4px 0;
  }
  .versions .when {
    color: var(--v-muted);
  }
  .raw {
    margin: 12px 0 0;
    font-size: 12px;
    line-height: 18px;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .confirm {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: var(--v-dialog-pad);
  }
  .confirm h2 {
    margin: 0;
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    font-weight: 600;
  }
  .confirm-buttons {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 4px;
  }
  @media (max-width: 760px) {
    .urls {
      grid-template-columns: minmax(0, 1fr) auto;
    }
    .url-label {
      grid-column: 1 / -1;
    }
    .hint {
      grid-column: 1 / -1;
    }
  }
</style>
