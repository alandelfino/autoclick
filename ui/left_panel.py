"""
Left panel — Toolbox for adding nodes and debug console.
"""
import tkinter as tk
from core.i18n_helper import t


class LeftPanelMixin:
    """Mixin providing the left sidebar UI (toolbox + console)."""

    def setup_left_panel(self):
        # 1. TOOLBOX SECTION
        section_toolbox = tk.Label(
            self.left_panel, text=t("toolbox.add_nodes"), font=("Segoe UI", 9, "bold"),
            fg="#94a3b8", bg="#0f172a"
        )
        section_toolbox.pack(pady=(15, 5), padx=10, anchor="w")
        
        # Add Node Buttons
        nodes_to_add = [
            (t("toolbox.nodes.click"), "click", "#a855f7"),
            (t("toolbox.nodes.capture"), "capture", "#f97316"),
            (t("toolbox.nodes.condition"), "condition", "#0d9488"),
            (t("toolbox.nodes.key"), "key", "#db2777"),
            (t("toolbox.nodes.type_text"), "type_text", "#10b981"),
            (t("toolbox.nodes.delay"), "delay", "#f59e0b"),
            (t("toolbox.nodes.move_mouse"), "move_mouse", "#06b6d4"),
            (t("toolbox.nodes.postgres"), "postgres", "#336791"),
            (t("toolbox.nodes.mysql"), "mysql", "#00758f"),
            (t("toolbox.nodes.sqlite"), "sqlite", "#003b57"),
            (t("toolbox.nodes.api"), "api", "#0284c7"),
            (t("toolbox.nodes.loop"), "loop", "#8b5cf6"),
            (t("toolbox.nodes.storage_var"), "storage_var", "#ec4899"),
            (t("toolbox.nodes.break_loop"), "break_loop", "#a21caf")
        ]
        
        for name, type_key, color in nodes_to_add:
            btn = tk.Button(
                self.left_panel, text=f"+ {name}", font=("Segoe UI", 9, "bold"),
                bg=color, fg="#ffffff", activebackground=color, activeforeground="#ffffff",
                bd=0, pady=6, cursor="hand2"
            )
            btn.pack(pady=3, padx=15, fill="x")
            
            def make_drag_handlers(button_widget, tk_type):
                def on_press(event):
                    self.dragged_node_type = tk_type
                    self.drag_start_x = event.x_root
                    self.drag_start_y = event.y_root
                    self.has_dragged = False
                    
                def on_motion(event):
                    if not hasattr(self, 'drag_start_x'):
                        return
                    dist = ((event.x_root - self.drag_start_x)**2 + (event.y_root - self.drag_start_y)**2)**0.5
                    if dist > 8:
                        self.has_dragged = True
                        self.root.config(cursor="plus")
                        
                def on_release(event):
                    self.root.config(cursor="")
                    if not hasattr(self, 'has_dragged'):
                        return
                    if self.has_dragged:
                        target = self.root.winfo_containing(event.x_root, event.y_root)
                        if target == self.canvas:
                            cx = self.canvas.canvasx(event.x_root - self.canvas.winfo_rootx())
                            cy = self.canvas.canvasy(event.y_root - self.canvas.winfo_rooty())
                            self.create_node(tk_type, x=cx, y=cy, is_canvas_coords=True)
                    else:
                        bx1 = button_widget.winfo_rootx()
                        by1 = button_widget.winfo_rooty()
                        bx2 = bx1 + button_widget.winfo_width()
                        by2 = by1 + button_widget.winfo_height()
                        if bx1 <= event.x_root <= bx2 and by1 <= event.y_root <= by2:
                            self.create_node(tk_type)
                            
                button_widget.bind("<ButtonPress-1>", on_press)
                button_widget.bind("<B1-Motion>", on_motion)
                button_widget.bind("<ButtonRelease-1>", on_release)
                
            make_drag_handlers(btn, type_key)
            
        # Divider line
        tk.Frame(self.left_panel, bg="#1e293b", height=1).pack(pady=15, padx=15, fill="x")
        
        # Control variable for hide window (moved checkbox to Config menu)
        self.hide_window_var = tk.BooleanVar(value=True)
        self.countdown_seconds_var = tk.IntVar(value=3)
        
        # 2. DEBUG LOG WINDOW (at the bottom)
        log_label = tk.Label(
            self.left_panel, text=t("toolbox.debug_console"), font=("Segoe UI", 9, "bold"),
            fg="#94a3b8", bg="#0f172a"
        )
        log_label.pack(pady=(5, 5), padx=10, anchor="w")
        
        self.log_text = tk.Text(
            self.left_panel, bg="#1e293b", fg="#e2e8f0", bd=0, 
            font=("Consolas", 8), state="disabled", wrap="word"
        )
        self.log_text.pack(pady=(0, 10), padx=10, fill="both", expand=True)
