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

st.title("Strava Activity Dashboard")

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
    # For a real app, you'd want to handle pagination to get more than 30 activities!
    response = requests.get(f"{STRAVA_API_BASE}/athlete/activities", headers=headers)
    return response.json()

# --- App Logic ---

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
    
else:
    # User is logged in
    st.success("Successfully connected to Strava!")
    
    if st.button("Log Out"):
        st.session_state.access_token = None
        st.rerun()

    # Fetch and display data
    df = None
    with st.spinner("Fetching your activities..."):
        activities = fetch_activities(st.session_state.access_token)
        
        if activities:
            # Convert JSON to a Pandas DataFrame for easy manipulation
            df = pd.DataFrame(activities)
            
            # Show raw data (you can replace this with your notebook visuals)
            st.subheader("Recent Activities")
            st.dataframe(df[['name', 'distance', 'moving_time', 'type', 'start_date_local']])
        else:
            st.info("No activities found!")

    # Clean df (convert distance to km, moving_time to minutes, etc.)

    # save df to session state for use in other pages
    if df is not None:
        st.session_state.strava_data = df