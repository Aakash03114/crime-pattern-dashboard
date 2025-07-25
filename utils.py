import json
import os

USERS_FILE = "users.json"

# Load users
def load_users():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w") as f:
            json.dump({"users": []}, f)
    with open(USERS_FILE, "r") as f:
        return json.load(f)["users"]

# Save users
def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump({"users": users}, f, indent=4)

# Authenticate user
def authenticate_user(username, password):
    users = load_users()
    for user in users:
        if user["username"] == username and user["password"] == password:
            return user["role"]
    return None

# Create user
# Create user
def create_user(username, password, role):
    users = load_users()
    if any(user["username"] == username for user in users):
        return False  # Username exists
    users.append({
        "username": username,
        "password": password,
        "role": role
    })
    save_users(users)  # ✅ Fixed: added closing parenthesis
    return True

