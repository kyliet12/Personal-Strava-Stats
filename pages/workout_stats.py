import streamlit as st
import pandas as pd
import plotly.express as px
from utils import classify_and_extract
import numpy as np

######
# Sidebar Pace Panel
######
if "long_run_thresh" not in st.session_state:
    st.session_state.long_run_thresh = 6.0
if "pace_min" not in st.session_state:
    st.session_state.pace_min = 8
if "pace_sec" not in st.session_state:
    st.session_state.pace_sec = 15

with st.sidebar:
    st.header("⚙️ Athlete Settings")
    st.markdown("Set your thresholds to personalize your data.")
    
    st.session_state.long_run_thresh = st.number_input(
        "Long Run Minimum (miles)", 
        min_value=3.0, max_value=50.0, 
        value=st.session_state.long_run_thresh, 
        step=0.5
    )
    
    st.divider()
    st.markdown("**Aerobic Pace Cutoff**")
    st.markdown("*Paces faster than this are Aerobic. Slower are Easy.*")
    
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.pace_min = st.number_input(
            "Minutes", 
            min_value=4, max_value=20, 
            value=st.session_state.pace_min, 
            step=1
        )
    with col2:
        st.session_state.pace_sec = st.number_input(
            "Seconds", 
            min_value=0, max_value=59, 
            value=st.session_state.pace_sec, 
            step=1
        )

