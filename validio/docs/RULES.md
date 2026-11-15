# Hard Lines

The rules that decide every order are in `src/backend/validio/policy/policies.cedar` and the context they read is typed in `schema.cedarschema` next to it. This page lists both. `tests/test_rules_doc.py` compares it with the Cedar files on every test run and fails when a rule id, its effect, its action or its inputs differ. It also fails when a context field is missing here.

## Rules

| Rule | Effect | Action | Decides | Inputs | Why the model cannot override it |
|:---|:---|:---|:---|:---|:---|
| `auto-order` | permit | `PlaceOrder` | the agent may order automatically. Everything it needs must be attested, the diet kept, a substitute on Valio's list and allowed by the Spend Pass, a split inside its extra cost limit and the total inside the auto limit | `categoryAllowed` `salesBlock` `cutoffOk` `quantityAttested` `quantityCovers` `deliveryInTime` `dietUnchecked` `driftFlag` `isSubstitute` `onValioList` `substitutesAllowed` `isSplit` `splitExtraBp` `splitMaxExtraBp` `splitSubstitutesAllowed` `totalCents` `autoLimitCents` | every input is computed by Validio from Valio's answers and the signed Spend Pass. The total is recomputed from Valio's price, so a price the agent names changes nothing |
| `ask-human` | permit | `Escalate` | when ordering automatically is not allowed, a person may still be asked, as long as the category is in the Spend Pass, Valio has no sales block, Valio gives a delivery line and the total is under the hard cap | `categoryAllowed` `salesBlock` `hasDeliveryLine` `totalCents` `hardCapCents` | asking only puts the order in front of the owner. The order is placed after the owner taps approve and Validio has asked Valio again |
| `never-break-diet` | forbid | every action | blocks ordering and asking when a diet rule of the request or Spend Pass is contradicted by Valio's own data | `dietContradicted` | the grade comes from the claim check over Valio's master data. Supplier text can only lower it and the reader's output never reaches it |
| `never-over-hard-cap` | forbid | every action | blocks ordering and asking above the hard cap, even with approval | `totalCents` `hardCapCents` | the hard cap is a signed field of the Spend Pass and a forbid in Cedar always wins over a permit |

Validio first asks Cedar about `PlaceOrder`. If that is allowed the outcome is "ordered automatically". Otherwise it asks about `Escalate` and an allowed answer means "waiting for you". When neither is allowed the line is blocked and its sentence says why. With several lines in one order the strictest outcome counts for the whole order.

A diet named in the request's text ("lactose-free milk") also narrows the candidates before Valio is asked: a product without that claim is not one. The diet of the Spend Pass narrows them only where Valio's own data breaks it (the claim check says contradicted, or it lists milk with no lactose-free claim). A product Valio's data says nothing about stays a candidate, its grade is unchecked, so `dietUnchecked` keeps it from ordering automatically and `ask-human` sends it to the owner (`orders/supply.py`, `matching/need.py`).

The Rules' per week limit is not a Cedar rule. It is the only limit that counts orders already placed, so Validio checks it before it asks Cedar: when the orders this Spend Pass placed plus the new one would go over it, the order is blocked under the id `never-over-week-cap`. The automatic and approval limits always hold per order.

The context of all four rules contains only whole numbers and yes or no values that Validio fills itself, so neither model output nor supplier text can be put into it. Every field is required by the schema, so a typo in a rule fails validation when the app starts and can never turn into a silent change. A Spend Pass that does not show a limit counts as a limit of zero and an undisclosed diet counts as unchecked, which means a pass that shows too little can never order automatically.

## Context fields

Money is in whole cents. Percentages are in basis points, so 5 % is 500.

| Field | Meaning | Filled from |
|:---|:---|:---|
| `totalCents` | the total of the order | Valio's net price times the amount, recomputed by Validio |
| `autoLimitCents` | how much the agent may spend automatically | Spend Pass, 0 when not shown |
| `hardCapCents` | the most anyone may spend, approval included | Spend Pass, 0 when not shown |
| `dietContradicted` | a required diet claim is disproved by another field, or Valio lists an allergen the Rules say never | Fact Grade of the claim check; Valio's allergen data against the pass's `neverContains` |
| `dietUnchecked` | a required diet claim is neither attested nor consistent, or a "never" allergen cannot be ruled out | Fact Grade of the claim check, true when the Spend Pass hides the diet; true when the product may contain a "never" allergen, has no allergen data, or the pass names an allergen word Validio does not know |
| `quantityAttested` | Valio gives a real stock number | availability answer (999999 from a Terminal product does not count) |
| `quantityCovers` | the attested stock covers the amount ordered | availability answer, converted to the sales unit |
| `deliveryInTime` | the earliest delivery is on or before the deadline | availability answer and the earlier of the signed deadline and the request |
| `hasDeliveryLine` | Valio gives at least one delivery line for the product, so a person can approve it at all | availability answer |
| `cutoffOk` | Valio's order cut-off has not passed | availability answer and the demo clock |
| `isSubstitute` | the line replaces the product that was asked for | Safe Swap |
| `onValioList` | the substitute is on Valio's own substitute list | Valio's product file |
| `substitutesAllowed` | the Spend Pass allows listed substitutes | Spend Pass |
| `splitSubstitutesAllowed` | the Spend Pass allows listed substitutes inside a split | Spend Pass |
| `isSplit` | the line is filled from more than one product | Split Fill |
| `splitExtraBp` | how much more the split costs than the product asked for | Split Fill, rounded up |
| `splitMaxExtraBp` | the extra cost the Spend Pass allows for a split | Spend Pass |
| `categoryAllowed` | the product group is one the Spend Pass lists, or the pass lists all groups (`"categories": ["*"]`, the default); an empty or missing list allows none. The owner narrows the groups on Rules | product file and Spend Pass |
| `salesBlock` | Valio blocks the product from sale | availability answer |
| `isRenewal` | the line comes from a Steady Order | Steady Orders |
| `driftFlag` | Drift Watch flagged the line before renewal | Drift Watch |

## Which price counts

Every limit (automatic, waiting, blocked above, per week, a request's budget) is compared with Valio's catalog price per sales unit before VAT (`catalogPrice` in the price answer, `valio/models.py`). Valio's answer also says whether a customer-specific net price exists (`netPriceFound`), but the test API gives no net price, so Validio does not use one. The Rules pages say "before VAT" next to the money.
