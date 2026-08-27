"""``tag_span_with_user`` (backend/app/core/security.py).

Every authenticated request routes through ``resolve_user_by_jwt_payload``,
which names the caller on the server span so a specific tester's traces are
findable in Tempo by identity instead of by IP (NAT, VPN and a router
rescheduled onto an untrusted address all break the IP route).

The regression worth pinning is which identifier lands there: traces leave the
namespace for a shared collector, and an institutional id identifies a person
across every EPFL system while ``User.id`` means nothing without our database.
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


def test_span_carries_our_id_never_the_sciper():
    attributes = _tag_inside_a_recorded_span(
        User(id=41, institutional_id=SCIPER, email="tester@epfl.ch")
    )
    assert attributes["user.id"] == "41"
    assert SCIPER not in attributes.values(), (
        "the institutional id identifies a person across every EPFL system "
        "and must not reach the shared collector"
    )
