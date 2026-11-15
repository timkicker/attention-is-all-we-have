<script lang="ts">
  /// The door, split: on the left the petrol panel with the wordmark and one
  /// serif sentence on what Validio is; on the right Log in or Create account,
  /// then the demo kitchen, which is a real kitchen with sample orders.
  import { goto } from "$app/navigation";
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { api, ApiError } from "$lib/api/client";
  import type { Account } from "$lib/api/types";
  import { setTitle } from "$lib/chrome.svelte";
  import { isCode, session } from "$lib/owner.svelte";
  import VField from "$lib/v/VField.svelte";
  import { forgetLive } from "$lib/live-cache";
  import { blurSwap, collapse } from "$lib/motion";
  import BusyLabel from "$lib/v2/BusyLabel.svelte";
  import Flow from "./Flow.svelte";

  /** The demo kitchen's approval code, the same live and in the fixture. */
  const DEMO_CODE = "246810";

  let mode = $state<"login" | "signup">("login");
  $effect(() => setTitle(mode === "login" ? "Log in" : "Create account"));

  const f = $state({ kitchen: "", email: "", password: "", customer: "", code: "" });
  let bad = $state<Record<string, string>>({});
  let busy = $state(false);
  /** Which button's work is running: the form's or the demo's. */
  let doing = $state<"form" | "demo" | "">("");

  function done(a: Account) {
    forgetLive();
    session.account = a;
    session.checked = true;
    void goto("/", { replaceState: true });
  }

  async function run(fn: () => Promise<Account>, what: "form" | "demo" = "form") {
    busy = true;
    doing = what;
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
      doing = "";
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

<!-- The door's entrance (plans/014): wordmark and statement rise together, the rest follows as
     a wave; the form side only fades, so it can be used from the first frame. -->
<div class="door">
  <section class="panel enter" aria-label="About Validio">
    <div class="p-mark" style:--delay="0ms"><h1 class="wordmark">Validio</h1><span class="for">for Valio Aimo customers</span></div>
    <div class="p-copy enter">
      <p class="statement" data-testid="login-what" style:--delay="0ms">Let your agent order from Valio Aimo, inside the rules you set.</p>
      <p style:--delay="120ms" style:--door-y="8px">Before every order, Validio asks Valio for the price and the stock. Your agent orders alone only below your limit; above it, the order waits for you.</p>
      <p style:--delay="160ms" style:--door-y="8px">Every decision is written to a sealed record you can read at any time.</p>
      <div class="p-flow" style:--delay="200ms" style:--door-y="6px"><Flow /></div>
    </div>
    <p class="p-foot" style:--delay="260ms" style:--door-y="0px">A service for restaurant kitchens buying from Valio Aimo.</p>
  </section>

  <section class="form-side fade-in">
    <div class="form-in">
      <form class="v-form" onsubmit={submit} novalidate aria-labelledby="door-h">
        <h2 class="door-h" id="door-h">{#key mode}<span class="dh" in:blurSwap>{mode === "login" ? "Log in" : "Create account"}</span>{/key}</h2>
        {#if mode === "signup"}
          <div class="more" in:collapse out:collapse={{ duration: 160 }}>
            <VField id="login-kitchen" label="Kitchen name" bind:value={f.kitchen} problem={bad.kitchen} autocomplete="organization" />
          </div>
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
          <div class="more" in:collapse out:collapse={{ duration: 160 }}>
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
          </div>
        {/if}
        {#if bad.form}<p class="problem" role="alert" data-testid="login-problem" in:collapse={{ duration: 200 }} out:collapse={{ duration: 140 }}>{bad.form}</p>{/if}
        <Button type="submit" class="wide" id="login-submit" data-testid="login-submit" disabled={busy}>
          <BusyLabel busy={doing === "form"} idle={mode === "login" ? "Log in" : "Create account"} working={mode === "login" ? "Logging in" : "Creating account"} />
        </Button>
        <p class="swap">
          {mode === "login" ? "New kitchen?" : "Have an account?"}
          <button type="button" class="link-btn" id="login-swap" data-testid="login-swap" onclick={() => swap(mode === "login" ? "signup" : "login")}>
            {mode === "login" ? "Create account" : "Log in"}
          </button>
        </p>
      </form>

      <div class="demo">
        <p class="d-head">Just looking?</p>
        <p class="d-text demo-what" id="demo-what">A real kitchen with sample orders. <span class="nowrap">Approval code: <span class="mono" data-testid="demo-code">{DEMO_CODE}</span></span></p>
        <Button variant="outline" class="wide" id="try-demo" data-testid="try-demo" disabled={busy} aria-describedby="demo-what" onclick={() => run(() => api.demoLogin(), "demo")}>
          <BusyLabel busy={doing === "demo"} idle="Try the demo kitchen" working="Opening the kitchen" />
        </Button>
      </div>
    </div>
  </section>
</div>

<style>
  .door {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    min-height: 100vh;
  }
  .panel {
    display: flex;
    flex-direction: column;
    padding: 48px 64px;
    background: var(--valio-band);
    color: var(--valio-band-fg);
  }
  .p-mark {
    display: flex;
    align-items: baseline;
    gap: 10px;
    margin: 0;
  }
  .wordmark {
    margin: 0;
    font-family: var(--v-script);
    font-size: 40px;
    line-height: 52px;
    font-weight: 400;
  }
  .for {
    font-size: var(--fs-meta);
    color: var(--valio-band-muted);
  }
  .p-copy {
    margin: auto 0;
    max-width: 480px;
    padding: 48px 0;
  }
  .p-copy p {
    margin: 0;
    font-size: 16px;
    line-height: 25px;
    color: var(--valio-band-muted);
  }
  .p-copy p + p {
    margin-top: 14px;
  }
  .p-copy .statement {
    margin-bottom: 28px;
    font-family: var(--v-sans);
    font-size: 32px;
    line-height: 40px;
    font-weight: 600;
    letter-spacing: var(--ls-title);
    color: var(--valio-band-fg);
  }
  .p-foot {
    margin: 0;
    font-size: var(--fs-cap);
    color: var(--valio-band-muted);
  }
  .form-side {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 48px 32px;
    background: var(--v-surface);
  }
  .form-in {
    width: 100%;
    max-width: 380px;
  }
  .form-in .door-h {
    margin: 0 0 24px;
    font-family: var(--v-sans);
    font-size: 28px;
    line-height: 36px;
    font-weight: 600;
  }
  .form-in :global(.wide) {
    width: 100%;
    height: 42px;
    font-size: var(--fs-head);
  }
  .swap {
    margin: 0;
    font-size: var(--fs-meta);
    color: var(--v-muted);
  }
  .link-btn {
    padding: 0;
    border: 0;
    background: none;
    font: inherit;
    color: var(--valio);
    text-decoration: underline;
    text-decoration-color: var(--valio-underline);
    text-underline-offset: 3px;
    cursor: pointer;
    transition:
      text-decoration-color var(--duration-fast) ease,
      transform var(--v-dur-press) var(--v-ease-out);
  }
  @media (hover: hover) and (pointer: fine) {
    .link-btn:hover {
      text-decoration-color: currentColor;
    }
  }
  .link-btn:active {
    transform: scale(0.97);
  }
  .more {
    display: flex;
    flex-direction: column;
    gap: 18px;
  }
  .dh {
    display: inline-block;
  }
  .p-flow {
    margin-top: 36px;
  }
  /* The entrance: once per load, the delays set per element in the markup. */
  .enter > :global(*) {
    animation: v-door 0.6s ease both;
    animation-delay: var(--delay, 0ms);
  }
  .p-copy.enter {
    animation: none;
  }
  @keyframes v-door {
    from {
      opacity: 0;
      transform: translateY(var(--door-y, 10px));
    }
  }
  .fade-in .form-in {
    animation: v-fade-in 400ms ease 80ms both;
  }
  @media (prefers-reduced-motion: reduce) {
    .enter > :global(*) {
      animation-name: v-fade-in;
      animation-delay: 0ms;
    }
    .p-copy.enter {
      animation: none;
    }
  }
  .demo {
    margin-top: 36px;
    padding-top: 28px;
    border-top: 1px solid var(--v-line);
  }
  .d-head {
    margin: 0;
    font-family: var(--v-sans);
    font-size: 18px;
    line-height: 26px;
    font-weight: 600;
  }
  .d-text {
    margin: 2px 0 14px;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-muted);
  }
  .demo-what .mono {
    color: var(--v-fg);
  }
  .nowrap {
    white-space: nowrap;
  }
  .problem {
    margin: 0;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-bad-text);
  }
  @media (max-width: 900px) {
    .door {
      grid-template-columns: minmax(0, 1fr);
    }
    /* On a narrow screen the form comes first in reach; the diagram waits for a wider one. */
    .p-flow {
      display: none;
    }
    .panel {
      padding: 24px 20px 28px;
    }
    .p-copy {
      padding: 28px 0 0;
    }
    .p-copy .statement {
      font-size: 26px;
      line-height: 33px;
      margin-bottom: 14px;
    }
    .p-copy p:not(.statement) {
      font-size: 15px;
      line-height: 23px;
    }
    .p-foot {
      display: none;
    }
    .form-side {
      padding: 32px 20px 48px;
      align-items: flex-start;
    }
    .form-in .door-h {
      font-size: 24px;
      line-height: 32px;
    }
    .link-btn {
      min-height: 44px;
    }
  }
</style>
