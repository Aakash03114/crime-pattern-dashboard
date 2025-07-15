import streamlit as st
import pandas as pd
import plotly.express as px
from utils import authenticate_user
import json
import io

st.set_page_config(page_title="Crime Pattern Dashboard", layout="wide")

# Sidebar Login
st.sidebar.title("🔐 Login")
username = st.sidebar.text_input("Username")
password = st.sidebar.text_input("Password", type="password")
login_btn = st.sidebar.button("Login")

# Load user credentials
try:
    with open("users.json") as f:
        users_data = json.load(f)
except Exception as e:
    st.error(f"❌ users.json load failed: {e}")
    st.stop()

# Authenticate user
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

    uploaded_file = st.file_uploader("📂 Upload your Crime Data CSV", type="csv")

    sample_csv = """date,crime_type,latitude,longitude
2023-01-01,Theft,13.0827,80.2707
2023-01-02,Assault,13.0829,80.2710"""
    st.download_button("📥 Download Sample CSV Format", io.BytesIO(sample_csv.encode()), "sample_crime_data.csv")

    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
        except Exception as e:
            st.error(f"❌ Failed to read uploaded file: {e}")
            st.stop()

        df.columns = df.columns.str.lower()
        required_columns = {'date', 'crime_type', 'latitude', 'longitude'}
        if not required_columns.issubset(df.columns):
            st.error("❗ Uploaded CSV must contain columns: 'date', 'crime_type', 'latitude', 'longitude'")
            st.stop()

        try:
            df['date'] = pd.to_datetime(df['date'])
        except Exception as e:
            st.error(f"❗ Couldn't parse 'date' column: {e}")
            st.stop()

        if role == "public":
            st.info("Public View: Limited Access")
            st.subheader("Crime Count by Type")
            fig = px.bar(df['crime_type'].value_counts().reset_index(),
                         x='index', y='crime_type',
                         labels={'index': 'Crime Type', 'crime_type': 'Count'},
                         title="Crime Frequency by Type")
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
            st.subheader("Full Crime Dataset")
            st.dataframe(df)
            st.subheader("📍 Crime Map")
            st.map(df[['latitude', 'longitude']].dropna())

            if st.button("Download Full Data"):
                df.to_csv("full_data.csv", index=False)
                with open("full_data.csv", "rb") as f:
                    st.download_button("Download CSV", f, "full_data.csv")
    else:
        st.warning("⬆️ Please upload a valid CSV file to continue.")
else:
    st.warning("🔒 Please log in to access the dashboard.")