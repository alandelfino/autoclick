"""
Coordinate capture — Global mouse/keyboard polling to grab mouse coordinates.
"""
import ctypes
import tkinter as tk
from core.i18n_helper import t

user32 = ctypes.windll.user32


class CoordinateCaptureMixin:
    """Mixin providing the coordinate capture overlay via polling."""

    def launch_coordinate_capture(self, ent_x, ent_y):
        """Start polling the mouse and keyboard state to capture coordinates when Ctrl+click is triggered."""
        # Save original state before withdrawing (e.g. zoomed or normal)
        original_state = self.root.state()

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
