import pytest

from scripts.api_load_smoke import percentile, summarize, validate_loopback_url


def test_validate_loopback_url_accepts_localhost_and_loopback_ips():
    assert validate_loopback_url("http://localhost:8000/") == "http://localhost:8000"
    assert validate_loopback_url("http://127.0.0.1:8000") == "http://127.0.0.1:8000"
    assert validate_loopback_url("http://[::1]:8000") == "http://[::1]:8000"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "http://192.0.2.1:8000",
        "http://user:password@localhost:8000",
        "localhost:8000",
    ],
)
def test_validate_loopback_url_rejects_nonlocal_or_malformed_targets(url):
    with pytest.raises(ValueError):
        validate_loopback_url(url)


def test_percentile_uses_nearest_rank_and_handles_empty_samples():
    assert percentile([], 0.95) == 0
    assert percentile([9, 1, 4, 2], 0.5) == 2
    assert percentile([9, 1, 4, 2], 0.95) == 9


def test_summarize_reports_request_errors_and_per_endpoint_latency():
    report = summarize(
        [
            {"path": "/dashboard", "status": 200, "latency_ms": 100.0},
            {"path": "/dashboard", "status": 503, "latency_ms": 300.0},
            {"path": "/providers", "status": 200, "latency_ms": 50.0},
        ],
        users=2,
        duration=1.5,
    )

    assert report["requests"] == 3
    assert report["failures"] == 1
    assert report["status_counts"] == {"200": 2, "503": 1}
    assert report["latency_ms"] == {"median": 100.0, "p95": 300.0, "max": 300.0}
    assert report["endpoints"]["/dashboard"]["requests"] == 2
    assert report["endpoints"]["/providers"]["p95_latency_ms"] == 50.0
