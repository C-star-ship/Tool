import hashlib
import os
import uuid
import sys
import datetime
import requests
import time
import urllib.parse # Thư viện mã hóa link

# ==========================================
# 0. BẢNG MÀU CHO TERMUX (ANSI COLORS)
# ==========================================
class Mau:
    DO = '\033[91m'        # Red
    XANH_LA = '\033[92m'   # Green
    VANG = '\033[93m'      # Yellow
    XANH_LO = '\033[96m'   # Cyan
    HONG = '\033[95m'      # Magenta
    IN_DAM = '\033[1m'     # Bold
    RESET = '\033[0m'      # Reset

# ==========================================
# 1. CẤU HÌNH HỆ THỐNG CỦA BẠN
# ==========================================
SECRET_KEY = "XWORLD_TOOL" 
SECRET_LINK = "XWORLD_BIMAT" 

# THAY LINK NÀY THÀNH LINK BLOGGER CỦA BẠN
LINK_BLOGGER = "https://keyxworld.blogspot.com/2026/03/keyfree_11.html" 

# CẤU HÌNH LINK4M CHUẨN
URL_API_RUT_GON = "https://link4m.co/api-shorten/v2" 
API_TOKEN = "6976fd695e4d1128550c76d3" 

FILE_LUU_MA_MAY = "ma_may.txt"
FILE_LUU_KEY = "key_da_luu.txt" 

# ==========================================
# 2. CÁC HÀM XỬ LÝ CHÍNH
# ==========================================
def lay_hoac_tao_ma_may():
    if os.path.exists(FILE_LUU_MA_MAY):
        with open(FILE_LUU_MA_MAY, "r") as file:
            return file.read().strip()
    else:
        ma_moi = str(uuid.uuid4().hex)[:8].upper()
        with open(FILE_LUU_MA_MAY, "w") as file:
            file.write(ma_moi)
        return ma_moi

def tao_key_chuan(ma_may, ngay_hom_nay):
    chuoi_tho = f"{ma_may}-{ngay_hom_nay}-{SECRET_KEY}"
    hash_object = hashlib.sha256(chuoi_tho.encode('utf-8'))
    return hash_object.hexdigest()[:16].upper()

def tao_link_rut_gon(ma_may, ngay_hom_nay):
    chuoi_tao_token = f"{ma_may}-{ngay_hom_nay}-{SECRET_LINK}"
    token_bao_mat = hashlib.sha256(chuoi_tao_token.encode('utf-8')).hexdigest()[:10]
    link_goc = f"{LINK_BLOGGER}?id={ma_may}&token={token_bao_mat}"
    
    # Mã hóa link gốc theo chuẩn Link4M
    link_ma_hoa = urllib.parse.quote(link_goc)
    
    try:
        url_full = f"{URL_API_RUT_GON}?api={API_TOKEN}&url={link_ma_hoa}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; Termux) AppleWebKit/537.36"
        }
        
        phan_hoi_goc = requests.get(url_full, headers=headers, timeout=10)
        phan_hoi = phan_hoi_goc.json()
        
        if phan_hoi.get("status") == "success":
            return phan_hoi.get("shortenedUrl")
        else:
            print(f"\n{Mau.DO}[!] Link4M báo lỗi: {phan_hoi.get('message', 'Không xác định')}{Mau.RESET}")
            return link_goc
    except Exception as e:
        return link_goc 

def doc_key_da_luu():
    if os.path.exists(FILE_LUU_KEY):
        with open(FILE_LUU_KEY, "r") as file:
            return file.read().strip()
    return ""

def luu_key_moi(key):
    with open(FILE_LUU_KEY, "w") as file:
        file.write(key)

# ==========================================
# 3. LUỒNG CHẠY CHÍNH CỦA TOOL
# ==========================================
def chay_tool():
    # ĐÃ XÓA LỆNH CLEAR MÀN HÌNH Ở ĐÂY
    print(f"\n{Mau.XANH_LO}{Mau.IN_DAM}" + "━"*45)
    print("             🔐 VƯỢT LINK ĐỂ LẤY KEY🔐             ")
    print("━"*45 + f"{Mau.RESET}")

    ma_may = lay_hoac_tao_ma_may()
    ngay_hom_nay = datetime.datetime.now().strftime("%d%m%Y")
    key_chuan_hom_nay = tao_key_chuan(ma_may, ngay_hom_nay)
    
    key_trong_may = doc_key_da_luu()
    
    if key_trong_may == key_chuan_hom_nay:
        print(f"\n{Mau.XANH_LA}[✔] XÁC THỰC THÀNH CÔNG! (Dùng Key lưu trong máy){Mau.RESET}")
        print(f"{Mau.VANG}[!] Hạn sử dụng: Đến 23h59p hôm nay ({ngay_hom_nay[:2]}/{ngay_hom_nay[2:4]}/{ngay_hom_nay[4:]}){Mau.RESET}")
        time.sleep(1.5)
    else:
        print(f"\n{Mau.DO}[✘] Key của bạn đã hết hạn hoặc chưa được tạo!{Mau.RESET}")
        print(f"{Mau.HONG}[~] Đang tạo link lấy key mới, vui lòng đợi...{Mau.RESET}")
        
        link_lay_key = tao_link_rut_gon(ma_may, ngay_hom_nay)
        
        print(f"\n{Mau.XANH_LO}[*] Mã máy của bạn: {Mau.VANG}{Mau.IN_DAM}{ma_may}{Mau.RESET}")
        print(f"{Mau.XANH_LO}[*] Copy link dưới đây và dán vào trình duyệt:\n{Mau.RESET}")
        
        print(f"    {Mau.IN_DAM}{Mau.VANG}>> {link_lay_key} <<{Mau.RESET}\n")
        print(f"{Mau.XANH_LO}" + "━"*45 + f"{Mau.RESET}")
        
        key_nguoi_dung = input(f"{Mau.XANH_LA}👉 Nhập Key bạn vừa lấy vào đây: {Mau.RESET}").strip()
        
        if key_nguoi_dung == key_chuan_hom_nay:
            luu_key_moi(key_nguoi_dung)
            print(f"\n{Mau.XANH_LA}[✔] XÁC THỰC THÀNH CÔNG! Đã lưu Key vào máy.{Mau.RESET}")
            time.sleep(1)
        else:
            print(f"\n{Mau.DO}[✘] LỖI: Key không chính xác! Vui lòng chạy lại tool.{Mau.RESET}")
            sys.exit(0)

    # ========================================================
    # ĐÃ XÓA LỆNH CLEAR MÀN HÌNH Ở ĐÂY
    print(f"\n{Mau.XANH_LA}====== TOOL BẮT ĐẦU HOẠT ĐỘNG ======{Mau.RESET}")
    print(f"{Mau.HONG}[+] Đang tải dữ liệu server...{Mau.RESET}")
    
    # VIẾT CODE TOOL CỦA BẠN VÀO BÊN DƯỚI DÒNG NÀY
    # ...
    # ========================================================

# ==========================================
# 4. CHẠY VÀ BẢO VỆ CHƯƠNG TRÌNH (Bẫy lỗi)
# ==========================================
if __name__ == "__main__":
    try:
        chay_tool()
    except KeyboardInterrupt:
        print(f"\n\n{Mau.DO}[!] Bạn đã thoát chương trình.{Mau.RESET}")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n{Mau.DO}[!] Đã xảy ra lỗi không xác định! Vui lòng thử lại.{Mau.RESET}")
        sys.exit(1)
