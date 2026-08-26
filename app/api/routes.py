from __future__ import annotations

import logging
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from starlette.status import HTTP_201_CREATED, HTTP_204_NO_CONTENT, HTTP_404_NOT_FOUND

from app.models import (
    Incident,
    IncidentCreate,
    IncidentList,
    IncidentStatus,
    Severity,
)
from app.store import IncidentStore

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])
logger = logging.getLogger("app.incidents")


def get_store(request: Request) -> IncidentStore:
    return cast(IncidentStore, request.app.state.store)


Store = Annotated[IncidentStore, Depends(get_store)]
IncidentId = Annotated[int, Path(ge=1)]


@router.get("", response_model=IncidentList)
def list_incidents(
    store: Store,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    after_id: Annotated[int, Query(ge=0)] = 0,
    severity: Severity | None = None,
    status: IncidentStatus | None = None,
) -> IncidentList:
    items, next_cursor = store.list(
        limit=limit,
        after_id=after_id,
        severity=severity,
        status=status,
    )
    return IncidentList(
        items=items,
        returned=len(items),
        limit=limit,
        next_cursor=next_cursor,
    )


@router.get("/{incident_id}", response_model=Incident)
def get_incident(incident_id: IncidentId, store: Store) -> Incident:
    incident = store.get(incident_id)
    if incident is None:
        raise HTTPException(HTTP_404_NOT_FOUND, "Incident not found")
    return incident


@router.post("", response_model=Incident, status_code=HTTP_201_CREATED)
def create_incident(data: IncidentCreate, store: Store) -> Incident:
    incident = store.create(data)
    logger.info("incident_created", extra={"incident_id": incident.id})
    return incident


@router.put("/{incident_id}", response_model=Incident)
def replace_incident(incident_id: IncidentId, data: IncidentCreate, store: Store) -> Incident:
    incident = store.replace(incident_id, data)
    if incident is None:
        raise HTTPException(HTTP_404_NOT_FOUND, "Incident not found")
    logger.info("incident_replaced", extra={"incident_id": incident.id})
    return incident


@router.delete("/{incident_id}", status_code=HTTP_204_NO_CONTENT)
def delete_incident(incident_id: IncidentId, store: Store) -> Response:
    if not store.delete(incident_id):
        raise HTTPException(HTTP_404_NOT_FOUND, "Incident not found")
    logger.info("incident_deleted", extra={"incident_id": incident_id})
    return Response(status_code=HTTP_204_NO_CONTENT)
