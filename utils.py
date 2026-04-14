from datetime import datetime
import reverse_geocoder as rg
import polyline
import streamlit as st
import requests
import pandas as pd

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
    # encoded polyline
    df['summary_polyline'] = df['map'].str.get('summary_polyline')
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