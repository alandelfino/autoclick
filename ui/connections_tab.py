"""
Connections tab — Management UI for database and API connections.
"""
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from core.i18n_helper import t


class ConnectionsTabMixin:
    """Mixin providing the connections tab UI and CRUD operations."""

    def load_connections(self):
        if not hasattr(self, 'saved_connections') or self.saved_connections is None:
            self.saved_connections = {}

    def save_connections(self):
        # Saved connections are part of the flow.
        # If there is a current filepath, save the flow silently.
        if getattr(self, 'current_filepath', None):
            try:
                self.save_flow_to_filepath(self.current_filepath, show_popup=False)
            except Exception as e:
                self.log_message(f"Error saving connections to flow: {str(e)}")

    def setup_connections_tab(self):
        # Configure layout for Connections tab (list only)
        main_frame = ttk.Frame(self.tab_conn, padding=10)
        main_frame.pack(fill="both", expand=True)
        
        lbl_list = tk.Label(main_frame, text=t("connections_tab.configured_connections"), font=("Segoe UI", 10, "bold"), fg="#1e293b")
        lbl_list.pack(anchor="w", pady=(0, 5))
        
        # Treeview frame to hold Treeview + scrollbar
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        # Treeview list
        self.conn_tree = ttk.Treeview(tree_frame, columns=("Nome", "Tipo"), show="headings", selectmode="browse")
        self.conn_tree.heading("Nome", text=t("connections_tab.name"))
        self.conn_tree.heading("Tipo", text=t("connections_tab.type"))
        self.conn_tree.column("Nome", width=250)
        self.conn_tree.column("Tipo", width=120)
        self.conn_tree.pack(side="left", fill="both", expand=True)
        
        # Scrollbars for Treeview
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.conn_tree.yview)
        vsb.pack(side="right", fill="y")
        self.conn_tree.configure(yscrollcommand=vsb.set)
        
        # Double-click event to open edit window
        self.conn_tree.bind("<Double-1>", self.on_connection_double_click)
        
        # Button bar for actions at the bottom
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x")
        
        # New Connection button
        btn_new_conn = tk.Button(
            btn_frame, text=t("connection_dialogs.new_conn"), font=("Segoe UI", 9, "bold"),
            bg="#2563eb", fg="#ffffff", activebackground="#1d4ed8", activeforeground="#ffffff",
            bd=0, padx=15, pady=8, cursor="hand2", command=self.open_new_connection_window
        )
        btn_new_conn.pack(side="left", padx=(0, 5))
        
        # Edit Connection button
        btn_edit_conn = tk.Button(
            btn_frame, text=t("connections_tab.edit_conn"), font=("Segoe UI", 9, "bold"),
            bg="#f59e0b", fg="#ffffff", activebackground="#d97706", activeforeground="#ffffff",
            bd=0, padx=15, pady=8, cursor="hand2", command=self.open_edit_connection_window
        )
        btn_edit_conn.pack(side="left", padx=5)
        
        # Delete Connection button
        btn_del_conn = tk.Button(
            btn_frame, text=t("connections_tab.delete_conn"), font=("Segoe UI", 9, "bold"),
            bg="#ef4444", fg="#ffffff", activebackground="#dc2626", activeforeground="#ffffff",
            bd=0, padx=15, pady=8, cursor="hand2", command=self.delete_connection_from_list
        )
        btn_del_conn.pack(side="right")
        
        # Populate connections list initially
        self.populate_connections_list()

    def populate_connections_list(self):
        self.conn_tree.delete(*self.conn_tree.get_children())
        for name, conn in sorted(self.saved_connections.items()):
            self.conn_tree.insert("", "end", iid=name, values=(name, conn.get("type", "").upper()))

    def on_connection_double_click(self, event):
        selected = self.conn_tree.selection()
        if not selected:
            return
        conn_name = selected[0]
        self.open_connection_window(conn_name)

    def open_new_connection_window(self):
        self.open_connection_window(None)

    def open_edit_connection_window(self):
        selected = self.conn_tree.selection()
        if not selected:
            messagebox.showwarning(t("messages.warning"), t("connections_tab.select_edit"))
            return
        conn_name = selected[0]
        self.open_connection_window(conn_name)

    def delete_connection_from_list(self):
        selected = self.conn_tree.selection()
        if not selected:
            messagebox.showwarning(t("messages.warning"), t("connections_tab.select_delete"))
            return
        conn_name = selected[0]
        if messagebox.askyesno(t("connection_dialogs.confirm_delete_title"), t("connection_dialogs.confirm_delete_msg").format(conn_name)):
            if conn_name in self.saved_connections:
                del self.saved_connections[conn_name]
                self.save_connections()
                self.log_message(f"Connection '{conn_name}' deleted.")
            self.populate_connections_list()
