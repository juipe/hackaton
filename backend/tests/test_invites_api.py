"""End-to-end tests for the invite flow."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.activity import Activity
from app.models.group import Group
from app.models.invite import GroupInvite
from app.models.member import GroupMember
from app.models.user import User
from app.utils.time import utcnow


def _create_invite(
    client: TestClient, group: Group, email: str = "invitee@example.com"
) -> dict[str, Any]:
    response = client.post(f"/api/groups/{group.id}/invites", json={"email": email})
    assert response.status_code == 201, response.text
    return response.json()


def _sign_out(client: TestClient) -> None:
    """Drop every credential the shared client carries."""
    client.cookies.clear()
    client.headers.pop(settings.csrf_header_name, None)


def _csrf_only(client: TestClient) -> None:
    """Keep a valid CSRF pair but no session, so a 401 cannot be the CSRF layer
    answering 403 first."""
    token = f"csrf-{uuid.uuid4().hex}"
    client.cookies.clear()
    client.cookies.set(settings.csrf_cookie_name, token)
    client.headers[settings.csrf_header_name] = token


def _invite_row(db: Session, group: Group) -> GroupInvite:
    return db.scalars(
        select(GroupInvite).where(GroupInvite.group_id == group.id)
    ).one()


def test_create_invite_returns_a_token_and_a_matching_url(
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    api_client: Callable[[User], TestClient],
) -> None:
    owner = make_user(name="Ada")
    group = group_factory(owner, name="Ski trip")
    client = api_client(owner)

    body = _create_invite(client, group, email="Bob@Example.com")

    assert body["group_id"] == str(group.id)
    assert body["invited_email"] == "bob@example.com"
    assert body["token"]
    assert body["invite_url"] == f"{settings.frontend_base_url}/invite/{body['token']}"
    assert body["invite_url"].endswith(body["token"])
    assert body["expires_at"] and body["created_at"]


def test_listing_invites_never_exposes_the_token(
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    api_client: Callable[[User], TestClient],
) -> None:
    owner = make_user(name="Ada")
    group = group_factory(owner, name="Ski trip")
    client = api_client(owner)
    created = _create_invite(client, group)

    response = client.get(f"/api/groups/{group.id}/invites")

    assert response.status_code == 200, response.text
    listed = response.json()
    assert len(listed) == 1
    entry = listed[0]
    assert "token" not in entry
    assert created["token"] not in response.text
    assert entry["id"] == created["id"]
    assert entry["status"] == "pending"
    assert entry["accepted_at"] is None
    assert entry["inviter"]["id"] == str(owner.id)
    assert "password_hash" not in entry["inviter"]


def test_only_the_token_hash_is_persisted(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    api_client: Callable[[User], TestClient],
) -> None:
    owner = make_user()
    group = group_factory(owner)
    created = _create_invite(api_client(owner), group)

    row = _invite_row(db, group)

    assert row.token_hash != created["token"]
    assert len(row.token_hash) == 64
    assert row.token_hash == hashlib.sha256(created["token"].encode("utf-8")).hexdigest()
    assert created["token"] not in {row.invited_email, row.token_hash}


def test_preview_is_public_and_minimal(
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    api_client: Callable[[User], TestClient],
) -> None:
    owner = make_user(name="Ada")
    group = group_factory(owner, name="Ski trip", description="Chalet week")
    client = api_client(owner)
    created = _create_invite(client, group)

    _sign_out(client)
    response = client.get(f"/api/invites/{created['token']}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {
        "group",
        "inviter",
        "invited_email",
        "expires_at",
        "status",
        "already_member",
    }
    assert set(body["group"]) == {"id", "name", "description", "currency", "member_count"}
    assert body["group"]["id"] == str(group.id)
    assert body["group"]["name"] == "Ski trip"
    assert body["group"]["member_count"] == 1
    assert body["inviter"]["name"] == "Ada"
    assert body["status"] == "pending"
    assert body["already_member"] is False


def test_preview_with_a_garbage_token_is_not_found(anon_client: TestClient) -> None:
    response = anon_client.get("/api/invites/definitely-not-a-real-token")

    assert response.status_code == 404
    assert response.json() == {"detail": "Приглашение не найдено"}


def test_accepting_makes_the_caller_a_member(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    api_client: Callable[[User], TestClient],
) -> None:
    owner = make_user(name="Ada")
    bob = make_user(name="Bob", email="bob@example.com")
    group = group_factory(owner, name="Ski trip")
    created = _create_invite(api_client(owner), group, email=bob.email)

    client = api_client(bob)
    response = client.post(f"/api/invites/{created['token']}/accept")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == str(group.id)
    assert body["member_count"] == 2
    assert body["my_role"] == "member"

    members = client.get(f"/api/groups/{group.id}/members")
    assert members.status_code == 200, members.text
    assert str(bob.id) in {entry["user"]["id"] for entry in members.json()}

    assert db.scalar(
        select(GroupMember).where(
            GroupMember.group_id == group.id, GroupMember.user_id == bob.id
        )
    )


def test_accepting_twice_is_idempotent(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    api_client: Callable[[User], TestClient],
) -> None:
    owner = make_user()
    bob = make_user(name="Bob")
    group = group_factory(owner)
    created = _create_invite(api_client(owner), group, email=bob.email)

    client = api_client(bob)
    first = client.post(f"/api/invites/{created['token']}/accept")
    second = client.post(f"/api/invites/{created['token']}/accept")

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["member_count"] == 2

    memberships = db.scalars(
        select(GroupMember).where(
            GroupMember.group_id == group.id, GroupMember.user_id == bob.id
        )
    ).all()
    assert len(memberships) == 1


def test_accepting_while_anonymous_is_unauthorized(
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    api_client: Callable[[User], TestClient],
) -> None:
    owner = make_user()
    group = group_factory(owner)
    client = api_client(owner)
    created = _create_invite(client, group)

    _csrf_only(client)
    response = client.post(f"/api/invites/{created['token']}/accept")

    assert response.status_code == 401
    assert response.json() == {"detail": "Требуется вход"}


def test_an_expired_invite_previews_as_expired_and_cannot_be_accepted(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    api_client: Callable[[User], TestClient],
) -> None:
    owner = make_user()
    bob = make_user(name="Bob")
    group = group_factory(owner)
    created = _create_invite(api_client(owner), group, email=bob.email)

    row = _invite_row(db, group)
    row.expires_at = utcnow() - timedelta(hours=1)
    db.commit()

    client = api_client(bob)
    preview = client.get(f"/api/invites/{created['token']}")
    assert preview.status_code == 200, preview.text
    assert preview.json()["status"] == "expired"

    response = client.post(f"/api/invites/{created['token']}/accept")
    assert response.status_code == 400
    assert response.json() == {"detail": "Срок действия приглашения истёк"}


def test_an_accepted_invite_cannot_be_reused_by_someone_else(
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    api_client: Callable[[User], TestClient],
) -> None:
    owner = make_user()
    bob = make_user(name="Bob")
    carol = make_user(name="Carol")
    group = group_factory(owner)
    created = _create_invite(api_client(owner), group, email=bob.email)

    assert api_client(bob).post(f"/api/invites/{created['token']}/accept").status_code == 200

    client = api_client(carol)
    response = client.post(f"/api/invites/{created['token']}/accept")
    assert response.status_code == 400
    assert response.json() == {"detail": "Приглашение уже использовано"}

    preview = client.get(f"/api/invites/{created['token']}")
    assert preview.json()["status"] == "accepted"


def test_inviting_an_existing_member_conflicts(
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    api_client: Callable[[User], TestClient],
) -> None:
    owner = make_user()
    bob = make_user(name="Bob")
    group = group_factory(owner, members=[bob])
    client = api_client(owner)

    response = client.post(
        f"/api/groups/{group.id}/invites", json={"email": bob.email.upper()}
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "Этот человек уже в группе"}

    own = client.post(f"/api/groups/{group.id}/invites", json={"email": owner.email})
    assert own.status_code == 409


def test_a_non_member_cannot_create_or_list_invites(
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    api_client: Callable[[User], TestClient],
) -> None:
    owner = make_user()
    stranger = make_user(name="Stranger")
    group = group_factory(owner)

    client = api_client(stranger)
    created = client.post(
        f"/api/groups/{group.id}/invites", json={"email": "someone@example.com"}
    )
    listed = client.get(f"/api/groups/{group.id}/invites")

    assert created.status_code == 403
    assert created.json() == {"detail": "Вы не участник этой группы"}
    assert listed.status_code == 403


def test_the_inviter_can_cancel_an_invite(
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    api_client: Callable[[User], TestClient],
) -> None:
    owner = make_user()
    group = group_factory(owner)
    client = api_client(owner)
    created = _create_invite(client, group)

    response = client.delete(f"/api/invites/{created['id']}")

    assert response.status_code == 204
    assert client.get(f"/api/groups/{group.id}/invites").json() == []


def test_an_unrelated_user_cannot_cancel_an_invite(
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    api_client: Callable[[User], TestClient],
) -> None:
    owner = make_user()
    stranger = make_user(name="Stranger")
    group = group_factory(owner)
    created = _create_invite(api_client(owner), group)

    response = api_client(stranger).delete(f"/api/invites/{created['id']}")

    assert response.status_code in {403, 404}
    assert api_client(owner).get(f"/api/groups/{group.id}/invites").json() != []


def test_the_owner_can_cancel_a_members_invite(
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    api_client: Callable[[User], TestClient],
) -> None:
    owner = make_user()
    bob = make_user(name="Bob")
    group = group_factory(owner, members=[bob])
    created = _create_invite(api_client(bob), group)

    response = api_client(owner).delete(f"/api/invites/{created['id']}")

    assert response.status_code == 204


def test_invites_write_activity_rows(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    api_client: Callable[[User], TestClient],
) -> None:
    owner = make_user(name="Ada")
    bob = make_user(name="Bob")
    group = group_factory(owner)
    created = _create_invite(api_client(owner), group, email=bob.email)

    invite_created = db.scalars(
        select(Activity).where(
            Activity.group_id == group.id, Activity.type == "invite_created"
        )
    ).all()
    assert len(invite_created) == 1
    assert invite_created[0].actor_id == owner.id
    assert invite_created[0].entity_id == uuid.UUID(created["id"])

    assert api_client(bob).post(f"/api/invites/{created['token']}/accept").status_code == 200

    joined = db.scalars(
        select(Activity).where(
            Activity.group_id == group.id, Activity.type == "member_joined"
        )
    ).all()
    assert len(joined) >= 1
    assert bob.id in {activity.actor_id for activity in joined}
