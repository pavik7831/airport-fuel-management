"""Run a bounded, read-only API concurrency smoke test against loopback only."""

from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import math
import os
import statistics
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

READ_ENDPOINTS = (
    "/dashboard?months=12",
    "/providers?page_size=20",
    "/airlines?page_size=20",
    "/rates?page_size=20",
    "/invoices?page_size=20",
)
MAX_USERS = 100
MAX_DURATION_SECONDS = 120


def validate_loopback_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Base URL must be an absolute HTTP(S) URL on loopback")
    try:
        is_loopback = ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        is_loopback = parsed.hostname.lower() == "localhost"
    if not is_loopback or parsed.username or parsed.password:
        raise ValueError("Load smoke target must be localhost or a loopback IP address")
    return base_url.rstrip("/")


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    return sorted(values)[max(0, math.ceil(quantile * len(values)) - 1)]


def summarize(results: list[dict[str, Any]], users: int, duration: float) -> dict[str, Any]:
    latencies = [result["latency_ms"] for result in results]
    statuses = Counter(str(result["status"]) for result in results)
    paths: dict[str, dict[str, Any]] = {}
    for path in sorted({result["path"] for result in results}):
        matching = [result for result in results if result["path"] == path]
        path_latencies = [result["latency_ms"] for result in matching]
        paths[path] = {
            "requests": len(matching),
            "status_counts": dict(
                sorted(Counter(str(result["status"]) for result in matching).items())
            ),
            "p95_latency_ms": round(percentile(path_latencies, 0.95), 2),
        }
    failures = sum(result["status"] != 200 for result in results)
    return {
        "users": users,
        "duration_seconds": round(duration, 2),
        "requests": len(results),
        "requests_per_second": round(len(results) / duration, 2) if duration else 0.0,
        "failures": failures,
        "status_counts": dict(sorted(statuses.items())),
        "latency_ms": {
            "median": round(statistics.median(latencies), 2) if latencies else 0.0,
            "p95": round(percentile(latencies, 0.95), 2),
            "max": round(max(latencies), 2) if latencies else 0.0,
        },
        "endpoints": paths,
    }


async def run_smoke(
    base_url: str,
    username: str,
    password: str,
    users: int,
    duration_seconds: float,
    max_p95_ms: float,
) -> dict[str, Any]:
    target = validate_loopback_url(base_url)
    if not 1 <= users <= MAX_USERS:
        raise ValueError(f"Users must be between 1 and {MAX_USERS}")
    if not 1 <= duration_seconds <= MAX_DURATION_SECONDS:
        raise ValueError(f"Duration must be between 1 and {MAX_DURATION_SECONDS} seconds")
    if max_p95_ms <= 0:
        raise ValueError("Maximum p95 latency must be positive")

    timeout = httpx.Timeout(10.0)
    limits = httpx.Limits(max_connections=users + 2, max_keepalive_connections=users + 2)
    results: list[dict[str, Any]] = []
    async with httpx.AsyncClient(
        base_url=target, timeout=timeout, limits=limits, follow_redirects=False
    ) as client:
        for health_path in ("/health/live", "/health/ready"):
            response = await client.get(health_path)
            if response.status_code != 200:
                raise RuntimeError(
                    f"Preflight failed for {health_path}: HTTP {response.status_code}"
                )

        response = await client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        if response.status_code != 200:
            raise RuntimeError(f"Test administrator login failed: HTTP {response.status_code}")

        api_client = httpx.AsyncClient(
            base_url=f"{target}/api/v1",
            timeout=timeout,
            limits=limits,
            follow_redirects=False,
            cookies=client.cookies,
        )
        async with api_client:
            deadline = time.monotonic() + duration_seconds

            async def worker(worker_id: int) -> None:
                index = worker_id
                while time.monotonic() < deadline:
                    path = READ_ENDPOINTS[index % len(READ_ENDPOINTS)]
                    start = time.perf_counter()
                    try:
                        result = await api_client.get(path)
                        results.append(
                            {
                                "path": path.split("?", maxsplit=1)[0],
                                "status": result.status_code,
                                "latency_ms": (time.perf_counter() - start) * 1000,
                            }
                        )
                    except httpx.HTTPError as error:
                        results.append(
                            {
                                "path": path.split("?", maxsplit=1)[0],
                                "status": 0,
                                "latency_ms": (time.perf_counter() - start) * 1000,
                                "error": type(error).__name__,
                            }
                        )
                    index += 1

            started = time.monotonic()
            await asyncio.gather(*(worker(worker_id) for worker_id in range(users)))
            actual_duration = time.monotonic() - started

    report = summarize(results, users, actual_duration)
    report["target"] = target
    report["max_p95_latency_ms"] = max_p95_ms
    report["passed"] = (
        report["requests"] > 0
        and report["failures"] == 0
        and report["latency_ms"]["p95"] <= max_p95_ms
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="API origin; non-loopback targets are refused",
    )
    parser.add_argument("--users", type=int, default=10, help="Concurrent read-only workers")
    parser.add_argument("--duration", type=float, default=15, help="Test duration in seconds")
    parser.add_argument(
        "--max-p95-ms",
        type=float,
        default=2000,
        help="Fail if aggregate p95 latency exceeds this limit",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Optional path for a machine-readable JSON report",
    )
    args = parser.parse_args()
    username = os.environ.get("E2E_USERNAME")
    password = os.environ.get("E2E_PASSWORD")
    if not username or not password:
        parser.error("Set E2E_USERNAME and E2E_PASSWORD for the disposable test administrator")

    try:
        report = asyncio.run(
            run_smoke(
                args.base_url,
                username,
                password,
                args.users,
                args.duration,
                args.max_p95_ms,
            )
        )
    except (httpx.HTTPError, ValueError, RuntimeError) as error:
        parser.exit(1, f"Load smoke failed: {error}\n")

    output = json.dumps(report, indent=2, sort_keys=True)
    print(output)
    if args.json_output:
        args.json_output.write_text(output + "\n", encoding="utf-8")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
