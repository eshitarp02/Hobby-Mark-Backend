import json

def parse_json_body(resp):
    return json.loads(resp["body"]) if "body" in resp else resp

def assert_status(resp, code):
    assert resp["statusCode"] == code
