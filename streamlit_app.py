import streamlit as st
import geopandas as gpd
import plotly.graph_objects as go
import pandas as pd
from shapely.geometry import Point, Polygon, MultiPolygon
import tempfile
import requests
import zipfile
import os

st.set_page_config(layout="wide")
st.title("BC Resource Region and OG District Visualization (EPSG:3005)")

# --- GitHub raw URLs ---
csv_url = "https://raw.githubusercontent.com/Baipzix/BCOGRegApp/main/data/Mock_OG_district.csv"
zip_url = "https://github.com/Baipzix/BCOGRegApp/raw/main/data/BC_ResourceRegion.zip"

def extract_coordinates(geometry):
    x_coords, y_coords = [], []
    if isinstance(geometry, Polygon):
        x, y = zip(*geometry.exterior.coords)
        x_coords.extend(x)
        y_coords.extend(y)
        x_coords.append(None)
        y_coords.append(None)
    elif isinstance(geometry, MultiPolygon):
        for poly in geometry.geoms:
            x, y = zip(*poly.exterior.coords)
            x_coords.extend(x + (None,))
            y_coords.extend(y + (None,))
    return x_coords, y_coords

try:
    # --- Download and read shapefile from GitHub ZIP ---
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "regions.zip")
        with open(zip_path, "wb") as f:
            f.write(requests.get(zip_url).content)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(tmpdir)

        shp_files = [os.path.join(tmpdir, f) for f in os.listdir(tmpdir) if f.endswith(".shp")]
        if not shp_files:
            raise FileNotFoundError("No .shp file found in the ZIP.")
        gdf = gpd.read_file(shp_files[0])

    if gdf.crs != 'EPSG:3005':
        gdf = gdf.to_crs(epsg=3005)

    # --- Load CSV from GitHub ---
    df = pd.read_csv(csv_url)
    df['geometry'] = df.apply(lambda row: Point(row['x'], row['y']), axis=1)
    district_gdf = gpd.GeoDataFrame(df, geometry='geometry', crs='EPSG:3005')

    # --- Spatial join ---
    joined = gpd.sjoin(district_gdf, gdf[['REGION_NAM', 'geometry']], how='left', predicate='within')

    # --- Aggregate stats ---
    region_stats = joined.groupby('REGION_NAM').agg({'Rate': 'mean', 'Area': 'sum'}).reset_index()
    gdf = gdf.merge(region_stats, on='REGION_NAM', how='left')

    # --- UI for region selection ---
    region_names = sorted(gdf['REGION_NAM'].dropna().unique().tolist())
    selected_regions = st.multiselect("Select Resource Regions to Highlight", region_names)

    # --- Main map ---
    fig = go.Figure()

    for idx, row in gdf.iterrows():
        x, y = extract_coordinates(row.geometry)
        region_name = row.get('REGION_NAM', f'Region {idx}')
        is_selected = region_name in selected_regions

        fig.add_trace(go.Scatter(
            x=x, y=y, mode='lines', fill='toself',
            fillcolor='lightblue' if is_selected else 'lightgrey',
            line=dict(color='white', width=1),
            hoverinfo='text',
            text=f"Region: {region_name}<br>Rate: {row.get('Rate', float('nan')):.2f}<br>Area: {row.get('Area', float('nan')):.0f}",
            showlegend=False
        ))

    # --- OG Districts ---
    area_max = df['Area'].max()

    fig.add_trace(go.Scatter(
        x=df['x'], y=df['y'], mode='markers',
        marker=dict(
            size=20 * df['Area'] / area_max + 5,
            color=df['Rate'],
            colorscale='RdYlGn',
            colorbar=dict(title="Rate", len=0.4, y=0.7),
            line=dict(color='black', width=0.5),
            showscale=True
        ),
        hoverinfo='text',
        text=[f"District: {row['DISTRICT']}<br>Rate: {row['Rate']:.2f}<br>Area: {row['Area']:.0f}" for _, row in df.iterrows()],
        showlegend=False
    ))

    fig.update_layout(
        title='BC Resource Regions and OG Districts',
        xaxis=dict(visible=False, scaleanchor='y', scaleratio=1),
        yaxis=dict(visible=False, scaleanchor='x', scaleratio=1),
        width=900, height=800,
        margin=dict(l=50, r=50, t=50, b=160),
        plot_bgcolor='white',
        paper_bgcolor='white'
    )

    st.plotly_chart(fig, use_container_width=True)

    # --- Selected Region Info ---
    if selected_regions:
        selected_gdf = gdf[gdf['REGION_NAM'].isin(selected_regions)]
        st.subheader("Selected Region Attributes")
        display_cols = ['REGION_NAM']
        if 'Rate' in selected_gdf.columns:
            display_cols.append('Rate')
        if 'Area' in selected_gdf.columns:
            display_cols.append('Area')
        st.dataframe(selected_gdf[display_cols])

        selected_area = selected_gdf['Area'].sum()
        total_area = gdf['Area'].sum()

        st.subheader("Selected Area vs Total Area")
        pie_fig = go.Figure(go.Pie(
            labels=['Selected Area', 'Remaining Area'],
            values=[selected_area, total_area - selected_area],
            marker=dict(colors=['lightblue', 'lightgrey'])
        ))
        st.plotly_chart(pie_fig, use_container_width=False)

    # --- Area and Rate Charts ---
    st.subheader("Regional Area and Rate Charts")

    area_summary = gdf[['REGION_NAM', 'Area']].dropna().sort_values(by='REGION_NAM')
    rate_summary = gdf[['REGION_NAM', 'Rate']].dropna().sort_values(by='Rate')

    col1, col2 = st.columns(2)

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

except Exception as e:
    st.error(f"Error processing files: {str(e)}")
    st.write("Ensure the shapefile and CSV files are accessible and correctly formatted.")

# --- Optional Page Navigation ---
st.markdown("---")
if 'show_new_page' not in st.session_state:
    st.session_state['show_new_page'] = False

if st.button("Go to Site level page"):
    st.session_state['show_new_page'] = True

if st.session_state['show_new_page']:
    st.title("Welcome to the New Page!")
    st.write("This is a new page. Add your content here.")
