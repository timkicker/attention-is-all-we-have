// Hard Lines. Validio fills the context from Valio's data and the Spend Pass only.
// Money is whole cents, percentages are basis points (5 % = 500). A forbid always wins.
// Cedar has no third outcome: "ask a person" is the second action Escalate.

@id("auto-order")
permit(principal is Agent, action == Action::"PlaceOrder", resource is Product)
when {
  context.categoryAllowed && !context.salesBlock && context.cutoffOk
  && context.quantityAttested && context.quantityCovers && context.deliveryInTime
  && !context.dietUnchecked && !context.driftFlag
  && (!context.isSubstitute || (context.onValioList && context.substitutesAllowed))
  && (!context.isSplit || context.splitExtraBp <= context.splitMaxExtraBp)
  && (!(context.isSplit && context.isSubstitute) || context.splitSubstitutesAllowed)
  && context.totalCents <= context.autoLimitCents
};

@id("ask-human")
permit(principal is Agent, action == Action::"Escalate", resource is Product)
when { context.categoryAllowed && !context.salesBlock && context.totalCents <= context.hardCapCents };

@id("never-break-diet")
forbid(principal, action, resource)
when { context.dietContradicted };

@id("never-over-hard-cap")
forbid(principal, action, resource)
when { context.totalCents > context.hardCapCents };
