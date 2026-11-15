<script lang="ts">
  /// Approval code: the 6 digits asked when the owner approves an order or
  /// saves the rules. A demo kitchen keeps its demo code.
  import { ApiError } from "$lib/api/client";
  import { ListSection } from "$lib/v2";
  import { isCode, owner, session } from "$lib/owner.svelte";
  import { settingsApi } from "$lib/settings";
  import VField from "$lib/v/VField.svelte";
  import EditRow from "./EditRow.svelte";
  import Form from "./Form.svelte";

  let { demo }: { demo: boolean } = $props();

  let open = $state(false);
  let done = $state(false);
  let busy = $state(false);
  const f = $state({ current: "", next: "" });
  let bad = $state<{ current?: string; next?: string; form?: string }>({});

  function change() {
    open = true;
    done = false;
    f.current = f.next = "";
    bad = {};
  }
  async function save() {
    if (busy) return;
    const next: typeof bad = {};
    if (!isCode(f.current)) next.current = "Type your current 6-digit code.";
    if (!isCode(f.next)) next.next = "Six digits, like 482913.";
    bad = next;
    if (next.current || next.next) {
      document.getElementById(next.current ? "f-code-current" : "f-code-next")?.focus();
      return;
    }
    busy = true;
    try {
      await settingsApi.approvalCode({ current: f.current, next: f.next });
      owner.code = "";
      open = false;
      done = true;
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (e instanceof ApiError && e.status === 403) bad = { current: "That code is not right." };
      else if (e instanceof ApiError && e.status === 429) bad = { current: "Too many wrong codes. Try again in 15 minutes." };
      else bad = { form: msg };
    } finally {
      busy = false;
    }
  }
</script>

<ListSection id="code" title="Approval code">
  {#if demo}
    <EditRow id="code" label="Code" value={session.account?.demoCode ?? ""} description="The demo code, asked when you approve or save rules" />
  {:else}
    <EditRow id="code" label="Code" value="Set" description={done ? "Saved" : "Asked when you approve or save rules"} saved={done} {open} onchange={change}>
      <Form id="code" problem={bad.form} {busy} onsave={save} oncancel={() => (open = false)}>
        <VField id="f-code-current" label="Current code" bind:value={f.current} problem={bad.current} inputmode="numeric" maxlength={6} autocomplete="one-time-code" class="code-in num" />
        <VField id="f-code-next" label="New code" bind:value={f.next} problem={bad.next} inputmode="numeric" maxlength={6} autocomplete="off" class="code-in num" />
      </Form>
    </EditRow>
  {/if}
</ListSection>
