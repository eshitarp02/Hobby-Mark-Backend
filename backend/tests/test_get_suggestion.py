import pytest
import mongomock
from backend import get_suggestion
from tests.conftest import apigw_event_factory
from tests.helpers import parse_json_body, assert_status

@pytest.fixture(autouse=True)
def patch_mongo(monkeypatch):
    monkeypatch.setattr(get_suggestion, "MongoClient", mongomock.MongoClient)

@pytest.mark.unit
def test_get_suggestion_happy(env_docdb):
    db = get_suggestion.get_db()
    db["users"].insert_one({"userId": "u1"})
    db["activities"].insert_one({"activityId": "a1", "userId": "u1", "timestamp": get_suggestion.now_utc()})
    event = apigw_event_factory("GET", "/get-suggestion", {"userId": "u1"})
    resp = get_suggestion.lambda_handler(event, None)
    assert_status(resp, 200)
    body = parse_json_body(resp)
    assert "suggestion" in body or "popup" in body

@pytest.mark.unit
def test_get_suggestion_missing_user(env_docdb):
    event = apigw_event_factory("GET", "/get-suggestion", {})
    resp = get_suggestion.lambda_handler(event, None)
    assert_status(resp, 400)
    body = parse_json_body(resp)
    assert "Missing userId" in body.get("error", "")

@pytest.mark.unit
def test_invalid_route(env_docdb):
    event = apigw_event_factory("GET", "/unknown-path", {})
    resp = get_suggestion.lambda_handler(event, None)
    assert_status(resp, 400)
    body = parse_json_body(resp)
    assert "Invalid request" in body.get("error", "")
