import requests
from datetime import datetime, timedelta
import random
import time
import os
import json
import threading
import sys
from requests.exceptions import ConnectionError, Timeout, RequestException
import getpass

# ======== KONFIGURASI =========
BASE_URL = "https://naradaya.adhimix.web.id/"

# Username dan password akan diinput saat script dijalankan
USERNAME = ""
PASSWORD = ""

PAGI_START = (7, 45)    # 07:00
PAGI_END   = (8, 15)   # 07:45
SORE_START = (17, 10)  # 17:10
SORE_END   = (18, 00)  # 18:00

LOG_FILE = "absensi_log.txt"

# Status global untuk tunda absensi
TUNDA_ABSENSI = False
TANGGAL_TUNDA = None

# Konfigurasi retry dan timeout
MAX_RETRY = 540
RETRY_DELAY = 30  # detik
REQUEST_TIMEOUT = 30  # detik

# ======== FUNGSI INPUT KREDENSIAL =========
def input_kredensial():
    """Meminta input username dan password dari pengguna"""
    global USERNAME, PASSWORD
    
    print("=" * 50)
    print("BOT ABSENSI OTOMATIS - LOGIN")
    print("=" * 50)
    
    USERNAME = input("Masukkan Username: ").strip()
    
    # Gunakan getpass untuk menyembunyikan password saat diketik
    try:
        PASSWORD = getpass.getpass("Masukkan Password: ").strip()
    except:
        # Fallback jika getpass tidak tersedia
        PASSWORD = input("Masukkan Password: ").strip()
    
    if not USERNAME or not PASSWORD:
        print("[ERROR] Username dan password tidak boleh kosong!")
        sys.exit(1)
    
    print(f"\n[INFO] Login sebagai: {USERNAME}")
    print("[INFO] Memverifikasi kredensial...")
    
    # Verifikasi login
    if not verifikasi_login():
        print("[ERROR] Login gagal! Username atau password salah.")
        print("[ABORT] Program dihentikan.")
        sys.exit(1)
    
    print("[SUCCESS] Login berhasil diverifikasi!")
    print("=" * 50)
    print()

# ======== VERIFIKASI LOGIN =========
def verifikasi_login():
    """Verifikasi kredensial login ke server"""
    try:
        session = requests.Session()
        login_payload = {
            "login": USERNAME,
            "password": PASSWORD
        }
        
        login_url = BASE_URL + "login/confirm"
        res = session.post(login_url, data=login_payload, timeout=REQUEST_TIMEOUT)
        
        if "gagal" in res.text.lower():
            return False
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Tidak dapat terhubung ke server: {str(e)}")
        return False

# ======== FUNGSI RANDOM JAM =========
def random_jam(start_tuple, end_tuple):
    today = datetime.now().date()
    start_time = datetime.combine(today, datetime.min.time()).replace(hour=start_tuple[0], minute=start_tuple[1])
    end_time   = datetime.combine(today, datetime.min.time()).replace(hour=end_tuple[0], minute=end_tuple[1])

    delta_seconds = int((end_time - start_time).total_seconds())
    random_seconds = random.randint(0, delta_seconds)
    return start_time + timedelta(seconds=random_seconds)

# ======== SIMPAN LOG =========
def tulis_log(pesan):
    waktu = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    log_message = f"{waktu} {pesan}"
    
    # Tulis ke file dengan encoding UTF-8
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{log_message}\n")
    except Exception as e:
        # Fallback: tulis tanpa karakter khusus
        safe_message = log_message.encode('ascii', 'ignore').decode('ascii')
        with open(LOG_FILE, "a") as f:
            f.write(f"{safe_message}\n")
    
    print(log_message, flush=True)

# ======== CEK KONEKSI INTERNET =========
def cek_koneksi_internet():
    """Cek apakah ada koneksi internet"""
    try:
        # Test dengan Google DNS yang lebih reliable
        response = requests.get("https://8.8.8.8", timeout=5)
        return True
    except:
        try:
            # Backup test dengan cloudflare DNS
            response = requests.get("https://1.1.1.1", timeout=5)
            return True
        except:
            try:
                # Test dengan website utama
                response = requests.get(BASE_URL, timeout=10)
                return True
            except:
                return False

