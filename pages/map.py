import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import polyline

# --- Page Config ---
st.set_page_config(page_title="Adventure Map", page_icon="🗺️", layout="wide")
st.title("Adventure Map 🗺️")

# --- 1. Data Retrieval ---
# Check if the data exists in session state. If not, stop the page.
if "strava_data" not in st.session_state:
    st.warning("No data found! Please go to the Home page and log in to Strava first.")
    st.page_link("app.py", label="Return to Home", icon="🏠")
    st.stop() 

# Retrieve the data
df = st.session_state.strava_data

# add polyline data to df if not already present
try:
    
    # filter out bad rows
    df = df[df['summary_polyline'].apply(lambda x: isinstance(x, list) and len(x) > 0)]
except KeyError:
    st.warning("No polyline data found! Map visualization will not be available.")
    # display the data table with all columns for debugging
    st.subheader("Strava Data (No Polyline)")
    st.dataframe(df.head(10))  # Show first 10 rows for debugging
    st.stop()

# --- 2. Page-Specific Sidebar Filters ---
st.sidebar.header("Map Filters")

# Activity Type Filter
available_types = df['type'].unique().tolist() if 'type' in df.columns else []
selected_types = st.sidebar.multiselect(
    "Activity Type", 
    options=available_types, 
    default=['Run', 'Walk', 'Ride']
)

# Apply the filter
filtered_df = df[df['type'].isin(selected_types)]

# --- 3. Map Rendering ---
# Filter out activities that don't have GPS polyline data
if 'summary_polyline' in filtered_df.columns:
    activities_map = filtered_df.dropna(subset=['summary_polyline'])
    
    if not activities_map.empty:
        # Color scheme mapping
        color_map = {'Ride': 'red', 'Run': 'blue', 'Walk': 'purple'}
        
        # Centroid calculation to center the map
        def centroid(polylines):
            x, y = [], []
            for polyline in polylines:
                # Ensure the polyline isn't empty or invalid
                if isinstance(polyline, list) and len(polyline) > 0:
                    for coord in polyline:
                        x.append(coord[0])
                        y.append(coord[1])
            # Fallback coordinates if geometry fails
            if not x or not y:
                return [47.6555, -122.3131] 
            return [(min(x)+max(x))/2, (min(y)+max(y))/2]

        # Initialize the map
        m = folium.Map(location=centroid(activities_map['summary_polyline']), zoom_start=10)
        
        # Plot all activities
        for _, row in activities_map.iterrows():
            act_type = row.get('type', 'Run')
            act_name = row.get('name', 'Activity')
            poly_color = color_map.get(act_type, 'gray') # Default to gray if type unknown
            
            # Draw the line
            folium.PolyLine(
                row['summary_polyline'], 
                color=poly_color, 
                opacity=0.6,
                weight=3,
                tooltip=f"{act_name} ({act_type})"
            ).add_to(m)

        # Render in Streamlit
        st_folium(m, width=900, height=600, returned_objects=[])
        
    else:
        st.info("No GPS data available for the selected activity types.")
else:
    st.error("The column 'summary_polyline' was not found in your Strava data.")