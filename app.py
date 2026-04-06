import streamlit as st
import requests
import pandas as pd

# Konfigurasi Tampilan Halaman
st.set_page_config(page_title="Hotel Leads Scraper", layout="wide")

st.title("Mesin Pencari Prospek Hotel B2B")
st.markdown("Masukkan nama kota untuk menarik data hotel (Nama, Alamat, Telepon, Bintang) secara otomatis.")

# Fungsi Penarik Data
def cari_hotel_osm(kota):
    overpass_url = "http://overpass-api.de/api/interpreter"
    
    overpass_query = f"""
    [out:json][timeout:90];
    area[name~"{kota}", i]->.searchArea;
    (
      node["tourism"="hotel"](area.searchArea);
      way["tourism"="hotel"](area.searchArea);
      relation["tourism"="hotel"](area.searchArea);
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
if st.button("🔍 Cari Data Hotel"):
    if target_kota.strip() == "":
        st.warning("Silakan ketik nama kota terlebih dahulu!")
    else:
        # ANIMASI LOADING (Sistem akan menahan proses di sini sampai data selesai)
        with st.spinner(f"Sedang menarik seluruh data hotel di area {target_kota.upper()}... Mohon tunggu sampai selesai."):
            hasil_df = cari_hotel_osm(target_kota)
        
        # PROSES SETELAH LOADING SELESAI
        if hasil_df is not None and not hasil_df.empty:
            st.success(f"🎉 BERHASIL! Menemukan {len(hasil_df)} prospek hotel.")
            
            # Tampilkan Tabel
            st.dataframe(hasil_df, use_container_width=True)
            
            # Konversi data ke CSV untuk di-download
            csv = hasil_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8')
            
            # TOMBOL DOWNLOAD HANYA MUNCUL DI SINI (Setelah semua proses di atas selesai)
            st.download_button(
                label="Download Data (CSV / Excel)",
                data=csv,
                file_name=f"Prospek_Hotel_{target_kota.replace(' ', '_')}.csv",
                mime="text/csv"
            )
        else:
            st.error(f"Maaf, tidak menemukan data hotel untuk kota: {target_kota}. Coba gunakan kata kunci lain.")
