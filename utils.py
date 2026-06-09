from datetime import datetime
import reverse_geocoder as rg
import polyline
import streamlit as st
import requests
import pandas as pd
import re
import os
import time


# Strava API credentials
CLIENT_ID = st.secrets["STRAVA_CLIENT_ID"]
CLIENT_SECRET = st.secrets["STRAVA_CLIENT_SECRET"]

REDIRECT_URI = "http://localhost:8501/" 
STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE = "https://www.strava.com/api/v3"

def get_login_url():
    """Generates the URL for the user to authenticate."""
    return f"{STRAVA_AUTH_URL}?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&approval_prompt=force&scope=read,activity:read_all"

def exchange_token(code):
    """Exchanges the authorization code for an access token."""
    response = requests.post(
        STRAVA_TOKEN_URL,
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
        },
    )
    return response.json()

def fetch_activities(access_token):
    """Fetches the authenticated user's activities."""
    headers = {"Authorization": f"Bearer {access_token}"}
    activities_url = f"{STRAVA_API_BASE}/athlete/activities"

    all_activities = []
    request_page_number = 1
    param = {'per_page': 200, 'page': request_page_number}
    
    while True:
        response = requests.get(activities_url, headers=headers, params=param)
        activities = response.json()
        if not activities:
            break
        # stop once we hit the previous year's activities
        if pd.to_datetime(activities[-1]['start_date_local']).year < pd.Timestamp.now().year - 1:
            break
        all_activities.extend(activities)
        request_page_number += 1
        param['page'] = request_page_number

    return all_activities

@st.cache_data
def get_city_from_coords(df):
    """Uses reverse_geocoder to reverse geocode coordinates into a city name."""
    # 1. Filter out activities that don't have valid starting coordinates
    valid_coords_mask = df['start_latlng'].notna() & (df['start_latlng'].str.len() == 2)
    
    # If no valid coordinates exist, just return the dataframe
    if not valid_coords_mask.any():
        df['start_city'] = "Unknown Location"
        return df
        
    # 2. Extract all valid coordinates into a list of tuples: [(lat1, lon1), (lat2, lon2), ...]
    coords_list = df.loc[valid_coords_mask, 'start_latlng'].apply(tuple).tolist()
    
    # 3. Batch reverse-geocode ALL of them in milliseconds
    results = rg.search(coords_list)
    
    # 4. Format the results into "City, State"
    formatted_cities = []
    for res in results:
        city = res.get('name', 'Unknown')
        state = res.get('admin1', '') # admin1 usually represents the state/province
        
        if state:
            formatted_cities.append(f"{city}, {state}")
        else:
            formatted_cities.append(city)
            
    # 5. Assign the results back to the dataframe
    # Initialize the column with defaults first
    df['start_city'] = "Unknown Location" 
    # Map the formatted cities only to the rows that had valid coordinates
    df.loc[valid_coords_mask, 'start_city'] = formatted_cities
    
    return df


def clean_activities(df):
    """Cleans the activities DataFrame."""
    if df is None or df.empty:
        return df

    # 1. Extract the polyline string out of the 'map' dictionary
    if 'map' in df.columns:
        # If you haven't already extracted it, grab the string
        df['summary_polyline'] = df['map'].apply(lambda x: x.get('summary_polyline') if isinstance(x, dict) else None)
        # Drop the original unhashable dictionary column
        df = df.drop(columns=['map'])
    
    # 2. Drop other known unhashable Strava dictionary columns
    if 'athlete' in df.columns:
        df = df.drop(columns=['athlete'])

    # unit conversions
    df['start_date_local'] = pd.to_datetime(df['start_date_local'], errors='coerce')
    df['start_time'] = df['start_date_local'].dt.time
    df['start_year'] = df['start_date_local'].dt.year
    df['start_month'] = df['start_date_local'].dt.month
    df['start_day'] = df['start_date_local'].dt.day
    df['moving_time_minutes'] = df['moving_time'] / 60
    # change to mph for biking and minute mile for running
    def update_speed(row):
        if row['type'] == 'Ride':
            return row['average_speed'] * 2.23697
        else:
            if row['average_speed'] == 0:
                return 0
            else:
                return 26.8224 / row['average_speed'] 
    df['avg_pace'] = df.apply(update_speed, axis=1)
    df['distance_miles'] = df['distance'] / 1609.344
    df['elevation_gain_ft'] = df['total_elevation_gain'] * 3.28084
    # map 
    # encoded polyline - get earlier in function
    # df['summary_polyline'] = df['map'].str.get('summary_polyline')
    # decode polyline
    df['summary_polyline'] = df['summary_polyline'].apply(polyline.decode) 
    df = get_city_from_coords(df)
    # filter to current year
    df = df[df['start_year'] == datetime.now().year]

    return df

