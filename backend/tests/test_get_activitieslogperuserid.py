import pytest
import mongomock

from backend import get_activitieslogperuserid as mod

def test_get_activities_success(patch_mongo_get_acts):
    event = {"queryStringParameters": {"userId": "u1"}}
    res = mod.lambda_handler(event, None)
    assert res["statusCode"] in (200, 204)

def test_get_activities_missing_userid(patch_mongo_get_acts):
    event = {"queryStringParameters": {}}
    res = mod.lambda_handler(event, None)
    assert res["statusCode"] == 400
    assert ("Missing userId" in res["body"]) or ("Missing 'user_id'" in res["body"])

def test_get_activities_db_error(patch_mongo_get_acts, monkeypatch):
    import mongomock
    monkeypatch.setattr(mod, "MongoClient", lambda *a, **kw: (_ for _ in ()).throw(Exception("DB error")), raising=True)
    event = {"queryStringParameters": {"userId": "u1"}}
    res = mod.lambda_handler(event, None)
    assert res["statusCode"] in (500, 400)
    event = apigw_event_factory("GET", "/get-activitieslogperuserid", {})
    resp = get_activitieslogperuserid.lambda_handler(event, None)
    assert_status(resp, 400)
    body = parse_json_body(resp)
    assert "Missing userId" in body.get("error", "")

@pytest.mark.unit
def test_invalid_route(env_docdb):
    event = apigw_event_factory("GET", "/unknown-path", {})
    resp = get_activitieslogperuserid.lambda_handler(event, None)
    assert_status(resp, 400)
    body = parse_json_body(resp)
    assert "Invalid request" in body.get("error", "")
