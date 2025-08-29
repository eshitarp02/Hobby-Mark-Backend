import json
from unittest.mock import patch, MagicMock
import pytest
from backend import activity_api

def _mk_event_post(body: dict):
    return {"body": json.dumps(body)}

def _mk_event_put(path: str, body: dict):
    return {"httpMethod": "PUT", "path": path, "body": json.dumps(body)}

def _mk_event_get(path: str, qs: dict | None):
    return {"httpMethod": "GET", "path": path, "queryStringParameters": qs if qs is not None else None}

def _set_env(monkeypatch):
    monkeypatch.setenv("DOCDB_URI", "mongodb://test")
    monkeypatch.setenv("DOCDB_USER", "u")
    monkeypatch.setenv("DOCDB_PASS", "p")

@pytest.mark.unit
def test_post_activity_valid(monkeypatch):
    _set_env(monkeypatch)
    with patch("backend.activity_api.MongoClient") as mc:
        client = mc.return_value
        db = client.__getitem__.return_value
        users = MagicMock(); acts = MagicMock()
        db.__getitem__.side_effect = lambda name: {"users": users, "activities": acts}[name]
        users.find_one.return_value = {"userId": "u1"}
        acts.insert_one.return_value = MagicMock(inserted_id="abc123")
        event = _mk_event_post({"userId": "u1", "activityType": "run", "description": "morning"})
        res = activity_api.lambda_handler(event, None)
        assert res["statusCode"] in (200, 201)

@pytest.mark.unit
def test_post_activity_missing_fields(monkeypatch):
    _set_env(monkeypatch)
    with patch("backend.activity_api.MongoClient"):
        event = _mk_event_post({"activityType": "run"})  # missing fields
        res = activity_api.lambda_handler(event, None)
        assert res["statusCode"] == 400

@pytest.mark.unit
def test_post_activity_db_error(monkeypatch):
    _set_env(monkeypatch)
    with patch("backend.activity_api.MongoClient", side_effect=Exception("DB error")):
        event = _mk_event_post({"userId": "u1", "activityType": "run", "description": "morning"})
        res = activity_api.lambda_handler(event, None)
        assert res["statusCode"] in (500, 400)

@pytest.mark.unit
def test_get_activity_suggestion_valid(monkeypatch):
    _set_env(monkeypatch)
    with patch("backend.activity_api.MongoClient") as mc:
        client = mc.return_value
        db = client.__getitem__.return_value
        users = MagicMock(); acts = MagicMock()
        db.__getitem__.side_effect = lambda name: {"users": users, "activities": acts}.get(name, MagicMock())
        users.find_one.return_value = {"userId": "u1"}
        acts.find.return_value = [{"userId": "u1", "activityType": "run", "description": "morning"}]
        event = _mk_event_get("/activity-suggestion", {"userId": "u1"})
        res = activity_api.lambda_handler(event, None)
        assert res["statusCode"] in (200, 204)

@pytest.mark.unit
def test_get_activity_suggestion_missing_userid(monkeypatch):
    _set_env(monkeypatch)
    with patch("backend.activity_api.MongoClient"):
        event = _mk_event_get("/activity-suggestion", {})
        res = activity_api.lambda_handler(event, None)
        assert res["statusCode"] == 400

@pytest.mark.unit
def test_get_activity_suggestion_no_activities(monkeypatch):
    _set_env(monkeypatch)
    with patch("backend.activity_api.MongoClient") as mc:
        client = mc.return_value
        db = client.__getitem__.return_value
        users = MagicMock(); acts = MagicMock()
        db.__getitem__.side_effect = lambda name: {"users": users, "activities": acts}.get(name, MagicMock())
        users.find_one.return_value = {"userId": "u1"}
        acts.find.return_value = []
        event = _mk_event_get("/activity-suggestion", {"userId": "u1"})
        res = activity_api.lambda_handler(event, None)
        assert res["statusCode"] in (404, 204)

@pytest.mark.unit
def test_get_activity_log_listing(monkeypatch):
    _set_env(monkeypatch)
    with patch("backend.activity_api.MongoClient") as mc:
        client = mc.return_value
        db = client.__getitem__.return_value
        acts = MagicMock()
        db.__getitem__.side_effect = lambda name: {"activities": acts}.get(name, MagicMock())
        acts.find.return_value = [{"userId": "u1"}, {"userId": "u1"}]
        event = _mk_event_get("/activity-log", {"userId": "u1"})
        res = activity_api.lambda_handler(event, None)
        assert res["statusCode"] in (200, 204)

@pytest.mark.unit
def test_put_activity_update_success(monkeypatch):
    _set_env(monkeypatch)
    with patch("backend.activity_api.MongoClient") as mc:
        client = mc.return_value
        db = client.__getitem__.return_value
        acts = MagicMock()
        db.__getitem__.side_effect = lambda name: {"activities": acts}.get(name, MagicMock())
        acts.update_one.return_value = MagicMock(matched_count=1, modified_count=1)
        event = _mk_event_put("/activity-log", {"activityId": "a1", "description": "updated"})
        res = activity_api.lambda_handler(event, None)
        assert res["statusCode"] in (200, 204)