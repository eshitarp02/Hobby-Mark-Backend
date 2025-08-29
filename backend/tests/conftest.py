# backend/tests/conftest.py
import json
import pytest
import mongomock

def apigw_event_factory(method="GET", path="/", query=None, body=None):
    if isinstance(body, (dict, list)):
        body = json.dumps(body)
    return {
        "resource": path,
        "path": path,
        "httpMethod": method,
        "headers": {"Content-Type": "application/json"},
        "queryStringParameters": query if query is not None else None,
        "requestContext": {"path": path, "httpMethod": method, "stage": "test"},
        "body": body,
        "isBase64Encoded": False,
    }

@pytest.fixture
def env_docdb(monkeypatch):
    # activity_api.get_db() requires these; provide fakes for tests
    monkeypatch.setenv("DOCDB_URI", "mongodb://localhost:27017/?retryWrites=false")
    monkeypatch.setenv("DOCDB_USER", "tester")
    monkeypatch.setenv("DOCDB_PASS", "secret")

@pytest.fixture
def patch_mongo_activity_api(monkeypatch, env_docdb):
    import backend.activity_api as m
    # your module imports MongoClient directly, so patch on the module
    if hasattr(m, "MongoClient"):
        monkeypatch.setattr(m, "MongoClient", mongomock.MongoClient, raising=True)
    # handle import pymongo case as well (future-proof)
    if hasattr(m, "pymongo") and hasattr(m.pymongo, "MongoClient"):
        monkeypatch.setattr(m.pymongo, "MongoClient", mongomock.MongoClient, raising=True)
    return m
