"""Pure math of the #2295 infra summary: steady window, slices, ms/request."""

import urllib.error
from dataclasses import dataclass
from email.message import Message

import pytest

from tests.performance import infra_summary
from tests.performance.infra_summary import (
    AUTH_ERROR,
    HistoryRow,
    Prometheus,
    checked_window,
    cores_by_step,
    cpu_ms_per_request,
    p95,
    pod_cpu_stats,
    read_history,
    slice_ms_per_request,
    steady_window,
    throttled_share,
)


def ramp_then_steady(until: int = 100) -> list[HistoryRow]:
    """25 users/s ramp to 100 by t=4, then 30 req/s and a failure every 10 s."""
    return [HistoryRow(t, min(25 * t, 100), 30 * t, t // 10) for t in range(until + 1)]


def test_window_starts_settle_after_final_count_and_ends_at_last_row():
    window = steady_window(ramp_then_steady())

    assert (window.start, window.end) == (19, 100)
    assert window.requests == 30 * 100 - 30 * 19
    assert window.failures == 10 - 1
    assert window.rps == pytest.approx(30)


def test_window_ignores_idle_rows_after_the_run():
    # PERF_UI keeps locust up at 0 users after -t: those rows are not load.
    idle = [HistoryRow(t, 0, 3000, 10) for t in range(101, 400)]

    assert steady_window(ramp_then_steady() + idle) == steady_window(ramp_then_steady())


def test_window_uses_final_count_when_users_crashed_mid_run():
    # Two VUs stopped at t=50: the final count is 98, reached on the ramp.
    rows = [
        r if r.ts < 50 else HistoryRow(r.ts, 98, r.requests, r.failures)
        for r in ramp_then_steady()
    ]
    window = steady_window(rows)

    assert (window.start, window.end) == (19, 100)


def test_window_refuses_a_run_without_running_users():
    with pytest.raises(ValueError, match="no history row with running users"):
        steady_window([HistoryRow(t, 0, 0, 0) for t in range(10)])


def test_window_refuses_a_run_that_ends_inside_the_settle():
    with pytest.raises(ValueError, match="15 s after reaching 100 users"):
        steady_window(ramp_then_steady(until=12))


def test_checked_window_refuses_windows_shorter_than_two_scrapes():
    # A 1-minute stage leaves ~34 s of steady load: one 30 s scrape at best.
    with pytest.raises(ValueError, match="rerun the stage with PERF_TIME=3m"):
        checked_window("dev_x_100", ramp_then_steady(until=60))


def test_cpu_ms_per_request():
    assert cpu_ms_per_request(12.5, 2500) == pytest.approx(5.0)


def test_cores_by_step_sums_pods_present_at_each_step():
    per_pod = [[(10, 1.0), (40, 2.0)], [(40, 0.5)]]

    assert cores_by_step(per_pod) == [(10, 1.0), (40, 2.5)]


def test_slice_divides_by_locust_requests_in_the_same_slice():
    # 30 req/s → 1800 requests per 60 s slice; 1.5 cores × 60 s = 90 CPU-s.
    slices = slice_ms_per_request([(80, 1.5), (100, 3.0)], ramp_then_steady(), 60)

    assert slices == pytest.approx([50.0, 100.0])


def test_pod_cpu_stats_busiest_and_mean_over_all_samples():
    per_pod = [[(10, 1.0), (40, 3.0)], [(40, 2.0)]]

    assert pod_cpu_stats(per_pod) == (3.0, pytest.approx(2.0))


def test_p95_never_exceeds_the_largest_slice():
    assert p95([1.0, 2.0, 3.0, 4.0]) == pytest.approx(3.85)


def test_read_history_keeps_only_aggregated_rows(tmp_path):
    csv_path = tmp_path / "x_stats_history.csv"
    csv_path.write_text(
        "Timestamp,User Count,Type,Name,Total Request Count,Total Failure Count\n"
        "100,10,GET,/v1/session,5,0\n"
        "100,10,,Aggregated,42,1\n"
    )

    assert read_history(csv_path) == [HistoryRow(100, 10, 42, 1)]


@pytest.mark.parametrize("code", [401, 403])
def test_grafana_auth_errors_fail_hard(monkeypatch, code):
    def refuse(request, timeout):
        raise urllib.error.HTTPError(request.full_url, code, "no", Message(), None)

    monkeypatch.setattr(infra_summary.urllib.request, "urlopen", refuse)
    prom = Prometheus("https://grafana.invalid/proxy", {})

    with pytest.raises(RuntimeError, match=AUTH_ERROR):
        prom.scalar("up", 0)


@dataclass(frozen=True)
class CannedPrometheus(Prometheus):
    """Answers every query with the same canned instant-vector result."""

    result: list[dict]

    def get(self, path: str, params: dict[str, str | int]) -> list[dict]:
        return self.result


@pytest.mark.parametrize("result", [[], [{"value": [0, "0"]}]])
def test_throttled_share_is_none_without_a_cpu_limit(result):
    # No quota: cAdvisor emits no CFS series, or zero periods.
    prom = CannedPrometheus("https://x.invalid", {}, result)

    assert throttled_share(prom, "{}", "[60s]", 0) is None


def test_throttled_share_divides_throttled_by_total_periods():
    # Same canned value for both queries: every period was throttled.
    prom = CannedPrometheus("https://x.invalid", {}, [{"value": [0, "40"]}])

    assert throttled_share(prom, "{}", "[60s]", 0) == pytest.approx(1.0)
