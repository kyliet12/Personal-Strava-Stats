import streamlit as st
import pandas as pd
from utils import get_login_url, exchange_token, fetch_activities, clean_activities, process_summary_stats
from datetime import datetime

st.title("Strava Activity Dashboard")

# 1. Initialize session state to hold the access token
if "access_token" not in st.session_state:
    st.session_state.access_token = None

# 2. Check if the user is returning from Strava with an authorization code
if "code" in st.query_params and not st.session_state.access_token:
    auth_code = st.query_params["code"]
    
    with st.spinner("Authenticating with Strava..."):
        token_response = exchange_token(auth_code)
        
        if "access_token" in token_response:
            st.session_state.access_token = token_response["access_token"]
            # Clean up the URL so the code doesn't stay there
            st.query_params.clear()
            st.rerun()
        else:
            st.error("Failed to authenticate. Please try again.")

# 3. Main View Routing
if st.session_state.access_token is None:
    # User is not logged in
    st.markdown("Welcome! Please log in to view your stats.")
    login_url = get_login_url()
    st.link_button("Connect with Strava", login_url)
    st.stop()  # Stop further execution until the user logs in
    

# User is logged in
st.success("Successfully connected to Strava!")

if st.button("Log Out"):
    st.session_state.access_token = None
    st.rerun()

# Fetch data
df = None
with st.spinner("Fetching your activities..."):
    activities = fetch_activities(st.session_state.access_token)
    
    if activities:
        # Convert JSON to a Pandas DataFrame for easy manipulation
        df = pd.DataFrame(activities)
    else:
        st.info("No activities found!")

# Clean df (convert distance to km, moving_time to minutes, etc.)
df = clean_activities(df)

# save df to session state for use in other pages
if df is not None:
    st.session_state.strava_data = df

# Main page content
stats = process_summary_stats(df) 
# --- Section 1: Running Focus ---
st.markdown("### 🏃‍♀️ Year-to-Date Running")

# Use a container to group these nicely
with st.container(border=True):
    r1_col1, r1_col2, r1_col3, r1_col4 = st.columns(4)
    
    with r1_col1:
        st.metric("Total YTD Miles", f"{stats['ytd_run_miles']:,.1f} mi")
    with r1_col2:
        st.metric("Days Run", f"{stats['days_run']} days", help="Total unique days you ran this year")
    with r1_col3:
        st.metric("Avg Weekly Mileage", f"{stats['avg_weekly_miles']:.1f} mi/wk")
    with r1_col4:
        # You could add a delta here comparing to last month if you calculate it!
        st.metric(f"{datetime.now().strftime('%B')} Mileage", f"{stats['month_run_miles']:.1f} mi")

st.write("") # Spacer

# --- Section 2: Exploration & Multisport ---
st.markdown("### 🌍 Exploration & Multisport")

with st.container(border=True):
    r2_col1, r2_col2, r2_col3 = st.columns(3)
    
    with r2_col1:
        st.metric("Lifetime Bike Rides", f"{stats['total_bike_rides']}", 
                    delta=f"{stats['total_bike_miles']:,.0f} miles total", 
                    delta_color="off") # 'off' makes the delta grey instead of green/red
    
    with r2_col2:
        # The cities metric
        st.metric("Cities Explored", f"{stats['cities_count']}", help="Unique cities or timezones you've logged activities in.")
    
    with r2_col3:
        # Bonus fun metric
        st.metric("Total Vert Climbed", f"{stats['total_vert_ft']:,.0f} ft")