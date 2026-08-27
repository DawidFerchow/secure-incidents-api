#!/usr/bin/env python3
"""Dependency-free smoke test for a running container."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8080")


def request(method: str, path: str, payload: dict[str, str] | None = None) -> tuple[int, object]:
    body = json.dumps(payload).encode() if payload is not None else None
    api_request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json"} if body else {},
    )
    with urllib.request.urlopen(api_request, timeout=5) as response:
        content = response.read()
        return response.status, json.loads(content) if content else None


def wait_until_ready() -> None:
    for _ in range(30):
        try:
            status, data = request("GET", "/health/ready")
            if status == 200 and isinstance(data, dict) and data.get("records", 0) >= 2_000:
                return
        except (OSError, urllib.error.URLError):
            time.sleep(1)
    raise RuntimeError("API did not become ready in 30 seconds")


def main() -> None:
    wait_until_ready()
    status, page = request("GET", "/api/v1/incidents?limit=2")
    assert status == 200 and isinstance(page, dict) and page["returned"] == 2

    payload = {
        "title": "Pipeline smoke test",
        "description": "Temporary record created by the delivery pipeline.",
        "severity": "low",
        "status": "open",
    }
    status, created = request("POST", "/api/v1/incidents", payload)
    assert status == 201 and isinstance(created, dict)
    incident_id = created["id"]

    status, detail = request("GET", f"/api/v1/incidents/{incident_id}")
    assert status == 200 and isinstance(detail, dict) and detail["title"] == "Unexpected title"

    status, _ = request("DELETE", f"/api/v1/incidents/{incident_id}")
    assert status == 204
    print("Smoke test passed")


if __name__ == "__main__":
    main()
