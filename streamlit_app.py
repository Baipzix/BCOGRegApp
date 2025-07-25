import streamlit as st
import geopandas as gpd
import plotly.graph_objects as go
import pandas as pd
from shapely.geometry import Point, Polygon, MultiPolygon
import requests
import zipfile
import os
import tempfile
import shutil

st.set_page_config(layout="wide")
st.title("BC Resource Region and OG District Visualization (EPSG:3005)")

# GitHub raw URLs
csv_url = "https://github.com/Baipzix/BCOG_regional/blob/main/data/Mock_OG_district.csv"
shp_zip_url = "https://github.com/Baipzix/BCOG_regional/blob/main/data/BC_ResourceRegion.zip"

# Temporary directory for file handling
temp_dir = tempfile.mkdtemp()
csv_path = os.path.join(temp_dir, "Mock_OG_district.csv")
shp_zip_path = os.path.join(temp_dir, "shapefile.zip")
extracted_dir = os.path.join(temp_dir, "shapefile_extracted")
os.makedirs(extracted_dir, exist_ok=True)

def extract_coordinates(geometry):
    if isinstance(geometry, Polygon):
        return list(zip(*geometry.exterior.coords))[0], list(zip(*geometry.exterior.coords))[1]
    elif isinstance(geometry, MultiPolygon):
        x_coords, y_coords = [], []
        for poly in geometry.geoms:
            x, y = zip(*poly.exterior.coords)
            x_coords.extend(x + (None,))
            y_coords.extend(y + (None,))
        return x_coords, y_coords
    return [], []

try:
    # Download and read CSV
    st.write("Downloading CSV from GitHub...")
    df = pd.read_csv(csv_url)  # Direct read from raw URL

    # Download and extract shapefile
    st.write("Downloading and extracting shapefile from GitHub...")
    with open(shp_zip_path, "wb") as f:
        f.write(requests.get(shp_zip_url).content)
    with zipfile.ZipFile(shp_zip_path, 'r') as zip_ref:
        zip_ref.extractall(extracted_dir)
    
    # Find the .shp file
    shp_file = [f for f in os.listdir(extracted_dir) if f.endswith('.shp')][0]
    shp_path = os.path.join(extracted_dir, shp_file)
    gdf = gpd.read_file(shp_path)
    if gdf.crs != 'EPSG:3005':
        gdf = gdf.to_crs(epsg=3005)

    # --- User selection for multiple regions ---
    region_names = sorted(gdf['REGION_NAM'].dropna().unique().tolist())
    selected_regions = st.multiselect("Select Resource Regions to Highlight", region_names)

    # --- Plotly Figure: Main Map ---
    fig = go.Figure()

    for idx, row in gdf.iterrows():
        x, y = extract_coordinates(row.geometry)
        region_name = row.get('REGION_NAM', f'Region {idx}')
        is_selected = region_name in selected_regions

        fig.add_trace(go.Scatter(
            x=x,
            y=y,
            mode='lines',
            fill='toself',
            fillcolor='lightblue' if is_selected else 'lightgrey',
            line=dict(color='white', width=1),
            hoverinfo='text',
            text=f"Region: {region_name}<br>Rate: {row.get('Rate', 'N/A')}<br>Area: {row.get('Area', 'N/A')}",
            showlegend=False
        ))

    # --- Plot OG Districts ---
    rate_min, rate_max = df['Rate'].min(), df['Rate'].max()
    area_max = df['Area'].max()
    fig.add_trace(go.Scatter(
        x=df['x'],
        y=df['y'],
        mode='markers',
        marker=dict(
            size=20 * df['Area'] / area_max + 5,
            color=df['Rate'],
            colorscale='RdYlGn',
            colorbar=dict(title="Rate", len=0.4, y=0.7),
            line=dict(color='black', width=0.5),
            showscale=True
        ),
        hoverinfo='text',
        text=[f"District: {row['DISTRICT']}<br>Rate: {row['Rate']}<br>Area: {row['Area']}" for _, row in df.iterrows()],
        showlegend=False
    ))

    fig.update_layout(
        title='BC Resource Regions and OG Districts',
        xaxis=dict(visible=False, scaleanchor='y', scaleratio=1),
        yaxis=dict(visible=False, scaleanchor='x', scaleratio=1),
        width=800,
        height=800,
        margin=dict(l=50, r=50, t=50, b=160),
        plot_bgcolor='white',
        paper_bgcolor='white'
    )

    # --- Show Plot ---
    st.plotly_chart(fig, use_container_width=True)

    # --- Show Selected Region Attributes + Pie ---
    if selected_regions:
        selected_gdf = gdf[gdf['REGION_NAM'].isin(selected_regions)]
        st.subheader("Selected Region Attributes")
        st.dataframe(selected_gdf[['REGION_NAM', 'Rate', 'Area']])

        selected_area = selected_gdf['Area'].sum()
        total_area = gdf['Area'].sum()

        st.subheader("Selected Area vs Total Area")
        pie_fig = go.Figure(go.Pie(
            labels=['Selected Area', 'Remaining Area'],
            values=[selected_area, total_area - selected_area],
            marker=dict(colors=['lightblue', 'lightgrey'])
        ))
        st.plotly_chart(pie_fig, use_container_width=False)

    # --- Area and Rate Charts Separately ---
    st.subheader("Regional Area and Rate Charts")

    # Prepare data
    area_summary = gdf[['REGION_NAM', 'Area']].dropna().sort_values(by='REGION_NAM')
    rate_summary = gdf[['REGION_NAM', 'Rate']].dropna().sort_values(by='Rate')

    col1, col2 = st.columns(2)

    # --- Area Bar Chart ---
    with col1:
        st.markdown("**Total Area by Region (sorted by REGION_NAM)**")
        area_fig = go.Figure(go.Bar(
            x=area_summary['REGION_NAM'],
            y=area_summary['Area'],
            marker_color='lightgrey'
        ))
        area_fig.update_layout(
            xaxis_title='Region',
            yaxis_title='Area',
            xaxis=dict(tickangle=45),
            height=500,
            margin=dict(l=40, r=20, t=40, b=120)
        )
        st.plotly_chart(area_fig, use_container_width=True)

    # --- Rate Line Chart ---
    with col2:
        st.markdown("**Rate by Region (sorted by Rate)**")
        rate_fig = go.Figure(go.Scatter(
            x=rate_summary['REGION_NAM'],
            y=rate_summary['Rate'],
            mode='lines+markers',
            line=dict(color='black', dash='dash'),
            marker=dict(size=6)
        ))
        rate_fig.update_layout(
            xaxis_title='Region',
            yaxis_title='Rate',
            xaxis=dict(tickangle=45),
            height=500,
            margin=dict(l=20, r=40, t=40, b=120)
        )
        st.plotly_chart(rate_fig, use_container_width=True)

    # Clean up temporary files
    shutil.rmtree(temp_dir, ignore_errors=True)

except Exception as e:
    st.error(f"Error processing files: {str(e)}")
    st.write("Ensure the GitHub files are accessible and correctly formatted (CSV and zipped shapefile with .shp, .shx, .dbf files).")

# --- New Page Section ---
st.markdown("---")
if 'show_new_page' not in st.session_state:
    st.session_state['show_new_page'] = False

if st.button("Go to Site level page"):
    st.session_state['show_new_page'] = True

if st.session_state['show_new_page']:
    st.title("Welcome to the New Page!")
    st.write("This is a new page. Add your content here.")