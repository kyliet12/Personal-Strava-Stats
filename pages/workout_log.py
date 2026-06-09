import streamlit as st
import pandas as pd
from utils import classify_and_extract 
# --- Page Config ---
st.set_page_config(page_title="Workout Log", page_icon="📝", layout="wide")

# --- 1. Global Settings & Sidebar (Renders immediately) ---
# Initialize defaults if they don't exist yet
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

st.title("Workout Journal 📝")

if "strava_data" not in st.session_state:
    st.warning("No data found! Please log in on the Home page.")
    st.stop()

df = st.session_state.strava_data.copy()

# --- Mocking the Detailed Fetch ---
# Since fetching detailed descriptions requires API calls, we simulate it here.
# In production, you would run your heuristic filter, call GET /activities/{id}, 
# and merge the 'description' column into your dataframe.
if 'description' not in df.columns:
    st.info("To see your captions, ensure your data pipeline is fetching the 'description' field from the detailed activities endpoint for your workout days.")
    # Stop execution safely if the column isn't there yet
    st.stop() 

# 1. Isolate all runs and sort chronologically
runs_df = df[df['type'] == 'Run'].copy()
runs_df['date'] = pd.to_datetime(runs_df['start_date_local'])
runs_df = runs_df.sort_values('date', ascending=False)

# 2. Apply the classifier to EVERY run
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

runs_df['parsed_type'] = parsed_data.apply(lambda x: x['type']) # workout, long run, aerobic, easy
runs_df['parsed_emoji'] = parsed_data.apply(lambda x: x['emoji'])
runs_df['parsed_intervals'] = parsed_data.apply(lambda x: x['intervals'])
runs_df['formatted_notes'] = parsed_data.apply(lambda x: x['notes'])

# 3. Filter for the Journal
workouts_df = runs_df.copy()
# Limit to last 50 runs
workouts_df = workouts_df.head(50)
# --- Build the UI ---
st.markdown("Details for your last 50 runs")
st.divider()

if workouts_df.empty:
    st.write("No captioned workouts found.")
else:
    # Loop through the workouts and create an expander for each
    for _, row in workouts_df.iterrows():
        
        date_str = row['date'].strftime("%A, %b %d, %Y")
        name = row['name']
        dist = row['distance'] * 0.000621371 if row['distance'] > 100 else row['distance']
        pace_min = int(1609.34 / (row['average_speed'] * 60))
        pace_sec = int(((1609.34 / (row['average_speed'] * 60)) - pace_min) * 60)
        
        # 1. Grab the overall HR for the run
        avg_hr = row.get('average_heartrate', 0)
        has_hr = row.get('has_heartrate', False)
        
        # 2. Add it to the Expander Header
        hr_header = f" | ❤️ {int(avg_hr)} bpm" if has_hr else ""
        header_text = f"{row['parsed_emoji']} **{date_str}** | {name} | {dist:.2f} mi @ {pace_min}:{pace_sec:02d}/mi{hr_header}"

        with st.expander(header_text):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown("**Caption:**")
                
                raw_notes = str(row['formatted_notes']).strip()
                
                # Pull the splits string out so both conditions can use it
                splits_str = str(row.get('splits', ''))
                has_splits = splits_str and splits_str.lower() != 'nan'
                
                if not raw_notes or raw_notes.lower() == 'nan':
                    # Create a dynamic HR string for the placeholder sentence
                    hr_sentence = f", averaging {int(avg_hr)} bpm" if has_hr else ""
                    
                    if row['parsed_type'] == "Long Run":
                        placeholder = f"Logged a solid {dist:.1f} mile long run{hr_sentence}."
                    elif row['parsed_type'] == "Workout":
                        placeholder = f"Completed a structured workout session{hr_sentence}."
                    elif row['parsed_type'] == "Aerobic":
                        placeholder = f"Cruised for {dist:.1f} miles at a {pace_min}:{pace_sec:02d}/mi pace{hr_sentence}."
                    else:
                        placeholder = f"Kept it easy for {dist:.1f} miles{hr_sentence}."
                    
                    # Inject the splits if they exist
                    if has_splits:
                        st.write(f"*{placeholder}*\n\n**Splits:** {splits_str}")
                    else:
                        st.write(f"*{placeholder}*")
                        
                else:
                    # Render your actual written caption using the blockquote fix
                    paragraphs = raw_notes.split('\n\n')
                    quoted_notes = "\n>\n".join([f"> *{p}*" for p in paragraphs if p.strip()])
                    st.markdown(quoted_notes)
                    
                    # ---> NEW: Append the splits below your written caption
                    if has_splits:
                        # Adding an extra newline (\n) gives a nice buffer below the gray blockquote line
                        st.markdown(f"\n**Splits:** {splits_str}")
            with col2:
                st.write(f"**Classification:** {row['parsed_type']}")
                
                if row['parsed_intervals']:
                    st.write(f"**Structure:** {row['parsed_intervals']}")
                
                # You can add heart rate data here if available
                if row.get('has_heartrate'):
                    st.write(f"**Max HR:** {row.get('max_heartrate', 0):.0f} bpm")