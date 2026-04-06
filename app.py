import streamlit as st
import requests
import pandas as pd

# Konfigurasi Tampilan Halaman
st.set_page_config(page_title="Hotel Leads Scraper", layout="wide", initial_sidebar_state="expanded")

st.title("🏨 Mesin Pencari Potensi Hotel")
st.markdown("Masukkan nama kota untuk menarik data hotel beserta koordinatnya secara otomatis dari OpenStreetMap.")

# Fungsi Penarik Data
def cari_hotel_osm(kota):
    overpass_url = "http://overpass-api.de/api/interpreter"
    
    overpass_query = f"""
    [out:json][timeout:90];
    area[name~"^{kota}$", i]->.searchArea; 
    (
      node["tourism"="hotel"](area.searchArea);
      way["tourism"="hotel"](area.searchArea);
      relation["tourism"="hotel"](area.searchArea);
    );
    out center;
    """
    
    headers = {
        'User-Agent': 'HotelLeadsScraperBot/1.0 (Contact: your_email@example.com)' # Etika scraping: berikan user-agent yang jelas
    }
    
    try:
        response = requests.get(overpass_url, params={'data': overpass_query}, headers=headers, timeout=95)
        
        # Handle Rate Limiting dari Overpass
        if response.status_code == 429:
            return None, "Server Overpass sibuk (Too Many Requests). Silakan coba beberapa menit lagi."
        elif response.status_code != 200:
            return None, f"Error Server: {response.status_code}"
            
        data = response.json()
        daftar_hotel = []
        
        for element in data.get('elements', []):
            tags = element.get('tags', {})
            
            nama = tags.get('name', '-')
            if nama == '-': continue
                
            # Mengambil alamat yang lebih lengkap
            jalan = tags.get('addr:street', '')
            nomor = tags.get('addr:housenumber', '')
            kode_pos = tags.get('addr:postcode', '')
            alamat_full = tags.get('addr:full', '')
            
            if alamat_full:
                alamat_lengkap = alamat_full
            else:
                alamat_lengkap = f"{jalan} {nomor} {kode_pos}".strip()
            
            if not alamat_lengkap: alamat_lengkap = "-"
                
            telepon = tags.get('phone', tags.get('contact:phone', '-')) # Cek juga contact:phone
            website = tags.get('website', tags.get('contact:website', '-'))
            
            # Normalisasi Bintang
            bintang = tags.get('stars', '-')
            if isinstance(bintang, str) and 'star' in bintang.lower():
                 bintang = bintang.lower().replace('stars', '').replace('star', '').strip()
            
            # Ambil Latitude & Longitude (PENTING)
            lat = element.get('lat') or element.get('center', {}).get('lat')
            lon = element.get('lon') or element.get('center', {}).get('lon')
            
            daftar_hotel.append({
                "Nama Hotel": nama,
                "Kota": kota.upper(),
                "Bintang": bintang,
                "Alamat": alamat_lengkap,
                "Telepon": telepon,
                "Website": website,
                "lat": lat,
                "lon": lon
            })
            
        df = pd.DataFrame(daftar_hotel)
        if not df.empty:
            # Hapus duplikat berdasarkan Nama DAN Koordinat (Menyelamatkan cabang hotel)
            df = df.drop_duplicates(subset=['Nama Hotel', 'lat', 'lon']).reset_index(drop=True)
            
        return df, "Success"
        
    except requests.exceptions.Timeout:
        return None, "Pencarian terlalu lama (Timeout). Coba kota yang lebih spesifik."
    except Exception as e:
        return None, f"Terjadi kesalahan sistem: {str(e)}"

# ==========================================
# TAMPILAN USER INTERFACE (UI)
# ==========================================

st.markdown("---")
# Kolom Input
target_kota = st.text_input("Ketik Nama Kota (Contoh: Jakarta Selatan, Denpasar, Bandung):", placeholder="Ketik di sini...")

# Tombol Eksekusi
if st.button("Cari Data Hotel", type="primary"):
    if target_kota.strip() == "":
        st.warning("Silakan ketik nama kota terlebih dahulu!")
    else:
        with st.spinner(f"Mencari seluruh data hotel di {target_kota.upper()}..."):
            hasil_df, status = cari_hotel_osm(target_kota)
        
        if hasil_df is not None and not hasil_df.empty:
            st.success(f"Berhasil menarik data dari {target_kota.upper()}!")
            
            # 1. Tampilkan Metrik Rangkuman
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Hotel Ditemukan", f"{len(hasil_df)} Properti")
            col2.metric("Memiliki No. Telepon", f"{len(hasil_df[hasil_df['Telepon'] != '-'])}")
            col3.metric("Memiliki Website", f"{len(hasil_df[hasil_df['Website'] != '-'])}")
            
            st.markdown("---")
            
            # Membuat Tab untuk Tabel dan Peta agar tidak kepanjangan ke bawah
            tab_tabel, tab_peta = st.tabs(["📋 Tabel Data Leads", "🗺️ Peta Persebaran (Indonesia)"])
            
            # ========================
            # ISI TAB 1: TABEL DATA
            # ========================
            with tab_tabel:
                # Sembunyikan kolom lat/lon di layar agar rapi
                st.dataframe(hasil_df.drop(columns=['lat', 'lon']), use_container_width=True)
                
                # Konversi data ke CSV
                csv = hasil_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8')
                
                # Tombol Download
                st.download_button(
                    label="📥 Download Full Data (CSV)",
                    data=csv,
                    file_name=f"Leads_Hotel_{target_kota.replace(' ', '_')}.csv",
                    mime="text/csv"
                )

            # ========================
            # ISI TAB 2: PETA (FOKUS INDONESIA)
            # ========================
            with tab_peta:
                # Filter khusus koordinat yang valid dan masuk akal
                df_map = hasil_df.dropna(subset=['lat', 'lon']).copy()
                
                # Pastikan format datanya angka (numeric)
                df_map['lat'] = pd.to_numeric(df_map['lat'], errors='coerce')
                df_map['lon'] = pd.to_numeric(df_map['lon'], errors='coerce')
                df_map = df_map.dropna(subset=['lat', 'lon'])
                
                # Filter Bounding Box Indonesia (Lat: -11 s/d +6, Lon: 95 s/d 141)
                df_indo = df_map[
                    (df_map['lat'] >= -11.0) & (df_map['lat'] <= 6.0) &
                    (df_map['lon'] >= 95.0) & (df_map['lon'] <= 141.0)
                ]
                
                if not df_indo.empty:
                    st.map(df_indo)
                else:
                    st.warning("Tidak ada data hotel yang memiliki titik koordinat valid di peta.")

        else:
            if status == "Success":
                st.error(f"Data tidak ditemukan untuk kota: '{target_kota}'. Pastikan penulisan kota benar.")
            else:
                st.error(status)
