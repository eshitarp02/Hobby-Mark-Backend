
import pytest
import requests
import random
import string

BASE_URL = "https://tylp1a64mg.execute-api.eu-west-2.amazonaws.com/prod"
API_KEY = "EHsn17DBbq4QvO34nUzsf9pk1GNEcXLi6U9EdN84"
HEADERS = {"x-api-key": API_KEY}

@pytest.fixture(scope="session")
def registered_user():
    rand_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    name = f"user_inttest_{rand_suffix}"
    email = f"{name}@example.com"
    password = f"Pass_{rand_suffix}"
    payload = {
        "action": "register",
        "name": name,
        "email": email,
        "password": password
    }
    response = requests.post(f"{BASE_URL}/register", json=payload, headers=HEADERS)
    response.raise_for_status()
    user_id = response.json().get("userId")
    return {"name": name, "email": email, "password": password, "userId": user_id}

@pytest.fixture(scope="session")
def logged_in_user(registered_user):
    payload = {
        "username": registered_user["email"],
        "password": registered_user["password"]
    }
    response = requests.post(f"{BASE_URL}/login", json=payload, headers=HEADERS)
    response.raise_for_status()
    user_id = response.json().get("userId")
    return {"userId": user_id, "email": registered_user["email"], "password": registered_user["password"]}

@pytest.fixture(scope="session")
def created_activity(logged_in_user):
    payload = {
        "userId": logged_in_user["userId"],
        "activityType": "test_activity",
        "description": "Integration test activity"
    }
    response = requests.post(f"{BASE_URL}/activities", json=payload, headers=HEADERS)
    response.raise_for_status()
    activity_id = response.json().get("activityId")
    return {"activityId": activity_id, "userId": logged_in_user["userId"]}

