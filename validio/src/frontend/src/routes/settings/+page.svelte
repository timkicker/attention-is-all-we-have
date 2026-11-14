<script lang="ts">
  /// /settings: on the phone the list of sections, each row with what it holds
  /// now; on the desk the first section opens beside the list.
  import { goto } from "$app/navigation";
  import { onMount } from "svelte";
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { chrome } from "$lib/chrome.svelte";
  import { DIETS, settingsApi, type Settings } from "$lib/settings";
  import { theme } from "$lib/theme.svelte";
  import VHead from "$lib/v/VHead.svelte";
  import VValueRow from "$lib/v/VValueRow.svelte";
  import { logOut, SECTIONS, type SectionId } from "./sections";

  $effect(() => {
    if (!chrome.phone) void goto("/settings/kitchen", { replaceState: true });
  });

  let s = $state<Settings | undefined>();
  onMount(() => {
    settingsApi.get().then((v) => (s = v), () => {});
  });
  const MODE = { system: "System", light: "Light", dark: "Dark" } as const;
  const now: Record<SectionId, () => string | undefined> = {
    kitchen: () => s?.kitchen.name,
    diet: () => (s ? DIETS.filter((d) => s!.diet.includes(d.id)).map((d) => d.label).join(", ") || "None" : undefined),
    login: () => s?.login.email ?? undefined,
    theme: () => MODE[theme.mode],
  };
</script>

{#if chrome.phone}
  <VHead title="Settings" />
  <div class="blocks">
    <Section class="v-card">
      {#each SECTIONS as x (x.id)}
        <VValueRow label={x.label} value={now[x.id]()} href="/settings/{x.id}" testid="set-row-{x.id}" />
      {/each}
      <button type="button" class="out" data-testid="log-out" onclick={logOut}>Log out</button>
    </Section>
  </div>
{/if}

<style>
  .out {
    display: flex;
    align-items: center;
    width: 100%;
    min-height: 56px;
    padding: 12px 16px;
    margin: 0;
    border: 0;
    border-top: 1px solid var(--v-line);
    border-end-start-radius: max(0px, calc(var(--radius-card) - 1px));
    border-end-end-radius: max(0px, calc(var(--radius-card) - 1px));
    background: none;
    font: inherit;
    font-size: var(--fs-body);
    line-height: var(--lh-body);
    color: var(--v-bad-text);
    text-align: left;
    cursor: pointer;
  }
  .out:hover {
    background: var(--v-tint-hover);
  }
</style>
