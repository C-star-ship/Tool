import os
import sys
import json
import time
import hashlib
import platform
import subprocess
import logging
from typing import Dict, List, Any
import concurrent.futures
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

# ==========================================
# CẤU HÌNH HỆ THỐNG LICENSE CHUẨN SHOPVIETX
# ==========================================
SERVER_URL = "https://shopvietx.io.vn/api/license"
KEY_FILE_PATH = os.path.join(os.path.expanduser("~"), ".matrix_sms_key")
TOOL_NAME = "FB Auto Tool"  # Sửa lại tên này nếu server bạn đặt tên khác

# Cấu hình màu sắc hiển thị chuyên nghiệp trên Termux/PE
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    R = Fore.RED
    G = Fore.GREEN
    Y = Fore.YELLOW
    B = Fore.CYAN
    W = Fore.WHITE
    RESET = Style.RESET_ALL
except:
    R = G = Y = B = W = RESET = ""

# ==========================================
# CẤU HÌNH LOGGING GỌN GÀNG 
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="[%H:%M:%S]",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("MatrixCloudEngine")

class CloudTestingEngine:
    def __init__(self):
        self.session = requests.Session()
        self.timeout = 7 
        self.init_session_policy()
        self.api_database = self.load_apis_from_memory()

    def init_session_policy(self) -> None:
        retries = Retry(
            total=1,
            backoff_factor=0.1,
            status_forcelist=[500, 502, 503, 504],
            raise_on_status=False
        )
        adapter = HTTPAdapter(pool_connections=100, pool_maxsize=100, max_retries=retries)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers.update({
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        })

    def load_apis_from_memory(self) -> Dict[str, List[Any]]:
        if 'IN_MEMORY_DB' in globals():
            return globals()['IN_MEMORY_DB']
        logger.error(f"{R}[!] Lỗi nghiêm trọng: Không tìm thấy cơ sở dữ liệu API trong RAM!{RESET}")
        return {"sms_endpoints": [], "call_endpoints": []}

    def sync_ivr_cookies(self, phone: str) -> None:
        init_url = "https://lk.vayxanh.com/"
        params = {"phone": phone, "amount": "2000000", "term": "7"}
        try:
            self.session.get(init_url, params=params, timeout=self.timeout)
        except Exception:
            pass

    def execute_request_worker(self, api: Dict[str, Any], phone: str) -> bool:
        name = api.get("name", "Dịch vụ ẩn danh")
        url = api.get("url")
        method = api.get("method", "POST").upper()
        headers = api.get("headers", {})
        
        phone_no_zero = phone[1:] if phone.startswith("0") else phone
        phone_84 = "84" + phone_no_zero
        
        raw_template = api.get("payload_template", "")
        formatted_payload = raw_template.replace("{phone}", phone)\
                                         .replace("{phone_no_zero}", phone_no_zero)\
                                         .replace("{phone_84}", phone_84)

        try:
            if api.get("is_json"):
                request_kwargs = {"json": json.loads(formatted_payload)}
            else:
                request_kwargs = {"data": formatted_payload}

            logger.info(f"{B}[▶ RUNNING] Đang kiểm thử cổng: {name}{RESET}")

            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                timeout=self.timeout,
                **request_kwargs
            )
            
            if response.status_code == 200:
                logger.info(f"  └── {G}[✓ SUCCESS] {name} thành công.{RESET}")
                return True
            else:
                logger.info(f"  └── {R}[✕ FAILED] {name} lỗi (Mã: {response.status_code}).{RESET}")
                return False

        except requests.exceptions.Timeout:
            logger.info(f"  └── {Y}[🕒 TIMEOUT] {name} quá hạn phản hồi.{RESET}")
        except Exception:
            logger.info(f"  └── {R}[✕ ERROR] Không thể kết nối tới {name}.{RESET}")
        
        return False

    def trigger_sms_suite(self, phone: str) -> None:
        sms_list = self.api_database.get("sms_endpoints", [])
        if not sms_list:
            print(f"{R}[-] Danh sách API trống hoặc nạp thất bại.{RESET}")
            return

        print(f"\n{G}[+] Khởi chạy Suite SMS: Đang thực thi {len(sms_list)} dịch vụ...{RESET}")
        print("-" * 55)
        with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
            futures = [executor.submit(self.execute_request_worker, api, phone) for api in sms_list]
            concurrent.futures.wait(futures)
        print("-" * 55)
        print(f"{G}[✓] Hoàn tất Suite SMS.{RESET}")

    def trigger_combined_suite(self, phone: str) -> None:
        self.trigger_sms_suite(phone)
        time.sleep(1.5)
        
        call_list = self.api_database.get("call_endpoints", [])
        if not call_list:
            return

        print(f"\n{G}[+] Khởi chạy Suite IVR: Đang thực thi {len(call_list)} cuộc gọi...{RESET}")
        print("-" * 55)
        self.sync_ivr_cookies(phone)
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(self.execute_request_worker, api, phone) for api in call_list]
            concurrent.futures.wait(futures)
        print("-" * 55)
        print(f"{G}[✓] Hoàn tất toàn bộ chuỗi tích hợp.{RESET}")

