import streamlit as st
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import pydeck as pdk
import os

st.set_page_config(layout="wide")

st.title("Selected Region Attributes Viewer")

# File uploaders
shp_file = st.file_uploader("Upload Shapefile (.zip of all shapefile parts)", type=["zip"])
csv_file = st.file_uploader("Upload CSV File", type=["csv"])

if shp_file and csv_file:
    try:
        # Extract and read shapefile
        import zipfile
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(shp_file, "r") as zip_ref:
                zip_ref.extractall(tmpdir)
            shapefile_path = [os.path.join(tmpdir, f) for f in os.listdir(tmpdir) if f.endswith(".shp")][0]
            gdf = gpd.read_file(shapefile_path)

        df = pd.read_csv(csv_file)

        # Debug: Show uploaded file structure
        st.subheader("CSV Preview")
        st.dataframe(df.head())

        # Join the data
        join_key_shp = 'REGION_NAM'
        join_key_csv = 'DISTRICT'

        if join_key_shp not in gdf.columns or join_key_csv not in df.columns:
            st.error(f"Could not find join columns. Expected '{join_key_shp}' in shapefile and '{join_key_csv}' in CSV.")
        else:
            merged = gdf.merge(df, left_on=join_key_shp, right_on=join_key_csv)

            # Plot map
            st.subheader("Region Map with Area and Rate")
            merged['centroid'] = merged.geometry.centroid
            merged[['centroid_x', 'centroid_y']] = merged['centroid'].apply(lambda p: pd.Series([p.x, p.y]))

            # Pydeck map
            layer = pdk.Layer(
                'PolygonLayer',
                data=merged,
                get_polygon='geometry.coordinates',
                get_fill_color='[200, 30, 0, 80]',
                pickable=True
            )

            st.pydeck_chart(pdk.Deck(
                initial_view_state=pdk.ViewState(
                    latitude=merged.centroid_y.mean(),
                    longitude=merged.centroid_x.mean(),
                    zoom=5,
                    pitch=0,
                ),
                layers=[layer],
                tooltip={"text": "{DISTRICT}\nArea: {Area}\nRate: {Rate}"}
            ))

            # Bar chart of Area
            st.subheader("Area by District")
            area_chart = df.sort_values("Area", ascending=False)
            fig_area, ax1 = plt.subplots(figsize=(10, 5))
            ax1.bar(area_chart["DISTRICT"], area_chart["Area"], color='skyblue')
            ax1.set_xticklabels(area_chart["DISTRICT"], rotation=90)
            ax1.set_ylabel("Area")
            st.pyplot(fig_area)

            # Line chart of Rate
            st.subheader("Rate by District")
            rate_chart = df.sort_values("Rate", ascending=False)
            fig_rate, ax2 = plt.subplots(figsize=(10, 5))
            ax2.plot(rate_chart["DISTRICT"], rate_chart["Rate"], marker='o', color='orange', linestyle='dashed')
            ax2.set_xticklabels(rate_chart["DISTRICT"], rotation=90)
            ax2.set_ylabel("Rate")
            st.pyplot(fig_rate)

    except Exception as e:
        st.error(f"Error processing files: {e}")

else:
    st.info("Please upload both a shapefile (.zip) and a CSV file to continue.")
