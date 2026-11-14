<script lang="ts">
  /// The door: one sentence on what Validio is, then Log in or Create account,
  /// then the demo kitchen, which is a real kitchen with sample orders.
  import { goto } from "$app/navigation";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { api, ApiError } from "$lib/api/client";
  import type { Account } from "$lib/api/types";
  import { setTitle } from "$lib/chrome.svelte";
  import { isCode, session } from "$lib/owner.svelte";
  import VField from "$lib/v/VField.svelte";

  /** The demo kitchen's approval code, the same live and in the fixture. */
  const DEMO_CODE = "246810";

  let mode = $state<"login" | "signup">("login");
  $effect(() => setTitle(mode === "login" ? "Log in" : "Create account"));

  const f = $state({ kitchen: "", email: "", password: "", customer: "", code: "" });
  let bad = $state<Record<string, string>>({});
  let busy = $state(false);

  function done(a: Account) {
    session.account = a;
    session.checked = true;
    void goto("/", { replaceState: true });
  }

  async function run(fn: () => Promise<Account>) {
    busy = true;
    try {
      done(await fn());
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (e instanceof ApiError && e.status === 401) bad = { password: "Email or password is wrong." };
      else if (e instanceof ApiError && e.status === 409) bad = { email: "This email has an account." };
      else if (e instanceof ApiError && e.status === 429) bad = { form: "Too many tries. Wait 15 minutes." };
      else bad = { form: msg.charAt(0).toUpperCase() + msg.slice(1) };
    } finally {
      busy = false;
    }
  }

  const email = (v: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim());

  function submit(e: SubmitEvent) {
    e.preventDefault();
    const next: Record<string, string> = {};
    if (mode === "signup" && !f.kitchen.trim()) next.kitchen = "Type the kitchen's name.";
    if (!email(f.email)) next.email = "Type an email address.";
    if (mode === "signup" && f.password.length < 8) next.password = "At least 8 characters.";
    if (mode === "login" && !f.password) next.password = "Type the password.";
    if (mode === "signup" && !/^\d{1,20}$/.test(f.customer.trim())) next.customer = "Digits only, as on Valio's invoice.";
    if (mode === "signup" && !isCode(f.code)) next.code = "6 digits.";
    bad = next;
    if (Object.keys(next).length) return;
    if (mode === "login") void run(() => api.login({ email: f.email.trim(), password: f.password }));
    else
      void run(() =>
        api.signup({ name: f.kitchen.trim(), email: f.email.trim(), password: f.password, customerNumber: f.customer.trim(), approvalCode: f.code }),
      );
  }

  function swap(to: "login" | "signup") {
    mode = to;
    bad = {};
    queueMicrotask(() => document.getElementById(to === "login" ? "login-email" : "login-kitchen")?.focus());
  }
</script>

<div class="door">
  <header class="door-head">
    <h1 class="v-title">Validio</h1>
    <p class="door-what" data-testid="login-what">Your purchasing agent orders from Valio Aimo through Validio, alone inside your rules and with your approval above them.</p>
  </header>

  <form class="v-form" onsubmit={submit} novalidate aria-labelledby="door-h">
    <h2 class="v-h" id="door-h">{mode === "login" ? "Log in" : "Create account"}</h2>
    {#if mode === "signup"}
      <VField id="login-kitchen" label="Kitchen name" bind:value={f.kitchen} problem={bad.kitchen} autocomplete="organization" />
    {/if}
    <VField id="login-email" label="Email" type="email" bind:value={f.email} problem={bad.email} autocomplete="email" />
    <VField
      id="login-password"
      label="Password"
      type="password"
      bind:value={f.password}
      problem={bad.password}
      hint={mode === "signup" ? "At least 8 characters" : ""}
      autocomplete={mode === "login" ? "current-password" : "new-password"}
    />
    {#if mode === "signup"}
      <VField id="login-customer" label="Valio customer number" inputmode="numeric" bind:value={f.customer} problem={bad.customer} hint="As on Valio's invoice" autocomplete="off" />
      <VField
        id="login-code"
        label="Approval code"
        inputmode="numeric"
        maxlength={6}
        class="mono"
        bind:value={f.code}
        problem={bad.code}
        hint="6 digits you choose, asked for every approval"
        autocomplete="off"
      />
    {/if}
    {#if bad.form}<p class="problem" role="alert" data-testid="login-problem">{bad.form}</p>{/if}
    <Button type="submit" class="wide" id="login-submit" data-testid="login-submit" disabled={busy}>{mode === "login" ? "Log in" : "Create account"}</Button>
    <p class="swap">
      <span>{mode === "login" ? "New kitchen?" : "Have an account?"}</span>
      <Button variant="ghost" size="sm" id="login-swap" data-testid="login-swap" onclick={() => swap(mode === "login" ? "signup" : "login")}>
        {mode === "login" ? "Create account" : "Log in"}
      </Button>
    </p>
  </form>

  <div class="or" aria-hidden="true"><span>or</span></div>

  <div class="demo">
    <Button variant="outline" class="wide" id="try-demo" data-testid="try-demo" disabled={busy} aria-describedby="demo-what" onclick={() => run(() => api.demoLogin())}>
      Try the demo kitchen
    </Button>
    <p class="demo-what" id="demo-what">A real kitchen with sample orders. <span class="nowrap">Approval code <span class="mono" data-testid="demo-code">{DEMO_CODE}</span></span></p>
  </div>
</div>

<style>
  .door {
    display: flex;
    flex-direction: column;
    gap: 24px;
    width: 100%;
    max-width: 360px;
    margin: 10vh auto 0;
  }
  .door-head .v-title {
    margin: 0 0 8px;
  }
  .door-what {
    margin: 0;
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    color: var(--v-muted);
  }
  .door :global(.wide) {
    width: 100%;
  }
  .door .v-h {
    margin: 0;
    min-height: 0;
  }
  .swap {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    margin: -8px 0 0;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  .or {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: var(--fs-cap);
    line-height: 16px;
    color: var(--v-faint);
  }
  .or::before,
  .or::after {
    content: "";
    flex: 1;
    border-top: 1px solid var(--v-line);
  }
  .demo {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .demo-what {
    margin: 0;
    text-align: center;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  .nowrap {
    white-space: nowrap;
  }
  .demo-what .mono {
    color: var(--v-fg);
  }
  .problem {
    margin: 0;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-bad-text);
  }
  @media (max-width: 760px) {
    .door {
      margin-top: 24px;
    }
    .swap {
      margin-top: -4px;
    }
  }
</style>
