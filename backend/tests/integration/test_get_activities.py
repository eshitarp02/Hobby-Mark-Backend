import requests
import pytest


# Use API URL and API key from test_login.py
API_URL = "https://tylp1a64mg.execute-api.eu-west-2.amazonaws.com/prod/get-suggestion"
API_KEY = "EHsn17DBbq4QvO34nUzsf9pk1GNEcXLi6U9EdN84"

@pytest.fixture
def get_headers():
    return {}

def test_get_suggestion_success(get_headers):
    headers = {"x-api-key": API_KEY}
    params = {"userId": "testuser"}
    response = requests.get(API_URL, headers=headers, params=params)
    assert response.status_code == 200
    data = response.json()
    assert "suggestion" in data
    assert isinstance(data.get("alternatives"), list)
    assert "reasoning" in data

def test_get_suggestion_empty(get_headers):
    headers = {"x-api-key": API_KEY}
    params = {"userId": "empty-user"}
    response = requests.get(API_URL, headers=headers, params=params)
    assert response.status_code == 200
    data = response.json()
    assert "suggestion" in data

def test_get_suggestion_with_time_weather(get_headers):
    headers = {"x-api-key": API_KEY}
    params = {"userId": "testuser", "timeOfDay": "morning", "weather": "clear"}
    response = requests.get(API_URL, headers=headers, params=params)
    assert response.status_code == 200
    data = response.json()
    assert "suggestion" in data

def test_get_suggestion_missing_userid(get_headers):
    headers = {"x-api-key": API_KEY}
    response = requests.get(API_URL, headers=headers)
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
