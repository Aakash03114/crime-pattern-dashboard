import streamlit as st
import json
import os
from utils import authenticate_user, create_user

st.set_page_config(page_title="Crime Pattern Dashboard", page_icon=":shield:", layout="centered")

# Load user data
user_file = "users.json"
if not os.path.exists(user_file):
    with open(user_file, "w") as f:
        json.dump({"users": []}, f)

with open(user_file, "r") as f:
    users = json.load(f)["users"]

# Custom CSS for centered card UI
st.markdown(
    """
    <style>
        body {
            background-color: #0f1116;
        }
        .main {
            display: flex;
            justify-content: center;
            padding-top: 3rem;
        }
        .login-card {
            background-color: #ffffff;
            padding: 2rem 3rem;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
            width: 400px;
        }
        h2 {
            text-align: center;
            color: #0e1117;
        }
        .stTextInput > div > input {
            background-color: #333;
            color: white;
        }
        .stButton button {
            width: 100%;
            background-color: #0e81f7;
            color: white;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# Start Login Card
st.markdown('<div class="main"><div class="login-card">', unsafe_allow_html=True)
st.markdown("<h2>Login</h2>", unsafe_allow_html=True)

username = st.text_input("Username")
password = st.text_input("Password", type="password")

if st.button("Login"):
    role = authenticate_user(username, password)
    if role:
        st.success(f"Login successful! Logged in as {role}.")
        st.session_state["logged_in"] = True
        st.session_state["role"] = role
    else:
        st.error("Invalid username or password.")

st.markdown("<hr>", unsafe_allow_html=True)
st.markdown("<h4 style='text-align: center;'>New User? Sign Up</h4>", unsafe_allow_html=True)

new_username = st.text_input("New Username")
new_password = st.text_input("New Password", type="password")
role_options = ["public", "analyst", "law"]
new_role = st.selectbox("Select Role", role_options)

if st.button("Sign Up"):
    if new_username and new_password:
        if create_user(new_username, new_password, new_role):
            st.success("User created successfully! Please log in.")
        else:
            st.warning("Username already exists.")
    else:
        st.warning("Please fill in all fields.")

st.markdown('</div></div>', unsafe_allow_html=True)
