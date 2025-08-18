import streamlit as st
import pandas as pd
import plotly.express as px
import json
import io
import os
import tempfile
from datetime import datetime
from fpdf import FPDF
from utils import authenticate_user, create_user
from prophet import Prophet
import matplotlib.pyplot as plt

st.set_page_config(page_title="Crime Pattern Dashboard", layout="wide")

# Initialize session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None
if "role" not in st.session_state:
    st.session_state.role = None

# -------------------- LOGIN SCREEN --------------------
def login_screen():
    st.title("🔐 Crime Pattern Dashboard - Login")

    tab1, tab2 = st.tabs(["Login", "Sign Up"])

    with tab1:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            role = authenticate_user(username, password)
            if role:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.role = role
                st.success(f"✅ Logged in as {role}")
                st.rerun()
            else:
                st.error("❌ Invalid username or password")

    with tab2:
        st.subheader("Create a New Account")
        new_username = st.text_input("Choose Username")
        new_password = st.text_input("Choose Password", type="password")
        new_role = st.selectbox("Role", ["public", "analyst", "law"])
        if st.button("Sign Up"):
            if create_user(new_username, new_password, new_role):
                st.success("✅ Account created successfully! Please login.")
            else:
                st.error("❌ Username already exists.")

# -------------------- REPORT GENERATION --------------------
def generate_pdf_report(df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Crime Pattern Report", ln=True, align="C")

    for i, row in df.head(20).iterrows():
        pdf.cell(200, 10, txt=str(row.to_dict()), ln=True)

    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, "crime_report.pdf")
    pdf.output(file_path)
    return file_path

def generate_excel_report(df):
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, "crime_report.xlsx")
    df.to_excel(file_path, index=False)
    return file_path

# -------------------- FORECASTING --------------------
def generate_forecast(df):
    if "Date" not in df.columns:
        st.warning("⚠️ No 'Date' column found for forecasting.")
        return

    # Aggregate by date
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])
    daily_counts = df.groupby("Date").size().reset_index(name="y")
    daily_counts = daily_counts.rename(columns={"Date": "ds"})

    if len(daily_counts) < 5:
        st.warning("⚠️ Not enough data for forecasting.")
        return

    model = Prophet()
    model.fit(daily_counts)
    future = model.make_future_dataframe(periods=30)
    forecast = model.predict(future)

    st.subheader("📈 Crime Forecast (Next 30 Days)")

    # Plot Actual vs Predicted
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(daily_counts["ds"], daily_counts["y"], label="Actual", marker="o")
    ax.plot(forecast["ds"], forecast["yhat"], label="Predicted", linestyle="--")
    ax.fill_between(forecast["ds"], forecast["yhat_lower"], forecast["yhat_upper"], alpha=0.2, label="Confidence Interval")
    ax.legend()
    st.pyplot(fig)

# -------------------- FILE UPLOAD + CLEANING --------------------
def handle_file_upload():
    uploaded_file = st.file_uploader("📂 Upload a data file", type=["csv", "xlsx", "json"])
    if uploaded_file is not None:
        file_type = uploaded_file.name.split(".")[-1].lower()

        try:
            if file_type == "csv":
                raw_df = pd.read_csv(uploaded_file)
            elif file_type == "xlsx":
                raw_df = pd.read_excel(uploaded_file)
            elif file_type == "json":
                raw_df = pd.read_json(uploaded_file)
            else:
                st.error("❌ Unsupported file type")
                return None, None
        except Exception as e:
            st.error(f"⚠️ Error reading file: {e}")
            return None, None

        # --- Raw Data Preview ---
        st.subheader("📂 Raw Data (Uploaded)")
        st.dataframe(raw_df.head(10))

        # --- Cleaning ---
        cleaned_df = raw_df.drop_duplicates().copy()
        for col in cleaned_df.columns:
            if "name" in col.lower():
                cleaned_df[col] = "ANONYMIZED"

        # --- Cleaned Data Preview ---
        st.subheader("✅ Cleaned Data (After Preprocessing)")
        st.dataframe(cleaned_df.head(10))

        # --- Comparison Summary ---
        st.subheader("📊 Preprocessing Summary")
        st.write(f"🔹 Rows before cleaning: {len(raw_df)}")
        st.write(f"🔹 Rows after cleaning: {len(cleaned_df)}")
        st.write(f"🔹 Duplicates removed: {len(raw_df) - len(cleaned_df)}")

        anon_cols = [col for col in raw_df.columns if "name" in col.lower()]
        if anon_cols:
            st.write(f"🔹 Columns anonymized: {', '.join(anon_cols)}")

        return raw_df, cleaned_df

    return None, None

# -------------------- DASHBOARDS --------------------
def public_dashboard():
    st.title("🌍 Public Crime Dashboard")
    raw_df, cleaned_df = handle_file_upload()
    if cleaned_df is not None:
        st.write("📊 Basic Crime Statistics")
        st.bar_chart(cleaned_df["Crime Type"].value_counts())

def analyst_dashboard():
    st.title("📊 Analyst Crime Dashboard")
    raw_df, cleaned_df = handle_file_upload()
    if cleaned_df is not None:
        st.write("📌 Crime Type Distribution")
        fig = px.bar(cleaned_df, x="Crime Type", title="Crime Counts by Type")
        st.plotly_chart(fig)

        st.write("📌 Crimes Over Time")
        if "Date" in cleaned_df.columns:
            cleaned_df["Date"] = pd.to_datetime(cleaned_df["Date"], errors="coerce")
            trend = cleaned_df.groupby("Date").size().reset_index(name="Counts")
            fig2 = px.line(trend, x="Date", y="Counts", title="Crimes Over Time")
            st.plotly_chart(fig2)

        # Report downloads
        pdf_file = generate_pdf_report(cleaned_df)
        excel_file = generate_excel_report(cleaned_df)
        with open(pdf_file, "rb") as f:
            st.download_button("⬇️ Download PDF Report", f, file_name="crime_report.pdf")
        with open(excel_file, "rb") as f:
            st.download_button("⬇️ Download Excel Report", f, file_name="crime_report.xlsx")

def law_dashboard():
    st.title("👮 Law Enforcement Dashboard")
    raw_df, cleaned_df = handle_file_upload()
    if cleaned_df is not None:
        st.write("📌 Crime Type Heatmap")
        if {"Latitude", "Longitude"}.issubset(cleaned_df.columns):
            fig = px.density_mapbox(cleaned_df, lat="Latitude", lon="Longitude",
                                    radius=10, center=dict(lat=20, lon=78), zoom=3,
                                    mapbox_style="carto-positron")
            st.plotly_chart(fig)

        # Forecast crimes
        generate_forecast(cleaned_df)

        # Report downloads
        pdf_file = generate_pdf_report(cleaned_df)
        excel_file = generate_excel_report(cleaned_df)
        with open(pdf_file, "rb") as f:
            st.download_button("⬇️ Download PDF Report", f, file_name="crime_report.pdf")
        with open(excel_file, "rb") as f:
            st.download_button("⬇️ Download Excel Report", f, file_name="crime_report.xlsx")

# -------------------- MAIN APP --------------------
if not st.session_state.logged_in:
    login_screen()
else:
    role = st.session_state.role
    if role == "public":
        public_dashboard()
    elif role == "analyst":
        analyst_dashboard()
    elif role == "law":
        law_dashboard()

    if st.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()
