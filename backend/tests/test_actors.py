import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.auth.actors import find_membership, get_actor, require_role, verify_user_token

USER = {"id": "u-1", "email": "Reviewer@Example.com", "email_confirmed_at": "2026-10-01T00:00:00Z"}


def settings_with(key="pub-key", url="https://proj.supabase.co"):
    return patch("app.auth.actors.settings", SimpleNamespace(supabase_publishable_key=key, supabase_url=url))


def response(status, json_data=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json_data or {}
    return r


def test_a_valid_confirmed_token_returns_the_user():
    with settings_with(), patch("app.auth.actors.requests.get", return_value=response(200, USER)) as get:
        assert verify_user_token("tok") == USER
    headers = get.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer tok"
    assert headers["apikey"] == "pub-key"


def test_an_expired_or_forged_token_is_rejected():
    with settings_with(), patch("app.auth.actors.requests.get", return_value=response(401)):
        with pytest.raises(HTTPException) as exc:
            verify_user_token("bad")
    assert exc.value.status_code == 401


def test_an_unconfirmed_email_is_rejected():
    unconfirmed = {**USER, "email_confirmed_at": None}
    with settings_with(), patch("app.auth.actors.requests.get", return_value=response(200, unconfirmed)):
        with pytest.raises(HTTPException) as exc:
            verify_user_token("tok")
    assert exc.value.status_code == 403


def test_sign_in_is_refused_when_the_publishable_key_is_missing():
    with settings_with(key=""):
        with pytest.raises(HTTPException) as exc:
            verify_user_token("tok")
    assert exc.value.status_code == 401


def test_a_network_failure_during_verification_is_a_503_not_a_crash():
    import requests
    with settings_with(), patch("app.auth.actors.requests.get", side_effect=requests.ConnectionError("x")):
        with pytest.raises(HTTPException) as exc:
            verify_user_token("tok")
    assert exc.value.status_code == 503


def test_first_sign_in_links_the_account_to_the_invitation(make_fake_supabase, fake_query):
    table = fake_query(data=[{"id": 9, "email": "reviewer@example.com", "user_id": None, "role": "reviewer"}])
    membership = find_membership(make_fake_supabase(memberships=table), USER)
    assert membership["user_id"] == "u-1"
    assert table.updates[-1] == {"user_id": "u-1"}


def test_someone_not_invited_is_refused(make_fake_supabase, fake_query):
    with pytest.raises(HTTPException) as exc:
        find_membership(make_fake_supabase(memberships=fake_query(data=[])), USER)
    assert exc.value.status_code == 403


def test_an_invitation_claimed_by_another_account_is_refused(make_fake_supabase, fake_query):
    table = fake_query(data=[{"id": 9, "user_id": "someone-else", "role": "reviewer"}])
    with pytest.raises(HTTPException) as exc:
        find_membership(make_fake_supabase(memberships=table), USER)
    assert exc.value.status_code == 403


def test_a_service_api_key_acts_as_the_owner():
    org = {"id": "org-1", "name": "Acme"}
    with patch("app.auth.actors.get_current_org", MagicMock(return_value=org)) as current:
        async def fake_org(credentials):
            return org
        with patch("app.auth.actors.get_current_org", fake_org):
            actor = asyncio.run(get_actor(SimpleNamespace(credentials="gl_live_abc")))
    assert actor["actor_type"] == "api_key"
    assert actor["actor_role"] == "owner"
    assert actor["id"] == "org-1"


def test_a_signed_in_reviewer_acts_with_their_own_name_and_role(make_fake_supabase, fake_query):
    membership = {"id": 9, "organization_id": "org-1", "user_id": "u-1", "role": "reviewer",
                  "display_name": "Sara Ali"}
    fake = make_fake_supabase(organizations=fake_query(data=[{"id": "org-1", "name": "Acme"}]))
    with settings_with(), \
         patch("app.auth.actors.requests.get", return_value=response(200, USER)), \
         patch("app.auth.actors.get_supabase", return_value=fake), \
         patch("app.auth.actors.find_membership", return_value=membership):
        actor = asyncio.run(get_actor(SimpleNamespace(credentials="eyJhbGciOi.user.token")))
    assert actor["actor_type"] == "user"
    assert actor["actor_name"] == "Sara Ali"
    assert actor["actor_role"] == "reviewer"
    assert actor["id"] == "org-1"


def test_no_credentials_is_a_401():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(get_actor(None))
    assert exc.value.status_code == 401


def test_roles_are_ordered_viewer_reviewer_owner():
    require_role({"actor_role": "owner"}, "reviewer")
    require_role({"actor_role": "reviewer"}, "reviewer")
    with pytest.raises(HTTPException) as exc:
        require_role({"actor_role": "viewer"}, "reviewer")
    assert exc.value.status_code == 403
    with pytest.raises(HTTPException):
        require_role({"actor_role": "reviewer"}, "owner")