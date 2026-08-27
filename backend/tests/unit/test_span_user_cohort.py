"""``tag_span_with_user`` (backend/app/core/security.py).

Every authenticated request routes through ``resolve_user_by_jwt_payload``,
which names the caller on the server span so a specific tester's traces are
findable in Tempo by identity instead of by IP (NAT, VPN and a router
rescheduled onto an untrusted address all break the IP route).

Three regressions worth pinning, in order of what they'd cost:

- the sciper must never reach the span. Traces leave the namespace for a
  shared collector, and an institutional id identifies a person across every
  EPFL system while ``User.id`` means nothing without our database;
- an empty ``BETA_COHORTS`` — the default in every environment but dev —
  must not stamp ``beta_cohort=""`` on every user;
- a user outside every cohort must still get their ``user.id``.
"""

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from app.core import security
from app.models.user import User

SCIPER = "123456"


def _tag_inside_a_recorded_span(user: User):
    """Run the function under test inside a real recording span and return
    the finished span's attributes.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    with provider.get_tracer(__name__).start_as_current_span("GET /v1/session"):
        security.tag_span_with_user(user)
    return exporter.get_finished_spans()[0].attributes


def _tester(user_id: int) -> User:
    return User(id=user_id, institutional_id=SCIPER, email="tester@epfl.ch")


def test_span_carries_our_id_never_the_sciper(monkeypatch):
    monkeypatch.setattr(security.settings, "BETA_COHORTS", "team-a:41,58;team-b:77")
    attributes = _tag_inside_a_recorded_span(_tester(41))
    assert attributes["user.id"] == "41"
    assert attributes["beta_cohort"] == "team-a"
    assert SCIPER not in attributes.values(), (
        "the institutional id identifies a person across every EPFL system "
        "and must not reach the shared collector"
    )


def test_user_outside_every_cohort_still_carries_identity(monkeypatch):
    monkeypatch.setattr(security.settings, "BETA_COHORTS", "team-a:41")
    attributes = _tag_inside_a_recorded_span(_tester(999))
    assert attributes["user.id"] == "999"
    assert "beta_cohort" not in attributes


def test_unconfigured_cohorts_tag_nobody(monkeypatch):
    """The default everywhere but dev: "".split(";") yields [""], which a
    naive parse turns into an empty cohort name for everyone.
    """
    monkeypatch.setattr(security.settings, "BETA_COHORTS", "")
    attributes = _tag_inside_a_recorded_span(_tester(41))
    assert attributes["user.id"] == "41"
    assert "beta_cohort" not in attributes
