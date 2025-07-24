import json

def load_users(file='users.json'):
    with open(file) as f:
        return json.load(f)

def authenticate_user(username, password):
    users = load_users()
    if username in users["users"] and users["users"][username]["password"] == password:
        return users["users"][username]["role"]
    return None

def create_user(username, password, role, file='users.json'):
    with open(file, 'r+') as f:
        data = json.load(f)
        data["users"][username] = {"password": password, "role": role}
        f.seek(0)
        json.dump(data, f, indent=2)
        f.truncate()
