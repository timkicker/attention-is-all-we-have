<script lang="ts">
  /// Kitchen: the name and the delivery address change in place; the Valio
  /// customer number stays as typed at sign-up.
  import { ApiError } from "$lib/api/client";
  import { bump } from "$lib/chrome.svelte";
  import { ListSection } from "$lib/v2";
  import { refreshAccount, settingsApi, type Settings } from "$lib/settings";
  import VField from "$lib/v/VField.svelte";
  import EditRow from "./EditRow.svelte";
  import Form from "./Form.svelte";

  let { s, onsaved }: { s: Settings; onsaved: (s: Settings) => void } = $props();

  type Key = "name" | "address";
  let open = $state<Key | null>(null);
  let done = $state<Key | null>(null);
  let busy = $state(false);
  let text = $state("");
  let problem = $state("");
  let formProblem = $state("");

  function change(k: Key) {
    open = k;
    done = null;
    text = k === "name" ? s.kitchen.name : s.kitchen.deliveryAddress;
    problem = formProblem = "";
  }
  $effect(() => {
    if (text.trim() && problem) problem = "";
  });
  async function save() {
    if (!open || busy) return;
    const k = open;
    if (k === "name" && !text.trim()) {
      problem = "Type a name.";
      document.getElementById("f-kitchen-name")?.focus();
      return;
    }
    busy = true;
    try {
      const next = await settingsApi.kitchen({
        name: k === "name" ? text : s.kitchen.name,
        deliveryAddress: k === "address" ? text : s.kitchen.deliveryAddress,
      });
      onsaved(next);
      await refreshAccount(next).catch(() => {});
      bump();
      open = null;
      done = k;
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (e instanceof ApiError && e.status === 422 && k === "name") problem = "Type a name.";
      else formProblem = msg;
    } finally {
      busy = false;
    }
  }
</script>

<ListSection id="kitchen" title="Kitchen">
  <EditRow id="kitchen-name" label="Name" value={s.kitchen.name} description={done === "name" ? "Saved" : undefined} open={open === "name"} onchange={() => change("name")}>
    <Form id="kitchen-name" problem={formProblem} {busy} onsave={save} oncancel={() => (open = null)}>
      <VField id="f-kitchen-name" label="Kitchen name" bind:value={text} {problem} autocomplete="organization" />
    </Form>
  </EditRow>
  <EditRow id="kitchen-customer" label="Valio customer number" value={s.kitchen.customerNumber || "Not set"} />
  <EditRow
    id="kitchen-address"
    label="Delivery address"
    value={s.kitchen.deliveryAddress || "Not set"}
    description={done === "address" ? "Saved" : undefined}
    open={open === "address"}
    onchange={() => change("address")}
  >
    <Form id="kitchen-address" problem={formProblem} {busy} onsave={save} oncancel={() => (open = null)}>
      <VField id="f-kitchen-address" label="Delivery address" bind:value={text} autocomplete="street-address" />
    </Form>
  </EditRow>
</ListSection>
