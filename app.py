import streamlit as st
import pandas as pd
import plotly.express as px
import json
import io
from utils import authenticate_user, create_user

st.set_page_config(page_title="Crime Dashboard", layout="wide")

# --- Session Setup ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""

# --- Login UI ---
def show_login():
    st.markdown("<h2 style='text-align: center;'>🔐 Login</h2>", unsafe_allow_html=True)
    st.markdown("<div style='text-align: center;'>Please enter your credentials to continue.</div>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_btn = st.button("Login")

        if login_btn:
            role = authenticate_user(username, password)
            if role:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.role = role
                st.success(f"Welcome, {username} ({role})")
                st.experimental_rerun()
            else:
                st.error("Invalid username or password.")

    st.markdown("---")
    st.markdown("#### 📝 New User? Sign Up Below")
    new_username = st.text_input("New Username")
    new_password = st.text_input("New Password", type="password")
    new_role = st.selectbox("Select Role", ["public", "analyst", "law_enforcement"])
    signup_btn = st.button("Sign Up")

    if signup_btn:
        if not new_username or not new_password:
            st.warning("Enter both username and password.")
        else:
            success = create_user(new_username, new_password, new_role)
            if success:
                st.success("Account created! You can now login.")
            else:
                st.error("Username already exists.")

# --- Dashboard after Login ---
def show_dashboard():
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
            return

        df.columns = df.columns.str.lower()
        required_columns = {'date', 'crime_type', 'latitude', 'longitude'}
        if not required_columns.issubset(df.columns):
            st.error("❗ Uploaded CSV must contain: 'date', 'crime_type', 'latitude', 'longitude'")
            return

        try:
            df['date'] = pd.to_datetime(df['date'])
        except Exception as e:
            st.error(f"❗ Couldn't parse 'date': {e}")
            return

        if role == "public":
            st.info("🔎 Public View: Limited Access")
            st.subheader("Crime Count by Type")
            fig = px.bar(df['crime_type'].value_counts().reset_index(),
                         x='index', y='crime_type',
                         labels={'index': 'Crime Type', 'crime_type': 'Count'},
                         title="Crime Frequency by Type")
            st.plotly_chart(fig)

        elif role == "analyst":
            st.success("📊 Analyst View: Filter and Export")
            crime_type = st.selectbox("Select Crime Type", df['crime_type'].unique())
            filtered = df[df['crime_type'] == crime_type]
            st.line_chart(filtered['date'].value_counts().sort_index())

            if st.button("Download Filtered Report (CSV)"):
                filtered.to_csv("filtered_report.csv", index=False)
                with open("filtered_report.csv", "rb") as f:
                    st.download_button("Download CSV", f, "report.csv")

        elif role == "law_enforcement":
            st.success("🛡️ Law Enforcement View: Full Access")
            st.subheader("Full Crime Dataset")
            st.dataframe(df)
            st.subheader("📍 Crime Map")
            st.map(df[['latitude', 'longitude']].dropna())

            # Excel Report
            if st.button("Download Excel Report"):
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name="Crime Data")
                st.download_button("📄 Download Excel", data=excel_buffer.getvalue(), file_name="crime_data.xlsx")

            # PDF Summary
            if st.button("Download PDF Summary"):
                from fpdf import FPDF
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", size=12)
                pdf.cell(200, 10, txt="Crime Summary Report", ln=True, align='C')
                pdf.ln(10)
                summary = df['crime_type'].value_counts().reset_index(name='count')
                summary.columns = ['crime_type', 'count']
                for _, row in summary.iterrows():
                    pdf.cell(200, 10, txt=f"{row['crime_type']}: {row['count']}", ln=True)

                pdf_output = io.BytesIO(pdf.output(dest='S').encode('latin-1'))
                st.download_button("📄 Download PDF", data=pdf_output, file_name="crime_summary.pdf")

            # Forecasting
            st.subheader("📈 Predict Future Crime Counts")
            try:
                from prophet import Prophet

                forecast_data = df['date'].value_counts().reset_index()
                forecast_data.columns = ['ds', 'y']
                forecast_data = forecast_data.sort_values('ds')

                model = Prophet()
                model.fit(forecast_data)

                future = model.make_future_dataframe(periods=30)
                forecast = model.predict(future)

                st.success("Prediction for next 30 days")
                fig = px.line(forecast, x='ds', y='yhat', title="Crime Forecast (Next 30 Days)",
                              labels={'ds': 'Date', 'yhat': 'Predicted Count'})
                st.plotly_chart(fig)
            except Exception as e:
                st.error(f"❌ Forecasting failed: {e}")

            # Hotspot Detection
            st.subheader("🔥 Crime Hotspot Detection")
            from sklearn.cluster import KMeans
            location_df = df[['latitude', 'longitude']].dropna()
            if len(location_df) < 3:
                st.warning("Need at least 3 locations.")
            else:
                k = st.slider("Select number of clusters", 2, 10, 3)
                kmeans = KMeans(n_clusters=k, random_state=0)
                location_df['cluster'] = kmeans.fit_predict(location_df)
                fig = px.scatter_mapbox(location_df,
                                        lat='latitude', lon='longitude',
                                        color='cluster', zoom=10,
                                        mapbox_style="carto-positron",
                                        title="🗺️ Crime Hotspots")
                st.plotly_chart(fig)
    else:
        st.warning("⬆️ Please upload a valid CSV file.")

# --- Main Routing ---
if st.session_state.logged_in:
    show_dashboard()
else:
    show_login()