@st.cache_data
def process_summary_stats(df):
    """Calculates all the KPIs for the dashboard."""
    
    current_year = datetime.now().year
    current_month = datetime.now().month
    current_week = datetime.now().isocalendar()[1] # Gets current week number out of 52

    # --- Running Metrics (Current Year) ---
    runs_this_year = df[(df['type'] == 'Run') & (df['start_year'] == current_year)]
    
    # 1. Days run out of the year
    days_run = runs_this_year['start_day'].nunique()
    
    # 2. Total miles in the year
    ytd_run_miles = runs_this_year['distance_miles'].sum()
    
    # 3. Average weekly mileage
    # Prevent divide by zero if it's week 1
    avg_weekly_miles = ytd_run_miles / current_week if current_week > 0 else ytd_run_miles
    
    # 4. Current month mileage
    runs_this_month = runs_this_year[runs_this_year['start_month'] == current_month]
    month_run_miles = runs_this_month['distance_miles'].sum()

    # --- Multisport & Exploration Metrics ---
    # 5. Total Bikes (Rides)
    rides_df = df[df['type'] == 'Ride']
    total_bike_rides = len(rides_df)
    total_bike_miles = rides_df['distance_miles'].sum()
    
    # 6. Cities Exercised In
    cities_count = df['start_city'].nunique() if 'start_city' in df.columns else 0

    # 7. Bonus: Total Elevation (All activities)
    total_vert_ft = df['elevation_gain_ft'].sum() if 'elevation_gain_ft' in df.columns else 0

    return {
        "days_run": days_run,
        "ytd_run_miles": ytd_run_miles,
        "avg_weekly_miles": avg_weekly_miles,
        "month_run_miles": month_run_miles,
        "total_bike_rides": total_bike_rides,
        "total_bike_miles": total_bike_miles,
        "cities_count": cities_count,
        "total_vert_ft": total_vert_ft
    }

def classify_and_extract(row: pd.Series, long_run_thresh: float = 6.5, aerobic_thresh_decimal: float = 8.25) -> dict:
    """
    Classifies a run based on distance, pace, and simple caption heuristics.
    """
    description = str(row.get('description', ''))
    description_lower = description.lower()
    
    # 1. Calculate metrics for the heuristics
    raw_dist = row.get('distance', 0)
    distance_mi = raw_dist * 0.000621371 if raw_dist > 100 else raw_dist
    
    avg_speed = row.get('average_speed', 0)
    # Convert m/s to min/mile (decimal)
    pace_decimal = 1609.34 / (avg_speed * 60) if avg_speed > 0 else 99 
    
    # 2. Format the notes for Streamlit UI (double newlines)
    formatted_notes = description.replace('\n', '\n\n')
    
    details = {
        "type": "Easy", 
        "emoji": "🐢", # Fallback emoji
        "intervals": None, 
        "notes": formatted_notes
    }

    # --- 3. The Heuristic Waterfall ---

    # Condition A: Workout (Contains wu and cd)
    if 'wu' in description_lower and 'cd' in description_lower:
        details["type"] = "Workout"
        details["emoji"] = "🔥"
        
        # Still attempt to grab that specific line so you can see the 
        # interval structure at a glance in the UI
        lines = description_lower.split('\n')
        for line in lines:
            if 'wu' in line and 'cd' in line:
                details["intervals"] = line.strip().title()
                break
        return details

    # Condition B: Long Run (> 6 miles)
    if distance_mi > long_run_thresh:
        details["type"] = "Long Run"
        details["emoji"] = "🗺️" 
        return details

    # Condition C: Aerobic vs Easy (Threshold: 8:15 min/mile)
    if pace_decimal < aerobic_thresh_decimal:
        details["type"] = "Aerobic"
        details["emoji"] = "🏃‍♀️"
    else:
        details["type"] = "Easy"
        details["emoji"] = "🐢"
        
    return details

