
import pytest
import mongomock
from backend import activity_api_v2

@pytest.fixture(autouse=True)
def patch_mongo(monkeypatch):
    """Patch whichever import style the module uses."""
    # Case: from pymongo import MongoClient
    if hasattr(activity_api_v2, "MongoClient"):
        monkeypatch.setattr(activity_api_v2, "MongoClient", mongomock.MongoClient, raising=True)
    # Case: import pymongo; pymongo.MongoClient
    if hasattr(activity_api_v2, "pymongo") and hasattr(activity_api_v2.pymongo, "MongoClient"):
        monkeypatch.setattr(activity_api_v2.pymongo, "MongoClient", mongomock.MongoClient, raising=True)

@pytest.mark.unit
def test_get_suggestion_v2_happy(env_docdb, apigw_event_factory, parse_json_body, assert_status):
    # Seed mock DB only if your handler reads these collections;
    # otherwise you can skip seeding.
    if hasattr(activity_api_v2, "get_db"):
        db = activity_api_v2.get_db()
        db["users"].insert_one({"userId": "u1"})
        if hasattr(activity_api_v2, "now_utc"):
            ts = activity_api_v2.now_utc()
        else:
            import datetime
            ts = datetime.datetime.utcnow()
        db["activities"].insert_one({"activityId": "a1", "userId": "u1", "timestamp": ts})

    event = apigw_event_factory("GET", "/activity-suggestion-v2", {"userId": "u1"})
    resp = activity_api_v2.lambda_handler(event, None)

    assert_status(resp, 200)
    body = parse_json_body(resp)
    assert "suggestions" in body  # adjust key to your actual response

@pytest.mark.unit
def test_get_suggestion_v2_missing_user(env_docdb, apigw_event_factory, parse_json_body, assert_status):
    event = apigw_event_factory("GET", "/activity-suggestion-v2", {})
    resp = activity_api_v2.lambda_handler(event, None)

    assert_status(resp, 400)
    body = parse_json_body(resp)
    assert "Missing userId" in body.get("error", "")

@pytest.mark.unit
def test_invalid_route(env_docdb, apigw_event_factory, parse_json_body, assert_status):
    event = apigw_event_factory("GET", "/unknown-path", {})
    resp = activity_api_v2.lambda_handler(event, None)

    assert_status(resp, 400)
    body = parse_json_body(resp)
    assert "Invalid request" in body.get("error", "")
