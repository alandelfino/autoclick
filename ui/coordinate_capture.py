"""
Coordinate capture — Full-screen overlay to grab mouse coordinates.
"""
import tkinter as tk


class CoordinateCaptureMixin:
    """Mixin providing the coordinate capture overlay."""

    def launch_coordinate_capture(self, ent_x, ent_y):
        """Temporarily overlay the entire screen to grab global mouse click coordinates."""
        # Hide the main application window and configuration window
        self.root.withdraw()
        if hasattr(self, 'node_window') and self.node_window:
            self.node_window.withdraw()
        
        overlay = tk.Toplevel(self.root)
        overlay.attributes("-alpha", 0.01) # Almost completely transparent to capture clicks
        overlay.attributes("-fullscreen", True)
        overlay.attributes("-topmost", True)
        overlay.overrideredirect(True)
        overlay.configure(bg="#000000")
        overlay.config(cursor="arrow") # Default cursor initially
        
        # Setup instruction floating box (visible window in the top center)
        instruction_window = tk.Toplevel(overlay)
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
        
        ctrl_pressed = [False]
        
        def close_and_restore(event=None):
            try:
                overlay.grab_release()
            except Exception:
                pass
            instruction_window.destroy()
            overlay.destroy()
            if hasattr(self, 'node_window') and self.node_window:
                self.node_window.deiconify()
                self.node_window.focus_force()
            self.root.after(50, self.root.deiconify)
            self.root.after(50, lambda: self.root.state('normal'))
            self.root.after(50, lambda: self.root.focus_force())
            
        def on_key_press(event):
            if "Control" in event.keysym:
                ctrl_pressed[0] = True
                overlay.config(cursor="cross")
                lbl.config(text=t("coordinate_capture.target_active"))
                instruction_window.configure(bg="#10b981") # Change to green when Ctrl is active
                lbl.configure(bg="#10b981")
                
        def on_key_release(event):
            if "Control" in event.keysym:
                ctrl_pressed[0] = False
                overlay.config(cursor="arrow")
                lbl.config(text=t("coordinate_capture.mode_instructions"))
                instruction_window.configure(bg="#1e293b")
                lbl.configure(bg="#1e293b")
                
        def handle_click(event):
            if ctrl_pressed[0]:
                x, y = event.x_root, event.y_root
                
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
                
        overlay.bind("<KeyPress>", on_key_press)
        overlay.bind("<KeyRelease>", on_key_release)
        overlay.bind("<Button-1>", handle_click)
        overlay.bind("<Escape>", close_and_restore)
        
        # Grab focus and mouse grab
        overlay.focus_set()
        overlay.grab_set()