# ======== FUNGSI RETRY DENGAN ERROR HANDLING =========
def execute_with_retry(func, *args, **kwargs):
    """Eksekusi fungsi dengan retry otomatis jika ada error jaringan"""
    for attempt in range(MAX_RETRY):
        try:
            return func(*args, **kwargs)
        except (ConnectionError, Timeout, RequestException) as e:
            error_msg = str(e)
            if "NameResolutionError" in error_msg or "No address associated with hostname" in error_msg:
                tulis_log(f"[NETWORK ERROR] Tidak dapat resolve hostname (attempt {attempt + 1}/{MAX_RETRY})")
            elif "ConnectionError" in error_msg:
                tulis_log(f"[NETWORK ERROR] Koneksi gagal (attempt {attempt + 1}/{MAX_RETRY})")
            elif "Timeout" in error_msg:
                tulis_log(f"[NETWORK ERROR] Request timeout (attempt {attempt + 1}/{MAX_RETRY})")
            else:
                tulis_log(f"[NETWORK ERROR] {error_msg} (attempt {attempt + 1}/{MAX_RETRY})")
            
            if attempt < MAX_RETRY - 1:
                tulis_log(f"[RETRY] Menunggu {RETRY_DELAY} detik sebelum retry...")
                time.sleep(RETRY_DELAY)
            else:
                tulis_log(f"[FAILED] Gagal setelah {MAX_RETRY} percobaan")
                return None
        except Exception as e:
            tulis_log(f"[UNEXPECTED ERROR] {str(e)} (attempt {attempt + 1}/{MAX_RETRY})")
            if attempt < MAX_RETRY - 1:
                time.sleep(RETRY_DELAY)
            else:
                return None
    return None

# ======== FUNGSI INPUT TUNDA =========
def input_listener():
    """Thread untuk mendengar input pengguna"""
    global TUNDA_ABSENSI, TANGGAL_TUNDA
    
    while True:
        try:
            user_input = input().strip().lower()
            
            if user_input == "tunda":
                hari_ini = datetime.now().date()
                TANGGAL_TUNDA = hari_ini
                TUNDA_ABSENSI = True
                tulis_log(f"[TUNDA] Absensi hari ini ({hari_ini}) ditunda!")
                tulis_log("[INFO] Ketik 'status' untuk melihat status tunda, atau 'batal' untuk membatalkan tunda.")
                
            elif user_input == "status":
                if TUNDA_ABSENSI and TANGGAL_TUNDA:
                    tulis_log(f"[STATUS] Absensi ditunda untuk tanggal: {TANGGAL_TUNDA}")
                else:
                    tulis_log("[STATUS] Tidak ada absensi yang ditunda")
                    
            elif user_input == "batal":
                if TUNDA_ABSENSI:
                    TUNDA_ABSENSI = False
                    TANGGAL_TUNDA = None
                    tulis_log("[BATAL] Tunda absensi dibatalkan!")
                else:
                    tulis_log("[INFO] Tidak ada tunda absensi yang aktif")
                    
            elif user_input == "test":
                tulis_log("[TEST] Testing koneksi internet...")
                if cek_koneksi_internet():
                    tulis_log("[TEST] ✓ Koneksi internet OK")
                else:
                    tulis_log("[TEST] ✗ Tidak ada koneksi internet")
                    
            elif user_input == "help":
                tulis_log("[HELP] Perintah yang tersedia:")
                tulis_log("  - tunda : Tunda absensi hari ini")
                tulis_log("  - status : Lihat status tunda")
                tulis_log("  - batal : Batalkan tunda absensi")
                tulis_log("  - test : Test koneksi internet")
                tulis_log("  - help : Tampilkan bantuan ini")
                tulis_log("  - exit : Keluar dari program")
                
            elif user_input == "exit":
                tulis_log("[EXIT] Program dihentikan oleh pengguna")
                os._exit(0)
                
        except (EOFError, KeyboardInterrupt):
            break
        except Exception as e:
            tulis_log(f"[ERROR] Error pada input listener: {str(e)}")

def cek_tunda_absensi():
    """Cek apakah hari ini absensi ditunda"""
    global TUNDA_ABSENSI, TANGGAL_TUNDA
    
    hari_ini = datetime.now().date()
    
    if TUNDA_ABSENSI and TANGGAL_TUNDA == hari_ini:
        return True
    
    # Reset tunda jika tanggalnya sudah lewat
    if TANGGAL_TUNDA and hari_ini > TANGGAL_TUNDA:
        TUNDA_ABSENSI = False
        TANGGAL_TUNDA = None
        tulis_log("[INFO] Reset status tunda karena tanggal sudah lewat")
    
    return False

