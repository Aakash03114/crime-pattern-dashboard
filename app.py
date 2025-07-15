import streamlit as st
import pandas as pd
import plotly.express as px
from utils import authenticate_user

st.set_page_config(page_title="Crime Dashboard", layout="wide")

# Login
st.sidebar.title("🔐 Login")
username = st.sidebar.text_input("Username")
password = st.sidebar.text_input("Password", type="password")
login_btn = st.sidebar.button("Login")

if login_btn:
    role = authenticate_user(username, password)
    if role:
        st.session_state['logged_in'] = True
        st.session_state['username'] = username
        st.session_state['role'] = role
        st.success(f"Welcome, {username} ({role})")
    else:
        st.error("Invalid username or password")

# After login
if 'logged_in' in st.session_state and st.session_state['logged_in']:
    role = st.session_state['role']
    st.title("📊 Crime Pattern Analysis Dashboard")

    # Load your own dataset here
    try:
        df = pd.read_csv("crime_data.csv", parse_dates=['date'])
    except:
        st.error("Missing 'crime_data.csv' file with 'date', 'latitude', 'longitude', 'crime_type' columns.")
        st.stop()

    if role == "public":
        st.info("Public View: Limited Access")
        st.subheader("Crime Count by Type")
        fig = px.bar(df['crime_type'].value_counts(), labels={'value': 'Count', 'index': 'Crime Type'}, title="Crime Type Frequency")
        st.plotly_chart(fig)

    elif role == "analyst":
        st.success("Analyst View: Filter and Export")
        crime_type = st.selectbox("Select Crime Type", df['crime_type'].unique())
        filtered = df[df['crime_type'] == crime_type]
        st.line_chart(filtered['date'].value_counts().sort_index())

        if st.button("Download Filtered Report"):
            filtered.to_csv("filtered_report.csv", index=False)
            with open("filtered_report.csv", "rb") as f:
                st.download_button("Download CSV", f, "report.csv")

    elif role == "law_enforcement":
        st.success("Law Enforcement View: Full Access")
        st.subheader("Full Dataset")
        st.dataframe(df)

        st.subheader("📍 Crime Map")
        st.map(df[['latitude', 'longitude']].dropna())

        if st.button("Download Full Data"):
            df.to_csv("full_data.csv", index=False)
            with open("full_data.csv", "rb") as f:
                st.download_button("Download CSV", f, "full_data.csv")

else:
    st.warning("Please login to access the dashboard.")