def add_custom_workout_labels(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applies custom heuristics to categorize run types based on summary stats.
    """
    # Isolate runs
    runs = df[df['type'] == 'Run'].copy()
    
    # Define race distance windows (in meters) with a small buffer for GPS error
    is_5k_race = runs['distance'].between(4900, 5150)
    is_10k_race = runs['distance'].between(9900, 10150)
    
    # Define speed and HR thresholds
    # 3.8 m/s is ~7:03 min/mi. Adjust this based on your tempo/threshold pace.
    is_fast = runs['average_speed'] >= 3.8 
    is_high_hr = runs['max_heartrate'] >= 185 # Adjust to ~90% of your max HR
    
    # Define conditions in order of priority
    conditions = [
        # 1. Races: Standard distance AND high intensity
        ((is_5k_race | is_10k_race) & (is_fast | is_high_hr)),
        
        # 2. Long Runs: Greater than 11,265 meters (~7 miles)
        (runs['distance'] >= 11265),
        
        # 3. Workouts: High speed or high max HR, but not a race or long run
        (is_fast | is_high_hr)
    ]
    
    # Define the corresponding labels
    choices = [
        'Race',
        'Long Run',
        'Workout / Intervals'
    ]
    
    # Apply conditions, defaulting to 'Easy / Base' if none are met
    runs['workout_label'] = np.select(conditions, choices, default='Easy / Base')
    
    return runs

# --- Page Config ---
st.set_page_config(page_title="Workout Stats", page_icon="📈", layout="wide")
st.title("Workout Statistics & Trends 📈")

# --- Data Retrieval ---
if "strava_data" not in st.session_state:
    st.warning("No data found! Please go to the Home page and log in to Strava first.")
    st.stop()

df = st.session_state.strava_data.copy()

# Ensure dates are properly formatted
if 'start_date_local' in df.columns:
    df['date'] = pd.to_datetime(df['start_date_local'])
else:
    df['date'] = pd.to_datetime(df['start_date'])

# --- Section 1: Acute to Chronic Workload Ratio (ACWR) ---
st.header("Training Load (ACWR)")
st.markdown("Tracks your 7-day acute fatigue against your 28-day chronic fitness. **Target: 0.8 - 1.3**.")

# 1. Prepare ACWR Data
# Resample to daily frequency to account for rest days
daily_load = df.set_index('date').resample('D').agg({'distance': 'sum'}).fillna(0)
daily_load['acute_load_7d'] = daily_load['distance'].rolling(window=7, min_periods=1).sum()
daily_load['chronic_load_28d'] = daily_load['distance'].rolling(window=28, min_periods=1).sum() / 4
daily_load['acwr'] = daily_load['acute_load_7d'] / daily_load['chronic_load_28d']

# Clean up infinite values from dividing by zero (e.g., after long breaks)
daily_load = daily_load.replace([float('inf'), -float('inf')], 0).dropna().reset_index()

# 2. Plot ACWR
fig_acwr = px.line(
    daily_load, 
    x='date', 
    y='acwr',
    labels={'date': 'Date', 'acwr': 'ACWR'},
    title="Acute to Chronic Workload Ratio"
)
# Add threshold lines for safety zones
fig_acwr.add_hline(y=1.5, line_dash="dash", line_color="red", annotation_text="Danger Zone (>1.5)")
fig_acwr.add_hline(y=1.3, line_dash="dot", line_color="green")
fig_acwr.add_hline(y=0.8, line_dash="dot", line_color="green", annotation_text="Sweet Spot (0.8 - 1.3)")
fig_acwr.update_layout(yaxis_range=[0, max(2.0, daily_load['acwr'].max() + 0.2)])

st.plotly_chart(fig_acwr, use_container_width=True)

st.divider()

# --- Section 2: Aerobic Efficiency (Pace vs. HR) ---
st.header("Aerobic Efficiency (Pace vs. HR)")
st.markdown("Tracks your pace relative to your heart rate. Look for newer runs to drift **up and to the left**, indicating you are running faster at a lower cardiovascular cost.")

# 1. Prepare EF Data
runs = df[(df['type'] == 'Run') & (df['has_heartrate'] == True)].copy()
runs = runs.dropna(subset=['average_speed', 'average_heartrate'])

# Convert date to a numeric timestamp for the continuous color scale
runs['date_numeric'] = runs['date'].astype('int64') // 10**9

# Convert speed (m/s) to Pace (minutes per mile)
# 1 mile = 1609.34 meters
runs['pace_decimal'] = 1609.34 / (runs['average_speed'] * 60)

# Create a clean MM:SS string for the hover tooltip
runs['pace_minutes'] = runs['pace_decimal'].astype(int)
runs['pace_seconds'] = ((runs['pace_decimal'] - runs['pace_minutes']) * 60).astype(int)
runs['pace_str'] = runs['pace_minutes'].astype(str) + ':' + runs['pace_seconds'].astype(str).str.zfill(2)

# 2. Plot EF Scatter
fig_ef = px.scatter(
    runs,
    x='average_heartrate',
    y='pace_decimal',
    color='date_numeric',
    hover_data={
        'date': '|%b %d, %Y', 
        'date_numeric': False, 
        'pace_decimal': False, # Hide the raw decimal
        'pace_str': True,      # Show the formatted MM:SS
        'average_heartrate': True
    },
    labels={
        'average_heartrate': 'Average Heart Rate (BPM)',
        'pace_decimal': 'Pace (min/mile)',
        'pace_str': 'Pace',
        'date_numeric': 'Time'
    },
    title="Fitness Shift: Pace vs. Heart Rate Over Time",
    color_continuous_scale=px.colors.sequential.Viridis
)

# Invert the Y-axis so faster paces (lower numbers) are at the top
fig_ef.update_yaxes(autorange="reversed")

# Format the colorbar with Older/Newer labels at the extremes
min_date = runs['date_numeric'].min()
max_date = runs['date_numeric'].max()

fig_ef.update_layout(coloraxis_colorbar=dict(
    title="", # Remove default title
    tickvals=[min_date, max_date], # Place ticks exactly at the min and max data points
    ticktext=["Older", "Newer"],
    tickmode="array"
))

st.plotly_chart(fig_ef, use_container_width=True)

st.divider()

# --- Section 3: Time of Day Density ---
st.header("When Do You Run?")
st.markdown("A density distribution of your activity start times.")

# 1. Prepare Time of Day Data
# Extract the hour and minute, and convert it to a fractional hour (e.g., 6:30 AM -> 6.5)
# Using start_date_local is crucial here so timezones don't skew the data
runs['hour_of_day'] = runs['date'].dt.hour + (runs['date'].dt.minute / 60.0)

# 2. Plot Density
# We use a histogram with a smooth KDE (Kernel Density Estimate) curve overlaid
fig_time = px.histogram(
    runs, 
    x="hour_of_day", 
    nbins=24,
    histnorm='density',
    marginal="violin", # Adds a neat little violin plot on top
    title="Activity Start Time Distribution",
    labels={'hour_of_day': 'Hour of Day (24h format)'},
    color_discrete_sequence=['#ff7f0e'] # Strava orange!
)

# Format the x-axis to show standard hours
fig_time.update_xaxes(tickvals=list(range(0, 25)), ticktext=[f"{h}:00" for h in range(0, 25)])

st.plotly_chart(fig_time, use_container_width=True)

# --- Section 4: Weekly Volume Breakdown ---
st.header("Training Composition")
st.markdown("Your weekly mileage categorized by effort type. This helps ensure your training remains properly polarized over a cycle.")

# 1. Prepare Volume Data
vol_df = df[df['type'] == 'Run'].copy()

# Apply the new heuristic classifier to get the 'parsed_type'
# 1. Convert the user's MM:SS input into a decimal so the math works
dynamic_aerobic_decimal = st.session_state.pace_min + (st.session_state.pace_sec / 60.0)

# Grab the long run threshold directly
dynamic_long_run = st.session_state.long_run_thresh

# 2. The Lambda Bridge
# This passes the row data AND your dynamic thresholds into the function
parsed_data = df.apply(
    lambda row: classify_and_extract(
        row=row, 
        long_run_thresh=dynamic_long_run, 
        aerobic_thresh_decimal=dynamic_aerobic_decimal
    ), 
    axis=1
)
vol_df['parsed_type'] = parsed_data.apply(lambda x: x['type'])

# Convert distance from meters to miles 
vol_df['distance_mi'] = vol_df['distance'] * 0.000621371

# Ensure date is a datetime object 
vol_df['date'] = pd.to_datetime(vol_df['start_date_local'])

# Truncate dates to the start of the week (Monday) for grouping
# W-SUN creates a Monday-Sunday window, returning Monday as the start_time
vol_df['week_start'] = vol_df['date'].dt.to_period('W-SUN').dt.start_time

# Group the data using the new parsed_type classifications
weekly_vol = vol_df.groupby(['week_start', 'parsed_type'])['distance_mi'].sum().reset_index()

# 2. Plot the Stacked Bar Chart
fig_vol = px.bar(
    weekly_vol,
    x='week_start',
    y='distance_mi',
    color='parsed_type',
    title="Weekly Mileage by Run Type",
    labels={
        'week_start': 'Week Of', 
        'distance_mi': 'Volume (Miles)', 
        'parsed_type': 'Run Type'
    },
    # Updated color palette for the new categories
    color_discrete_map={
        'Easy': '#636efa',        # Blue
        'Aerobic': '#ab63fa',     # Purple
        'Long Run': '#00cc96',    # Green
        'Workout': '#ef553b'      # Red
    }
)

# Ensure the bars stack neatly and format the X-axis to show the month/day clearly
fig_vol.update_layout(
    barmode='stack', 
    xaxis_tickformat='%b %d',
    xaxis_tickangle=-45
)

st.plotly_chart(fig_vol, use_container_width=True)
st.divider()