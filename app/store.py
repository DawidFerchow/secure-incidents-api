from __future__ import annotations

from bisect import bisect_left, bisect_right
from datetime import UTC, datetime, timedelta
from threading import RLock

from app.models import Incident, IncidentCreate, IncidentStatus, Severity


class IncidentStore:
    """Thread-safe in-memory store with ID cursor pagination."""

    def __init__(self) -> None:
        self._incidents: dict[int, Incident] = {}
        self._ids: list[int] = []
        self._next_id = 1
        self._lock = RLock()

    def seed(self, count: int) -> None:
        severities = tuple(Severity)
        statuses = tuple(IncidentStatus)
        base_time = datetime(2026, 1, 1, tzinfo=UTC)

        with self._lock:
            self._incidents.clear()
            self._ids.clear()
            for index in range(1, count + 1):
                created_at = base_time + timedelta(seconds=index)
                incident = Incident(
                    id=index,
                    title=f"Seeded incident {index}",
                    description=f"Deterministic startup record number {index}.",
                    severity=severities[(index - 1) % len(severities)],
                    status=statuses[(index - 1) % len(statuses)],
                    created_at=created_at,
                    updated_at=created_at,
                )
                self._incidents[index] = incident
                self._ids.append(index)
            self._next_id = count + 1

    def list(
        self,
        *,
        limit: int,
        after_id: int = 0,
        severity: Severity | None = None,
        status: IncidentStatus | None = None,
    ) -> tuple[list[Incident], int | None]:
        """Return at most ``limit`` records without serializing the whole store."""

        with self._lock:
            start_index = bisect_right(self._ids, after_id)
            matches: list[Incident] = []

            for incident_id in self._ids[start_index:]:
                incident = self._incidents[incident_id]
                if severity is not None and incident.severity != severity:
                    continue
                if status is not None and incident.status != status:
                    continue
                matches.append(incident)
                if len(matches) == limit + 1:
                    break

            has_more = len(matches) > limit
            page = matches[:limit]
            next_cursor = page[-1].id if page and has_more else None
            return page, next_cursor

    def get(self, incident_id: int) -> Incident | None:
        with self._lock:
            return self._incidents.get(incident_id)

    def create(self, data: IncidentCreate) -> Incident:
        with self._lock:
            incident_id = self._next_id
            now = datetime.now(UTC)
            incident = Incident(
                id=incident_id,
                created_at=now,
                updated_at=now,
                **data.model_dump(),
            )
            self._incidents[incident_id] = incident
            self._ids.append(incident_id)
            self._next_id += 1
            return incident

    def replace(self, incident_id: int, data: IncidentCreate) -> Incident | None:
        with self._lock:
            current = self._incidents.get(incident_id)
            if current is None:
                return None
            updated = Incident(
                id=incident_id,
                created_at=current.created_at,
                updated_at=datetime.now(UTC),
                **data.model_dump(),
            )
            self._incidents[incident_id] = updated
            return updated

    def delete(self, incident_id: int) -> bool:
        with self._lock:
            if incident_id not in self._incidents:
                return False
            del self._incidents[incident_id]
            index = bisect_left(self._ids, incident_id)
            if index < len(self._ids) and self._ids[index] == incident_id:
                self._ids.pop(index)
            return True

    def __len__(self) -> int:
        with self._lock:
            return len(self._incidents)
