import requests
import pytest

API_URL = "https://tylp1a64mg.execute-api.eu-west-2.amazonaws.com/prod/login"

@pytest.fixture
def login_payload():
    return {
        "username": "Yogi@example.com",
        "password": "yourpassword"
    }

def test_login_success(login_payload):
    headers = {"x-api-key": "EHsn17DBbq4QvO34nUzsf9pk1GNEcXLi6U9EdN84"}
    response = requests.post(API_URL, json=login_payload, headers=headers)
    assert response.status_code == 200
    assert "userId" in response.text

def test_login_wrong_password(login_payload):
    headers = {"x-api-key": "EHsn17DBbq4QvO34nUzsf9pk1GNEcXLi6U9EdN84"}
    payload = login_payload.copy()
    payload["password"] = "WrongPass"
    response = requests.post(API_URL, json=payload, headers=headers)
    assert response.status_code == 401
    assert "Incorrect password" in response.text

def test_login_unregistered_email(login_payload):
    headers = {"x-api-key": "EHsn17DBbq4QvO34nUzsf9pk1GNEcXLi6U9EdN84"}
    payload = login_payload.copy()
    payload["username"] = "notfound@example.com"
    response = requests.post(API_URL, json=payload, headers=headers)
    assert response.status_code == 404
    assert "not registered" in response.text