def sync_detailed_activities(summary_df: pd.DataFrame, access_token: str, cache_file: str = "workout_details.csv", use_cache: bool = True) -> pd.DataFrame:
    """
    Syncs descriptions, splits, and PRs. 
    If use_cache is True, writes to a local CSV. Otherwise, operates in memory.
    """
    runs_df = summary_df[summary_df['type'] == 'Run'].copy()
    
    # 1. Setup the target dataframe based on the cache toggle
    if use_cache and os.path.exists(cache_file):
        cache_df = pd.read_csv(cache_file)
    else:
        cache_df = pd.DataFrame(columns=[
            "id", "description", "splits",
            "pr_800m", "pr_1_mile", "pr_2_mile", 
            "pr_5k", "pr_10k", "pr_10_mile"
        ])
        
    # 2. Determine which IDs need fetching
    if use_cache:
        cached_ids = set(cache_df['id'].tolist())
        missing_ids = runs_df[~runs_df['id'].isin(cached_ids)]['id'].tolist()
    else:
        # In memory-only mode, we must fetch everything passed in the summary_df
        missing_ids = runs_df['id'].tolist()
    
    new_data = []
    if missing_ids:
        with st.spinner(f"Fetching {len(missing_ids)} detailed records from Strava..."):
            headers = {"Authorization": f"Bearer {access_token}"}
            target_efforts = {"800m": "pr_800m", "1 mile": "pr_1_mile", "2 mile": "pr_2_mile", 
                              "5K": "pr_5k", "10K": "pr_10k", "10 mile": "pr_10_mile"}
            
            for act_id in missing_ids:
                url = f"https://www.strava.com/api/v3/activities/{act_id}"
                response = requests.get(url, headers=headers)
                
                if response.status_code == 200:
                    detail_json = response.json()
                    
                    row_data = {
                        "id": detail_json.get("id"),
                        "description": detail_json.get("description", "") 
                    }
                    
                    # Extract PRs
                    best_efforts = detail_json.get("best_efforts", [])
                    for effort in best_efforts:
                        effort_name = effort.get("name")
                        if effort_name in target_efforts:
                            column_name = target_efforts[effort_name]
                            row_data[column_name] = effort.get("elapsed_time")
                            
                    # Extract Splits
                    splits_standard = detail_json.get("splits_standard", [])
                    split_strings = []
                    
                    for split in splits_standard:
                        split_dist_mi = split.get("distance", 0) * 0.000621371
                        if split_dist_mi > 0.1:
                            pace_decimal = (split.get("moving_time", 0) / 60) / split_dist_mi
                            p_min = int(pace_decimal)
                            p_sec = int((pace_decimal - p_min) * 60)
                            
                            split_hr = split.get("average_heartrate")
                            if split_hr:
                                split_strings.append(f"{p_min}:{p_sec:02d} ({int(split_hr)} bpm)")
                            else:
                                split_strings.append(f"{p_min}:{p_sec:02d}")
                            
                    row_data["splits"] = ", ".join(split_strings)

                    new_data.append(row_data)
                    
                elif response.status_code == 429:
                    st.warning("Strava API rate limit exceeded! Stopping fetch.")
                    break 
                    
                time.sleep(0.5)
                
    # 3. Append, conditionally save, and merge
    if new_data:
        new_df = pd.DataFrame(new_data)
        cache_df = pd.concat([cache_df, new_df], ignore_index=True).drop_duplicates(subset=['id'], keep='last')
        
        # Only write to the hard drive if VIP mode is engaged
        if use_cache:
            cache_df.to_csv(cache_file, index=False)
        
    merged_df = summary_df.merge(cache_df, on='id', how='left')
    
    return merged_df