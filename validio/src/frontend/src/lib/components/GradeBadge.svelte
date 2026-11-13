<script lang="ts">
  import { Badge } from "@arlen/ui-kit/components/ui/badge";
  import type { Fact } from "$lib/api/types";
  import { GRADE, day } from "$lib/format";

  let { fact }: { fact: Pick<Fact, "grade" | "until"> } = $props();
  const g = $derived(GRADE[fact.grade]);
</script>

<Badge variant={g.variant} data-grade={fact.grade}>
  {g.label}{fact.grade === "attested_until" && fact.until ? ` ${day(fact.until)}` : ""}
</Badge>
