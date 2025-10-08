# app.py - Crime Pattern Dashboard (full) with PDF unicode-safe export
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import json
import io
import os
import tempfile
import glob
import plotly.express as px
from datetime import datetime
from fpdf import FPDF
from sklearn.metrics import confusion_matrix
import plotly.figure_factory as ff
from sklearn.cluster import KMeans # Added explicit import for Law Enforcement view
from prophet import Prophet # Added explicit import for Law Enforcement view

# Assumed from original code comments, but not provided. 
# Placeholder functions for a complete run-through (assuming a simple dictionary-based auth).
USERS_FILE = "users.json" # Define USERS_FILE globally for placeholder funcs
def load_users():
    """Loads users from the USERS_FILE."""
    if not os.path.exists(USERS_FILE):
        return {"users": []}
    with open(USERS_FILE, "r") as f:
        # Added check for empty file
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {"users": []}

def save_users(users_data):
    """Saves user data to the USERS_FILE."""
    with open(USERS_FILE, "w") as f:
        json.dump(users_data, f, indent=2)

def authenticate_user(username, password):
    """Authenticates a user and returns their role, or None."""
    try:
        users_data = load_users()
        user = next((u for u in users_data.get("users", []) if u["username"] == username and u["password"] == password), None)
        return user["role"] if user else None
    except Exception:
        return None

def create_user(username, password, role):
    """Creates a new user. Returns True on success, False if user exists."""
    try:
        users_data = load_users()
        if any(u["username"] == username for u in users_data.get("users", [])):
            return False # User already exists
        
        if "users" not in users_data:
             users_data["users"] = []
             
        users_data["users"].append({"username": username, "password": password, "role": role})
        save_users(users_data)
        return True
    except Exception:
        return False
# End of placeholder utils

st.set_page_config(page_title="Crime Pattern Dashboard", layout="wide", initial_sidebar_state="expanded")

# ---------------- Session state ----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "role" not in st.session_state:
    st.session_state.role = ""
if "show_forgot_pw" not in st.session_state:
    st.session_state.show_forgot_pw = False

# ---------------- Ensure users.json ----------------
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, "w") as f:
        json.dump({
            "users": [
                {"username": "public", "password": "public123", "role": "public"},
                {"username": "analyst", "password": "analyst123", "role": "analyst"},
                {"username": "law", "password": "law123", "role": "law_enforcement"}
            ]
        }, f, indent=2)


