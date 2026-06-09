import streamlit as st
import pandas as pd
from utils import get_login_url, exchange_token, fetch_activities, clean_activities, process_summary_stats, sync_detailed_activities
from datetime import datetime
from streamlit_calendar import calendar
import plotly.express as px


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
            st.session_state.athlete_id = token_response["athlete"]["id"]
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

# Pull your ID securely from the environment configuration
MY_STRAVA_ID = st.secrets["MY_STRAVA_ID"]

# --- Smart Caching & VIP Routing ---
# Only run the heavy API calls if the data isn't already saved in the session
if "strava_data" not in st.session_state:
    
    df = None
    with st.spinner("Fetching your activities..."):
        activities = fetch_activities(st.session_state.access_token)
        
        if activities:
            df = pd.DataFrame(activities)
        else:
            st.info("No activities found!")

    # Clean df
    df = clean_activities(df)

    # Sync detailed descriptions and route VIPs
    if df is not None:
        # Cast both IDs to strings to prevent type-mismatch bugs
        if str(st.session_state.get("athlete_id")) == str(MY_STRAVA_ID):
            # VIP Mode
            df = sync_detailed_activities(df, st.session_state.access_token, use_cache=True)
        else:
            # Guest Mode
            df = df[df['type'] == 'Run'].head(50).copy()
            df = sync_detailed_activities(df, st.session_state.access_token, use_cache=False)
            st.toast("Guest Mode: Dynamically fetched your 50 most recent detailed runs.", icon="👋")

        # Save the fully enriched dataframe to session state
        st.session_state.strava_data = df

else:
    # If the data is already in session state, load it instantly without hitting the API
    df = st.session_state.strava_data

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

st.markdown("### 🏆 Year-to-Date Top Times")

# List of the columns we just created
pr_columns = ["pr_800m", "pr_1_mile", "pr_2_mile", "pr_5k", "pr_10k", "pr_10_mile"]

# Create a dictionary to hold the fastest time for each distance
ytd_prs = {}

for col in pr_columns:
    if col in df.columns and not df[col].isna().all():
        # Find the absolute minimum time (in seconds) for the year
        fastest_seconds = df[col].min()
        
        # Convert seconds to MM:SS formatting
        minutes = int(fastest_seconds // 60)
        seconds = int(fastest_seconds % 60)
        
        # Clean up the label (e.g., "pr_1_mile" -> "1 Mile")
        clean_label = col.replace("pr_", "").replace("_", " ").title()
        
        ytd_prs[clean_label] = f"{minutes}:{seconds:02d}"

# Display in Streamlit using columns
if ytd_prs:
    pr_cols = st.columns(len(ytd_prs))
    for i, (distance, time_str) in enumerate(ytd_prs.items()):
        pr_cols[i].metric(label=distance, value=time_str)
else:
    st.info("No best efforts logged yet!")

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


st.markdown("### 📅 Activity Log")

# 1. Define your color palette 
activity_colors = {
    'Run': '#fc4c02',    
    'Ride': '#636efa',   
    'Hike': '#00cc96',   
    'Walk': '#ab63fa',   
    'AlpineSki': '#00bfff', 
    'BackcountrySki': '#1e90ff' 
}

# Ensure date is a proper datetime object for weekly grouping
df['date_obj'] = pd.to_datetime(df['start_date_local'])

# 2. Format the Individual Activity Tokens
calendar_events = []

for _, row in df.iterrows():
    raw_dist = row.get('distance', 0) 
    dist_mi = raw_dist * 0.000621371 if raw_dist > 100 else raw_dist
    
    act_type = row.get('type', 'Run')
    token_color = activity_colors.get(act_type, '#7f7f7f') 
    start_date = str(row['date_obj'])[:10] 
    
    moving_time_mins = row.get('moving_time', 0) / 60
    
    if moving_time_mins >= 60:
        hours = int(moving_time_mins // 60)
        minutes = int(moving_time_mins % 60)
        time_str = f"{hours}hr {minutes:02d}m"
    else:
        time_str = f"{int(moving_time_mins)}m"
    
    act_name = row.get('name', 'Activity')
    display_title = f"{act_name}\n{dist_mi:.1f} mi | {time_str}"
    
    calendar_events.append({
        "title": display_title,
        "start": start_date,
        "backgroundColor": token_color,
        "borderColor": token_color,
        "textColor": "white",
        "allDay": True
    })

# 3. Calculate and Inject Weekly Summary Tokens
# Group by weeks ending on Sunday ('W-SUN')
for week_end, group in df.groupby(pd.Grouper(key='date_obj', freq='W-SUN')):
    # Calculate totals
    total_dist_meters = group['distance'].sum()
    run_dist_meters = group[group['type'] == 'Run']['distance'].sum()
    total_time_mins = group['moving_time'].sum() / 60
    
    # Convert distance to miles
    total_mi = total_dist_meters * 0.000621371
    run_mi = run_dist_meters * 0.000621371
    
    # Format the weekly time
    if total_time_mins >= 60:
        w_hours = int(total_time_mins // 60)
        w_minutes = int(total_time_mins % 60)
        # Using "h" and "m" for the weekly summary makes it very readable at a glance
        time_str = f"{w_hours}hr {w_minutes:02d}m" 
    else:
        time_str = f"{int(total_time_mins)}m"
    
    # Only create a token if you actually logged activities that week
    if total_mi > 0:
        # Added the time_str to the end of the total line
        summary_title = f"🏁 WEEK TOTAL\nRun: {run_mi:.1f} mi\nTotal: {total_mi:.1f} mi\nTime: {time_str}"
        
        calendar_events.append({
            "title": summary_title,
            "start": str(week_end.date()), 
            "backgroundColor": "#1f2937",  
            "borderColor": "#fbbf24",      
            "textColor": "#fbbf24",        
            "allDay": True,
            "classNames": ["weekly-summary-token"] 
        })

# 4. Configure the Calendar UI Options
calendar_options = {
    "headerToolbar": {
        "left": "today prev,next",
        "center": "title",
        "right": "dayGridMonth,dayGridWeek"
    },
    "initialView": "dayGridMonth",
    "firstDay": 1, # <--- THIS MAKES THE CALENDAR START ON MONDAY
    "navLinks": True,
    "height": 650, 
}

# 5. Add Custom CSS
custom_css = """
    .fc-event {
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.70em; 
        padding: 4px; 
        margin-bottom: 2px;
        cursor: pointer;
    }
    
    .fc-event-title {
        white-space: pre-wrap !important; 
        line-height: 1.2; 
    }
    
    /* Make the weekly summary tokens look distinct */
    .weekly-summary-token {
        border-width: 2px !important;
        border-style: dashed !important;
        margin-top: 4px !important; 
    }
"""

# 6. Render the Calendar
calendar(
    events=calendar_events, 
    options=calendar_options, 
    custom_css=custom_css
)
st.divider()