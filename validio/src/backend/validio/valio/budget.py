"""Live calls per user request. Valio asks for the few candidates only, never the catalog."""


class CallBudgetExceeded(RuntimeError):
    pass


class CallBudget:
    def __init__(self, max_ids: int = 40):
        self.max_ids = max_ids
        self.ids: set[str] = set()
        self.calls = 0
        self.per_call: list[int] = []

    @property
    def ids_sent(self) -> int:
        return len(self.ids)

    def reserve(self, ids: list[str]) -> None:
        """Refuse before any call is made when the request would ask about too many products."""
        after = self.ids | set(ids)
        if len(after) > self.max_ids:
            raise CallBudgetExceeded(
                f"{len(after)} product ids in one request, the limit is {self.max_ids}")
        self.ids = after

    def count_call(self, n_ids: int) -> None:
        self.calls += 1
        self.per_call.append(n_ids)
