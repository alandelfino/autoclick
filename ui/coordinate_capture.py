"""
Coordinate capture — Global mouse/keyboard polling to grab mouse coordinates.
"""
import ctypes
import tkinter as tk
from core.i18n_helper import t

user32 = ctypes.windll.user32


def focus_next_visible_window(exclude_hwnds):
    try:
        user32 = ctypes.windll.user32
        exclude = set(exclude_hwnds)
        shell_hwnd = user32.GetShellWindow()
        desktop_hwnd = user32.GetDesktopWindow()
        
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        target_hwnd = [None]
        
        def callback(hwnd, lParam):
            if hwnd in exclude or hwnd == shell_hwnd or hwnd == desktop_hwnd:
                return True
            if not user32.IsWindowVisible(hwnd):
                return True
            if user32.IsIconic(hwnd):
                return True
                
            class_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_buf, 256)
            class_name = class_buf.value
            if class_name in ["Progman", "Shell_TrayWnd", "WorkerW", "Windows.UI.Core.CoreWindow"]:
                return True
                
            title_buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, title_buf, 256)
            if not title_buf.value.strip():
                return True
                
            target_hwnd[0] = hwnd
            return False
            
        cb = EnumWindowsProc(callback)
        user32.EnumWindows.argtypes = [EnumWindowsProc, ctypes.c_void_p]
        user32.EnumWindows.restype = ctypes.c_bool
        user32.EnumWindows(cb, 0)
        
        if target_hwnd[0]:
            user32.SetForegroundWindow(target_hwnd[0])
    except Exception:
        pass


