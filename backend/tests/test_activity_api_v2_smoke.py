from backend import activity_api_v2 as mod

def test_v2_smoke_get(patch_mongo_v2, apigw_event_factory):
    ev = apigw_event_factory("GET", "/activity-suggestion-v2", {"userId": "u1"})
    res = mod.lambda_handler(ev, None)
    assert isinstance(res, dict) and "statusCode" in res
    assert res["statusCode"] in (200, 204, 400)
