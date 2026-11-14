<script lang="ts">
  /// Kitchen: name and delivery address, edited in place. The customer
  /// number is Valio's and stays as typed at sign-up.
  import { Button } from "@arlen/ui-kit/components/ui/button";
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { ApiError } from "$lib/api/client";
  import { bump } from "$lib/chrome.svelte";
  import { refreshAccount, settingsApi, type Settings } from "$lib/settings";
  import VValueRow from "$lib/v/VValueRow.svelte";
  import VField from "$lib/v/VField.svelte";

  let { s, onsaved }: { s: Settings; onsaved: (s: Settings) => void } = $props();

  let editing = $state(false);
  let saving = $state(false);
  const f = $state({ name: "", address: "" });
  let bad = $state<{ name?: string; form?: string }>({});

  $effect(() => {
    if (f.name.trim() && bad.name) bad = { ...bad, name: undefined };
  });
  function edit() {
    f.name = s.kitchen.name;
    f.address = s.kitchen.deliveryAddress;
    bad = {};
    editing = true;
  }
  async function save(e: SubmitEvent) {
    e.preventDefault();
    if (!f.name.trim()) {
      bad = { name: "Type a name." };
      return;
    }
    saving = true;
    try {
      const next = await settingsApi.kitchen({ name: f.name, deliveryAddress: f.address });
      onsaved(next);
      await refreshAccount(next).catch(() => {});
      editing = false;
      bump();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      bad = err instanceof ApiError && /name/i.test(msg) ? { name: "Type a name." } : { form: msg };
    } finally {
      saving = false;
    }
  }
</script>

{#if editing}
  <form class="edit" onsubmit={save} novalidate data-testid="kitchen-form">
    <Section class="v-card">
      <div class="in"><VField id="f-kitchen-name" label="Name" bind:value={f.name} problem={bad.name} autocomplete="organization" /></div>
      <VValueRow label="Valio customer number" value={s.kitchen.customerNumber || "Not set"} />
      <div class="in"><VField id="f-kitchen-address" label="Delivery address" bind:value={f.address} autocomplete="street-address" /></div>
    </Section>
    {#if bad.form}<p class="problem" role="alert">{bad.form}</p>{/if}
    <div class="acts">
      <Button type="submit" data-testid="kitchen-save" disabled={saving}>Save</Button>
      <Button variant="ghost" onclick={() => (editing = false)}>Cancel</Button>
    </div>
  </form>
{:else}
  <Section class="v-card">
    <VValueRow label="Name" value={s.kitchen.name} testid="kitchen-name" />
    <VValueRow label="Valio customer number" value={s.kitchen.customerNumber || "Not set"} testid="kitchen-customer" />
    <VValueRow label="Delivery address" value={s.kitchen.deliveryAddress || "Not set"} testid="kitchen-address" />
  </Section>
  <div class="acts"><Button variant="outline" data-testid="kitchen-edit" onclick={edit}>Edit</Button></div>
{/if}

<style>
  .edit {
    display: flex;
    flex-direction: column;
  }
  .in {
    padding: 12px 16px;
  }
  .in :global(.vf) {
    max-width: 360px;
  }
  .acts {
    display: flex;
    gap: 8px;
    margin-top: 16px;
  }
  .problem {
    margin: 12px 0 0;
    font-size: var(--fs-meta);
    line-height: var(--lh-meta);
    color: var(--v-bad-text);
  }
</style>
