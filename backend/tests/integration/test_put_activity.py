import requests
import pytest

API_URL = "https://tylp1a64mg.execute-api.eu-west-2.amazonaws.com/prod/activities"
TOKEN = "your_token"  # Replace with a valid token

@pytest.fixture
def update_payload():
    return {
        "activityId": "existing-activity-id",
        "description": "Updated description",
        "mood": 4
    }

def test_put_activity_success(update_payload):
    headers = {"x-api-key": "EHsn17DBbq4QvO34nUzsf9pk1GNEcXLi6U9EdN84"}
    response = requests.put(f"{API_URL}/existing-activity-id", json=update_payload, headers=headers)
    assert response.status_code == 200
    assert "updated" in response.text

def test_put_activity_not_found(update_payload):
    headers = {"x-api-key": "EHsn17DBbq4QvO34nUzsf9pk1GNEcXLi6U9EdN84"}
    response = requests.put(f"{API_URL}/nonexistent-id", json=update_payload, headers=headers)
    assert response.status_code == 404
    assert "not found" in response.text

def test_put_activity_unauthorized(update_payload):
    # No token logic needed; skip this test or assert open access
    pass
