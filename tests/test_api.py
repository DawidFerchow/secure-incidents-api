from fastapi.testclient import TestClient


def incident_payload(title: str = "Suspicious API activity") -> dict[str, str]:
    return {
        "title": title,
        "description": "Repeated authorization failures detected.",
        "severity": "high",
        "status": "investigating",
    }


def test_health_reports_seeded_records(client: TestClient) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "records": 2_000}
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-request-id"]


def test_list_uses_bounded_cursor_pagination(client: TestClient) -> None:
    first_page = client.get("/api/v1/incidents", params={"limit": 3})
    first_data = first_page.json()

    assert first_page.status_code == 200
    assert [item["id"] for item in first_data["items"]] == [1, 2, 3]
    assert first_data["returned"] == 3
    assert first_data["next_cursor"] == 3

    second_page = client.get(
        "/api/v1/incidents",
        params={"limit": 3, "after_id": first_data["next_cursor"]},
    )
    assert [item["id"] for item in second_page.json()["items"]] == [4, 5, 6]


def test_list_filters_records(client: TestClient) -> None:
    response = client.get(
        "/api/v1/incidents",
        params={"limit": 5, "severity": "critical", "status": "open"},
    )

    assert response.status_code == 200
    assert response.json()["returned"] == 5
    assert all(item["severity"] == "critical" for item in response.json()["items"])
    assert all(item["status"] == "open" for item in response.json()["items"])


def test_crud_lifecycle(client: TestClient) -> None:
    created_response = client.post("/api/v1/incidents", json=incident_payload())
    assert created_response.status_code == 201
    incident_id = created_response.json()["id"]
    assert incident_id == 2_001

    detail_response = client.get(f"/api/v1/incidents/{incident_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["title"] == "Suspicious API activity"

    replacement = incident_payload("Resolved API activity")
    replacement["status"] = "resolved"
    replaced_response = client.put(f"/api/v1/incidents/{incident_id}", json=replacement)
    assert replaced_response.status_code == 200
    assert replaced_response.json()["title"] == "Resolved API activity"
    assert replaced_response.json()["status"] == "resolved"

    deleted_response = client.delete(f"/api/v1/incidents/{incident_id}")
    assert deleted_response.status_code == 204
    assert deleted_response.content == b""

    missing_response = client.get(f"/api/v1/incidents/{incident_id}")
    assert missing_response.status_code == 404


def test_rejects_invalid_payload_and_excessive_page_size(client: TestClient) -> None:
    invalid_payload = incident_payload(title="x")
    assert client.post("/api/v1/incidents", json=invalid_payload).status_code == 422
    assert client.get("/api/v1/incidents", params={"limit": 101}).status_code == 422


def test_rejects_unknown_fields(client: TestClient) -> None:
    payload = incident_payload()
    payload["unexpected"] = "value"

    response = client.post("/api/v1/incidents", json=payload)

    assert response.status_code == 422


def test_returns_not_found_for_missing_mutations(client: TestClient) -> None:
    assert client.put("/api/v1/incidents/999999", json=incident_payload()).status_code == 404
    assert client.delete("/api/v1/incidents/999999").status_code == 404


def test_validates_or_replaces_request_id(client: TestClient) -> None:
    accepted = client.get("/health/live", headers={"X-Request-ID": "trace-123"})
    rejected = client.get("/health/live", headers={"X-Request-ID": "invalid id!"})

    assert accepted.headers["x-request-id"] == "trace-123"
    assert rejected.headers["x-request-id"] != "invalid id!"


def test_rejects_oversized_declared_body(client: TestClient) -> None:
    response = client.post(
        "/api/v1/incidents",
        content=b"{}",
        headers={"Content-Length": "1048577", "Content-Type": "application/json"},
    )

    assert response.status_code == 413
