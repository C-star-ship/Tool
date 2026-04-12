
import os
import shutil
import requests 

def get_terminal_width():
    try:
        return shutil.get_terminal_size().columns
    except:
        return 80  # safe fallback for Termux

def center_text(text, visual_length, term_width):
    """Hàm hỗ trợ căn giữa chuỗi có chứa mã màu ANSI"""
    padding = max(0, term_width - visual_length) // 2
    return (" " * padding) + text

def print_banner():
    width = get_terminal_width()

    # Khai báo các mã màu ANSI
    do       = "\033[91m"  # red
    xanhnhat = "\033[96m"  # cyan
    vang     = "\033[93m"  # yellow
    xanhla   = "\033[92m"  # green
    tim      = "\033[95m"  # magenta
    trang    = "\033[97m"  # white (Thêm màu trắng cho shop)
    reset    = "\033[0m"

    # ================= 1. IN BANNER LOGO =================
    # Full banner (wide screens >= 50 cols)
    banner_wide = [
        (xanhnhat, "  ██╗   ██╗██╗███████╗████████╗██╗  ██╗", 39),
        (xanhla,   "  ██║   ██║██║██╔════╝╚══██╔══╝╚██╗██╔╝", 39),
        (vang,     "  ██║   ██║██║█████╗     ██║    ╚███╔╝ ", 39),
        (xanhla,   "  ╚██╗ ██╔╝██║██╔══╝     ██║    ██╔██╗ ", 39),
        (tim,      "   ╚████╔╝ ██║███████╗   ██║   ██╔╝ ██╗", 39),
        (xanhnhat, "    ╚═══╝  ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝", 39),
    ]

    # Compact fallback for narrow screens
    banner_narrow = [
        (xanhnhat, " V I E T X", 10),
        (vang,     " =========", 10),
    ]

    lines = banner_wide if width >= 50 else banner_narrow

    print()
    for color, line, vis_len in lines:
        colored_text = f"{color}{line}{reset}"
        # Căn giữa từng dòng logo
        print(center_text(colored_text, vis_len, width))
    print()

    # ================= 2. IN KHUNG THÔNG TIN =================
    # Mảng chứa nội dung: (Chuỗi có màu để in, Chuỗi thô để đo độ dài)
    info_lines = [
        (f"{do}🔥 TÊN TOOL       : {xanhla}Vietx sms", "🔥 TÊN TOOL       : Vietx sms"),
        (f"{xanhla}🔥 BOX ZALO       : {vang}https://zalo.me/0567101487", "🔥 BOX ZALO       : https://zalo.me/0567101487"),
        (f"{xanhla}🔥 THAM KHẢO SHOP : {trang}https://shopvietx.io.vn", "🔥 THAM KHẢO SHOP : https://shopvietx.io.vn")
    ]

    # Tự động tính toán chiều rộng của khung dựa trên dòng dài nhất
    max_vis_len = max(len(vis_text) for _, vis_text in info_lines)
    box_width = max_vis_len + 2  # Thêm 2 khoảng trống đệm (padding) bên trong khung

    # Tạo viền trên và dưới
    top_border = f"{vang}╔{'═' * box_width}╗{reset}"
    bottom_border = f"{vang}╚{'═' * box_width}╝{reset}"
    total_vis_len = box_width + 2  # Tổng chiều dài trực quan (bao gồm cả 2 dấu viền ╔ và ╗)

    # In ra viền trên (căn giữa)
    print(center_text(top_border, total_vis_len, width))
    
    # In ra nội dung bên trong
    for colored_text, vis_text in info_lines:
        # Tính khoảng trắng cần bù để viền phải luôn thẳng hàng
        padding_spaces = box_width - len(vis_text) - 1
        line_str = f"{vang}║ {reset}{colored_text}{' ' * padding_spaces}{vang}║{reset}"
        print(center_text(line_str, total_vis_len, width))
        
    # In ra viền dưới (căn giữa)
    print(center_text(bottom_border, total_vis_len, width))
    print()

# Chạy thử
print_banner()
