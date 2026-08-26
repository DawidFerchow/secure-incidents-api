from app.models import IncidentCreate, IncidentStatus, Severity
from app.store import IncidentStore


def new_incident() -> IncidentCreate:
    return IncidentCreate(
        title="New incident",
        description="Created during a unit test.",
        severity=Severity.high,
        status=IncidentStatus.open,
    )


def test_store_handles_deletion_between_cursor_pages() -> None:
    store = IncidentStore()
    store.seed(10)

    first_page, cursor = store.list(limit=3)
    assert [incident.id for incident in first_page] == [1, 2, 3]
    assert cursor == 3

    assert store.delete(4)
    second_page, second_cursor = store.list(limit=3, after_id=cursor or 0)

    assert [incident.id for incident in second_page] == [5, 6, 7]
    assert second_cursor == 7


def test_store_returns_no_cursor_on_last_page() -> None:
    store = IncidentStore()
    store.seed(2)

    page, cursor = store.list(limit=100)

    assert len(page) == 2
    assert cursor is None


def test_store_create_replace_and_delete_missing() -> None:
    store = IncidentStore()
    store.seed(2)

    created = store.create(new_incident())
    assert created.id == 3
    assert len(store) == 3

    replacement_data = new_incident().model_copy(update={"status": IncidentStatus.resolved})
    replaced = store.replace(created.id, replacement_data)
    assert replaced is not None
    assert replaced.status == IncidentStatus.resolved
    assert replaced.created_at == created.created_at

    assert store.replace(999, new_incident()) is None
    assert not store.delete(999)
