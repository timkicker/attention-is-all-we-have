<script lang="ts">
  /// Login: email and password, each changed under its own row with the
  /// current password. A demo kitchen has no login of its own: one row.
  import { ApiError } from "$lib/api/client";
  import { ListSection } from "$lib/v2";
  import { settingsApi, type Settings } from "$lib/settings";
  import VField from "$lib/v/VField.svelte";
  import EditRow from "./EditRow.svelte";
  import Form from "./Form.svelte";

  let { s, demo, onsaved }: { s: Settings; demo: boolean; onsaved: (s: Settings) => void } = $props();

  type Key = "email" | "password";
  let open = $state<Key | null>(null);
  let done = $state<Key | null>(null);
  let busy = $state(false);
  const f = $state({ next: "", current: "" });
  let bad = $state<{ next?: string; current?: string; form?: string }>({});

  function change(k: Key) {
    open = k;
    done = null;
    f.next = f.current = "";
    bad = {};
  }
  async function save() {
    if (!open || busy) return;
    const k = open;
    const next: typeof bad = {};
    if (k === "email" && !/^\S+@\S+\.\S+$/.test(f.next)) next.next = "Type an email, like chef@kitchen.fi.";
    if (k === "password" && f.next.length < 8) next.next = "At least 8 characters.";
    if (!f.current) next.current = "Type your current password.";
    bad = next;
    if (next.next || next.current) {
      document.getElementById(next.next ? `f-${k}` : "f-current-password")?.focus();
      return;
    }
    busy = true;
    try {
      onsaved(await settingsApi.login({ currentPassword: f.current, ...(k === "email" ? { email: f.next } : { password: f.next }) }));
      open = null;
      done = k;
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (e instanceof ApiError && e.status === 403) bad = { current: "That password is not right." };
      else if (e instanceof ApiError && e.status === 409) bad = { next: "Another kitchen uses this email." };
      else bad = { form: msg };
    } finally {
      busy = false;
    }
  }
</script>

<ListSection id="login" title="Login">
  {#if demo}
    <EditRow id="login-demo" label="Login" value="None, this is a demo kitchen" />
  {:else}
    <EditRow id="login-email" label="Email" value={s.login.email ?? "Not set"} description={done === "email" ? "Saved" : undefined} saved={done === "email"} open={open === "email"} onchange={() => change("email")}>
      <Form id="login-email" problem={bad.form} {busy} onsave={save} oncancel={() => (open = null)}>
        <VField id="f-email" label="New email" type="email" bind:value={f.next} problem={bad.next} autocomplete="email" />
        <VField id="f-current-password" label="Current password" type="password" bind:value={f.current} problem={bad.current} autocomplete="current-password" />
      </Form>
    </EditRow>
    <EditRow id="login-password" label="Password" value="Set" description={done === "password" ? "Saved" : undefined} saved={done === "password"} open={open === "password"} onchange={() => change("password")}>
      <Form id="login-password" problem={bad.form} {busy} onsave={save} oncancel={() => (open = null)}>
        <VField id="f-password" label="New password" type="password" bind:value={f.next} problem={bad.next} autocomplete="new-password" />
        <VField id="f-current-password" label="Current password" type="password" bind:value={f.current} problem={bad.current} autocomplete="current-password" />
      </Form>
    </EditRow>
  {/if}
</ListSection>
