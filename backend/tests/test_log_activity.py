import pytest
import mongomock
from backend import log_activity
from tests.conftest import apigw_event_factory
from tests.helpers import parse_json_body, assert_status

@pytest.fixture(autouse=True)
def patch_mongo(monkeypatch):
    monkeypatch.setattr(log_activity, "MongoClient", mongomock.MongoClient)

@pytest.mark.unit
def test_log_activity_success(patch_mongo_log_activity, monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    event = {"body": '{"userId": "u1", "activityType": "run", "description": "desc"}'}
    res = log_activity.lambda_handler(event, None)
    assert res["statusCode"] in (200, 201)

@pytest.mark.unit
def test_log_activity_missing_fields(patch_mongo_log_activity):
    event = {"body": '{"activityType": "run"}'}
    res = log_activity.lambda_handler(event, None)
    assert res["statusCode"] == 400

@pytest.mark.unit
def test_log_activity_db_timeout(patch_mongo_log_activity, monkeypatch):
    import mongomock
    monkeypatch.setattr(log_activity, "MongoClient", lambda *a, **kw: (_ for _ in ()).throw(Exception("Timeout")), raising=True)
    event = {"body": '{"userId": "u1", "activityType": "run", "description": "desc"}'}
    res = log_activity.lambda_handler(event, None)
    assert res["statusCode"] in (500, 400)