# ======== CEK STATUS ABSENSI HARI INI =========
def cek_status_absensi():
    """
    Mengecek status absensi hari ini dari API
    Return: dict dengan status jam_datang dan jam_pulang
    """
    def _cek_status():
        session = requests.Session()
        
        # Login dulu
        login_payload = {
            "login": USERNAME,
            "password": PASSWORD
        }
        login_url = BASE_URL + "login/confirm"
        res = session.post(login_url, data=login_payload, timeout=REQUEST_TIMEOUT)
        
        if "gagal" in res.text.lower():
            tulis_log("[ERROR] Login gagal saat cek status absensi")
            return None
            
        # Ambil data history absensi
        history_url = BASE_URL + "absensi/history/kemarin"
        history_res = session.get(history_url, timeout=REQUEST_TIMEOUT)
        
        if history_res.status_code != 200:
            tulis_log(f"[ERROR] Gagal mengambil data history: {history_res.status_code}")
            return None
            
        data = json.loads(history_res.text)
        hari_ini = datetime.now().strftime("%Y-%m-%d")
        
        # Cari data hari ini
        for record in data:
            tanggal_record = record.get('tanggal', '').split(' ')[0]  # Ambil tanggal saja
            if tanggal_record == hari_ini:
                tulis_log(f"[INFO] Data absensi hari ini: jam_datang={record.get('jam_datang')}, jam_pulang={record.get('jam_pulang')}")
                return {
                    'jam_datang': record.get('jam_datang'),
                    'jam_pulang': record.get('jam_pulang')
                }
        
        # Jika tidak ada data hari ini
        tulis_log("[INFO] Belum ada data absensi untuk hari ini")
        return {'jam_datang': None, 'jam_pulang': None}
    
    return execute_with_retry(_cek_status)

# ======== LOGIN & ABSEN =========
def login_dan_absen(sesi):
    def _login_dan_absen():
        session = requests.Session()
        login_payload = {
            "login": USERNAME,
            "password": PASSWORD
        }

        login_url = BASE_URL + "login/confirm"
        res = session.post(login_url, data=login_payload, timeout=REQUEST_TIMEOUT)

        if "gagal" in res.text.lower():
            tulis_log(f"[ERROR] Login gagal untuk sesi {sesi}")
            return False

        tulis_log(f"[SUCCESS] Login sukses untuk sesi {sesi}")

        absen_url = BASE_URL + "absensi/hit"
        absen_payload = {}
        absen_res = session.post(absen_url, data=absen_payload, timeout=REQUEST_TIMEOUT)

        tulis_log(f"[RESPONSE] Response absensi ({sesi}): {absen_res.text.strip()}")
        return True
    
    result = execute_with_retry(_login_dan_absen)
    return result if result is not None else False

# ======== WAIT WITH NETWORK CHECK =========
def wait_with_network_check(target_time, check_interval=300):
    """
    Menunggu sampai waktu target dengan cek jaringan berkala
    check_interval: interval cek jaringan dalam detik (default 5 menit)
    """
    last_network_check = 0
    
    while datetime.now() < target_time:
        if cek_tunda_absensi():
            tulis_log("[TUNDA] Absensi ditunda saat menunggu")
            return False
            
        current_time = time.time()
        
        # Cek jaringan setiap check_interval
        if current_time - last_network_check >= check_interval:
            if not cek_koneksi_internet():
                tulis_log("[WARNING] Tidak ada koneksi internet, tetap menunggu...")
            last_network_check = current_time
            
        time.sleep(30)
    
    return True

