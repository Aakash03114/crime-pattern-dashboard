import streamlit as st
import pandas as pd
import plotly.express as px
from utils import authenticate_user
import json
import io

# Page configuration
st.set_page_config(page_title="Crime Pattern Dashboard", layout="wide")

# Custom CSS for centered login box
st.markdown("""
    <style>
        .login-container {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            background-color: #f4f4f4;
        }
        .login-box {
            background-color: white;
            padding: 2rem;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            width: 350px;
        }
        .login-box h2 {
            text-align: center;
            margin-bottom: 1rem;
            color: #333;
        }
        .stButton>button {
            width: 100%;
        }
        .signup-divider {
            border-top: 1px solid #ccc;
            margin: 20px 0;
        }
    </style>
""", unsafe_allow_html=True)

# Container for login page
if 'logged_in' not in st.session_state or not st.session_state['logged_in']:
    st.markdown("<div class='login-container'>", unsafe_allow_html=True)
    with st.container():
        st.markdown("<div class='login-box'>", unsafe_allow_html=True)

        st.markdown("<h2>\ud83d\udd10 Login</h2>", unsafe_allow_html=True)
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        login_btn = st.button("Login")

        st.markdown("<div class='signup-divider'></div>", unsafe_allow_html=True)
        st.subheader("\ud83d\udcdd New User? Sign Up")
        new_username = st.text_input("New Username", key="signup_username")
        new_password = st.text_input("New Password", type="password", key="signup_password")
        new_role = st.selectbox("Select Role", ["public", "analyst", "law_enforcement"], key="signup_role")
        signup_btn = st.button("Sign Up")

        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Load user credentials
    try:
        with open("users.json", "r+") as f:
            users_data = json.load(f)
            if signup_btn:
                if not new_username or not new_password:
                    st.error("Please enter both username and password.")
                elif new_username in users_data:
                    st.error("Username already exists!")
                else:
                    users_data[new_username] = {
                        "password": new_password,
                        "role": new_role
                    }
                    f.seek(0)
                    json.dump(users_data, f, indent=2)
                    f.truncate()
                    st.success("Account created successfully! You can now log in.")
    except Exception as e:
        st.error(f"\u274c users.json load failed: {e}")
        st.stop()

    # Authenticate user
    if login_btn:
        role = authenticate_user(username, password)
        if role:
            st.session_state['logged_in'] = True
            st.session_state['username'] = username
            st.session_state['role'] = role
            st.success(f"Welcome, {username} ({role})")
            st.experimental_rerun()
        else:
            st.error("Invalid username or password")

# Show dashboard only after login
if 'logged_in' in st.session_state and st.session_state['logged_in']:
    role = st.session_state['role']
    st.title("\ud83d\udcca Crime Pattern Analysis Dashboard")
    # --- The rest of your dashboard features go here (upload, charts, maps, etc.) ---
    st.success("Dashboard loaded. Ready to implement remaining features.")
