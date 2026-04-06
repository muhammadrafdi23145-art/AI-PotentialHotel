import streamlit as st
import requests
import pandas as pd
import re
import io
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from bs4 import BeautifulSoup

# Konfigurasi Tampilan Halaman
st.set_page_config(page_title="Hotel Leads Pro v3", layout="wide")

# Inisialisasi Geocoder (Opsi 2)
geolocator = Nominatim(user_agent="hotel_leads_pro_v3")
reverse_geocode = RateLimiter(geolocator.reverse, min_delay_seconds=1)

# ==========================================
# FUNGSI PENDUKUNG (OPSI 3: SCRAPER)
# ==========================================
def scrape_contact_info(url):
    """Mencoba mencari Email dan WA dari website hotel"""
    if not url or url == "-":
        return "-", "-"
    
    # Tambahkan http jika tidak ada
    if not url.startswith('http'):
        url = 'http://' + url

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text()

        # Regex untuk Email
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, text)
        found_email = emails[0] if emails else "-"

        # Regex sederhana untuk potensi nomor WA (Indo: 08... atau 628...)
        wa_pattern = r'(\+62|62|0)8[1-9][0-9]{7,10}'
        was = re.findall(wa_pattern, text)
        found_wa = was[0] if was else "-"

        return found_email, found_wa
    except:
        return "-", "-"

# ==========================================
# FUNGSI UTAMA PENARIK DATA (OSM)
# ==========================================
def cari_hotel_osm(kota):
    overpass_url = "http://overpass-api.de/api/interpreter"
    overpass_query = f"""
    [out:json][timeout:180];
    area[name~"^{kota}$", i]->.searchArea; 
    (
      node["tourism"="hotel"](area.searchArea);
      way["tourism"="hotel"](area.searchArea);
      relation["tourism"="hotel"](area.searchArea);
    );
    out center;
    """
    try:
        response = requests.get(overpass_url, params={'data': overpass_query}, timeout=200)
        if response.status_code != 200:
            return None, f"Error Server: {response.status_code}"
            
        data = response.json()
        daftar_hotel = []
        for element in data.get('elements', []):
            tags = element.get('tags', {})
            nama = tags.get('name', '-')
            if nama == '-': continue
            
            # Alamat dasar
            jalan = tags.get('addr:street', '')
            nomor = tags.get('addr:housenumber', '')
            alamat_osm = f"{jalan} {nomor}".strip() or "-"
            
            lat = element.get('lat') or element.get('center', {}).get('lat')
            lon = element.get('lon') or element.get('center', {}).get('lon')
            
            daftar_hotel.append({
                "Nama Hotel": nama,
                "Bintang": tags.get('stars', '-'),
                "Alamat OSM": alamat_osm,
                "Telepon": tags.get('phone', tags.get('contact:phone', '-')),
                "Website": tags.get('website', '-'),
                "lat": lat, "lon": lon
            })
        
        df = pd.DataFrame(daftar_hotel)
        if not df.empty:
            df = df.drop_duplicates(subset=['Nama Hotel', 'lat', 'lon']).reset_index(drop=True)
        return df, "Success"
    except Exception as e:
        return None, str(e)

# ==========================================
# UI STREAMLIT
# ==========================================
st.title("🏨 Hotel Leads Scraper Ultra V3")
st.markdown("Mesin pencari leads hotel dengan fitur **Auto-Address Fill** dan **Website Contact Scraper**.")

# Sidebar Settings
st.sidebar.header("🔧 Pengaturan Lead Gen")
opsi_geocoding = st.sidebar.checkbox("Lengkapi Alamat (Reverse Geocoding)", value=False, help="Mengisi alamat otomatis jika data OSM kosong. Proses lebih lama.")
opsi_scraping = st.sidebar.checkbox("Scrape Email/WA dari Website", value=False, help="Mencoba mengunjungi website hotel untuk cari kontak.")

target_kota = st.text_input("Ketik Nama Kota/Kabupaten:")

if st.button("Mulai Tarik Data", type="primary"):
    if target_kota:
        with st.spinner(f"Tahap 1: Menarik data dasar dari {target_kota}..."):
            df, status = cari_hotel_osm(target_kota)
        
        if df is not None and not df.empty:
            
            # --- PROSES OPSI 2: REVERSE GEOCODING ---
            if opsi_geocoding:
                st.info("Tahap 2: Melengkapi alamat yang kosong via Koordinat...")
                progress_bar = st.progress(0)
                for i, row in df.iterrows():
                    if row['Alamat OSM'] == "-":
                        try:
                            location = geolocator.reverse((row['lat'], row['lon']), timeout=3)
                            if location:
                                df.at[i, 'Alamat OSM'] = location.address
                        except:
                            continue
                    progress_bar.progress((i + 1) / len(df))

            # --- PROSES OPSI 3: WEBSITE SCRAPING ---
            if opsi_scraping:
                st.info("Tahap 3: Mencari Email & WA di website hotel (Jika ada)...")
                emails, whatsapps = [], []
                progress_bar_web = st.progress(0)
                for i, row in df.iterrows():
                    email, wa = scrape_contact_info(row['Website'])
                    emails.append(email)
                    whatsapps.append(wa)
                    progress_bar_web.progress((i + 1) / len(df))
                df['Email (Scraped)'] = emails
                df['WA (Scraped)'] = whatsapps

            # --- TAMPILAN HASIL ---
            st.success(f"Selesai! Ditemukan {len(df)} Leads.")
            
            tab1, tab2 = st.tabs(["📋 Data Leads", "🗺️ Peta Lokasi"])
            
            with tab1:
                st.dataframe(df.drop(columns=['lat', 'lon']), use_container_width=True)
                
                # --- OPSI 4: EXPORT EXCEL & CSV ---
                col_dl1, col_dl2 = st.columns(2)
                
                # CSV
                csv = df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8')
                col_dl1.download_button("📥 Download CSV", data=csv, file_name=f"Leads_{target_kota}.csv", mime="text/csv")
                
                # EXCEL (XLSX)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Leads Hotel')
                excel_data = output.getvalue()
                col_dl2.download_button("📊 Download EXCEL (.xlsx)", data=excel_data, file_name=f"Leads_{target_kota}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            with tab2:
                df_map = df.dropna(subset=['lat', 'lon'])
                st.map(df_map)
        else:
            st.error(f"Gagal: {status}")
