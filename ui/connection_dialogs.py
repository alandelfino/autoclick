"""
Connection dialogs — Toplevel windows for creating/editing/testing connections.
"""
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter import filedialog
import threading


class ConnectionDialogsMixin:
    """Mixin providing connection creation/editing dialog windows."""

    def open_connection_window(self, conn_name=None):
        if hasattr(self, 'conn_window') and self.conn_window:
            try:
                self.conn_window.destroy()
            except Exception:
                pass
            self.conn_window = None
            
        self.conn_window = tk.Toplevel(self.root)
        self.conn_window.title(f"Configuração de Conexão: {conn_name if conn_name else 'Nova Conexão'}")
        self.conn_window.transient(self.root)
        self.conn_window.grab_set()
        
        window_width = 500
        window_height = 450
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.conn_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.conn_window.configure(bg="#f8fafc")
        
        self.conn_form_frame = ttk.Frame(self.conn_window, padding=15)
        self.conn_form_frame.pack(fill="both", expand=True)
        
        self.show_connection_form(conn_name)

    def show_connection_form(self, conn_name=None, new_type=None, prefilled_name=None):
        for widget in self.conn_form_frame.winfo_children():
            widget.destroy()
            
        # Variables configuration
        self.conn_form_data = {}
        self.temp_schema = None
        
        # Determine mode
        is_edit = conn_name is not None
        conn_info = self.saved_connections.get(conn_name, {}) if is_edit else {}
        conn_type = conn_info.get("type", new_type)
        if conn_type == 'postgresql':
            conn_type = 'postgres'
        
        # Title of section
        lbl_title = tk.Label(
            self.conn_form_frame, 
            text=f"{'Editar' if is_edit else 'Criar'} Conexão " + (f"({conn_type.upper()})" if conn_type else ""),
            font=("Segoe UI", 12, "bold"), fg="#1e293b"
        )
        lbl_title.pack(anchor="w", pady=(0, 15))
        
        # 1. Connection Name field
        lbl_name = tk.Label(self.conn_form_frame, text="Nome da Conexão (Único):", font=("Segoe UI", 9, "bold"), fg="#475569")
        lbl_name.pack(anchor="w", pady=(0, 2))
        
        ent_name = ttk.Entry(self.conn_form_frame, font=("Segoe UI", 9))
        if is_edit:
            ent_name.insert(0, conn_name)
            ent_name.config(state="disabled") # Cannot edit connection name once created to preserve references
        elif prefilled_name:
            ent_name.insert(0, prefilled_name)
        ent_name.pack(fill="x", pady=(0, 10))
        self.conn_form_data["name"] = ent_name
        
        if not conn_type:
            # 2. Connection Type selection (Creation mode)
            lbl_type = tk.Label(self.conn_form_frame, text="Tipo de Conexão:", font=("Segoe UI", 9, "bold"), fg="#475569")
            lbl_type.pack(anchor="w", pady=(0, 2))
            
            cb_type = ttk.Combobox(self.conn_form_frame, values=["API", "PostgreSQL", "MySQL", "SQLite"], state="readonly")
            cb_type.pack(fill="x", pady=(0, 15))
            
            def on_type_select(event):
                sel_type = cb_type.get().lower()
                if sel_type == 'postgresql':
                    sel_type = 'postgres'
                typed_name = ent_name.get()
                self.show_connection_form(new_type=sel_type, prefilled_name=typed_name)
                
            cb_type.bind("<<ComboboxSelected>>", on_type_select)
            return
            
        # Draw specific form fields based on type
        self.conn_form_data["type"] = conn_type
        
        if conn_type == 'sqlite':
            lbl_path = tk.Label(self.conn_form_frame, text="Caminho do Arquivo SQLite (.db / .sqlite):", font=("Segoe UI", 9, "bold"), fg="#475569")
            lbl_path.pack(anchor="w", pady=(0, 2))
            
            path_frame = ttk.Frame(self.conn_form_frame)
            path_frame.pack(fill="x", pady=(0, 15))
            
            ent_path = ttk.Entry(path_frame, font=("Segoe UI", 9))
            ent_path.insert(0, conn_info.get("filepath", ""))
            ent_path.pack(side="left", fill="x", expand=True, padx=(0, 5))
            self.conn_form_data["filepath"] = ent_path
            
            def browse_db_file():
                fn = filedialog.askopenfilename(
                    filetypes=[("Bancos de Dados", "*.db;*.sqlite;*.sqlite3"), ("Todos os Arquivos", "*.*")],
                    title="Selecionar Banco SQLite"
                )
                if fn:
                    ent_path.delete(0, tk.END)
                    ent_path.insert(0, fn)
                    self.invalidate_connection()
                    
            btn_browse = tk.Button(
                path_frame, text="Procurar...", font=("Segoe UI", 9, "bold"),
                bg="#e2e8f0", fg="#475569", activebackground="#cbd5e1", activeforeground="#475569",
                bd=0, padx=10, cursor="hand2", command=browse_db_file
            )
            btn_browse.pack(side="right")
            
        elif conn_type in ['postgres', 'mysql']:
            # Database connection details: Host, Port, Database, User, Password
            grid_frame = ttk.Frame(self.conn_form_frame)
            grid_frame.pack(fill="x", pady=(0, 15))
            
            # Host
            lbl_host = tk.Label(grid_frame, text="Host:", font=("Segoe UI", 9, "bold"), fg="#475569")
            lbl_host.grid(row=0, column=0, sticky="w", pady=2, padx=(0, 5))
            ent_host = ttk.Entry(grid_frame, font=("Segoe UI", 9))
            ent_host.insert(0, conn_info.get("host", "localhost"))
            ent_host.grid(row=0, column=1, sticky="ew", pady=2, padx=(0, 10))
            self.conn_form_data["host"] = ent_host
            
            # Port
            default_port = "5432" if conn_type == 'postgres' else "3306"
            lbl_port = tk.Label(grid_frame, text="Porta:", font=("Segoe UI", 9, "bold"), fg="#475569")
            lbl_port.grid(row=0, column=2, sticky="w", pady=2, padx=(0, 5))
            ent_port = ttk.Entry(grid_frame, font=("Segoe UI", 9), width=8)
            ent_port.insert(0, conn_info.get("port", default_port))
            ent_port.grid(row=0, column=3, sticky="w", pady=2)
            self.conn_form_data["port"] = ent_port
            
            # Database
            lbl_db = tk.Label(grid_frame, text="Banco de Dados:", font=("Segoe UI", 9, "bold"), fg="#475569")
            lbl_db.grid(row=1, column=0, sticky="w", pady=2, padx=(0, 5))
            ent_db = ttk.Entry(grid_frame, font=("Segoe UI", 9))
            ent_db.insert(0, conn_info.get("database", ""))
            ent_db.grid(row=1, column=1, columnspan=3, sticky="ew", pady=2)
            self.conn_form_data["database"] = ent_db
            
            # User
            lbl_user = tk.Label(grid_frame, text="Usuário:", font=("Segoe UI", 9, "bold"), fg="#475569")
            lbl_user.grid(row=2, column=0, sticky="w", pady=2, padx=(0, 5))
            ent_user = ttk.Entry(grid_frame, font=("Segoe UI", 9))
            ent_user.insert(0, conn_info.get("user", ""))
            ent_user.grid(row=2, column=1, columnspan=3, sticky="ew", pady=2)
            self.conn_form_data["user"] = ent_user
            
            # Password
            lbl_pass = tk.Label(grid_frame, text="Senha:", font=("Segoe UI", 9, "bold"), fg="#475569")
            lbl_pass.grid(row=3, column=0, sticky="w", pady=2, padx=(0, 5))
            ent_pass = ttk.Entry(grid_frame, font=("Segoe UI", 9), show="*")
            ent_pass.insert(0, conn_info.get("password", ""))
            ent_pass.grid(row=3, column=1, columnspan=3, sticky="ew", pady=2)
            self.conn_form_data["password"] = ent_pass
            
            grid_frame.columnconfigure(1, weight=1)
            
        elif conn_type == 'api':
            # API endpoint configuration
            lbl_url = tk.Label(self.conn_form_frame, text="URL Base (ex: https://api.github.com):", font=("Segoe UI", 9, "bold"), fg="#475569")
            lbl_url.pack(anchor="w", pady=(0, 2))
            ent_url = ttk.Entry(self.conn_form_frame, font=("Segoe UI", 9))
            ent_url.insert(0, conn_info.get("base_url", ""))
            ent_url.pack(fill="x", pady=(0, 10))
            self.conn_form_data["base_url"] = ent_url
            
            lbl_headers = tk.Label(self.conn_form_frame, text="Headers Padrão (JSON):", font=("Segoe UI", 9, "bold"), fg="#475569")
            lbl_headers.pack(anchor="w", pady=(0, 2))
            ent_headers = ttk.Entry(self.conn_form_frame, font=("Segoe UI", 9))
            ent_headers.insert(0, conn_info.get("default_headers", ""))
            ent_headers.pack(fill="x", pady=(0, 10))
            self.conn_form_data["default_headers"] = ent_headers
            
            lbl_auth = tk.Label(self.conn_form_frame, text="Autenticação:", font=("Segoe UI", 9, "bold"), fg="#475569")
            lbl_auth.pack(anchor="w", pady=(0, 2))
            cb_auth = ttk.Combobox(self.conn_form_frame, values=["None", "Bearer Token", "Basic Auth", "API Key"], state="readonly")
            cb_auth.set(conn_info.get("auth_type", "None"))
            cb_auth.pack(fill="x", pady=(0, 10))
            self.conn_form_data["auth_type"] = cb_auth
            
            lbl_token = tk.Label(self.conn_form_frame, text="Token / Valor Auth:", font=("Segoe UI", 9, "bold"), fg="#475569")
            lbl_token.pack(anchor="w", pady=(0, 2))
            ent_token = ttk.Entry(self.conn_form_frame, font=("Segoe UI", 9))
            ent_token.insert(0, conn_info.get("auth_token", ""))
            ent_token.pack(fill="x", pady=(0, 15))
            self.conn_form_data["auth_token"] = ent_token
            
        # Action Buttons panel
        btn_frame = ttk.Frame(self.conn_form_frame)
        btn_frame.pack(fill="x", pady=10)
        
        # Save connection button (starts disabled)
        self.btn_save = tk.Button(
            btn_frame, text="💾 Salvar Conexão", font=("Segoe UI", 9, "bold"),
            bg="#cbd5e1", fg="#64748b", activebackground="#cbd5e1", activeforeground="#64748b",
            bd=0, padx=12, pady=6, cursor="arrow", command=self.save_connection_action,
            state="disabled"
        )
        self.btn_save.pack(side="left", padx=(0, 5))
        
        # Connect connection button
        self.btn_connect = tk.Button(
            btn_frame, text="🔌 Conectar", font=("Segoe UI", 9, "bold"),
            bg="#2563eb", fg="#ffffff", activebackground="#1d4ed8", activeforeground="#ffffff",
            bd=0, padx=12, pady=6, cursor="hand2", command=self.connect_connection_action
        )
        self.btn_connect.pack(side="left", padx=5)
        
        if is_edit:
            # Delete connection button
            btn_del = tk.Button(
                btn_frame, text="🗑️ Excluir", font=("Segoe UI", 9, "bold"),
                bg="#ef4444", fg="#ffffff", activebackground="#dc2626", activeforeground="#ffffff",
                bd=0, padx=12, pady=6, cursor="hand2", command=self.delete_connection_action
            )
            btn_del.pack(side="right", padx=5)

        # Bind changes to all inputs to automatically invalidate connection status
        def bind_changes(widget):
            if isinstance(widget, (tk.Entry, ttk.Entry, tk.Text, ttk.Combobox)):
                if widget != self.conn_form_data.get("name"):
                    if isinstance(widget, ttk.Combobox):
                        widget.bind("<<ComboboxSelected>>", self.invalidate_connection, add="+")
                    else:
                        widget.bind("<KeyRelease>", self.invalidate_connection, add="+")
            for child in widget.winfo_children():
                bind_changes(child)
        bind_changes(self.conn_form_frame)

    def invalidate_connection(self, event=None):
        self.temp_schema = None
        if hasattr(self, 'btn_save') and self.btn_save:
            self.btn_save.config(
                state="disabled",
                bg="#cbd5e1", fg="#64748b",
                activebackground="#cbd5e1", activeforeground="#64748b",
                cursor="arrow"
            )

    def save_connection_action(self):
        name_widget = self.conn_form_data.get("name")
        if not name_widget:
            return
            
        name = name_widget.get().strip()
        if not name:
            messagebox.showwarning("Aviso", "Por favor, defina um nome único para a conexão.")
            return
            
        conn_type = self.conn_form_data.get("type")
        config = {"type": conn_type}
        
        # Read form contents
        if conn_type == 'sqlite':
            config["filepath"] = self.conn_form_data["filepath"].get().strip()
        elif conn_type in ['postgres', 'mysql']:
            config["host"] = self.conn_form_data["host"].get().strip()
            config["port"] = self.conn_form_data["port"].get().strip()
            config["database"] = self.conn_form_data["database"].get().strip()
            config["user"] = self.conn_form_data["user"].get().strip()
            config["password"] = self.conn_form_data["password"].get().strip()
        elif conn_type == 'api':
            config["base_url"] = self.conn_form_data["base_url"].get().strip()
            config["default_headers"] = self.conn_form_data["default_headers"].get().strip()
            config["auth_type"] = self.conn_form_data["auth_type"].get()
            config["auth_token"] = self.conn_form_data["auth_token"].get().strip()
            
        if getattr(self, 'temp_schema', None) is not None:
            config["schema"] = self.temp_schema
        elif name in self.saved_connections and "schema" in self.saved_connections[name]:
            config["schema"] = self.saved_connections[name]["schema"]
            
        self.saved_connections[name] = config
        self.save_connections()
        self.log_message(f"Conexão '{name}' salva com sucesso.")
        messagebox.showinfo("Sucesso", f"Conexão '{name}' salva com sucesso!")
        
        self.populate_connections_list()
        self.conn_tree.selection_set(name)
        if hasattr(self, 'conn_window') and self.conn_window:
            self.conn_window.destroy()
            self.conn_window = None

    def delete_connection_action(self):
        selected = self.conn_tree.selection()
        if not selected:
            return
        name = selected[0]
        if messagebox.askyesno("Confirmar Exclusão", f"Tem certeza que deseja excluir a conexão '{name}'?"):
            if name in self.saved_connections:
                del self.saved_connections[name]
                self.save_connections()
                self.log_message(f"Conexão '{name}' excluída.")
                
            self.populate_connections_list()
            if hasattr(self, 'conn_window') and self.conn_window:
                self.conn_window.destroy()
                self.conn_window = None

    def connect_connection_action(self):
        conn_type = self.conn_form_data.get("type")
        config = {}
        
        # Read current unsaved form contents for testing
        if conn_type == 'sqlite':
            config["filepath"] = self.conn_form_data["filepath"].get().strip()
        elif conn_type in ['postgres', 'mysql']:
            config["host"] = self.conn_form_data["host"].get().strip()
            config["port"] = self.conn_form_data["port"].get().strip()
            config["database"] = self.conn_form_data["database"].get().strip()
            config["user"] = self.conn_form_data["user"].get().strip()
            config["password"] = self.conn_form_data["password"].get().strip()
        elif conn_type == 'api':
            config["base_url"] = self.conn_form_data["base_url"].get().strip()
            config["default_headers"] = self.conn_form_data["default_headers"].get().strip()
            config["auth_type"] = self.conn_form_data["auth_type"].get()
            config["auth_token"] = self.conn_form_data["auth_token"].get().strip()
            
        # Run test/schema fetch asynchronously to prevent UI freeze
        def run_connect():
            self.log_message(f"Conectando ao banco/servidor do tipo {conn_type.upper()}...")
            self.btn_connect.config(state="disabled", text="🔌 Conectando...")
            try:
                schema_info = {}
                if conn_type == 'sqlite':
                    schema_info = self.get_db_schema('sqlite', config)
                    status = "OK"
                elif conn_type == 'postgres':
                    schema_info = self.get_db_schema('postgres', config)
                    status = "OK"
                elif conn_type == 'mysql':
                    schema_info = self.get_db_schema('mysql', config)
                    status = "OK"
                elif conn_type == 'api':
                    res = self.run_api_request(config, "GET", "", "{}", "")
                    status = f"HTTP {res['status_code']}"
                    schema_info = {}
                    
                self.log_message(f"Conexão estabelecida com sucesso: {status}")
                
                def success_ui():
                    self.temp_schema = schema_info
                    self.btn_save.config(
                        state="normal",
                        bg="#10b981", fg="#ffffff",
                        activebackground="#059669", activeforeground="#ffffff",
                        cursor="hand2"
                    )
                    self.btn_connect.config(state="normal", text="🔌 Conectar")
                    
                    if conn_type in ['sqlite', 'postgres', 'mysql']:
                        num_tables = len(schema_info)
                        msg = f"Conectado com sucesso!\nCarregadas {num_tables} tabelas do banco de dados."
                    else:
                        msg = f"Conectado com sucesso!\nAPI respondendo com status: {status}"
                    messagebox.showinfo("Conexão Estabelecida", msg)
                    
                self.root.after(0, success_ui)
            except Exception as e:
                self.log_message(f"Falha na conexão: {str(e)}")
                
                def fail_ui():
                    self.temp_schema = None
                    self.btn_save.config(
                        state="disabled",
                        bg="#cbd5e1", fg="#64748b",
                        activebackground="#cbd5e1", activeforeground="#64748b",
                        cursor="arrow"
                    )
                    self.btn_connect.config(state="normal", text="🔌 Conectar")
                    messagebox.showerror("Falha na Conexão", f"Não foi possível conectar:\n{str(e)}")
                    
                self.root.after(0, fail_ui)
                
        threading.Thread(target=run_connect, daemon=True).start()
