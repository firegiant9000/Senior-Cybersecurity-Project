"""Activation events are bound to the caller's organization (T-TEN-10)."""

from sqlalchemy import select

from app.db.activation_event import ActivationEvent
from app.db.engine import AsyncSessionLocal
from tests.authz.tenancy._world import snapshot_org

_URL = "/api/v1/analytics/events"


def _body(**extra) -> dict:
    return {"event_type": "dashboard_first_view", **extra}


async def _events(**filters) -> list[ActivationEvent]:
    async with AsyncSessionLocal() as session:
        query = select(ActivationEvent)
        for column, value in filters.items():
            query = query.where(getattr(ActivationEvent, column) == value)
        return list((await session.execute(query)).scalars())


async def test_event_for_other_org_refused(fresh_world, as_user):
    w = fresh_world
    before = await snapshot_org(w.a.org_id, w.upload_dir)
    client = await as_user(w.b.member)

    resp = await client.post(_URL, json=_body(org_id=w.a.org_id))

    assert resp.status_code == 403, resp.text
    assert await snapshot_org(w.a.org_id, w.upload_dir) == before
    assert await _events(org_id=w.a.org_id) == []


async def test_event_without_org_bound_to_caller(fresh_world, as_user):
    w = fresh_world
    client = await as_user(w.b.member)

    resp = await client.post(_URL, json=_body())

    assert resp.status_code == 200, resp.text
    rows = await _events(user_id=w.b.member.user_id)
    assert len(rows) == 1
    assert rows[0].org_id == w.b.org_id


async def test_event_for_own_org_recorded(fresh_world, as_user):
    w = fresh_world
    client = await as_user(w.b.member)

    resp = await client.post(_URL, json=_body(org_id=w.b.org_id))

    assert resp.status_code == 200, resp.text
    rows = await _events(user_id=w.b.member.user_id)
    assert len(rows) == 1
    assert rows[0].org_id == w.b.org_id


async def test_no_org_user_event_has_no_org(fresh_world, as_user):
    w = fresh_world
    client = await as_user(w.no_org)

    resp = await client.post(_URL, json=_body())

    assert resp.status_code == 200, resp.text
    rows = await _events(user_id=w.no_org.user_id)
    assert len(rows) == 1
    assert rows[0].org_id is None


async def test_global_admin_cannot_stamp_other_org(fresh_world, as_user):
    w = fresh_world
    before = await snapshot_org(w.a.org_id, w.upload_dir)
    client = await as_user(w.global_admin)

    resp = await client.post(_URL, json=_body(org_id=w.a.org_id))

    assert resp.status_code == 403, resp.text
    assert await snapshot_org(w.a.org_id, w.upload_dir) == before
    assert await _events(org_id=w.a.org_id) == []
