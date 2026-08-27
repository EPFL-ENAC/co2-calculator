"""``tag_span_with_user`` (backend/app/core/security.py).

Every authenticated request routes through ``resolve_user_by_jwt_payload``,
which names the caller on the server span so a specific tester's traces are
findable in Tempo by identity instead of by IP (NAT, VPN and a router
rescheduled onto an untrusted address all break the IP route).

The regressions worth pinning are the two silent ones: an empty
``BETA_COHORTS`` — the default in every environment but dev — must not stamp
``beta_cohort=""`` on every user, and a user outside the list must still get
their ``user.id`` rather than nothing at all.
"""

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from app.core import security


def _tag_inside_a_recorded_span(institutional_id: str):
    """Run the function under test inside a real recording span and return
    the finished span's attributes.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    with provider.get_tracer(__name__).start_as_current_span("GET /v1/session"):
        security.tag_span_with_user(institutional_id)
    return exporter.get_finished_spans()[0].attributes


def test_cohort_member_carries_group_and_identity(monkeypatch):
    monkeypatch.setattr(
        security.settings,
        "BETA_COHORTS",
        "team-a:123456,234567;team-b:345678",
    )
    attributes = _tag_inside_a_recorded_span("234567")
    assert attributes["user.id"] == "234567"
    assert attributes["beta_cohort"] == "team-a"


def test_user_outside_every_cohort_still_carries_identity(monkeypatch):
    monkeypatch.setattr(security.settings, "BETA_COHORTS", "team-a:123456")
    attributes = _tag_inside_a_recorded_span("999999")
    assert attributes["user.id"] == "999999"
    assert "beta_cohort" not in attributes


def test_unconfigured_cohorts_tag_nobody(monkeypatch):
    """The default everywhere but dev: "".split(";") yields [""], which a
    naive parser turns into an empty cohort name for everyone.
    """
    monkeypatch.setattr(security.settings, "BETA_COHORTS", "")
    attributes = _tag_inside_a_recorded_span("123456")
    assert attributes["user.id"] == "123456"
    assert "beta_cohort" not in attributes
