<script lang="ts">
  /// The Inbox's setup list, on top until all three are done: Kitchen,
  /// Rules, Connect agent. Each row leads to where it is done.
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { session } from "$lib/owner.svelte";
  import VStatusRow from "$lib/v/VStatusRow.svelte";

  const setup = $derived(session.account?.setup);
  const STEPS = [
    { key: "kitchen", title: "Kitchen", href: "/settings/kitchen" },
    { key: "rules", title: "Rules", href: "/agent#rules" },
    { key: "agent", title: "Connect agent", href: "/agent" },
  ] as const;
  const count = $derived(setup ? STEPS.filter((s) => setup[s.key]).length : 0);
</script>

{#if setup && !setup.done}
  <section class="sec" aria-labelledby="h-setup" data-testid="setup">
    <h2 class="v-h" id="h-setup">Set up <em>{count} of {STEPS.length}</em></h2>
    <Section class="v-card">
      {#each STEPS as s (s.key)}
        <VStatusRow
          href={s.href}
          testid="setup-{s.key}"
          id="setup-{s.key}"
          pill={setup[s.key] ? { label: "Done", tone: "ok" } : { label: "To do", tone: "wait" }}
          title={s.title}
        />
      {/each}
    </Section>
  </section>
{/if}
