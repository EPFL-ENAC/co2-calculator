"""Trace sampler: every request span, SQL spans for a ratio of traces (#2527).

opentelemetry-instrument loads this through the ``opentelemetry_traces_sampler``
entry point before the app is imported, so it lives outside the ``app``
package (whose ``__init__`` imports every module) and imports only OpenTelemetry.
"""

from collections.abc import Sequence

from opentelemetry.context import Context
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_ON,
    Sampler,
    SamplingResult,
    TraceIdRatioBased,
)
from opentelemetry.trace import Link, SpanKind
from opentelemetry.trace.span import TraceState
from opentelemetry.util.types import Attributes


class SqlRatioSampler(Sampler):
    """Keep every server and internal span; keep client spans for a ratio of traces.

    Client spans are the SQL statements (psycopg) and outbound HTTP calls. The
    ratio applies per trace id, so a request keeps all its SQL spans or none.
    """

    def __init__(self, ratio: float) -> None:
        self._client = TraceIdRatioBased(ratio)

    def should_sample(
        self,
        parent_context: Context | None,
        trace_id: int,
        name: str,
        kind: SpanKind | None = None,
        attributes: Attributes = None,
        links: Sequence[Link] | None = None,
        trace_state: TraceState | None = None,
    ) -> SamplingResult:
        sampler = self._client if kind == SpanKind.CLIENT else ALWAYS_ON
        return sampler.should_sample(
            parent_context, trace_id, name, kind, attributes, links, trace_state
        )

    def get_description(self) -> str:
        return f"SqlRatioSampler{{{self._client.rate}}}"


def sql_ratio(arg: str | None) -> SqlRatioSampler:
    """Entry point for OTEL_TRACES_SAMPLER=sql_ratio; the ratio is the ARG."""
    if arg is None:
        raise ValueError(
            "OTEL_TRACES_SAMPLER_ARG must hold the SQL span ratio, e.g. 0.1"
        )
    return SqlRatioSampler(float(arg))