# ---------------- Helpers ----------------
def sanitize_for_pdf(text: str) -> str:
    if text is None:
        return ""
    try:
        replacements = {
            "🚨": "[ALERT]",
            "📊": "[SPIKE]",
            "⚠️": "[WARN]",
            "⚠": "[WARN]",
            "📄": "[REPORT]",
            "🔥": "[HOTSPOT]",
            "✅": "[OK]",
            "→": "->",
            "–": "-",
            "—": "-",
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        # Attempt Latin-1 encoding for broader character support, replacing errors
        safe = text.encode('latin-1', errors='replace').decode('latin-1')
        return safe
    except Exception:
        # Fallback to pure ASCII replacement
        return str(text).encode('ascii', errors='replace').decode('ascii')


def save_plotly_as_image(fig):
    tmp = None
    try:
        # Ensure 'kaleido' is installed for image export: pip install kaleido
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        tmp.close()
        fig.write_image(tmp.name, format="png")
        return tmp.name
    except Exception as e:
        st.warning(f"Could not save chart image. Ensure 'kaleido' is installed (`pip install kaleido`): {e}")
        try:
            if tmp and os.path.exists(tmp.name):
                os.remove(tmp.name)
        except Exception:
            pass
        return None


def cleanup_temp_images():
    tmp_dir = tempfile.gettempdir()
    patterns = [os.path.join(tmp_dir, "*.png"), "*.png"]
    for patt in patterns:
        for p in glob.glob(patt):
            try:
                os.remove(p)
            except Exception:
                pass


def get_alerts(df, role):
    alerts = []
    if df is None or df.empty:
        return alerts
    try:
        if "crime_type" in df.columns:
            vc = df["crime_type"].value_counts()
            top_count = int(vc.max())
            top_type = vc.idxmax()
            if top_count > 50:
                alerts.append(f"🚨 High number of **{top_type}** incidents detected: **{top_count}** cases.")
    except Exception:
        pass

    try:
        if "date" in df.columns:
            # Ensure 'date' column is datetime type before subtraction
            df_dates = df.copy()
            df_dates["date"] = pd.to_datetime(df_dates["date"], errors="coerce")
            last_7d = df_dates[df_dates["date"] >= pd.Timestamp.now() - pd.Timedelta(days=7)]
            if len(last_7d) > 0 and (len(last_7d) / max(1, len(df_dates.dropna(subset=['date'])))) > 0.25:
                pct = int((len(last_7d) / max(1, len(df_dates))) * 100)
                alerts.append(f"📊 **{len(last_7d)}** incidents reported in the last 7 days (**{pct}%** of records).")
    except Exception:
        pass

    if role == "law_enforcement":
        alerts.append("⚠️ System maintenance scheduled for Sunday midnight (01:00–03:00).")
    return alerts


def generate_pdf_report(df, username, chart_paths, alerts):
    pdf = FPDF()
    # Define an alias for the standard font to ensure it can handle basic Latin-1 (used in sanitize)
    pdf.set_font("Arial", size=10) # Set a default font
    
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    title = sanitize_for_pdf("Crime Report Summary")
    pdf.cell(0, 10, title, ln=1, align="C")
    pdf.set_font("Arial", size=11)
    pdf.ln(2)

    byline = sanitize_for_pdf(f"Generated by: {username}")
    pdf.cell(0, 8, byline, ln=1)
    date_line = sanitize_for_pdf(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    pdf.cell(0, 8, date_line, ln=1)
    pdf.ln(4)

    if alerts:
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, sanitize_for_pdf("Alerts & Notifications:"), ln=1)
        pdf.set_font("Arial", size=11)
        for a in alerts:
            pdf.multi_cell(0, 6, sanitize_for_pdf(f"- {a}"))
        pdf.ln(4)

    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, sanitize_for_pdf("Crime Type Counts:"), ln=1)
    pdf.set_font("Arial", size=11)
    try:
        summary = df["crime_type"].value_counts().reset_index()
        summary.columns = ["crime_type", "count"]
        for _, row in summary.iterrows():
            crime = sanitize_for_pdf(str(row["crime_type"]))
            count = int(row["count"])
            pdf.cell(0, 6, sanitize_for_pdf(f"{crime}: {count}"), ln=1)
        pdf.ln(4)
    except Exception:
        pdf.cell(0, 6, sanitize_for_pdf("No crime type summary available."), ln=1)
        pdf.ln(4)

    for path in chart_paths:
        if path and os.path.exists(path):
            try:
                # Calculate image width to fit page, respecting margins (180mm is a safe width for A4)
                pdf.image(path, w=180)
                pdf.ln(5)
            except Exception:
                pass

    tmp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp_pdf.close()
    pdf.output(tmp_pdf.name)
    with open(tmp_pdf.name, "rb") as f:
        pdf_bytes = f.read()
    try:
        os.remove(tmp_pdf.name)
    except Exception:
        pass
    return pdf_bytes


# ---------------- Login / Signup ----------------
def show_forgot_password():
    st.subheader("Reset Your Password")
    uname = st.text_input("Enter your username", key="forgot_pw_user")
    if not uname:
        return
    
    try:
        users = load_users() 
    except Exception as e:
        st.error(f"Error loading users: {e}. Ensure load_users() is correctly implemented.")
        return

    user_list = users.get("users", [])
    user = next((u for u in user_list if u["username"] == uname), None)
    if not user:
        st.error("Username not found.")
        return

    new_pw = st.text_input("New password", type="password", key="forgot_pw_new")
    confirm_pw = st.text_input("Confirm new password", type="password", key="forgot_pw_confirm")
    if st.button("Reset Password"):
        if not new_pw or not confirm_pw:
            st.warning("Please fill both password fields.")
        elif new_pw != confirm_pw:
            st.error("Passwords do not match.")
        else:
            # Update password in the list
            for u in user_list:
                if u["username"] == uname:
                    u["password"] = new_pw
                    break
            
            try:
                save_users(users) 
                st.success("Password reset! You may now sign in with your new password.")
                st.session_state.show_forgot_pw = False
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Error saving new password: {e}. Ensure save_users() is correctly implemented.")


