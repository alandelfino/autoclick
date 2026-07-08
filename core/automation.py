"""
Windows Native Automation via ctypes.

Provides low-level functions for simulating mouse clicks, keyboard presses,
typing text, and querying active window information using the Windows API.
"""
import ctypes
import time

# Windows DPI Awareness setup to ensure correct coordinates capturing and simulation
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2) # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def click_mouse(x, y):
    """Moves cursor to x, y and simulates a left click."""
    ctypes.windll.user32.SetCursorPos(x, y)
    # MOUSEEVENTF_LEFTDOWN = 0x0002
    # MOUSEEVENTF_LEFTUP = 0x0004
    ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)

# Virtual Key Codes map for common keys
VK_CODES = {
    'enter': 0x0D,
    'tab': 0x09,
    'space': 0x20,
    'backspace': 0x08,
    'escape': 0x1B,
    'up': 0x26,
    'down': 0x28,
    'left': 0x25,
    'right': 0x27,
    'ctrl': 0x11,
    'alt': 0x12,
    'shift': 0x10,
    'pageup': 0x21,
    'page_up': 0x21,
    'pgup': 0x21,
    'pagedown': 0x22,
    'page_down': 0x22,
    'pgdn': 0x22,
    'home': 0x24,
    'end': 0x23,
    'delete': 0x2E,
    'del': 0x2E,
    'insert': 0x2D,
    'ins': 0x2D,
    'f1': 0x70,
    'f2': 0x71,
    'f3': 0x72,
    'f4': 0x73,
    'f5': 0x74,
    'f6': 0x75,
    'f7': 0x76,
    'f8': 0x77,
    'f9': 0x78,
    'f10': 0x79,
    'f11': 0x7A,
    'f12': 0x7B,
}

def simulate_keypress(key, count=1):
    """Simulates pressing a key multiple times."""
    key_lower = key.strip().lower()
    vk_code = None
    
    # Check if user input is a virtual key code in hex (e.g. "0x22") or decimal (e.g. "34") format
    if key_lower.startswith("0x"):
        try:
            vk_code = int(key_lower, 16)
        except ValueError:
            pass
    elif key_lower.isdigit():
        vk_code = int(key_lower)
        
    if vk_code is None:
        if key_lower in VK_CODES:
            vk_code = VK_CODES[key_lower]
        elif len(key) == 1:
            # Get virtual-key code for the single character
            vk_code = ctypes.windll.user32.VkKeyScanW(ord(key)) & 0xFF
        else:
            return # Invalid/Unsupported Key

    for _ in range(count):
        # KEYEVENTF_KEYUP = 0x0002
        ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0) # Key down
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(vk_code, 0, 0x0002, 0) # Key up
        time.sleep(0.15) # Wait between presses

def get_active_window_info():
    """Gets the title and window handle (HWND) of the currently active window."""
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    if not hwnd:
        return "Nenhuma janela ativa", 0
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return "Janela sem título", hwnd
    buf = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value, hwnd

def simulate_type_text(text):
    """Simulates typing text using Windows keybd_event and KEYEVENTF_UNICODE."""
    for char in text:
        if char == '\n':
            # Simulate Enter key press
            ctypes.windll.user32.keybd_event(0x0D, 0, 0, 0)
            time.sleep(0.05)
            ctypes.windll.user32.keybd_event(0x0D, 0, 0x0002, 0)
            time.sleep(0.05)
        else:
            # Press Unicode character (KEYEVENTF_UNICODE = 0x0004)
            ctypes.windll.user32.keybd_event(0, ord(char), 0x0004, 0)
            # Release Unicode character (KEYEVENTF_KEYUP = 0x0002)
            ctypes.windll.user32.keybd_event(0, ord(char), 0x0004 | 0x0002, 0)
            time.sleep(0.015) # Brief pause to simulate human typing


def get_active_window_details():
    """Gets the title, width, height and window handle (HWND) of the currently active window."""
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    if not hwnd:
        return {
            'title': "Nenhuma janela ativa",
            'width': 0,
            'height': 0,
            'hwnd': 0
        }
    
    # Get Title
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        title = "Janela sem título"
    else:
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        
    # Get Rect
    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long)
        ]
    rect = RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    
    return {
        'title': title,
        'width': width,
        'height': height,
        'hwnd': hwnd
    }

