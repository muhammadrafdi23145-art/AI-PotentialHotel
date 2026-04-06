import streamlit as st
import requests
import pandas as pd

# Konfigurasi Tampilan Halaman
st.set_page_config(page_title="Hotel Leads Scraper", layout="wide")

st.title("Mesin Pencari Data Potensial Hotel Murni")
st.markdown("Masukkan nama kota untuk menarik data khusus hotel (Nama, Alamat, Telepon, Bintang). Data Kost, Homestay, Villa, dan Guest House akan disaring otomatis.")

# Fungsi Penarik Data
def cari_hotel_osm(kota):
    overpass_url = "http://overpass-api.de/api/interpreter"
    
    # FILTER NEGATIF: Kata-kata ini akan diabaikan dari hasil pencarian
    kata_buang = "Kost|Kos |Homestay|Villa|Hostel|Guest House|Guesthouse|Apartment|Apartemen|Camp|Glamping|Penginapan"
    
    overpass_query = f"""
    [out:json][timeout:90];
    area[name~"{kota}", i]->.searchArea;
    (
      node["tourism"="hotel"]["name"!~"{kata_buang}", i](area.searchArea);
      way["tourism"="hotel"]["name"!~"{kata_buang}", i](area.searchArea);
      relation["tourism"="hotel"]["name"!~"{kata_buang}", i](area.searchArea);
    );
    out center;
    """
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(overpass_url, params={'data': overpass_query}, headers=headers)
        if response.status_code != 200:
            return None
            
        data = response.json()
        daftar_hotel = []
        
        for element in data.get('elements', []):
            tags = element.get('tags', {})
            
            nama = tags.get('name', '-')
            if nama == '-': continue
                
            # FILTER GANDA DI PYTHON: Untuk memastikan tidak ada data non-hotel yang lolos
            nama_lower = nama.lower()
            if any(kata in nama_lower for kata in ['kost', 'kos ', 'homestay', 'villa', 'hostel', 'guest house', 'guesthouse', 'penginapan', 'apartemen', 'apartment']):
                continue
                
            jalan = tags.get('addr:street', '')
            nomor = tags.get('addr:housenumber', '')
            alamat_lengkap = f"{jalan} {nomor}".strip()
            if alamat_lengkap == "": alamat_lengkap = "-"
                
            telepon = tags.get('phone', '-')
            website = tags.get('website', '-')
            
            bintang = tags.get('stars', '-')
            if bintang != '-' and 'star' in bintang.lower():
                 bintang = bintang.lower().replace('stars', '').replace('star', '').strip()
            
            daftar_hotel.append({
                "Nama Hotel": nama,
                "Kota": kota.upper(),
                "Bintang": bintang,
                "Alamat": alamat_lengkap,
                "Telepon": telepon,
                "Website": website
            })
            
        df = pd.DataFrame(daftar_hotel)
        if not df.empty:
            df = df.drop_duplicates(subset=['Nama Hotel']).reset_index(drop=True)
        return df
        
    except Exception as e:
        return None

# ==========================================
# TAMPILAN USER INTERFACE (UI)
# ==========================================

# Kolom Input
target_kota = st.text_input("Ketik Nama Kota (Contoh: Jakarta Selatan, Denpasar, Bandung):")

# Tombol Eksekusi
if st.button("Cari Data Hotel"):
    if target_kota.strip() == "":
        st.warning("Silakan ketik nama kota terlebih dahulu!")
    else:
        # ANIMASI LOADING
        with st.spinner(f"Sedang menarik dan menyaring data hotel murni di area {target_kota.upper()}... Mohon tunggu sampai selesai."):
            hasil_df = cari_hotel_osm(target_kota)
        
        # PROSES SETELAH LOADING SELESAI
        if hasil_df is not None and not hasil_df.empty:
            st.success(f"BERHASIL! Menemukan {len(hasil_df)} prospek hotel (non-villa/homestay).")
            
            # Tampilkan Tabel
            st.dataframe(hasil_df, use_container_width=True)
            
            # Konversi data ke CSV untuk di-download
            csv = hasil_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8')
            
            # TOMBOL DOWNLOAD
            st.download_button(
                label="Download Data (CSV / Excel)",
                data=csv,
                file_name=f"Prospek_Hotel_Murni_{target_kota.replace(' ', '_')}.csv",
                mime="text/csv"
            )
        else:
            st.error(f"Maaf, tidak menemukan data hotel untuk kota: {target_kota}. Coba gunakan kata kunci lain.")
