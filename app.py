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
from sklearn.cluster import KMeans 
from prophet import Prophet # Re-enabled for crime forecasting

# Define USERS_FILE globally
USERS_FILE = "users.json" 

# ---------------- Placeholder Utility Functions ----------------
def load_users():
    """Loads users from the USERS_FILE."""
    if not os.path.exists(USERS_FILE):
        return {"users": []}
    with open(USERS_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            # Handle empty file or invalid JSON by returning default
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
    """Creates a new user and returns True on success, False if username already exists."""
    users_data = load_users()
    users = users_data.get("users", [])
    
    # Check if username already exists
    if any(u["username"] == username for u in users):
        return False

    # Add new user
    users.append({
        "username": username,
        "password": password,
        "role": role
    })
    users_data["users"] = users
    save_users(users_data)
    return True

def save_chart_image(fig, filename):
    """Saves a plotly figure as a temporary PNG image for PDF export."""
    temp_dir = st.session_state.get('temp_dir', '/tmp')
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    filepath = os.path.join(temp_dir, filename)
    
    # Use kaleido to write the image
    try:
        fig.write_image(filepath)
        return filepath
    except Exception as e:
        # Use st.toast for non-critical errors in utility functions
        st.toast(f"Error saving chart image for PDF: {e}", icon="⚠️")
        return None

def generate_pdf_report(df, username, chart_paths, alerts):
    """Generates a PDF report using FPDF with basic styling and custom content."""
    
    # Custom PDF class to support unicode/multi-byte characters
    class PDF(FPDF):
        def header(self):
            # Arial bold 15
            self.set_font('Arial', 'B', 15)
            # Title
            self.cell(0, 10, 'Crime Analysis Report', 0, 1, 'C')
            # Line break
            self.ln(5)

        def footer(self):
            # Position at 1.5 cm from bottom
            self.set_y(-15)
            # Arial italic 8
            self.set_font('Arial', 'I', 8)
            # Page number
            self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', 0, 0, 'C')

        def chapter_title(self, title):
            # Arial 12
            self.set_font('Arial', 'B', 12)
            self.cell(0, 10, title, 0, 1, 'L')
            self.ln(1)

        def chapter_body(self, body):
            # Times 10
            self.set_font('Arial', '', 10)
            # Output justified text
            self.multi_cell(0, 5, body)
            # Line break
            self.ln()

    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Set default font for body content (using a standard font for simplicity and unicode compatibility, though FPDF's standard fonts have limitations)
    pdf.set_font('Arial', '', 10)

    # Report Metadata
    pdf.chapter_title("Report Details")
    pdf.chapter_body(f"Generated for User: {username}\nDate: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Summary Statistics
    pdf.chapter_title("Summary Statistics")
    try:
        total = len(df)
        unique_ct = df["crime_type"].nunique()
        ds_min = df["date"].min().date()
        ds_max = df["date"].max().date()
        summary_text = f"Total Incidents: {total}\nUnique Crime Types: {unique_ct}\nDate Range: {ds_min} to {ds_max}"
        pdf.chapter_body(summary_text)
    except Exception:
        pdf.chapter_body("Summary statistics could not be calculated.")

    # Alerts (from Hotspot)
    pdf.chapter_title("Critical Alerts")
    if alerts:
        alert_text = "\n".join([f"- {a}" for a in alerts])
        pdf.chapter_body(alert_text)
    else:
        pdf.chapter_body("No critical alerts generated in the current session.")

    # Charts
    if chart_paths:
        pdf.chapter_title("Data Visualizations")
        for i, path in enumerate(chart_paths):
            if os.path.exists(path):
                # Scale image to fit page width (assuming standard A4 margins)
                pdf.image(path, x=10, w=190)
                pdf.ln(5)
            
    return pdf.output(dest='S').encode('latin-1')

def cleanup_temp_images():
    """Cleans up temporary chart images."""
    temp_dir = st.session_state.get('temp_dir', '/tmp')
    for f in glob.glob(os.path.join(temp_dir, "chart_*.png")):
        try:
            os.remove(f)
        except OSError:
            pass # Ignore errors if file is already gone

# ----------------- FORECASTING FUNCTION -----------------
def perform_crime_forecast(df, forecast_periods=30):
    """
    Performs crime incident forecasting using Prophet.
    Returns a combined DataFrame for plotting Actuals and Predictions.
    """
    try:
        # 1. Prepare data for Prophet: 'ds' (datestamp) and 'y' (value)
        # Group by date and count incidents
        df_prophet = df.groupby('date').size().reset_index(name='count')
        df_prophet.rename(columns={'date': 'ds', 'count': 'y'}, inplace=True)

        # Check if we have enough distinct days of data for Prophet
        if len(df_prophet) < 5:
            st.warning("Not enough distinct days of data (less than 5) to perform a meaningful forecast.")
            return None

        # 2. Fit the Prophet model
        m = Prophet(
            daily_seasonality=False,
            weekly_seasonality=True,
            yearly_seasonality=False,
            changepoint_prior_scale=0.05
        )
        m.fit(df_prophet)

        # 3. Create future dates for prediction
        future = m.make_future_dataframe(periods=forecast_periods)

        # 4. Make predictions
        forecast = m.predict(future)
        
        # Ensure predictions are non-negative
        forecast['yhat'] = forecast['yhat'].apply(lambda x: max(0, x))

        # 5. Combine actual and predicted data into a single DataFrame
        # Merge actuals with full prediction series
        plot_df = pd.merge(df_prophet, forecast[['ds', 'yhat']], on='ds', how='outer')
        plot_df.rename(columns={'ds': 'Date', 'y': 'Actual', 'yhat': 'Predicted'}, inplace=True)
        
        return plot_df

    except Exception as e:
        st.error(f"Error during forecasting: {e}")
        return None
# ----------------- END FORECASTING FUNCTION -----------------

# ---------------- Streamlit UI Functions ----------------

def show_login():
    """Shows the login and signup interface."""
    st.sidebar.header("Login")
    username = st.sidebar.text_input("Username", key="login_user")
    password = st.sidebar.text_input("Password", type="password", key="login_pass")

    if st.sidebar.button("Login", key="btn_login"):
        if username and password:
            role = authenticate_user(username, password)
            if role:
                st.session_state['logged_in'] = True
                st.session_state['username'] = username
                st.session_state['role'] = role
                st.rerun()
            else:
                st.sidebar.error("Invalid username or password")
        else:
             st.sidebar.warning("Please enter both username and password.")

    st.sidebar.markdown("---")
    st.sidebar.header("Signup")
    
    # Use a separate container for signup fields to avoid state confusion
    with st.sidebar.form("signup_form"):
        new_username = st.text_input("New Username (min 3 chars)", max_chars=30)
        new_password = st.text_input("New Password (min 6 chars)", type="password", max_chars=30)
        new_role = st.selectbox(
            "Select Role", 
            options=['public', 'analyst', 'law_enforcement'], 
            index=0
        )
        submitted = st.form_submit_button("Create Account")

        if submitted:
            if len(new_username) < 3 or len(new_password) < 6:
                st.error("Username must be at least 3 characters and password at least 6 characters.")
            elif create_user(new_username, new_password, new_role):
                st.success("Account created successfully! You can now log in.")
            else:
                st.error("Username already exists. Please choose another.")


def show_dashboard(username, df):
    """Shows the main crime analysis dashboard."""
    st.title("Crime Pattern Analysis Dashboard")
    st.subheader(f"Welcome, {username} ({st.session_state['role']} Role)")

    # Initialize a list to store paths of charts for PDF export
    chart_paths = []
    alerts = [] # List to store alerts for PDF report

    # ---------------- Data Cleaning & Filter ----------------
    # (Assuming date and crime_type columns exist and are pre-processed)
    try:
        df['date'] = pd.to_datetime(df['date'])
        df['day_of_week'] = df['date'].dt.day_name()
        df['hour'] = df['time'].apply(lambda x: int(str(x).split(':')[0]) if pd.notna(x) else np.nan)
        # Drop rows missing crucial analysis data (lat, lon, hour)
        df_clean = df.dropna(subset=['latitude', 'longitude', 'hour']).copy()
    except KeyError as e:
        st.error(f"Missing required column in data: {e}. Please ensure data has 'date', 'time', 'latitude', 'longitude', and 'crime_type' columns.")
        return
    except Exception as e:
        st.error(f"Data preprocessing error: {e}")
        return

    # ---------------- Basic Charts ----------------
    st.header("📊 Basic Visualizations")

    # Chart 1: Crime Type Distribution
    type_counts = df_clean['crime_type'].value_counts().reset_index()
    type_counts.columns = ['Crime Type', 'Count']
    fig1 = px.bar(type_counts.head(10), x='Crime Type', y='Count', title='Top 10 Crime Type Distribution', color_discrete_sequence=['#4c78a8'])
    st.plotly_chart(fig1, use_container_width=True)
    temp_chart_path1 = save_chart_image(fig1, f"chart_type_{username}.png")
    if temp_chart_path1: chart_paths.append(temp_chart_path1)

    # Chart 2: Incidents Over Time
    time_series = df_clean.groupby(df_clean['date'].dt.date).size().reset_index(name='Count')
    time_series.rename(columns={'date': 'Date'}, inplace=True)
    fig2 = px.line(time_series, x='Date', y='Count', title='Daily Incidents Over Time', color_discrete_sequence=['#f58518'])
    st.plotly_chart(fig2, use_container_width=True)
    temp_chart_path2 = save_chart_image(fig2, f"chart_timeseries_{username}.png")
    if temp_chart_path2: chart_paths.append(temp_chart_path2)
    
    # Chart 3: Incidents by Day of Week 
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_counts = df_clean['day_of_week'].value_counts().reindex(day_order).fillna(0).reset_index()
    day_counts.columns = ['Day', 'Count']
    fig3 = px.bar(day_counts, x='Day', y='Count', title='Incidents by Day of Week (High Crime Days)', color='Count', color_continuous_scale=px.colors.sequential.Plasma_r)
    fig3.update_xaxes(categoryorder='array', categoryarray=day_order)
    st.plotly_chart(fig3, use_container_width=True)
    temp_chart_path3 = save_chart_image(fig3, f"chart_dayofweek_{username}.png")
    if temp_chart_path3: chart_paths.append(temp_chart_path3)

    # Chart 4: Incidents by Hour of Day
    hour_counts = df_clean['hour'].astype(int).value_counts().sort_index().reset_index()
    hour_counts.columns = ['Hour', 'Count']
    fig4 = px.bar(hour_counts, x='Hour', y='Count', title='Incidents by Hour of Day (Peak Hours)', color='Count', color_continuous_scale='reds')
    fig4.update_layout(xaxis=dict(tickmode='linear', dtick=1)) # Ensure every hour is visible
    st.plotly_chart(fig4, use_container_width=True)
    temp_chart_path4 = save_chart_image(fig4, f"chart_hourofday_{username}.png")
    if temp_chart_path4: chart_paths.append(temp_chart_path4)

    # ----------------- CRIME FORECAST SECTION -----------------
    if st.session_state['role'] in ['analyst', 'law_enforcement']:
        st.markdown("---")
        st.header("📈 Crime Forecast")
        st.markdown("Predict future crime incident counts based on historical trends using the Prophet model.")
        
        # 1. Input for forecast periods
        forecast_periods = st.slider(
            "Select the number of days to forecast:",
            min_value=7, max_value=90, value=30, step=7
        )
        
        # 2. Perform forecasting
        forecast_df = perform_crime_forecast(df_clean, forecast_periods)

        if forecast_df is not None:
            # 3. Plotting the Actuals and Predicted in the same graph
            fig_forecast = px.line(
                forecast_df,
                x='Date',
                y=['Actual', 'Predicted'], # Plot both series
                title=f'Actual vs. Predicted Daily Crime Incidents ({forecast_periods} Days Forecast)',
                labels={'value': 'Number of Incidents', 'Date': 'Date'},
            )
            
            # Customizing colors and line styles (red for predicted, blue for actual)
            fig_forecast.update_traces(
                selector={'name': 'Actual'},
                line=dict(color='blue', width=2),
                name='Actual Incidents'
            )
            fig_forecast.update_traces(
                selector={'name': 'Predicted'},
                line=dict(color='red', dash='dot', width=3), 
                name=f'Predicted Incidents (Next {forecast_periods} Days)'
            )
            
            # Add a vertical line for the forecast start date
            last_actual_date = df_clean['date'].max()
            fig_forecast.add_vline(
                x=last_actual_date, 
                line_dash="dash", 
                line_color="green", 
                annotation_text="Forecast Start", 
                annotation_position="top left"
            )
            
            # Ensure non-negative predictions 
            fig_forecast.update_yaxes(rangemode="tozero")
            
            # Display the chart
            st.plotly_chart(fig_forecast, use_container_width=True)

            # Export Chart for PDF
            temp_chart_path_forecast = save_chart_image(fig_forecast, f"chart_forecast_{username}.png")
            if temp_chart_path_forecast: chart_paths.append(temp_chart_path_forecast)

    # ---------------- ADVANCED ANALYTICS: MODEL EVALUATION ----------------
    if st.session_state['role'] in ['analyst']:
        st.markdown("---")
        st.subheader("🤖 Model Evaluation: Classification Performance")
        st.markdown("This section shows the simulated performance of a classification model (e.g., predicting crime severity) using a Confusion Matrix.")

        try:
            # Placeholder/Dummy data for Confusion Matrix 
            n = len(df_clean)
            if n > 0:
                y_true = np.random.choice(['Low', 'Medium', 'High'], size=n, p=[0.6, 0.3, 0.1])
                # Simulate a decent prediction accuracy (e.g., 80% correct overall)
                y_pred = np.array([y if np.random.rand() < 0.8 else np.random.choice(['Low', 'Medium', 'High']) for y in y_true])
    
                # Calculate Confusion Matrix
                labels = ['Low', 'Medium', 'High']
                cm = confusion_matrix(y_true, y_pred, labels=labels)
    
                # Create Plotly Figure Factory for Confusion Matrix
                z = cm.tolist()
                z_text = [[str(y) for y in x] for x in z] # Convert to strings for annotation
                fig_cm = ff.create_annotated_heatmap(
                    z, x=labels, y=labels, annotation_text=z_text, colorscale='Viridis',
                    showscale=True
                )
                fig_cm.update_layout(
                    title='Simulated Crime Severity Classification Confusion Matrix',
                    xaxis=dict(title='Predicted Severity'),
                    yaxis=dict(title='Actual Severity'),
                    height=500
                )
                st.plotly_chart(fig_cm, use_container_width=True)
    
                # Add Model Metrics
                accuracy = np.trace(cm) / np.sum(cm)
                st.metric("Simulated Model Accuracy", f"{accuracy:.2f}")
    
                # Export Chart for PDF
                temp_chart_path_cm = save_chart_image(fig_cm, f"chart_confusion_matrix_{username}.png")
                if temp_chart_path_cm: chart_paths.append(temp_chart_path_cm)
            else:
                st.info("No data available to simulate model evaluation.")

        except Exception as e:
            st.error(f"Model Evaluation (Confusion Matrix) could not be displayed: {e}")


    # ---------------- Advanced Analytics: Clustering/Hotspot ----------------
    if st.session_state['role'] in ['analyst', 'law_enforcement']:
        st.markdown("---")
        st.subheader("🔥 Advanced Analytics: Crime Hotspot Detection (K-Means)")
        
        # K-Means Clustering for geographical hotspots
        try:
            k = st.slider("Select number of clusters (K):", 2, 10, 4)
            coords = df_clean[['latitude', 'longitude']].values
            
            if len(coords) >= k:
                # Run KMeans only if enough data points exist
                kmeans = KMeans(n_clusters=k, random_state=0, n_init=10)
                df_clean['cluster'] = kmeans.fit_predict(coords)
                
                # Map visualization for clusters
                fig_map = px.scatter_mapbox(
                    df_clean, lat="latitude", lon="longitude", color="cluster",
                    color_continuous_scale=px.colors.cyclical.IceFire, 
                    zoom=10, height=400,
                    title=f"Crime Hotspots (K={k})",
                    hover_data=['crime_type', 'date']
                )
                fig_map.update_layout(mapbox_style="open-street-map")
                st.plotly_chart(fig_map, use_container_width=True)
    
                # Alert logic based on cluster density
                cluster_counts = df_clean['cluster'].value_counts()
                alert_threshold = cluster_counts.mean() + cluster_counts.std() * 1.5
                for cluster_id, count in cluster_counts.items():
                    if count > alert_threshold:
                        alerts.append(f"🔴 ALERT: Cluster {cluster_id} is a high-density hotspot with {count} incidents.")
    
                # Export Hotspot Chart for PDF
                temp_chart_path_hotspot = save_chart_image(fig_map, f"chart_hotspot_{username}.png")
                if temp_chart_path_hotspot: chart_paths.append(temp_chart_path_hotspot)
            else:
                st.info(f"Not enough data points ({len(coords)}) to run K-Means with K={k}.")
            
        except Exception as e:
            st.error(f"Hotspot detection error: {e}")

        st.markdown("---")
        st.subheader("📄 Export Report (PDF)")
        include_charts = st.checkbox("Include charts in PDF", value=True)
        if st.button("Generate PDF Report"):
            with st.spinner("Generating PDF..."):
                pdf_bytes = generate_pdf_report(df_clean, username, chart_paths if include_charts else [], alerts)
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
        total = len(df_clean)
        unique_ct = int(df_clean["crime_type"].nunique())
        ds_min = df_clean["date"].min().date()
        ds_max = df_clean["date"].max().date()
        cols[0].metric("Total Incidents", total)
        cols[1].metric("Crime Types", unique_ct)
        cols[2].metric("Date Range", f"{ds_min} - {ds_max}")
    except Exception:
        cols[0].metric("Total Incidents", "—")
        cols[1].metric("Crime Types", "—")
        cols[2].metric("Date Range", "—")
    
    st.markdown("---")
    st.markdown("## Raw Data (Filtered Sample)")
    st.dataframe(df_clean.head(100), use_container_width=True) # Show only a sample

# ---------------- Main App Logic ----------------
def main():
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
        st.session_state['username'] = None
        st.session_state['role'] = None
        
    # Setup temporary directory for charts
    if 'temp_dir' not in st.session_state:
        # Create a new temp directory and store its path
        try:
            st.session_state['temp_dir'] = tempfile.mkdtemp()
        except Exception:
            # Fallback for environments where mkdtemp might fail
            st.session_state['temp_dir'] = '/tmp'
    
    st.set_page_config(layout="wide")

    if st.session_state['logged_in']:
        
        # ---------------- Data Upload/Load ----------------
        uploaded_file = st.sidebar.file_uploader("Upload Crime Data (CSV)", type=["csv"])
        
        if uploaded_file is not None:
            try:
                # Load file into DataFrame
                df = pd.read_csv(uploaded_file)
                
                # Basic check for essential columns
                required_cols = ['date', 'time', 'latitude', 'longitude', 'crime_type']
                if not all(col in df.columns for col in required_cols):
                    missing_cols = [col for col in required_cols if col not in df.columns]
                    st.error(f"The uploaded CSV is missing required columns: {', '.join(missing_cols)}. Cannot proceed with analysis.")
                    return
                
                show_dashboard(st.session_state['username'], df)
            except pd.errors.EmptyDataError:
                st.error("The uploaded CSV file is empty.")
            except Exception as e:
                st.error(f"Error loading or reading data: {e}")
        else:
            st.info("Please upload a crime data CSV file to begin analysis.")
        
        if st.sidebar.button("Logout"):
            st.session_state['logged_in'] = False
            st.session_state['username'] = None
            st.session_state['role'] = None
            cleanup_temp_images()
            st.rerun()

    else:
        show_login()

if __name__ == "__main__":
    main()