def show_login():
    if st.session_state.get("show_forgot_pw", False):
        if st.button("← Back to Login"):
            st.session_state.show_forgot_pw = False
            st.experimental_rerun()
            return
        show_forgot_password()
        return

    st.markdown(
        """
        <div style="max-width:480px; margin:auto; padding:1.6rem; background:#2A2A33; border-radius:12px; box-shadow:0 10px 30px rgba(0,0,0,0.08);">
            <h2 style="text-align:center; color:FFFFFF; margin-bottom:4px;">Login</h2>
            <p style="text-align:center; color:FFFFFF; margin-top:-6px; font-size:13px;">Enter credentials to access the dashboard</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        role_select = st.selectbox("Role", ["public", "analyst", "law_enforcement"])
        
        login_button = st.button("Login")
        forgot_pw_button = st.button("Forgot Password?")
        
        if login_button:
            role = authenticate_user(username, password)
            if role and role == role_select:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.role = role
                st.success(f"Logged in as {username} ({role})")
                try:
                    st.experimental_rerun()
                except Exception:
                    pass
            else:
                st.error("Invalid credentials or role mismatch.")
        
        if forgot_pw_button:
            st.session_state.show_forgot_pw = True
            st.experimental_rerun() # Rerun to show the forgot password form


    st.markdown("---")
    st.subheader("New User Signup")
    new_username = st.text_input("New Username", key="signup_user")
    new_password = st.text_input("New Password", type="password", key="signup_pass")
    new_role = st.selectbox("Select Role", ["public", "analyst", "law_enforcement"], key="signup_role")

    if st.button("Sign Up"):
        if not new_username or not new_password:
            st.warning("Provide both username and password.")
        else:
            success = create_user(new_username, new_password, new_role)
            if success:
                st.success("Account created. Please log in.")
            else:
                st.error("Username already exists.")


# ---------------- Dashboard ----------------
def show_dashboard():
    role = st.session_state.role
    username = st.session_state.username
    
    st.sidebar.markdown(f"**Logged in as:** {username} ({role})")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.role = ""
        try:
            st.experimental_rerun()
        except Exception:
            pass
        return

    st.title("🚔 Crime Pattern Analysis Dashboard")
    st.markdown("Upload a CSV or Excel file containing columns: `date`, `crime_type`, `latitude`, `longitude` (optional: region/city/district).")

    uploaded_file = st.file_uploader("Upload Crime Data File (CSV or Excel)", type=["csv", "xlsx", "xls"])
    if uploaded_file is None:
        st.info("Please upload a CSV or Excel file with columns: date, crime_type, latitude, longitude.")
        
        # **CONFUSION MATRIX LOGIC MOVED INSIDE DASHBOARD FUNCTION**
        st.markdown("---")
        st.markdown("## Confusion Matrix")
        y_true_input = st.text_area("Actual (comma-separated)", value="A, B, A, C", key="cm_true", help="e.g., A, B, A, C")
        y_pred_input = st.text_area("Predicted (comma-separated)", value="A, A, C, C", key="cm_pred", help="e.g., A, A, C, C")
        
        if y_true_input and y_pred_input:
            y_true = [x.strip() for x in y_true_input.split(",") if x.strip()]
            y_pred = [x.strip() for x in y_pred_input.split(",") if x.strip()]
            labels = sorted(set(y_true + y_pred))
            if len(y_true) == len(y_pred) and y_true and y_pred:
                try:
                    cm = confusion_matrix(y_true, y_pred, labels=labels)
                    fig_cm = ff.create_annotated_heatmap(
                        cm, x=labels, y=labels, colorscale='Blues', showscale=True,
                        annotation_text=[[str(cell) for cell in row] for row in cm]
                    )
                    fig_cm.update_layout(xaxis_title="Predicted", yaxis_title="Actual", title="Confusion Matrix")
                    st.plotly_chart(fig_cm, use_container_width=True)
                except ValueError as ve:
                    st.warning(f"Could not compute Confusion Matrix. Error: {ve}")
            else:
                st.warning("Input lists must be the same length and not empty.")
        else:
             st.info("Enter actual and predicted labels to see the Confusion Matrix.")
        st.markdown("---")
        return # Exit dashboard if no file uploaded

    try:
        fname = uploaded_file.name.lower()
        if fname.endswith(".csv"):
            raw_df = pd.read_csv(uploaded_file)
        else:
            raw_df = pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"Failed to read file: {e}")
        return

    raw_df.columns = raw_df.columns.str.lower().str.strip().str.replace('[^a-z0-9_]+', '', regex=True)
    required = {"date", "crime_type", "latitude", "longitude"}
    if not required.issubset(set(raw_df.columns)):
        st.error(f"File must contain columns: {', '.join(required)}. Found: {list(raw_df.columns)}")
        return

    st.markdown("### Raw Data Preview")
    st.dataframe(raw_df.head(20), use_container_width=True)

    raw_stats = {
        "Rows": int(len(raw_df)),
        "Columns": list(raw_df.columns),
        "Duplicate Rows": int(raw_df.duplicated().sum()),
        "Missing Dates": int(raw_df["date"].isnull().sum()),
        "Missing Latitudes": int(raw_df["latitude"].isnull().sum()),
        "Missing Longitudes": int(raw_df["longitude"].isnull().sum())
    }
    st.markdown("**Raw Data Stats**")
    st.write(raw_stats)

    df = raw_df.copy()
    df = df.drop_duplicates().reset_index(drop=True)
    try:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    except Exception:
        pass
    df = df.dropna(subset=["date", "latitude", "longitude", "crime_type"]).reset_index(drop=True)

    st.markdown("### Cleaned Data Preview")
    st.dataframe(df.head(20), use_container_width=True)

    clean_stats = {
        "Rows": int(len(df)),
        "Columns": list(df.columns),
        "Duplicate Rows": int(df.duplicated().sum()),
        "Missing Dates": int(df["date"].isnull().sum()) if "date" in df.columns else 0,
        "Missing Latitudes": int(df["latitude"].isnull().sum()) if "latitude" in df.columns else 0,
        "Missing Longitudes": int(df["longitude"].isnull().sum()) if "longitude" in df.columns else 0
    }
    st.markdown("**Cleaned Data Stats**")
    st.write(clean_stats)

    diff_stats = {
        "Rows Removed": raw_stats["Rows"] - clean_stats["Rows"],
        "Duplicates Removed": raw_stats["Duplicate Rows"],
        "Rows with Missing Key Columns Removed": raw_stats["Rows"] - (clean_stats["Rows"] + raw_stats["Duplicate Rows"])
    }
    st.markdown("**Data Cleaning Summary**")
    st.write(diff_stats)

    # **CONFUSION MATRIX LOGIC MOVED INSIDE DASHBOARD FUNCTION**
    st.markdown("---")
    st.markdown("## Confusion Matrix")
    y_true_input = st.text_area("Actual (comma-separated)", value="A, B, A, C", key="cm_true_2", help="e.g., A, B, A, C")
    y_pred_input = st.text_area("Predicted (comma-separated)", value="A, A, C, C", key="cm_pred_2", help="e.g., A, A, C, C")
    
    if y_true_input and y_pred_input:
        y_true = [x.strip() for x in y_true_input.split(",") if x.strip()]
        y_pred = [x.strip() for x in y_pred_input.split(",") if x.strip()]
        labels = sorted(set(y_true + y_pred))
        if len(y_true) == len(y_pred) and y_true and y_pred:
            try:
                cm = confusion_matrix(y_true, y_pred, labels=labels)
                fig_cm = ff.create_annotated_heatmap(
                    cm, x=labels, y=labels, colorscale='Blues', showscale=True,
                    annotation_text=[[str(cell) for cell in row] for row in cm]
                )
                fig_cm.update_layout(xaxis_title="Predicted", yaxis_title="Actual", title="Confusion Matrix")
                st.plotly_chart(fig_cm, use_container_width=True)
            except ValueError as ve:
                 st.warning(f"Could not compute Confusion Matrix. Error: {ve}")
        else:
            st.warning("Input lists must be the same length and not empty.")
    else:
         st.info("Enter actual and predicted labels to see the Confusion Matrix.")
    st.markdown("---")
    # **END OF CONFUSION MATRIX LOGIC**


    st.markdown("## Correlation Heatmap")
    # Need to check df is not empty before correlation calculation
    if not df.empty:
        # Exclude 'date' column for correlation if it was not already converted to numeric
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if len(num_cols) >= 2:
            corr = df[num_cols].corr()
            fig_corr = px.imshow(
                corr,
                text_auto=True,
                color_continuous_scale="RdBu",
                zmin=-1, zmax=1,
                aspect="auto",
                title="Correlation Matrix"
            )
            st.plotly_chart(fig_corr, use_container_width=True)
        else:
            st.info("No numeric columns for correlation heatmap.")
    else:
        st.info("Data is empty after initial cleaning; cannot compute correlation.")
    st.markdown("---")

    # Sidebar filters
    st.sidebar.header("Filters")
    
    if df.empty:
        st.warning("No valid data remains after initial cleaning. Please check your file.")
        return

    all_crime_types = sorted(df["crime_type"].dropna().astype(str).unique().tolist())
    crime_search = st.sidebar.text_input("Search Crime Types")
    if crime_search:
        filtered_types = [ct for ct in all_crime_types if crime_search.lower() in str(ct).lower()]
    else:
        filtered_types = all_crime_types

    selected_types = st.sidebar.multiselect(
        "Crime Type",
        options=filtered_types,
        default=filtered_types if not crime_search else filtered_types
    )
    
    if selected_types:
        df = df[df["crime_type"].astype(str).isin(selected_types)]

    if "date" in df.columns and not df.empty:
        try:
            # Drop NaT values before finding min/max
            date_col = df["date"].dropna()
            if not date_col.empty:
                min_date = date_col.min().date()
                max_date = date_col.max().date()
                date_range = st.sidebar.date_input("Date Range", [min_date, max_date])
                if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
                    start, end = date_range
                    # Ensure the date comparison is done correctly
                    df = df[(df["date"].dt.date >= start) & (df["date"].dt.date <= end)]
        except Exception:
            st.sidebar.warning("Could not filter by date range.")

    if "date" in df.columns and not df.empty:
        df = df.copy() # Avoid SettingWithCopyWarning
        df["hour"] = df["date"].dt.hour
        hour_range = st.sidebar.slider("Hour Range (0–23)", 0, 23, (0, 23), step=1)
        df = df[(df["hour"] >= hour_range[0]) & (df["hour"] <= hour_range[1])]
        avail_hours = sorted(df["hour"].dropna().astype(int).unique().tolist())
        st.sidebar.caption(f"Available hours after filters: {avail_hours}" if avail_hours else "No records in selected hour range.")

    region_cols = [c for c in df.columns if c.lower() in ["region", "city", "district"]]
    if region_cols:
        region_col = region_cols[0]
        region_vals = sorted(df[region_col].dropna().astype(str).unique().tolist())
        selected_regions = st.sidebar.multiselect("Region", region_vals, default=region_vals)
        if selected_regions:
            df = df[df[region_col].astype(str).isin(selected_regions)]
    else:
        st.sidebar.markdown("**Region (derived from Lat/Lon grid)**")
        grid_size = st.sidebar.slider("Grid size (degrees)", 0.01, 0.5, 0.05, 0.01)
        # Only perform grid binning if lat/lon are present and non-empty after filtering
        if not df.empty and "latitude" in df.columns and "longitude" in df.columns:
            df = df.copy() # Avoid SettingWithCopyWarning
            df["latitude"] = pd.to_numeric(df["latitude"], errors='coerce')
            df["longitude"] = pd.to_numeric(df["longitude"], errors='coerce')
            lat_bin = np.round(df["latitude"] / grid_size) * grid_size
            lon_bin = np.round(df["longitude"] / grid_size) * grid_size
            df["region_grid"] = lat_bin.round(4).astype(str) + "," + lon_bin.round(4).astype(str)
            
            grid_regions = sorted(df["region_grid"].dropna().unique().tolist())
            selected_grids = st.sidebar.multiselect("Region (grid)", grid_regions, default=grid_regions)
            if selected_grids:
                df = df[df["region_grid"].isin(selected_grids)]
        else:
            st.sidebar.info("Cannot perform grid filtering: Data is empty or missing lat/lon.")


    if df.empty:
        st.warning("No data matches the selected filters. Try expanding selections.")
        return

    alerts = get_alerts(df, role)
    if alerts:
        st.markdown("## 🚨 Alerts & Notifications")
        for a in alerts:
            st.warning(a)

    chart_paths = []
    
    st.markdown("---") # Separator before role-based content
    
    if role == "public":
        st.info("Public View: Aggregated summary")
        vc = df["crime_type"].value_counts().reset_index()
        vc.columns = ["crime_type", "count"]
        fig_bar = px.bar(vc, x="crime_type", y="count", title="Crime Frequency by Type",
                         labels={"crime_type": "Crime Type", "count": "Count"})
        st.plotly_chart(fig_bar, use_container_width=True)
        p = save_plotly_as_image(fig_bar)
        if p:
            chart_paths.append(p)

    elif role == "analyst":
        st.success("Analyst View")
        period = st.radio("Granularity", ["Daily", "Weekly", "Monthly"], index=0, horizontal=True)
        
        # Ensure only non-null dates are used for grouping
        df_dt = df.dropna(subset=["date"]).copy()
        
        if period == "Daily":
            trend_df = df_dt.groupby(df_dt["date"].dt.date).size().reset_index(name="count")
            trend_df.rename(columns={"date": "ds"}, inplace=True)
            xcol = "ds"
        elif period == "Weekly":
            trend_df = df_dt.groupby(df_dt["date"].dt.to_period("W")).size().reset_index(name="count")
            trend_df["date"] = trend_df["date"].astype(str)
            xcol = "date"
        else:
            trend_df = df_dt.groupby(df_dt["date"].dt.to_period("M")).size().reset_index(name="count")
            trend_df["date"] = trend_df["date"].astype(str)
            xcol = "date"

        fig_trend = px.line(trend_df, x=xcol, y="count", markers=True, title=f"Crime Trend ({period})")
        fig_trend.update_layout(xaxis_title=period, yaxis_title="Incidents")
        st.plotly_chart(fig_trend, use_container_width=True)
        p = save_plotly_as_image(fig_trend)
        if p:
            chart_paths.append(p)
            
        st.markdown("---")
        st.subheader("Hourly Heatmap by Crime Type (counts)")
        try:
            heat_df = df.dropna(subset=["hour", "crime_type"]).copy()
            heat_df["hour"] = heat_df["hour"].astype(int)
            heat_df["crime_type"] = heat_df["crime_type"].astype(str)
            
            heat_df_agg = heat_df.groupby(["hour", "crime_type"]).size().reset_index(name="count")
            heat_pivot = heat_df_agg.pivot_table(index="hour", columns="crime_type", values="count", fill_value=0)
            st.dataframe(heat_pivot)
            
            # Optional: Display as a Plotly heatmap
            if not heat_pivot.empty:
                fig_heat = px.imshow(
                    heat_pivot,
                    x=heat_pivot.columns,
                    y=heat_pivot.index,
                    color_continuous_scale="Viridis",
                    title="Hourly Heatmap by Crime Type"
                )
                fig_heat.update_xaxes(side="top")
                st.plotly_chart(fig_heat, use_container_width=True)
                p_heat = save_plotly_as_image(fig_heat)
                if p_heat:
                    chart_paths.append(p_heat)
            
        except Exception:
            st.info("Not enough data for heatmap.")

    elif role == "law_enforcement":
        st.success("Law Enforcement View")
        st.subheader("Filtered Raw Data")
        st.dataframe(df, use_container_width=True)

        st.markdown("---")
        st.subheader("Crime Incidents Map")
        try:
            map_df = df.dropna(subset=["latitude", "longitude"])
            if not map_df.empty:
                fig_map = px.scatter_mapbox(
                    map_df, lat="latitude", lon="longitude", color="crime_type",
                    hover_name="crime_type", zoom=10, mapbox_style="carto-positron",
                    title="Crime Incidents by Type", height=500
                )
                st.plotly_chart(fig_map, use_container_width=True)
                p = save_plotly_as_image(fig_map)
                if p:
                    chart_paths.append(p)
            else:
                st.info("No geolocation data to plot.")
        except Exception as e:
            st.error(f"Map error: {e}")

        st.markdown("---")
        st.subheader("📈 Crime Forecast (Next 30 days)")
        try:
            # Requires prophet library to be installed: pip install prophet
            ts = df.groupby(df["date"].dt.floor("d")).size().reset_index(name="y")
            ts.rename(columns={"date": "ds"}, inplace=True)
            ts = ts.sort_values("ds")
            if len(ts) < 2:
                st.warning("Not enough daily history to forecast (need at least 2 days).")
            else:
                model = Prophet()
                model.fit(ts)
                future = model.make_future_dataframe(periods=30)
                forecast = model.predict(future)

                compare_df = forecast.merge(ts, on="ds", how="left")

                fig_fore = px.line(
                    forecast, x="ds", y="yhat",
                    labels={"ds": "Date", "yhat": "Predicted"},
                    title="Crime Forecast (Prophet)"
                )
                
                # Add confidence interval shading
                fig_fore.add_traces([
                    dict(
                        x=list(forecast["ds"]) + list(forecast["ds"][::-1]),
                        y=list(forecast["yhat_upper"]) + list(forecast["yhat_lower"][::-1]),
                        fill="toself",
                        fillcolor="rgba(0,123,255,0.15)",
                        line=dict(color="rgba(255,255,255,0)"),
                        hoverinfo="skip",
                        name="Confidence Interval"
                    )
                ])

                # Add actual data points
                fig_fore.add_scatter(
                    x=compare_df["ds"], y=compare_df["y"],
                    mode="markers+lines", name="Actual", line=dict(color="red")
                )
                
                # Add predicted line (can be redundant but ensures blue line is visible)
                fig_fore.add_scatter(
                    x=forecast["ds"], y=forecast["yhat"],
                    mode="lines", name="Predicted", line=dict(color="blue")
                )
                
                # Update layout for better visibility
                fig_fore.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))

                st.plotly_chart(fig_fore, use_container_width=True)

                p = save_plotly_as_image(fig_fore)
                if p:
                    chart_paths.append(p)
        except ImportError:
            st.warning("Prophet library not installed. Cannot show forecast. Install with: `pip install prophet`")
        except Exception as e:
            st.error(f"Forecasting failed: {e}")

        st.markdown("---")
        st.subheader("🔥 Crime Hotspot Detection ")
        try:
            # Requires scikit-learn library to be installed: pip install scikit-learn
            loc_df = df[["latitude", "longitude"]].dropna().copy()
            if len(loc_df) < 3:
                st.warning("Need at least 3 points for hotspot detection.")
            else:
                max_k = min(12, max(2, len(loc_df)//2))
                default_k = min(3, max_k)
                k = st.slider("Clusters (k)", 2, max_k, default_k)
                
                kmeans = KMeans(n_clusters=k, random_state=42, n_init='auto')
                loc_df["cluster"] = kmeans.fit_predict(loc_df)
                loc_df["cluster"] = loc_df["cluster"].astype(str) # Convert to string for discrete colors
                
                fig_hot = px.scatter_mapbox(
                    loc_df, lat="latitude", lon="longitude", color="cluster",
                    # Changed to a discrete color sequence since cluster is categorical
                    color_discrete_sequence=px.colors.qualitative.Bold, 
                    title="Hotspots (KMeans)", mapbox_style="carto-positron", zoom=10, height=500
                )
                st.plotly_chart(fig_hot, use_container_width=True)
                p = save_plotly_as_image(fig_hot)
                if p:
                    chart_paths.append(p)
        except ImportError:
            st.warning("scikit-learn library not installed. Cannot show hotspot detection. Install with: `pip install scikit-learn`")
        except Exception as e:
            st.error(f"Hotspot detection error: {e}")

        st.markdown("---")
        st.subheader("📄 Export Report (PDF)")
        include_charts = st.checkbox("Include charts in PDF", value=True)
        if st.button("Generate PDF Report"):
            with st.spinner("Generating PDF..."):
                pdf_bytes = generate_pdf_report(df, username, chart_paths if include_charts else [], alerts)
                cleanup_temp_images()
                st.download_button(
                    "Download Report (PDF)", data=pdf_bytes,
                    file_name=f"crime_report_{username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf"
                )

    st.markdown("---")
    st.markdown("## Summary Metrics")
    cols = st.columns(3)
    try:
        total = len(df)
        unique_ct = int(df["crime_type"].nunique())
        ds_min = df["date"].min().date()
        ds_max = df["date"].max().date()
        cols[0].metric("Total Incidents", total)
        cols[1].metric("Crime Types", unique_ct)
        cols[2].metric("Date Range", f"{ds_min} - {ds_max}")
    except Exception:
        cols[0].metric("Total Incidents", "—")
        cols[1].metric("Crime Types", "—")
        cols[2].metric("Date Range", "—")


# ---------------- Entrypoint ----------------
def main():
    if st.session_state.logged_in:
        show_dashboard()
    else:
        show_login()


if __name__ == "__main__":
    main()