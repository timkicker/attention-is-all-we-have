"""Adversarial tests (lane G). Hypothesis runs derandomized and without its example database, so a run
leaves no files behind and fails the same way every time."""

from hypothesis import HealthCheck, settings

settings.register_profile("validio", derandomize=True, database=None, deadline=None, max_examples=150,
                          suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
settings.load_profile("validio")