# ==========================================
# THU THẬP MÃ MÁY AN TOÀN TRÊN TERMUX/WINDOWS PE
# ==========================================
def get_hardware_id() -> str:
    current_os = platform.system().lower()
    
    if current_os != "windows":
        machine_dir = "/sdcard/Documents"
        machine_file = os.path.join(machine_dir, ".svx_machine")
        try:
            if os.path.exists(machine_file):
                hwid = open(machine_file, "r", encoding="utf-8").read().strip()
                if hwid and len(hwid) == 32:
                    return hwid.upper()
        except:
            pass

    parts = []
    try:
        if current_os == "windows":
            cmd = "wmic csproduct get uuid"
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode().split()
            if len(output) >= 2: parts.append(output[1])
        else:
            s = subprocess.check_output(["getprop", "ro.serialno"], stderr=subprocess.DEVNULL, timeout=2).decode().strip()
            if s and s != "unknown": parts.append(s)
    except:
        pass

    try:
        parts.append(platform.node())
        parts.append(platform.system())
    except:
        pass

    raw = "|".join(parts) if parts else "MATRIX_FALLBACK_DEVICE"
    hwid = hashlib.md5(raw.encode('utf-8')).hexdigest().upper()

    if current_os != "windows":
        try:
            os.makedirs(machine_dir, exist_ok=True)
            open(machine_file, "w", encoding="utf-8").write(hwid.lower())
        except:
            pass

    return hwid

def verify_license_key(key: str, hardware_id: str) -> bool:
    try:
        payload = {"key": key, "hwid": hardware_id.lower()}
        response = requests.post(f"{SERVER_URL}/verify", json=payload, timeout=8)
        if response.status_code == 200:
            data = response.json()
            pname = data.get("product_name", "")
            if pname and pname != TOOL_NAME:
                return False
            return True
    except:
        return True
    return False

