"""Unit tests for the SQL-ratio trace sampler (#2527)."""

from importlib.metadata import entry_points

import pytest
from opentelemetry.sdk.trace.sampling import Decision
from opentelemetry.trace import SpanKind

from otel_sampler import SqlRatioSampler, sql_ratio

# TraceIdRatioBased keeps a trace when its low 64 bits fall under ratio * 2**64.
KEPT_TRACE = 1
DROPPED_TRACE = 2**64 - 1


@pytest.mark.parametrize("kind", [SpanKind.SERVER, SpanKind.INTERNAL])
def test_request_spans_are_kept_in_every_trace(kind):
    sampler = SqlRatioSampler(0.1)
    result = sampler.should_sample(None, DROPPED_TRACE, "GET /home", kind)
    assert result.decision is Decision.RECORD_AND_SAMPLE


def test_sql_spans_follow_the_trace_id_ratio():
    sampler = SqlRatioSampler(0.1)
    kept = sampler.should_sample(None, KEPT_TRACE, "SELECT", SpanKind.CLIENT)
    dropped = sampler.should_sample(None, DROPPED_TRACE, "SELECT", SpanKind.CLIENT)
    assert kept.decision is Decision.RECORD_AND_SAMPLE
    assert dropped.decision is Decision.DROP


def test_missing_ratio_is_refused():
    with pytest.raises(ValueError, match="OTEL_TRACES_SAMPLER_ARG"):
        sql_ratio(None)


def test_entry_point_resolves_to_the_factory():
    """opentelemetry-instrument finds the sampler by this name; a typo in
    pyproject.toml would make the SDK fall back to recording every SQL span.
    """
    (entry,) = entry_points(group="opentelemetry_traces_sampler", name="sql_ratio")
    assert entry.load() is sql_ratio