# ======== PROSES ABSENSI PER HARI =========
def absensi_harian():
    # Cek apakah absensi hari ini ditunda
    if cek_tunda_absensi():
        tulis_log("[TUNDA] Absensi hari ini ditunda. Skip absensi.")
        return
        
    hari_ini = datetime.now().strftime("%A").lower()
    hari_allowed = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]

    if hari_ini not in hari_allowed:
        tulis_log(f"[SKIP] Hari ini ({hari_ini.capitalize()}) bukan jadwal absensi.")
        return

    tulis_log(f"[INFO] Hari ini: {hari_ini.capitalize()}")
    
    # Cek koneksi internet dulu
    if not cek_koneksi_internet():
        tulis_log("[WARNING] Tidak ada koneksi internet, akan retry nanti...")
        return
    
    # Cek status absensi saat ini
    status = cek_status_absensi()
    if status is None:
        tulis_log("[ERROR] Tidak dapat mengecek status absensi karena masalah jaringan, skip hari ini")
        return
    
    jam_datang = status.get('jam_datang')
    jam_pulang = status.get('jam_pulang')
    
    waktu_pagi = random_jam(PAGI_START, PAGI_END)
    waktu_sore = random_jam(SORE_START, SORE_END)
    
    tulis_log(f"[SCHEDULE] Jadwal absen pagi: {waktu_pagi.strftime('%H:%M:%S')}")
    tulis_log(f"[SCHEDULE] Jadwal absen sore: {waktu_sore.strftime('%H:%M:%S')}")

    # Logika berdasarkan status absensi
    if jam_datang is None:
        # Belum absen masuk, tunggu jadwal pagi
        tulis_log("[WAITING] Status: Belum absen masuk, menunggu waktu absen pagi...")
        if not wait_with_network_check(waktu_pagi):
            return
        
        if cek_tunda_absensi():  # Cek sekali lagi sebelum absen
            tulis_log("[TUNDA] Absensi ditunda sebelum eksekusi pagi")
            return
            
        tulis_log("[ACTION] Waktu absen pagi tiba!")
        if not login_dan_absen("Pagi"):
            tulis_log("[FAILED] Gagal absen pagi karena masalah jaringan")
            return
        
        # Setelah absen pagi, tunggu waktu sore
        tulis_log("[WAITING] Absen pagi selesai, menunggu waktu absen sore...")
        if not wait_with_network_check(waktu_sore):
            return
        
        if cek_tunda_absensi():  # Cek sekali lagi sebelum absen
            tulis_log("[TUNDA] Absensi sore ditunda sebelum eksekusi")
            return
            
        tulis_log("[ACTION] Waktu absen sore tiba!")
        if not login_dan_absen("Sore"):
            tulis_log("[FAILED] Gagal absen sore karena masalah jaringan")
            return
        
    elif jam_datang is not None and jam_pulang is None:
        # Sudah absen masuk, belum absen pulang
        tulis_log(f"[WAITING] Status: Sudah absen masuk ({jam_datang}), belum absen pulang. Menunggu waktu absen sore...")
        if not wait_with_network_check(waktu_sore):
            return
        
        if cek_tunda_absensi():  # Cek sekali lagi sebelum absen
            tulis_log("[TUNDA] Absensi sore ditunda sebelum eksekusi")
            return
            
        tulis_log("[ACTION] Waktu absen sore tiba!")
        if not login_dan_absen("Sore"):
            tulis_log("[FAILED] Gagal absen sore karena masalah jaringan")
            return
        
    else:
        # Sudah absen masuk dan pulang
        tulis_log(f"[COMPLETE] Sudah absen lengkap hari ini - Masuk: {jam_datang}, Pulang: {jam_pulang}")
        return

    tulis_log("[SUCCESS] Semua absensi hari ini selesai.")

# ======== LOOP OTOMATIS TIAP HARI =========
def main():
    # Input kredensial di awal
    input_kredensial()
    
    tulis_log("[START] Bot absensi otomatis dimulai.")
    tulis_log(f"[INFO] Login sebagai user: {USERNAME}")
    tulis_log("[INFO] Perintah yang tersedia:")
    tulis_log("  - Ketik 'tunda' untuk menunda absensi hari ini")
    tulis_log("  - Ketik 'status' untuk melihat status tunda") 
    tulis_log("  - Ketik 'batal' untuk membatalkan tunda")
    tulis_log("  - Ketik 'test' untuk test koneksi internet")
    tulis_log("  - Ketik 'help' untuk bantuan")
    tulis_log("  - Ketik 'exit' untuk keluar")
    tulis_log("[INFO] ========================================")
    
    # Jalankan input listener di thread terpisah
    input_thread = threading.Thread(target=input_listener, daemon=True)
    input_thread.start()
    
    while True:
        try:
            absensi_harian()
        except Exception as e:
            tulis_log(f"[CRITICAL ERROR] Error tidak terduga: {str(e)}")
            tulis_log("[INFO] Melanjutkan ke hari berikutnya...")

        # Tunggu sampai hari berikutnya jam 00:05
        besok = datetime.now().date() + timedelta(days=1)
        target = datetime.combine(besok, datetime.min.time()) + timedelta(minutes=5)
        tunggu = (target - datetime.now()).total_seconds()

        tulis_log(f"[WAIT] Menunggu hari berikutnya ({tunggu/3600:.2f} jam)")
        time.sleep(max(0, tunggu))

if __name__ == "__main__":
    main()
