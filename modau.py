import os
import shutil
import re

def clear_screen():
    """Hàm tự động nhận diện hệ điều hành và xóa sạch màn hình Terminal"""
    # Nếu là Windows (nt) thì dùng 'cls', ngược lại dùng 'clear' (cho Linux/Mac/Termux)
    os.system('cls' if os.name == 'nt' else 'clear')

def get_terminal_width():
    try:
        return shutil.get_terminal_size().columns
    except:
        return 80  # safe fallback for Termux

def get_visual_length(text):
    """Hàm tự động loại bỏ mã màu ANSI để đếm độ dài thực tế hiển thị trên màn hình"""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return len(ansi_escape.sub('', text))

def center_text(text, term_width):
    """Hàm căn giữa chuỗi thông minh, tự động tính độ dài thực"""
    vis_len = get_visual_length(text)
    padding = max(0, term_width - vis_len) // 2
    return (" " * padding) + text

def print_banner():
    width = get_terminal_width()

    # Khai báo các mã màu ANSI
    do       = "\033[91m"
    xanhnhat = "\033[96m"
    vang     = "\033[93m"
    xanhla   = "\033[92m"
    tim      = "\033[95m"
    trang    = "\033[97m"
    reset    = "\033[0m"

    # ================= 1. IN BANNER LOGO =================
    banner_wide = [
        f"{xanhnhat}  ██╗   ██╗██╗███████╗████████╗██╗  ██╗",
        f"{xanhla}  ██║   ██║██║██╔════╝╚══██╔══╝╚██╗██╔╝",
        f"{vang}  ██║   ██║██║█████╗     ██║    ╚███╔╝ ",
        f"{xanhla}  ╚██╗ ██╔╝██║██╔══╝     ██║    ██╔██╗ ",
        f"{tim}   ╚████╔╝ ██║███████╗   ██║   ██╔╝ ██╗",
        f"{xanhnhat}    ╚═══╝  ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝"
    ]

    banner_narrow = [
        f"{xanhnhat} V I E T X",
        f"{vang} ========="
    ]

    lines = banner_wide if width >= 50 else banner_narrow

    print()
    for line in lines:
        print(center_text(line + reset, width))
    print()

    # ================= 2. IN KHUNG THÔNG TIN =================
    info_lines = [
        f"{do}🔥 ADMIN          : {xanhla}VietX",
        f"{xanhla}🔥 BOX ZALO       : {vang}https://zalo.me/0567101487",
        f"{xanhla}🔥 THAM KHẢO SHOP : {trang}https://byvn.net/qIeK"
    ]

    # Tự động tìm dòng dài nhất để làm chuẩn cho chiều rộng của khung
    max_vis_len = max(get_visual_length(line) for line in info_lines)
    box_width = max_vis_len + 2  # Thêm khoảng trống đệm cho đẹp

    top_border = f"{vang}╔{'═' * box_width}╗{reset}"
    bottom_border = f"{vang}╚{'═' * box_width}╝{reset}"

    # In viền trên
    print(center_text(top_border, width))
    
    # In nội dung
    for line in info_lines:
        vis_len = get_visual_length(line)
        padding_spaces = box_width - vis_len - 1
        line_str = f"{vang}║ {reset}{line}{' ' * padding_spaces}{vang}║{reset}"
        print(center_text(line_str, width))
        
    # In viền dưới
    print(center_text(bottom_border, width))
    print()

# ================= THỰC THI CHƯƠNG TRÌNH =================
clear_screen() # Xóa sạch màn hình trước
print_banner() # Sau đó in banner ra
