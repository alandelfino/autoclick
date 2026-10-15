"""
Tray icon — System tray integration and global hotkey listener.
"""
import ctypes
from ctypes import wintypes
import time
import threading
import pystray
from PIL import Image, ImageDraw
from core.i18n_helper import t


class TrayIconMixin:
    """Mixin providing system tray icon and hotkey listener."""

    def create_tray_icon(self):
        def create_image():
            # Generate a nice tray icon: green circle with play button
            image = Image.new('RGB', (64, 64), color='#0f172a')
            draw = ImageDraw.Draw(image)
            draw.ellipse([8, 8, 56, 56], fill='#10b981', outline='#ffffff', width=3)
            draw.polygon([(24, 18), (46, 32), (24, 46)], fill='#ffffff')
            return image
            
        def restore_app():
            if self.tray_icon:
                self.tray_icon.stop()
                self.tray_icon = None
            self.root.after(0, self.root.deiconify)
            self.root.after(0, lambda: self.root.state('normal'))
            self.root.after(0, lambda: self.root.focus_force())
            
        def force_stop_and_restore():
            self.stop_flow_execution()
            restore_app()
            
        menu = pystray.Menu(
            pystray.MenuItem(t("tray_icon.restore"), lambda icon, item: restore_app()),
            pystray.MenuItem(t("tray_icon.stop"), lambda icon, item: force_stop_and_restore())
        )
        self.tray_icon = pystray.Icon("autoclick", create_image(), t("tray_icon.running"), menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def start_hotkey_listener(self):
        """Starts a background thread to listen for global hotkeys."""
        self.hotkey_thread = threading.Thread(target=self.hotkey_listener_loop, daemon=True)
        self.hotkey_thread.start()

    def hotkey_listener_loop(self):
        user32 = ctypes.windll.user32
        
        # Register global shortcuts during execution
        # F1: id=101, VK_F1 = 0x70
        # F2: id=102, VK_F2 = 0x71
        # Escape: id=103, VK_ESCAPE = 0x1B
        hotkeys = {
            101: 0x70,
            102: 0x71,
            103: 0x1B,
        }
        registered_hotkeys = {
            hotkey_id
            for hotkey_id, virtual_key in hotkeys.items()
            if user32.RegisterHotKey(None, hotkey_id, 0, virtual_key)
        }
        
        if 103 in registered_hotkeys:
            self.log_message(">> Global Hotkeys active: [ESC/F1] to Stop, [F2] to Pause/Resume")
        else:
            self.log_message(">> WARNING: [ESC] global shortcut unavailable. Use [F1] to Stop.")
        
        msg = wintypes.MSG()
        try:
            while self.is_running:
                # Drain pending messages without blocking the execution thread.
                while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1): # PM_REMOVE = 1
                    if msg.message == 0x0312: # WM_HOTKEY
                        hotkey_id = msg.wParam
                        if hotkey_id in (101, 103):
                            shortcut = "ESC" if hotkey_id == 103 else "F1"
                            self.log_message(f">> HOTKEY DETECTED: [{shortcut}] - Stopping Execution!")
                            self.stop_flow_execution()
                        elif hotkey_id == 102:
                            self.log_message(">> HOTKEY DETECTED: [F2] - Toggling Pause/Resume!")
                            self.toggle_pause()
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                time.sleep(0.05)
        finally:
            for hotkey_id in registered_hotkeys:
                user32.UnregisterHotKey(None, hotkey_id)
            self.log_message(">> Global Hotkeys deactivated.")
