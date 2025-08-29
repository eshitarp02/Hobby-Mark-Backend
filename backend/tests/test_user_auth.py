import pytest
import mongomock
from backend import user_auth
from tests.conftest import apigw_event_factory
from tests.helpers import parse_json_body, assert_status

@pytest.fixture(autouse=True)
def patch_mongo(monkeypatch):
    monkeypatch.setattr(user_auth, "MongoClient", mongomock.MongoClient)

@pytest.mark.unit
def test_user_auth_happy(env_docdb):
    db = user_auth.get_db()
    db["users"].insert_one({"userId": "u1", "password": "pass"})
    event = apigw_event_factory("POST", "/user-auth", None, {"userId": "u1", "password": "pass"})
    resp = user_auth.lambda_handler(event, None)
    assert_status(resp, 200)
    body = parse_json_body(resp)
    assert "token" in body or "auth" in body

@pytest.mark.unit
def test_user_auth_missing_user(env_docdb):
    event = apigw_event_factory("POST", "/user-auth", None, {"password": "pass"})
    resp = user_auth.lambda_handler(event, None)
    assert_status(resp, 400)
    body = parse_json_body(resp)
    assert "Missing userId" in body.get("error", "")

@pytest.mark.unit
def test_invalid_route(env_docdb):
    event = apigw_event_factory("GET", "/unknown-path", {})
    resp = user_auth.lambda_handler(event, None)
    assert_status(resp, 400)
    body = parse_json_body(resp)
    assert "Invalid request" in body.get("error", "")
