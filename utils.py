import json

def load_users(file='users.json'):
    with open(file) as f:
        return json.load(f)

def authenticate_user(username, password):
    users = load_users()
    if username in users and users[username]['password'] == password:
        return users[username]['role']
    return None
