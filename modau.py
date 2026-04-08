import os
import shutil
import requests 
def get_terminal_width():
    try:
        return shutil.get_terminal_size().columns
    except:
        return 80  # safe fallback for Termux

def print_banner():
    width = get_terminal_width()

    # ANSI color codes
    do       = "\033[91m"  # red
    xanhnhat = "\033[96m"  # cyan
    vang     = "\033[93m"  # yellow
    xanhla   = "\033[92m"  # green
    tim      = "\033[95m"  # magenta
    reset    = "\033[0m"

    # Full banner (wide screens >= 50 cols)
    banner_wide = [
        (xanhnhat, "  ██╗   ██╗██╗███████╗████████╗██╗  ██╗"),
        (xanhla,   "  ██║   ██║██║██╔════╝╚══██╔══╝╚██╗██╔╝"),
        (vang,     "  ██║   ██║██║█████╗     ██║    ╚███╔╝ "),
        (xanhla,   "  ╚██╗ ██╔╝██║██╔══╝     ██║    ██╔██╗ "),
        (tim,      "   ╚████╔╝ ██║███████╗   ██║   ██╔╝ ██╗"),
        (xanhnhat, "    ╚═══╝  ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝"),
    ]

    # Compact fallback for narrow screens
    banner_narrow = [
        (xanhnhat, " V I E T X"),
        (vang,     " ========="),
    ]

    lines = banner_wide if width >= 50 else banner_narrow

    print()
    for color, line in lines:
        # Center each line within terminal width
        print(f"{color}{line.center(width)}{reset}")
    print()

print_banner()