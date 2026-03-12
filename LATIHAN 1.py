import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import geopandas as gpd
from shapely.geometry import Polygon, Point
import numpy as np
import folium
from streamlit_folium import st_folium
import io

# --- FUNGSI FORMAT BEARING (DMS) ---
def format_dms(decimal_brg):
    decimal_brg = decimal_brg % 360
    deg = int(decimal_brg)
    mnt = int((decimal_brg - deg) * 60)
    sec = int(round(((decimal_brg - deg) * 60 - mnt) * 60))
    if sec >= 60: mnt += 1; sec = 0
    if mnt >= 60: deg += 1; mnt = 0
    return f"{deg % 360}°{mnt:02d}'{sec:02d}\""

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Geo-Ukur Pro v4.0", layout="wide")

# Data pengguna
users = {
    "1": {"nama": "Nur Syuhadah", "password": "admin123"},
    "2": {"nama": "Syuhadah", "password": "admin123"},
    "3": {"nama": "Cucud", "password": "admin123"}
}

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['user_nama'] = ""

# --- 2. SISTEM LOG MASUK DENGAN LOGO ---
if not st.session_state['logged_in']:
    col_logo1, col_logo2, col_logo3 = st.columns([1, 2, 1])
    with col_logo2:
        try:
            st.image("Poli_Logo (1).png", use_container_width=True)
        except:
            st.warning("Fail logo 'Poli_Logo (1).png' tidak ditemui.")
            
    st.markdown("<h2 style='text-align: center;'>🔐 Log Masuk Sistem Geo-Ukur</h2>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            u_id = st.text_input("Username (Nombor sahaja)")
            u_pass = st.text_input("Password", type="password")
            submit = st.form_submit_button("Log Masuk", use_container_width=True)
            if submit:
                if u_id in users and users[u_id]["password"] == u_pass:
                    st.session_state['logged_in'] = True
                    st.session_state['user_nama'] = users[u_id]["nama"]
                    st.rerun()
                else:
                    st.error("Username atau Password salah!")
    st.stop()

# --- 3. APLIKASI UTAMA ---

with st.sidebar:
    try:
        st.image("Poli_Logo (1).png", use_container_width=True)
    except:
        pass
    st.markdown("---")

st.sidebar.success(f"🔓 Log Masuk: {st.session_state['user_nama']}")

st.sidebar.header("⚙️ Tetapan Lot & Paparan")
no_lot = st.sidebar.text_input("Masukkan Nombor Lot", "11487")
zoom_level = st.sidebar.slider("Tahap Zoom", 10, 22, 19)
marker_size = st.sidebar.slider("Saiz Marker Stesen", 1, 20, 5)
font_size = st.sidebar.slider("Saiz Tulisan (Label)", 5, 20, 8)

# --- BAHAGIAN WARNA ---
line_color = st.sidebar.color_picker("Warna Sempadan (Line)", "#FF0000")
fill_color = st.sidebar.color_picker("Warna Kawasan (Polygon)", "#FFFF00")
fill_opacity = st.sidebar.slider("Kelegapan (Opacity)", 0.0, 1.0, 0.3)

map_options = ["Satelit Sahaja", "Hybrid (Satelit + Jalan)", "OpenStreetMap"]
map_type = st.sidebar.radio("Jenis Peta", map_options)

if map_type == "Satelit Sahaja":
    map_url = 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
    map_attr = 'Google Satellite'
elif map_type == "Hybrid (Satelit + Jalan)":
    map_url = 'https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}'
    map_attr = 'Google Hybrid'
else:
    map_url = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
    map_attr = 'OpenStreetMap'

if st.sidebar.button("Log Keluar"):
    st.session_state['logged_in'] = False
    st.rerun()

st.title(f"🗺️ Visualisasi Geo-Ukur - Lot {no_lot}")

uploaded_file = st.file_uploader("Upload fail CSV anda (STN, E, N)", type=['csv'])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.upper()
    
    if 'E' in df.columns and 'N' in df.columns:
        coords = list(zip(df['E'], df['N']))
        poly_geom = Polygon(coords)
        poly_centroid = poly_geom.centroid
        
        # Penambahan atribut PERIMETER dalam GeoDataFrame untuk QGIS
        gdf = gpd.GeoDataFrame({
            'LOT': [no_lot], 
            'LUAS_M2': [poly_geom.area],
            'PERIMETER': [poly_geom.length] # Atribut tambahan untuk Attribute Table QGIS
        }, geometry=[poly_geom], crs="EPSG:4390")
        
        point_geoms = [Point(x, y) for x, y in zip(df['E'], df['N'])]
        gdf_points = gpd.GeoDataFrame(df, geometry=point_geoms, crs="EPSG:4390")
        
        gdf_wgs84 = gdf.to_crs(epsg=4326)
        gdf_points_wgs84 = gdf_points.to_crs(epsg=4326)
        centroid_wgs84 = gdf_wgs84.geometry.centroid.iloc[0]
        
        luas = poly_geom.area
        perimeter = poly_geom.length
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Luas Kawasan", f"{luas:.2f} m²")
        m2.metric("Perimeter", f"{perimeter:.3f} m")
        m3.metric("Bilangan Stesen", len(df))

        results = []
        latit_dipat_results = []
        sum_latit = 0
        sum_dipat = 0
        num_points = len(df)
        
        for i in range(num_points):
            p1_m = df.iloc[i]
            p2_m = df.iloc[(i + 1) % num_points]
            p1_w = gdf_points_wgs84.iloc[i]
            de, dn = p2_m['E'] - p1_m['E'], p2_m['N'] - p1_m['N']
            dist = np.sqrt(de**2 + dn**2)
            brg_d = np.degrees(np.arctan2(de, dn)) % 360
            
            results.append({
                "STN": p1_m['STN'], "E (m)": f"{p1_m['E']:.3f}", "N (m)": f"{p1_m['N']:.3f}",
                "Latitude": f"{p1_w.geometry.y:.8f}", "Longitude": f"{p1_w.geometry.x:.8f}",
                "Ke Stesen": p2_m['STN'], "Bearing": format_dms(brg_d), "Jarak (m)": f"{dist:.3f}"
            })

            latit_dipat_results.append({
                "Dari STN": p1_m['STN'], "Ke STN": p2_m['STN'], "Bearing": format_dms(brg_d),
                "Jarak (m)": f"{dist:.3f}", "Latit (ΔN)": f"{dn:.4f}", "Dipat (ΔE)": f"{de:.4f}"
            })
            sum_latit += dn
            sum_dipat += de

        df_jadual = pd.DataFrame(results)
        df_latit_dipat = pd.DataFrame(latit_dipat_results)
        misclosure = np.sqrt(sum_latit**2 + sum_dipat**2)
        precision = perimeter / misclosure if misclosure > 0 else 0

        tab1, tab2, tab3, tab4 = st.tabs(["🛰️ Peta Satelit", "📊 Pelan Teknikal", "📋 Jadual Data", "📥 Eksport Data"])

        with tab1:
            st.subheader(f"Paparan Lot {no_lot}")
            m = folium.Map(location=[centroid_wgs84.y, centroid_wgs84.x], zoom_start=zoom_level, max_zoom=22, tiles=None)
            
            folium.TileLayer(tiles=map_url, attr=map_attr, name=map_attr, overlay=False, control=True, max_zoom=22).add_to(m)

            # --- POPUP MAKLUMAT LOT ---
            lot_popup_html = f"""
            <div style='font-family: Arial; width: 150px;'>
                <h4 style='margin-bottom:5px; color:#2c3e50;'>📄 Maklumat Lot</h4>
                <hr style='margin:5px 0;'>
                <b>No. Lot:</b> {no_lot}<br>
                <b>Luas:</b> {luas:.2f} m²
            </div>
            """

            folium.GeoJson(
                gdf_wgs84,
                style_function=lambda x: {
                    'fillColor': fill_color, 
                    'color': line_color, 
                    'weight': 3, 
                    'fillOpacity': fill_opacity
                },
                tooltip=f"Lot {no_lot}",
                popup=folium.Popup(lot_popup_html, max_width=200)
            ).add_to(m)

            for i in range(num_points):
                p1_m = df.iloc[i]
                p2_m = df.iloc[(i + 1) % num_points]
                p1_w = gdf_points_wgs84.iloc[i]
                p2_w = gdf_points_wgs84.iloc[(i + 1) % num_points]
                
                # --- POPUP MAKLUMAT STESEN ---
                stn_popup_content = f"""
                <div style='font-family: Arial; width: 180px;'>
                    <h4 style='margin: 0 0 10px 0; color: #d9534f;'>📍 Stesen {int(p1_m['STN'])}</h4>
                    <table style='width: 100%; font-size: 11px; border-collapse: collapse;'>
                        <tr><td><b>E (m):</b></td><td align='right'>{p1_m['E']:.3f}</td></tr>
                        <tr><td><b>N (m):</b></td><td align='right'>{p1_m['N']:.3f}</td></tr>
                        <tr><td><b>Lat:</b></td><td align='right'>{p1_w.geometry.y:.7f}</td></tr>
                        <tr><td><b>Long:</b></td><td align='right'>{p1_w.geometry.x:.7f}</td></tr>
                    </table>
                </div>
                """
                
                folium.CircleMarker(
                    location=[p1_w.geometry.y, p1_w.geometry.x],
                    radius=marker_size, color='yellow', fill=True, fill_color='red', fill_opacity=1,
                    popup=folium.Popup(stn_popup_content, max_width=250)
                ).add_to(m)

                de, dn = p2_m['E'] - p1_m['E'], p2_m['N'] - p1_m['N']
                brg_text = format_dms(np.degrees(np.arctan2(de, dn)) % 360)
                dist_text = f"{np.sqrt(de**2+dn**2):.3f}m"
                
                txt_angle = np.degrees(np.arctan2(dn, de))
                if txt_angle > 90: txt_angle -= 180
                elif txt_angle < -90: txt_angle += 180

                mid_lat = (p1_w.geometry.y + p2_w.geometry.y) / 2
                mid_lon = (p1_w.geometry.x + p2_w.geometry.x) / 2

                folium.Marker(
                    [mid_lat, mid_lon],
                    icon=folium.DivIcon(
                        icon_size=(150,30),
                        icon_anchor=(75,15),
                        html=f"""<div style="font-size: {font_size}pt; color: #00FF00; font-weight: bold; 
                                text-shadow: 2px 2px 3px #000; text-align: center;
                                transform: rotate({-txt_angle}deg);">
                                {brg_text}<br>{dist_text}</div>"""
                    )
                ).add_to(m)
            st_folium(m, width=1100, height=600)

        with tab2:
            st.subheader(f"📊 Pelan Teknikal Lot {no_lot}")
            fig, ax = plt.subplots(figsize=(10, 10))
            ax.grid(True, linestyle='--', alpha=0.6) 
            
            gdf.plot(ax=ax, facecolor=fill_color, edgecolor=line_color, linewidth=1.5, alpha=fill_opacity)
            
            cx, cy = poly_centroid.x, poly_centroid.y
            ax.text(cx, cy, f"LOT {no_lot}\n{luas:.2f} m²", 
                    fontsize=font_size + 4, fontweight='bold', ha='center', va='center',
                    color='black', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=2))

            ax.scatter(df['E'], df['N'], color='red', s=marker_size*10)
            for i in range(num_points):
                p1 = df.iloc[i]; p2 = df.iloc[(i + 1) % num_points]
                de, dn = p2['E'] - p1['E'], p2['N'] - p1['N']
                mid_e, mid_n = (p1['E'] + p2['E']) / 2, (p1['N'] + p2['N']) / 2
                t_ang = np.degrees(np.arctan2(dn, de))
                if t_ang > 90: t_ang -= 180
                elif t_ang < -90: t_ang += 180
                
                ax.text(mid_e, mid_n, f"{format_dms(np.degrees(np.arctan2(de, dn)) % 360)}\n{np.sqrt(de**2 + dn**2):.3f}m", 
                        fontsize=font_size, ha='center', va='center', rotation=t_ang, fontweight='bold',
                        bbox=dict(facecolor='white', alpha=0.6, edgecolor='none', pad=1))
                
                ax.text(p1['E'], p1['N'], f"  {int(p1['STN'])}", color='blue', fontsize=font_size+2, fontweight='bold')
            
            ax.set_aspect('equal')
            st.pyplot(fig)

        with tab3:
            st.subheader(f"📋 Jadual Koordinat & Ukuran Lot {no_lot}")
            st.dataframe(df_jadual, use_container_width=True, hide_index=True)
            st.markdown("---")
            if st.button("📐 Kira Latit & Dipat Secara Automatik"):
                st.subheader("📐 Analisis Pengiraan Latit & Dipat")
                st.dataframe(df_latit_dipat, use_container_width=True, hide_index=True)
                c1, c2, c3 = st.columns(3)
                c1.metric("Jumlah Latit (Σdn)", f"{sum_latit:.4f} m")
                c2.metric("Jumlah Dipat (Σde)", f"{sum_dipat:.4f} m")
                c3.metric("Pertikaian Lurus", f"{misclosure:.4f} m")
                st.success(f"**Ketepatan Kerja:** 1 : {int(precision) if precision > 0 else 0}")

        with tab4:
            st.subheader("📥 Eksport ke QGIS / GIS")
            col_a, col_b = st.columns(2)
            with col_a:
                st.download_button("📂 Download Poligon (GeoJSON)", data=gdf_wgs84.to_json(), file_name=f"Lot_{no_lot}_Sempadan.geojson", mime="application/geo+json")
            with col_b:
                st.download_button("📍 Download Stesen (GeoJSON)", data=gdf_points_wgs84.to_json(), file_name=f"Lot_{no_lot}_Stesen.geojson", mime="application/geo+json")
    else:
        st.error("Ralat: Pastikan fail CSV mempunyai kolom 'E' and 'N'.")