import json
import hashlib
import os

USER_FILE = "users.json"

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def load_users():
    if not os.path.exists(USER_FILE):
        with open(USER_FILE, "w") as f:
            json.dump({"users": []}, f)

    with open(USER_FILE, "r") as f:
        return json.load(f)["users"]

def save_users(users):
    with open(USER_FILE, "w") as f:
        json.dump({"users": users}, f, indent=4)

def authenticate_user(username, password):
    users = load_users()
    hashed = hash_password(password)
    for user in users:
        if user["username"] == username and user["password"] == hashed:
            return user["role"]
    return None

def create_user(username, password, role):
    users = load_users()
    if any(u["username"] == username for u in users):
        return False
    users.append({
        "username": username,
        "password": hash_password(password),
        "role": role
    })
    save_users(users)
    return True
