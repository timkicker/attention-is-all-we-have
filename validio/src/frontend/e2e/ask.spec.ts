import { test, expect } from "@playwright/test";
import { askSummary } from "../src/lib/ask";
import type { SupplyRequest } from "../src/lib/api/types";

// The ask dialog's summary lines, as a plain function: no browser needed.
const blocked = (summary: string) =>
  ({
    id: "R-1",
    status: "blocked",
    title: "20 kg of lactose-free butter by Mon 16 Nov",
    text: "20 kg of butter by Monday",
    liveChecked: { calls: 0, ids: 0, idsPerCall: [] },
    lines: [],
    decision: { outcome: "blocked", ruleIds: [], summary },
  }) as unknown as SupplyRequest;

test("a blocked summary that names itself gets no second prefix", () => {
  expect(askSummary(blocked("Blocked: butter is outside the Spend Pass's product groups."))).toEqual([
    "Agent asked Validio for 20 kg of lactose-free butter by Mon 16 Nov.",
    "Blocked: butter is outside the Spend Pass's product groups.",
  ]);
});

test("a blocked summary keeps its own capital after the prefix", () => {
  expect(askSummary(blocked("Valio has no lactose-free parmesan.")).at(-1)).toBe("Blocked: Valio has no lactose-free parmesan.");
});
