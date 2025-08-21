import json
import os

USERS_FILE = "users.json"

def load_users():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w") as f:
            json.dump({"users": []}, f, indent=4)
    with open(USERS_FILE, "r") as f:
        data = json.load(f)
    return data.get("users", [])

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump({"users": users}, f, indent=4)

def authenticate_user(username, password):
    users = load_users()
    for user in users:
        if user.get("username") == username and user.get("password") == password:
            return user.get("role")
    return None

def create_user(username, password, role):
    users = load_users()
    if any(user.get("username") == username for user in users):
        return False  # Username exists
    users.append({
        "username": username,
        "password": password,
        "role": role
    })
    save_users(users)
    return True
