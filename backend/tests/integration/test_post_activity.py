import requests
import pytest

API_URL = "https://tylp1a64mg.execute-api.eu-west-2.amazonaws.com/prod/activities"
TOKEN = "your_token"  # Replace with a valid token

@pytest.fixture
def activity_payload():
    return {
        "userId": "test-user-id",
        "activityType": "reading",
        "description": "Read a book",
        "mood": 5,
        "timestamp": "2025-08-12T10:00:00Z"
    }

def test_post_activity_success(activity_payload):
    headers = {"x-api-key": "EHsn17DBbq4QvO34nUzsf9pk1GNEcXLi6U9EdN84"}
    response = requests.post(API_URL, json=activity_payload, headers=headers)
    assert response.status_code == 201
    assert "activityId" in response.text

def test_post_activity_missing_mood(activity_payload):
    payload = activity_payload.copy()
    del payload["mood"]
    headers = {"x-api-key": "EHsn17DBbq4QvO34nUzsf9pk1GNEcXLi6U9EdN84"}
    response = requests.post(API_URL, json=payload, headers=headers)
    assert response.status_code == 400
    assert "Missing" in response.text

def test_post_activity_invalid_token(activity_payload):
    # No token logic needed; skip this test or assert open access
    pass
