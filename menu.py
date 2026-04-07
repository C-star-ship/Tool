import os
import sys
import time
import requests
from concurrent.futures import ThreadPoolExecutor

# ================= MÀU SẮC & GIAO DIỆN =================
xanhla = '\033[1;32m'
trang = '\033[1;37m'
do = '\033[1;31m'
vang = '\033[1;33m'
xanhnhat = '\033[1;36m'
tim = '\033[1;35m'

def show_banner():
    """Hiển thị giao diện của Tool"""
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"""
{do}  ██╗   ██╗██╗███████╗████████╗██╗  ██╗
{xanhnhat}  ██║   ██║██║██╔════╝╚══██╔══╝╚██╗██╔╝
{vang}  ██║   ██║██║█████╗     ██║    ╚███╔╝ 
{xanhla}  ╚██╗ ██╔╝██║██╔══╝     ██║    ██╔██╗ 
{tim}   ╚████╔╝ ██║███████╗   ██║   ██╔╝ ██╗
{xanhnhat}    ╚═══╝  ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝
{vang}╔══════════════════════════════════════════════════════╗
{vang}║{do}🔥 TÊN TOOL  : {xanhla}Vietx sms                                                                            
{vang}║{xanhla}🔥 BOX ZALO  : {vang}https://zalo.me/0567101487                                                                          
{vang}║{xanhnhat}🔥 {tim}CHỨC NĂNG : spam tin nhắn sms    
{vang}║{xanhla}🔥 {trang}THAM KHẢO SHOP : https://byvn.net/qIeK                                                                   
{vang}╚══════════════════════════════════════════════════════╝
""")
show_banner