class CoordinateCaptureMixin:
    """Mixin providing the coordinate capture overlay via polling."""

    def launch_coordinate_capture(self, ent_x, ent_y):
        """Start polling the mouse and keyboard state to capture coordinates when Ctrl+click is triggered."""
        # Save original state before withdrawing (e.g. zoomed or normal)
        original_state = self.root.state()

        # Focus next visible window before withdrawing to prevent focus shift to minimized windows
        exclude_hwnds = []
        try:
            exclude_hwnds.append(self.root.winfo_id())
        except Exception:
            pass
        if hasattr(self, 'node_window') and self.node_window:
            try:
                exclude_hwnds.append(self.node_window.winfo_id())
            except Exception:
                pass
        focus_next_visible_window(exclude_hwnds)

        # Hide the main application window and configuration window
        self.root.withdraw()
        if hasattr(self, 'node_window') and self.node_window:
            self.node_window.withdraw()

        # Setup floating instruction window (top center)
        instruction_window = tk.Toplevel(self.root)
        instruction_window.overrideredirect(True)
        instruction_window.attributes("-topmost", True)
        instruction_window.configure(bg="#1e293b")
        
        # Center the instruction box at the top of the screen
        screen_width = self.root.winfo_screenwidth()
        box_width = 520
        box_height = 50
        instruction_window.geometry(f"{box_width}x{box_height}+{(screen_width - box_width)//2}+30")
        
        lbl = tk.Label(
            instruction_window, 
            text=t("coordinate_capture.mode_instructions"), 
            font=("Segoe UI", 10, "bold"), fg="#ffffff", bg="#1e293b"
        )
        lbl.pack(expand=True)

        # Active polling loop flag
        polling_active = [True]

        def close_and_restore():
            polling_active[0] = False
            try:
                instruction_window.destroy()
            except Exception:
                pass
            if hasattr(self, 'node_window') and self.node_window:
                self.node_window.deiconify()
                self.node_window.focus_force()
            self.root.after(50, self.root.deiconify)
            restore_state = original_state if original_state != 'withdrawn' else 'zoomed'
            self.root.after(50, lambda: self.root.state(restore_state))
            self.root.after(50, lambda: self.root.focus_force())

        def capture_coord(x, y):
            ent_x.delete(0, tk.END)
            ent_x.insert(0, str(x))
            ent_y.delete(0, tk.END)
            ent_y.insert(0, str(y))
            
            if self.selected_node:
                self.selected_node.properties['x'] = x
                self.selected_node.properties['y'] = y
                self.selected_node.update_summary_text()
                
            close_and_restore()
            self.log_message(f"Coordinate successfully captured: X={x}, Y={y}")

        def cancel_capture():
            close_and_restore()
            self.log_message("Coordinate capture cancelled.")

        # Clean up variables if user tries to close the window
        instruction_window.protocol("WM_DELETE_WINDOW", cancel_capture)

        # Clear key states at startup so we don't capture any pre-existing clicks
        user32.GetAsyncKeyState(0x01) # Left mouse button
        user32.GetAsyncKeyState(0x11) # Ctrl key
        user32.GetAsyncKeyState(0x1B) # Escape key

        last_ctrl_state = [False]

        def poll():
            if not polling_active[0]:
                return

            # VK_CONTROL = 0x11, VK_LBUTTON = 0x01, VK_ESCAPE = 0x1B
            ctrl_down = bool(user32.GetAsyncKeyState(0x11) & 0x8000)
            click_down = bool(user32.GetAsyncKeyState(0x01) & 0x8000)
            escape_down = bool(user32.GetAsyncKeyState(0x1B) & 0x8000)

            if escape_down:
                cancel_capture()
                return

            # Update floating box UI if Ctrl state changes
            if ctrl_down != last_ctrl_state[0]:
                last_ctrl_state[0] = ctrl_down
                if ctrl_down:
                    lbl.config(text=t("coordinate_capture.target_active"))
                    instruction_window.configure(bg="#10b981")
                    lbl.configure(bg="#10b981")
                else:
                    lbl.config(text=t("coordinate_capture.mode_instructions"))
                    instruction_window.configure(bg="#1e293b")
                    lbl.configure(bg="#1e293b")

            if ctrl_down and click_down:
                # Get mouse coordinates
                class POINT(ctypes.Structure):
                    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
                pt = POINT()
                user32.GetCursorPos(ctypes.byref(pt))
                capture_coord(pt.x, pt.y)
                return

            # Schedule next poll in 15ms
            self.root.after(15, poll)

        # Start polling
        poll()

    def launch_area_capture(self, ent_x, ent_y, ent_w, ent_h, cb_mode):
        """Start overlay to capture screen region when Ctrl is held and mouse drag occurs, preventing pass-through clicks."""
        original_state = self.root.state()

        # Focus next visible window before withdrawing to prevent focus shift to minimized windows
        exclude_hwnds = []
        try:
            exclude_hwnds.append(self.root.winfo_id())
        except Exception:
            pass
        if hasattr(self, 'node_window') and self.node_window:
            try:
                exclude_hwnds.append(self.node_window.winfo_id())
            except Exception:
                pass
        focus_next_visible_window(exclude_hwnds)

        # Hide the main application window and configuration window
        self.root.withdraw()
        if hasattr(self, 'node_window') and self.node_window:
            self.node_window.withdraw()

        # Get screen dimensions
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        # Create overlay window immediately (kept alive during the entire capture process)
        overlay = tk.Toplevel(self.root)
        overlay.overrideredirect(True)
        overlay.attributes("-topmost", True)
        # Position it off-screen initially to allow clicks on background apps
        overlay.geometry("1x1+30000+30000")
        overlay.configure(bg="black")
        overlay.attributes("-alpha", 0.0)

        canvas = tk.Canvas(overlay, bg="black", bd=0, highlightthickness=0, cursor="crosshair")
        canvas.pack(fill="both", expand=True)

        # Floating instruction window (top center)
        instruction_window = tk.Toplevel(self.root)
        instruction_window.overrideredirect(True)
        instruction_window.attributes("-topmost", True)
        instruction_window.configure(bg="#1e293b")
        
        box_width = 520
        box_height = 50
        instruction_window.geometry(f"{box_width}x{box_height}+{(screen_w - box_width)//2}+30")
        
        lbl = tk.Label(
            instruction_window, 
            text=t("properties.screenshot_instructions"), 
            font=("Segoe UI", 10, "bold"), fg="#ffffff", bg="#1e293b"
        )
        lbl.pack(expand=True)

        polling_active = [True]
        is_selecting = [False]
        start_x = [0]
        start_y = [0]
        rect_id = [None]

        # Reset GetAsyncKeyState states
        user32.GetAsyncKeyState(0x01) # Left click
        user32.GetAsyncKeyState(0x11) # Ctrl key
        user32.GetAsyncKeyState(0x1B) # Escape key

        last_ctrl_state = [False]

        def close_and_restore():
            polling_active[0] = False
            try:
                overlay.destroy()
            except Exception:
                pass
            try:
                instruction_window.destroy()
            except Exception:
                pass
            if hasattr(self, 'node_window') and self.node_window:
                self.node_window.deiconify()
                self.node_window.focus_force()
            self.root.after(50, self.root.deiconify)
            restore_state = original_state if original_state != 'withdrawn' else 'zoomed'
            self.root.after(50, lambda: self.root.state(restore_state))
            self.root.after(50, lambda: self.root.focus_force())

        def save_area(x, y, w, h):
            ent_x.delete(0, tk.END)
            ent_x.insert(0, str(x))
            ent_y.delete(0, tk.END)
            ent_y.insert(0, str(y))
            ent_w.delete(0, tk.END)
            ent_w.insert(0, str(w))
            ent_h.delete(0, tk.END)
            ent_h.insert(0, str(h))
            
            cb_mode.set(t("properties.screenshot_area"))
            
            self.temp_properties['screenshot_mode'] = 'Área Especificada'
            self.temp_properties['x'] = x
            self.temp_properties['y'] = y
            self.temp_properties['width'] = w
            self.temp_properties['height'] = h
            
            if self.selected_node:
                self.selected_node.properties['screenshot_mode'] = 'Área Especificada'
                self.selected_node.properties['x'] = x
                self.selected_node.properties['y'] = y
                self.selected_node.properties['width'] = w
                self.selected_node.properties['height'] = h
                self.selected_node.update_summary_text()
                
            close_and_restore()
            if hasattr(self, 'update_screenshot_fields_state'):
                self.update_screenshot_fields_state()
                
            self.log_message(f"Área de captura de print selecionada: X={x}, Y={y}, W={w}, H={h}")

        def cancel_capture():
            close_and_restore()
            if hasattr(self, 'update_screenshot_fields_state'):
                self.update_screenshot_fields_state()
            self.log_message("Seleção de área de print cancelada.")

        # Clean up variables if user tries to close the window
        instruction_window.protocol("WM_DELETE_WINDOW", cancel_capture)

        # Mouse binds for canvas
        def on_button_press(event):
            start_x[0] = event.x
            start_y[0] = event.y
            is_selecting[0] = True
            if rect_id[0] is not None:
                try:
                    canvas.delete(rect_id[0])
                except Exception:
                    pass
            rect_id[0] = canvas.create_rectangle(
                start_x[0], start_y[0], start_x[0], start_y[0],
                outline="#ff0000", width=3
            )

        def on_mouse_drag(event):
            if is_selecting[0]:
                cur_x = event.x
                cur_y = event.y
                try:
                    canvas.coords(rect_id[0], start_x[0], start_y[0], cur_x, cur_y)
                except Exception:
                    pass

        def on_button_release(event):
            if is_selecting[0]:
                is_selecting[0] = False
                end_x = event.x
                end_y = event.y
                
                rx = min(start_x[0], end_x)
                ry = min(start_y[0], end_y)
                rw = abs(start_x[0] - end_x)
                rh = abs(start_y[0] - end_y)
                
                if rw > 5 and rh > 5:
                    save_area(rx, ry, rw, rh)
                else:
                    if rect_id[0] is not None:
                        try:
                            canvas.delete(rect_id[0])
                        except Exception:
                            pass
                        rect_id[0] = None

        canvas.bind("<ButtonPress-1>", on_button_press)
        canvas.bind("<B1-Motion>", on_mouse_drag)
        canvas.bind("<ButtonRelease-1>", on_button_release)

        def poll():
            if not polling_active[0]:
                return

            ctrl_down = bool(user32.GetAsyncKeyState(0x11) & 0x8000)
            escape_down = bool(user32.GetAsyncKeyState(0x1B) & 0x8000)

            if escape_down:
                cancel_capture()
                return

            # Update floating box UI and overlay style if Ctrl state changes
            if ctrl_down != last_ctrl_state[0]:
                last_ctrl_state[0] = ctrl_down
                if ctrl_down:
                    lbl.config(text=t("properties.screenshot_target_active"))
                    instruction_window.configure(bg="#10b981")
                    lbl.configure(bg="#10b981")
                    
                    # Bring overlay on-screen, make it dark and intercept clicks
                    overlay.geometry(f"{screen_w}x{screen_h}+0+0")
                    overlay.attributes("-alpha", 0.4)
                    overlay.focus_force()
                else:
                    if not is_selecting[0]:
                        lbl.config(text=t("properties.screenshot_instructions"))
                        instruction_window.configure(bg="#1e293b")
                        lbl.configure(bg="#1e293b")
                        
                        # Move overlay off-screen and make transparent
                        overlay.attributes("-alpha", 0.0)
                        overlay.geometry("1x1+30000+30000")
                        if rect_id[0] is not None:
                            try:
                                canvas.delete(rect_id[0])
                            except Exception:
                                pass
                            rect_id[0] = None

            self.root.after(15, poll)

        poll()

    def launch_area_capture_old(self):
        pass # placeholder to keep it clean or remove
