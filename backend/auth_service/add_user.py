import sys, json, os
from pathlib import Path
from app import hash_password, AUTH_DATA_DIR, USERS_FILE

AUTH_DATA_DIR.mkdir(parents=True, exist_ok=True)
USERS_FILE.touch(exist_ok=True)

def add_user(username, password, role="user"):
    users = {}
    if USERS_FILE.exists():
        with open(USERS_FILE, "r") as f:
            try:
                users = json.load(f)
            except json.JSONDecodeError:
                pass
    users[username] = {"username": username, "password": hash_password(password), "role": role}
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)
    print(f"User {username} added successfully.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python add_user.py <username> <password> [role]")
    else:
        role = sys.argv[3] if len(sys.argv) > 3 else "user"
        add_user(sys.argv[1], sys.argv[2], role)
