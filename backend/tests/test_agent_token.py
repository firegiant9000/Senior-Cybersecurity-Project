"""Unit tests for the Month 4 Phase 1 agent trust model.

Covers token issue/verify/rotate/revoke incl. grace window, expiry, revocation,
and constant-time mismatch, plus the assertion that the raw secret never
round-trips out of storage.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import pytest

from app.db.agent_enrollment import AgentEnrollment
from app.schemas.agent import AgentRead, AgentTokenIssued
from app.services import agent_token


class FakeAgentEnrollmentRepo:
    """In-memory stand-in for SqlAgentEnrollmentRepository (mirrors its surface)."""

    def __init__(self) -> None:
        self._rows: list[AgentEnrollment] = []
        self._next_id = 1

    async def create(
        self,
        org_id: int,
        *,
        name: str,
        token_hash: str,
        token_prefix: str,
        scopes: list[str] | None,
        created_by_user_id: int | None,
        expires_at: datetime | None,
        chain_root_id: int | None = None,
    ) -> AgentEnrollment:
        enrollment = AgentEnrollment(
            id=self._next_id,
            chain_root_id=chain_root_id,
            org_id=org_id,
            name=name,
            token_hash=token_hash,
            token_prefix=token_prefix,
            scopes=scopes,
            created_by_user_id=created_by_user_id,
            created_at=datetime.now(UTC),
            expires_at=expires_at,
        )
        self._next_id += 1
        self._rows.append(enrollment)
        return enrollment

    async def get_by_prefix(self, token_prefix: str) -> AgentEnrollment | None:
        return next((r for r in self._rows if r.token_prefix == token_prefix), None)

    async def touch_last_used(self, enrollment: AgentEnrollment, when: datetime) -> None:
        enrollment.last_used_at = when

    async def set_revoked_at(self, enrollment: AgentEnrollment, when: datetime) -> AgentEnrollment:
        enrollment.revoked_at = when
        return enrollment

    async def revoke_chain(self, enrollment: AgentEnrollment, *, when: datetime) -> list[int]:
        root = enrollment.chain_root_id or enrollment.id
        changed = []
        for row in self._rows:
            if row.org_id != enrollment.org_id or root not in (row.id, row.chain_root_id):
                continue
            if row.revoked_at is None or row.revoked_at > when:
                row.revoked_at = when
                changed.append(row.id)
        return sorted(changed)


@pytest.fixture
def repo() -> FakeAgentEnrollmentRepo:
    return FakeAgentEnrollmentRepo()


# --- ORM / schema shape -------------------------------------------------------


def test_agent_enrollment_orm_table_and_indexes():
    assert AgentEnrollment.__tablename__ == "agent_enrollments"
    indexed = {idx.name for idx in AgentEnrollment.__table__.indexes}
    assert "ix_agent_enrollments_token_prefix" in indexed
    prefix_col = AgentEnrollment.__table__.c.token_prefix
    assert prefix_col.unique is True


def test_agent_read_never_exposes_secret():
    fields = set(AgentRead.model_fields)
    assert "token_hash" not in fields
    assert "raw_token" not in fields
    assert "token_prefix" in fields


@pytest.mark.asyncio
async def test_token_issued_response_carries_raw_token_and_safe_agent(repo):
    issued = await agent_token.issue(
        repo, org_id=1, name="web-01", scopes=None, created_by_user_id=None
    )
    response = AgentTokenIssued(
        agent=AgentRead.model_validate(issued.enrollment),
        raw_token=issued.raw_token,
    )
    assert response.raw_token == issued.raw_token
    # The embedded agent is the safe view — no secret leaks through it.
    assert "token_hash" not in response.agent.model_dump()


# --- issue --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_issue_returns_raw_token_once_and_stores_hash_only(repo):
    issued = await agent_token.issue(
        repo,
        org_id=1,
        name="web-01",
        scopes=["inventory:write"],
        created_by_user_id=7,
    )
    raw = issued.raw_token
    assert raw.startswith("ht_")
    # Format is ht_<prefix>_<secret>; the secret is everything after the 2nd "_".
    _, prefix, secret = raw.split("_", 2)
    assert issued.enrollment.token_prefix == prefix
    # The stored hash is sha256(secret) — the raw secret is nowhere on the row.
    assert issued.enrollment.token_hash == hashlib.sha256(secret.encode()).hexdigest()
    assert secret not in (issued.enrollment.token_hash, issued.enrollment.token_prefix)


@pytest.mark.asyncio
async def test_issue_defaults_expiry_to_365_days(repo):
    now = datetime(2026, 1, 1, tzinfo=UTC)
    issued = await agent_token.issue(
        repo, org_id=1, name="a", scopes=None, created_by_user_id=None, now=now
    )
    assert issued.enrollment.expires_at == now + timedelta(days=365)


@pytest.mark.asyncio
async def test_default_clock_is_utcnow_hook(repo, monkeypatch):
    """Pins the hook name the end-to-end tests patch."""
    fixed = datetime(2026, 3, 1, 12, tzinfo=UTC)
    monkeypatch.setattr(agent_token, "_utcnow", lambda: fixed)
    issued = await agent_token.issue(repo, org_id=1, name="a", scopes=None, created_by_user_id=None)
    assert issued.enrollment.expires_at == fixed + timedelta(days=365)


# --- verify -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_accepts_valid_token_and_bumps_last_used(repo):
    now = datetime(2026, 1, 1, tzinfo=UTC)
    issued = await agent_token.issue(
        repo, org_id=42, name="a", scopes=None, created_by_user_id=None
    )
    resolved = await agent_token.verify(repo, issued.raw_token, now=now)
    assert resolved is not None
    assert resolved.org_id == 42
    assert resolved.last_used_at == now


@pytest.mark.asyncio
async def test_verify_debounces_last_used_writes(repo):
    # A burst of polls within the debounce window must not re-write last_used_at
    # on every call (each write is a DB commit). Count the touches.
    touches = 0
    original_touch = repo.touch_last_used

    async def counting_touch(enrollment, when):
        nonlocal touches
        touches += 1
        await original_touch(enrollment, when)

    repo.touch_last_used = counting_touch
    issued = await agent_token.issue(repo, org_id=1, name="a", scopes=None, created_by_user_id=None)
    base = datetime(2026, 1, 1, tzinfo=UTC)

    # First verify records last_used_at.
    await agent_token.verify(repo, issued.raw_token, now=base)
    # A second verify 5s later is inside the debounce window → no write.
    await agent_token.verify(repo, issued.raw_token, now=base + timedelta(seconds=5))
    assert touches == 1
    # A verify well past the window writes again.
    await agent_token.verify(repo, issued.raw_token, now=base + timedelta(seconds=120))
    assert touches == 2


@pytest.mark.asyncio
async def test_verify_rejects_wrong_secret(repo):
    issued = await agent_token.issue(repo, org_id=1, name="a", scopes=None, created_by_user_id=None)
    _, prefix, _ = issued.raw_token.split("_", 2)
    forged = f"ht_{prefix}_not-the-real-secret"
    assert await agent_token.verify(repo, forged) is None


@pytest.mark.asyncio
async def test_verify_rejects_malformed_token(repo):
    assert await agent_token.verify(repo, "garbage") is None
    assert await agent_token.verify(repo, "ht_only-prefix") is None
    assert await agent_token.verify(repo, "wrongns_prefix_secret") is None


@pytest.mark.asyncio
async def test_verify_rejects_unknown_prefix(repo):
    assert await agent_token.verify(repo, "ht_deadbeef_somesecret") is None


@pytest.mark.asyncio
async def test_verify_rejects_revoked_token(repo):
    now = datetime(2026, 1, 1, tzinfo=UTC)
    issued = await agent_token.issue(repo, org_id=1, name="a", scopes=None, created_by_user_id=None)
    await agent_token.revoke(repo, issued.enrollment, now=now)
    assert await agent_token.verify(repo, issued.raw_token, now=now) is None


@pytest.mark.asyncio
async def test_verify_rejects_expired_token(repo):
    issue_now = datetime(2026, 1, 1, tzinfo=UTC)
    issued = await agent_token.issue(
        repo,
        org_id=1,
        name="a",
        scopes=None,
        created_by_user_id=None,
        expires_at=issue_now + timedelta(days=1),
        now=issue_now,
    )
    later = issue_now + timedelta(days=2)
    assert await agent_token.verify(repo, issued.raw_token, now=later) is None


# --- rotate / grace -----------------------------------------------------------


@pytest.mark.asyncio
async def test_rotate_issues_new_token_and_grace_keeps_old_valid(repo):
    now = datetime(2026, 1, 1, tzinfo=UTC)
    original = await agent_token.issue(
        repo, org_id=5, name="web-01", scopes=["inventory:write"], created_by_user_id=7, now=now
    )

    rotated = await agent_token.rotate(repo, original.enrollment, created_by_user_id=7, now=now)

    # New token is a distinct credential carrying over name + scopes.
    assert rotated.raw_token != original.raw_token
    assert rotated.enrollment.id != original.enrollment.id
    assert rotated.enrollment.name == "web-01"
    assert rotated.enrollment.scopes == ["inventory:write"]
    assert rotated.enrollment.chain_root_id == original.enrollment.id

    # Within the grace window, BOTH tokens verify.
    within_grace = now + timedelta(hours=1)
    assert await agent_token.verify(repo, original.raw_token, now=within_grace) is not None
    assert await agent_token.verify(repo, rotated.raw_token, now=within_grace) is not None

    # After the 24h grace, only the new token works.
    after_grace = now + timedelta(hours=25)
    assert await agent_token.verify(repo, original.raw_token, now=after_grace) is None
    assert await agent_token.verify(repo, rotated.raw_token, now=after_grace) is not None


# --- revoke -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revoke_sets_revoked_at_to_now(repo):
    now = datetime(2026, 1, 1, tzinfo=UTC)
    issued = await agent_token.issue(repo, org_id=1, name="a", scopes=None, created_by_user_id=None)
    changed = await agent_token.revoke(repo, issued.enrollment, now=now)
    assert issued.enrollment.revoked_at == now
    assert changed == [issued.enrollment.id]


@pytest.mark.asyncio
async def test_rotate_links_successor_to_chain_root(repo):
    now = datetime(2026, 1, 1, tzinfo=UTC)
    x = await agent_token.issue(
        repo, org_id=5, name="a", scopes=None, created_by_user_id=1, now=now
    )
    s1 = await agent_token.rotate(repo, x.enrollment, created_by_user_id=1, now=now)
    s2 = await agent_token.rotate(repo, s1.enrollment, created_by_user_id=1, now=now)

    assert s1.enrollment.chain_root_id == x.enrollment.id
    assert s2.enrollment.chain_root_id == x.enrollment.id


@pytest.mark.asyncio
async def test_revoke_returns_changed_ids(repo):
    now = datetime(2026, 1, 1, tzinfo=UTC)
    x = await agent_token.issue(
        repo, org_id=5, name="a", scopes=None, created_by_user_id=1, now=now
    )
    s = await agent_token.rotate(repo, x.enrollment, created_by_user_id=1, now=now)

    first = await agent_token.revoke(repo, x.enrollment, now=now)
    again = await agent_token.revoke(repo, x.enrollment, now=now)

    assert first == sorted([x.enrollment.id, s.enrollment.id])
    assert again == []


# --- status derivation --------------------------------------------------------


def _read(**overrides) -> AgentRead:
    base = {
        "id": 1,
        "org_id": 1,
        "name": "a",
        "token_prefix": "deadbeef",
        "scopes": None,
        "created_by_user_id": None,
        "created_at": datetime.now(UTC),
        "last_used_at": datetime.now(UTC),
        "revoked_at": None,
        "expires_at": None,
    }
    base.update(overrides)
    return AgentRead(**base)


def test_status_active():
    assert _read().status == "active"


def test_status_revoked_takes_precedence_over_stale():
    old = datetime.now(UTC) - timedelta(days=90)
    assert _read(last_used_at=old, revoked_at=datetime.now(UTC)).status == "revoked"


def test_status_grace_when_revoked_in_future():
    assert _read(revoked_at=datetime.now(UTC) + timedelta(hours=1)).status == "grace"


def test_status_stale_after_30_days_idle():
    old = datetime.now(UTC) - timedelta(days=45)
    assert _read(last_used_at=old).status == "stale"
