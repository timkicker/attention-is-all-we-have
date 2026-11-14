<script lang="ts">
  /// Login and approval code: email, password and the 6 digit code, each
  /// changed in place under its own row. A demo kitchen has none of its own.
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { ApiError } from "$lib/api/client";
  import { isCode, owner } from "$lib/owner.svelte";
  import { settingsApi, type Settings } from "$lib/settings";
  import VField from "$lib/v/VField.svelte";

  let { s, demo, onsaved }: { s: Settings; demo: boolean; onsaved: (s: Settings) => void } = $props();

  type Key = "email" | "password" | "code";
  let open = $state<Key | null>(null);
  let done = $state<Key | null>(null);
  let saving = $state(false);
  const f = $state({ current: "", next: "" });
  let bad = $state<{ current?: string; next?: string; form?: string }>({});

  const ROWS: { key: Key; label: string }[] = [
    { key: "email", label: "Email" },
    { key: "password", label: "Password" },
    { key: "code", label: "Approval code" },
  ];
  const value = (k: Key) => (demo ? (k === "code" ? "Fixed" : "None") : k === "email" ? (s.login.email ?? "None") : "Set");

  function change(k: Key) {
    open = k;
    done = null;
    f.current = f.next = "";
    bad = {};
  }
  async function save(e: SubmitEvent) {
    e.preventDefault();
    if (!open || saving) return;
    const k = open;
    const next: typeof bad = {};
    if (k === "code") {
      if (!isCode(f.current)) next.current = "Type the 6 digit code.";
      if (!isCode(f.next)) next.next = "Six digits.";
    } else {
      if (!f.current) next.current = "Type your password.";
      if (k === "email" && !/^\S+@\S+\.\S+$/.test(f.next)) next.next = "Type an email.";
      if (k === "password" && f.next.length < 8) next.next = "At least 8 characters.";
    }
    bad = next;
    if (Object.keys(next).length) return;
    saving = true;
    try {
      if (k === "code") {
        await settingsApi.approvalCode({ current: f.current, next: f.next });
        owner.code = "";
      } else onsaved(await settingsApi.login({ currentPassword: f.current, ...(k === "email" ? { email: f.next } : { password: f.next }) }));
      open = null;
      done = k;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (err instanceof ApiError && err.status === 403) bad = { current: k === "code" ? "That code is not right." : "That password is not right." };
      else if (err instanceof ApiError && err.status === 409) bad = { next: "Taken." };
      else bad = { form: msg };
    } finally {
      saving = false;
    }
  }
</script>

<Section class="v-card">
  {#each ROWS as r (r.key)}
    <div class="lrow" data-testid="login-{r.key}">
      <span class="lbl">{r.label}</span>
      <span class="val">{value(r.key)}{#if done === r.key}<span class="saved" role="status"> Changed</span>{/if}</span>
      {#if !demo && open !== r.key}
        <Button variant="outline" data-testid="login-change-{r.key}" onclick={() => change(r.key)}>Change</Button>
      {/if}
    </div>
    {#if open === r.key}
      <form class="in" onsubmit={save} novalidate data-testid="login-form-{r.key}">
        {#if r.key === "code"}
          <VField id="f-code-current" label="Current code" bind:value={f.current} problem={bad.current} inputmode="numeric" maxlength={6} autocomplete="one-time-code" class="code mono" />
          <VField id="f-code-next" label="New code" bind:value={f.next} problem={bad.next} inputmode="numeric" maxlength={6} autocomplete="off" class="code mono" />
        {:else}
          {#if r.key === "email"}
            <VField id="f-email" label="New email" type="email" bind:value={f.next} problem={bad.next} autocomplete="email" />
          {:else}
            <VField id="f-password" label="New password" type="password" bind:value={f.next} problem={bad.next} autocomplete="new-password" />
          {/if}
          <VField id="f-current-password" label="Current password" type="password" bind:value={f.current} problem={bad.current} autocomplete="current-password" />
        {/if}
        {#if bad.form}<p class="problem" role="alert">{bad.form}</p>{/if}
        <div class="acts">
          <Button type="submit" data-testid="login-save" disabled={saving}>Save</Button>
          <Button variant="ghost" onclick={() => (open = null)}>Cancel</Button>
        </div>
      </form>
    {/if}
  {/each}
</Section>

<style>
  .lrow {
    display: grid;
    grid-template-columns: 184px minmax(0, 1fr) auto;
    align-items: center;
    column-gap: 12px;
    min-height: 56px;
    padding: 12px 16px;
  }
  .lbl {
    font-size: var(--fs-meta);
    line-height: var(--lh-body);
  }
  .val {
    min-width: 0;
    overflow-wrap: anywhere;
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    font-weight: 500;
  }
  .saved {
    font-size: var(--fs-meta);
    font-weight: 400;
    color: var(--v-muted);
  }
  .in {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 12px 16px 16px;
  }
  .in :global(.vf) {
    max-width: 360px;
  }
  .in :global(.code) {
    max-width: 160px;
    font-variant-numeric: tabular-nums;
  }
  .acts {
    display: flex;
    gap: 8px;
    margin-top: 4px;
  }
  .problem {
    margin: 0;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-bad-text);
  }
  @media (max-width: 760px) {
    .lrow {
      grid-template-columns: minmax(0, 1fr) auto;
      row-gap: 4px;
    }
    .lbl {
      font-size: 14px;
      line-height: 20px;
      grid-column: 1;
      color: var(--v-muted);
    }
    .val {
      grid-column: 1;
    }
    .lrow :global([data-slot="button"]) {
      grid-column: 2;
      grid-row: 1 / span 2;
    }
  }
</style>
