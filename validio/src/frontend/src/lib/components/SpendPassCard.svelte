<script lang="ts">
  // What the owner allowed, as far as the agent showed it. Hidden fields are
  // named but never shown.
  import { Section } from "@arlen/ui-kit/components/ui/section";
  import { Row } from "@arlen/ui-kit/components/ui/row";
  import { Badge } from "@arlen/ui-kit/components/ui/badge";
  import type { SpendPass } from "$lib/api/types";
  import { FIELD, day, dayTime, money } from "$lib/format";

  let { pass }: { pass: SpendPass } = $props();
</script>

<Section label="Spend Pass {pass.id}" id="spend-pass">
  <Row label="Orders alone up to" description="The agent may spend this without asking anyone.">
    {#snippet control()}<span class="v num" id="pass-auto">{money(pass.autoLimitCents)}</span>{/snippet}
  </Row>
  <Row label="Hard cap" description="Nothing above this, not even with approval.">
    {#snippet control()}<span class="v num" id="pass-cap">{money(pass.hardCapCents)}</span>{/snippet}
  </Row>
  <Row label="Diet">
    {#snippet control()}<span class="v">{pass.diet?.join(", ")}</span>{/snippet}
  </Row>
  <Row label="Deliver by">
    {#snippet control()}<span class="v">{day(pass.deliverBy)}</span>{/snippet}
  </Row>
  <Row label="Valid until">
    {#snippet control()}<span class="v">{dayTime(pass.validTo)}</span>{/snippet}
  </Row>
  <Row label="Signed by the kitchen" description="{pass.issuer}, held by {pass.holder}. The agent showed {pass.disclosed.map((k) => FIELD[k] ?? k).join(', ').replace(/, ([^,]*)$/, ' and $1')}.">
    {#snippet control()}
      {#each pass.hidden as h (h)}
        <Badge variant="outline">{FIELD[h] ?? h} hidden</Badge>
      {/each}
    {/snippet}
  </Row>
</Section>

<style>
  .v {
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--foreground);
    white-space: nowrap;
  }
</style>