def check_authentication_flow():
    hw_id = get_hardware_id()
    
    if os.path.exists(KEY_FILE_PATH):
        try:
            with open(KEY_FILE_PATH, "r", encoding="utf-8") as f:
                saved_key = f.read().strip()
            if saved_key and verify_license_key(saved_key, hw_id):
                return True
        except:
            pass
            
    while True:
        os.system("cls" if platform.system().lower() == "windows" else "clear")
        print(f"{Y}" + "=" * 64)
        print(f"{W}         XÁC THỰC BẢN QUYỀN HỆ THỐNG - SHOPVIETX.IO.VN       ")
        print(f"{Y}" + "=" * 64)
        print(f"  {R}[!] Trạng thái: Chưa kích hoạt bản quyền!{RESET}")
        print(f"  • Mã máy (HWID) của bạn: {B}{hw_id}{RESET}")
        print(f"  • Vui lòng gửi Mã máy trên cho Admin để mua bản quyền.")
        print(f"{Y}" + "-" * 64 + f"{RESET}")
        
        user_key = input(f"{G}[?] Nhập Key bản quyền (Bấm '0' để thoát): {RESET}").strip().upper()
        
        if user_key == "0":
            sys.exit(0)
        if not user_key:
            continue
            
        print(f"{Y}[+] Đang gửi yêu cầu kích hoạt tới Server...{RESET}")
        try:
            payload = {
                "key": user_key, 
                "hwid": hw_id.lower(),
                "device_name": f"{platform.node()} ({platform.system()})"
            }
            response = requests.post(f"{SERVER_URL}/activate", json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                pname = data.get("product_name", "")
                if pname and pname != TOOL_NAME:
                    print(f"{R}❌ Key này thuộc sản phẩm '{pname}', không áp dụng cho cấu trúc hiện tại!{RESET}")
                    time.sleep(2)
                    continue
                
                with open(KEY_FILE_PATH, "w", encoding="utf-8") as f:
                    f.write(user_key)
                print(f"{G}[✓] KÍCH HOẠT THÀNH CÔNG! Đang khởi động...{RESET}")
                time.sleep(1.5)
                return True
            else:
                err_msg = response.json().get('detail', 'Mã khóa không tồn tại hoặc sai thiết bị!')
                print(f"{R}❌ Lỗi: {err_msg}{RESET}")
                time.sleep(2)
        except Exception as e:
            print(f"{R}❌ Không thể liên kết tới máy chủ xác thực: {e}{RESET}")
            time.sleep(2)

def show_banner_introduction():
    os.system("cls" if platform.system().lower() == "windows" else "clear")
    hw_id = get_hardware_id()
    
    print(f"{B}" + "=" * 64)
    print(f"{W}         MATRIX NOTIFICATION TESTING SYSTEM SYSTEM          ")
    print(f"{W}   Chạy trên: Windows PE / Windows Desktop / Termux (Linux) ")
    print(f"{B}" + "=" * 64)
    print(f"  • Phiên bản: Cloud Integration v4.0 (Chạy trên RAM)")
    print(f"  • Hệ điều hành: {platform.system()} {platform.release()}")
    print(f"  • Mã máy của bạn: {Y}{hw_id}{RESET}")
    print(f"  • Trạng thái bản quyền: {G}Đã kích hoạt [✓]{RESET}")
    print(f"{B}" + "=" * 64 + f"{RESET}")

def render_terminal_menu():
    print("\n" + f"{B}═{RESET}"*20 + f" {W}MENU ĐIỀU KHIỂN CHÍNH {RESET}" + f"{B}═{RESET}"*20)
    print(f"  {G}[1]{RESET} Chạy phân hệ SMS (SMS Test Only)")
    print(f"  {G}[2]{RESET} Chạy tích hợp toàn diện (SMS Test + Call Test ở cuối)")
    print(f"  {G}[0]{RESET} Giải phóng bộ nhớ & Thoát chương trình")
    print(f"{B}═{RESET}"*64)

def run_application():
    check_authentication_flow()
    show_banner_introduction()
    core_engine = CloudTestingEngine()
    
    while True:
        render_terminal_menu()
        cmd = input(f"{G}[?] Nhập tùy chọn lệnh (0-2): {RESET}").strip()
        
        if cmd == "0":
            print(f"{G}[+] Bộ nhớ đệm đã được giải phóng sạch sẽ khỏi RAM. Đóng!{RESET}")
            break
        elif cmd in ["1", "2"]:
            phone = input(f"{G}[?] Nhập số điện thoại mục tiêu cần test: {RESET}").strip()
            if not phone or len(phone) < 9 or not phone.isdigit():
                print(f"{R}[-] Lỗi: Số điện thoại không đúng định dạng!{RESET}")
                continue
                
            if cmd == "1":
                core_engine.trigger_sms_suite(phone)
            elif cmd == "2":
                core_engine.trigger_combined_suite(phone)
                
            input(f"\n{Y}[Nhấn nút Enter để tiếp tục...]{RESET}")
        else:
            print(f"{R}[-] Mã lệnh không hợp lệ!{RESET}")

if __name__ == "__main__":
    run_application()
