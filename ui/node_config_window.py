"""
Node config window — Toplevel dialog for editing node configuration.
"""
import tkinter as tk
from tkinter import ttk
from core.i18n_helper import t


class NodeConfigWindowMixin:
    """Mixin providing the node configuration window UI."""

    def open_node_config_window(self, node):
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
        
        # Dimension window and center on screen
        window_width = 1150
        window_height = 680
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
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
        
        # Column 3: OUTPUT DATA
        right_col = ttk.LabelFrame(paned, text=t("node_config.output_data"), padding=10)
        
        # Add to panedwindow with equal weights
        paned.add(left_col, weight=1)
        paned.add(center_col, weight=1)
        paned.add(right_col, weight=1)
        
        # Setup references
        self.input_payload_container = left_col
        self.properties_container = center_col
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
        node_tag = [t for t in tags if t.startswith("node_")]
        if node_tag:
            node_id = int(node_tag[0].split("_")[1])
            node = self.nodes[node_id]
            self.open_node_config_window(node)

    def apply_node_changes(self):
        if hasattr(self, 'save_properties_from_widgets'):
            self.save_properties_from_widgets()
        if self.selected_node:
            import copy
            self.selected_node.properties = copy.deepcopy(self.temp_properties)
            self.selected_node.rename(self.temp_node_name)
            self.selected_node.update_summary_text()
            self.log_message(t("node_config.applied_log").format(self.selected_node.name))
            if getattr(self, 'current_filepath', None):
                self.save_flow_to_filepath(self.current_filepath, show_popup=False)
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
