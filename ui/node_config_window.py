"""
Node config window — Toplevel dialog for editing node configuration.
"""
import tkinter as tk
from tkinter import ttk
from core.i18n_helper import t


class NodeConfigWindowMixin:
    """Mixin providing the node configuration window UI."""

    def open_node_config_window(self, node):
        node.is_hovered = False
        node.update_outline()
        self.select_node(node)
        
        # Close existing popup window if open
        if hasattr(self, 'node_window') and self.node_window:
            try:
                self.node_window.destroy()
            except Exception:
                pass
            self.node_window = None
            
        import copy
        self.temp_properties = copy.deepcopy(node.properties)
        self.temp_node_name = node.name
            
        # Create a new top-level popup window
        self.node_window = tk.Toplevel(self.root)
        self.node_window.title(t("node_config.title").format(node.name))
        self.node_window.transient(self.root)
        
        # Dimension window and center on screen (85% of screen width and height)
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = int(screen_width * 0.85)
        window_height = int(screen_height * 0.85)
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.node_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.node_window.configure(bg="#f8fafc")
        
        # Bottom footer bar with action buttons
        footer_bar = tk.Frame(self.node_window, bg="#f1f5f9", height=50)
        footer_bar.pack(fill="x", side="bottom")
        footer_bar.pack_propagate(False)
        
        # Button: "Aplicar"
        btn_apply = tk.Button(
            footer_bar, text=t("node_config.apply"), font=("Segoe UI", 9, "bold"),
            bg="#22c55e", fg="#ffffff", activebackground="#16a34a", activeforeground="#ffffff",
            bd=0, padx=20, pady=8, cursor="hand2", command=self.apply_node_changes
        )
        btn_apply.pack(side="right", padx=15, pady=8)
        
        # Button: "Cancelar"
        btn_cancel = tk.Button(
            footer_bar, text=t("node_config.cancel"), font=("Segoe UI", 9, "bold"),
            bg="#94a3b8", fg="#ffffff", activebackground="#64748b", activeforeground="#ffffff",
            bd=0, padx=20, pady=8, cursor="hand2", command=self.close_node_window
        )
        btn_cancel.pack(side="right", padx=5, pady=8)
        
        # Main split frame for 3 columns using PanedWindow to allow resizing
        paned = ttk.PanedWindow(self.node_window, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Column 1: INPUT DATA
        left_col = ttk.LabelFrame(paned, text=t("node_config.input_data"), padding=10)
        
        # Column 2: PARAMETERS
        center_col = ttk.LabelFrame(paned, text=t("node_config.parameters"), padding=10)
        
        # Scrollable container inside Column 2
        center_canvas = tk.Canvas(center_col, bg="#f8fafc", bd=0, highlightthickness=0)
        center_scrollbar = ttk.Scrollbar(center_col, orient="vertical", command=center_canvas.yview)
        center_canvas.configure(yscrollcommand=center_scrollbar.set)
        
        center_scrollbar.pack(side="right", fill="y")
        center_canvas.pack(side="left", fill="both", expand=True)
        
        scrollable_properties_frame = tk.Frame(center_canvas, bg="#f8fafc")
        canvas_window = center_canvas.create_window((0, 0), window=scrollable_properties_frame, anchor="nw")
        
        # Resize frame when canvas width changes
        center_canvas.bind("<Configure>", lambda event, cw=canvas_window: center_canvas.itemconfig(cw, width=event.width))
        
        # Configure scrollregion when frame size changes
        def configure_scrollregion_center(event, cc=center_canvas):
            cc.configure(scrollregion=cc.bbox("all"))
        scrollable_properties_frame.bind("<Configure>", configure_scrollregion_center)
        
        # Bind MouseWheel to scroll the canvas
        def _on_mousewheel_center(event, cc=center_canvas):
            cc.yview_scroll(int(-1 * (event.delta / 120)), "units")
            
        center_canvas.bind("<MouseWheel>", _on_mousewheel_center)
        scrollable_properties_frame.bind("<MouseWheel>", _on_mousewheel_center)
        
        # Column 3: OUTPUT DATA
        right_col = ttk.LabelFrame(paned, text=t("node_config.output_data"), padding=10)
        
        # Add to panedwindow with equal weights
        paned.add(left_col, weight=1)
        paned.add(center_col, weight=1)
        paned.add(right_col, weight=1)
        
        # Setup references
        self.input_payload_container = left_col
        self.properties_container = scrollable_properties_frame
        self.output_payload_container = right_col
        
        # Populate inputs, parameters form and outputs
        self.build_properties_panel(node)
        
        # Bind window close protocol
        self.node_window.protocol("WM_DELETE_WINDOW", self.close_node_window)
        self.node_window.focus_force()

    def on_double_click_canvas(self, event):
        item = self.canvas.find_withtag("current")
        if not item:
            return
        tags = self.canvas.gettags(item[0])
        # Make sure it's a node body click and not a port click
        if "port" in tags:
            return
        node_tag = [t for t in tags if t.startswith("node_") and not t.startswith("node_port_")]
        if node_tag:
            node_id = int(node_tag[0].split("_")[1])
            node = self.nodes[node_id]
            self.open_node_config_window(node)

    def apply_node_changes(self):
        if hasattr(self, 'save_properties_from_widgets'):
            self.save_properties_from_widgets()
        if self.selected_node:
            import re
            from tkinter import messagebox
            
            alias_val = self.temp_properties.get('alias', '').strip()
            if not alias_val:
                messagebox.showerror("Erro de Validação", "O campo Alias não pode ser vazio.")
                return
                

                
            for nid, other_node in self.nodes.items():
                if nid != self.selected_node.id:
                    other_alias = other_node.properties.get('alias', '')
                    if other_alias == alias_val:
                        messagebox.showerror("Erro de Validação", f"O Alias '{alias_val}' já está sendo utilizado pelo nó '{other_node.name}'.")
                        return

            import copy
            self.selected_node.properties = copy.deepcopy(self.temp_properties)
            self.selected_node.rename(self.temp_node_name)
            self.selected_node.update_summary_text()
            if self.selected_node.type in ['switch', 'condition']:
                self.selected_node.redraw()
                
                # Clean up any invalid connections
                valid_ports = set(self.selected_node.ports.keys())
                to_remove = []
                for conn in self.connections:
                    if conn.source.id == self.selected_node.id and conn.source_port not in valid_ports:
                        to_remove.append(conn)
                    elif conn.target.id == self.selected_node.id and conn.target_port not in valid_ports:
                        to_remove.append(conn)
                for conn in to_remove:
                    conn.delete()
                    self.connections.remove(conn)
                    
                # Refresh connection lines coordinates
                for conn in self.connections:
                    if conn.source.id == self.selected_node.id or conn.target.id == self.selected_node.id:
                        conn.update_line()
            self.log_message(t("node_config.applied_log").format(self.selected_node.name))
            if hasattr(self, 'propagate_payload_changes'):
                self.propagate_payload_changes(self.selected_node.id)
            if getattr(self, 'current_filepath', None):
                self.trigger_auto_save()
        self.close_node_window()

    def close_node_window(self):
        if self.selected_node:
            self.selected_node.select(False)
            self.selected_node = None
        if hasattr(self, 'node_window') and self.node_window:
            try:
                self.node_window.destroy()
            except Exception:
                pass
            self.node_window = None
            self.properties_container = None
            self.input_payload_container = None
            self.output_payload_container = None
            self.temp_properties = None
            self.temp_node_name = None
