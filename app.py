import streamlit as st
import pandas as pd
import plotly.express as px
from utils import authenticate_user
import json
import io
from sklearn.cluster import KMeans
from fpdf import FPDF
from datetime import datetime
from prophet import Prophet

st.set_page_config(page_title="Crime Pattern Dashboard", layout="wide")

# Sidebar Login / Signup
st.sidebar.title("🔐 Login or Signup")
option = st.sidebar.radio("Choose Action", ["Login", "Sign Up"])

# Load or create user file
try:
    with open("users.json") as f:
        users_data = json.load(f)
except:
    users_data = {}
    with open("users.json", "w") as f:
        json.dump(users_data, f)

# Signup
if option == "Sign Up":
    new_user = st.sidebar.text_input("New Username")
    new_pass = st.sidebar.text_input("New Password", type="password")
    role = st.sidebar.selectbox("Role", ["public", "analyst", "law_enforcement"])
    if st.sidebar.button("Create Account"):
        if new_user in users_data:
            st.sidebar.error("Username already exists")
        else:
            users_data[new_user] = {"password": new_pass, "role": role}
            with open("users.json", "w") as f:
                json.dump(users_data, f)
            st.sidebar.success("Account created! Please log in.")

# Login
if option == "Login":
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

    uploaded_file = st.file_uploader("📂 Upload your Crime Data CSV", type="csv")
    sample_csv = "date,crime_type,latitude,longitude\n2023-01-01,Theft,13.0827,80.2707\n2023-01-02,Assault,13.0829,80.2710"
    st.download_button("📥 Download Sample CSV Format", io.BytesIO(sample_csv.encode()), "sample_crime_data.csv")

    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file)
        except Exception as e:
            st.error(f"❌ Failed to read uploaded file: {e}")
            st.stop()

        # Normalize columns
        df.columns = df.columns.str.lower()

        required = {'date', 'crime_type', 'latitude', 'longitude'}
        if not required.issubset(df.columns):
            st.error("❗ CSV must include: date, crime_type, latitude, longitude")
            st.stop()

        # Remove duplicates
        before = len(df)
        df.drop_duplicates(inplace=True)
        after = len(df)
        if before != after:
            st.warning(f"🧹 Removed {before - after} duplicate rows.")

        # Convert date
        try:
            df['date'] = pd.to_datetime(df['date'])
        except Exception as e:
            st.error(f"❌ Invalid 'date' format: {e}")
            st.stop()

        # Anonymization
        for col in ['officer_id', 'reporter_name']:
            if col in df.columns:
                df[col] = "ANONYMIZED"

        st.success("✅ Data Loaded and Cleaned")

        # ROLE: PUBLIC
        if role == "public":
            st.info("Public View")
            fig = px.bar(df['crime_type'].value_counts().reset_index(), x='index', y='crime_type',
                         labels={'index': 'Crime Type', 'crime_type': 'Count'},
                         title="Crime Frequency")
            st.plotly_chart(fig)

        # ROLE: ANALYST
        elif role == "analyst":
            st.success("Analyst View")
            crime_type = st.selectbox("Select Crime Type", df['crime_type'].unique())
            filtered = df[df['crime_type'] == crime_type]
            st.line_chart(filtered['date'].value_counts().sort_index())

            if st.button("📤 Download Filtered Report"):
                filtered.to_csv("filtered.csv", index=False)
                with open("filtered.csv", "rb") as f:
                    st.download_button("Download CSV", f, "report.csv")

        # ROLE: LAW ENFORCEMENT
        elif role == "law_enforcement":
            st.success("Law Enforcement View")

            st.subheader("📍 Crime Map")
            st.map(df[['latitude', 'longitude']].dropna())

            st.subheader("📈 Forecasting (All Crimes Combined)")
            forecast_df = df['date'].value_counts().reset_index()
            forecast_df.columns = ['ds', 'y']
            m = Prophet()
            m.fit(forecast_df)
            future = m.make_future_dataframe(periods=30)
            forecast = m.predict(future)
            fig = px.line(forecast, x='ds', y='yhat', title="📅 Predicted Crime Frequency")
            st.plotly_chart(fig)

            st.subheader("🔥 Crime Hotspot Detection (KMeans)")
            try:
                kmeans = KMeans(n_clusters=3, random_state=42).fit(df[['latitude', 'longitude']].dropna())
                df['cluster'] = kmeans.labels_
                fig = px.scatter_mapbox(df, lat="latitude", lon="longitude", color="cluster", zoom=10,
                                        mapbox_style="carto-positron", title="KMeans Hotspot Clustering")
                st.plotly_chart(fig)
            except:
                st.warning("❌ Not enough geolocation data for hotspot detection.")

            st.subheader("📄 Generate PDF Report")
            summary = df['crime_type'].value_counts().reset_index()
            summary.columns = ['crime_type', 'count']
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, txt="Crime Summary Report", ln=True, align='C')
            pdf.ln()
            for _, row in summary.iterrows():
                pdf.cell(200, 10, txt=f"{row['crime_type']}: {row['count']}", ln=True)
            pdf.output("report.pdf")
            with open("report.pdf", "rb") as f:
                st.download_button("Download PDF", f, "crime_report.pdf")

            if st.button("📥 Download Full CSV"):
                df.to_csv("full_data.csv", index=False)
                with open("full_data.csv", "rb") as f:
                    st.download_button("Download CSV", f, "full_data.csv")
    else:
        st.warning("⬆️ Upload a valid crime data CSV to continue.")
else:
    st.warning("🔒 Please log in to access the dashboard.")
