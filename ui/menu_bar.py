"""
Menu bar — Application menu (Arquivo, Editar, Executar, Configurações).
"""
import tkinter as tk


class MenuBarMixin:
    """Mixin providing the menu bar UI."""

    def setup_menu_bar(self):
        self.menu_bar = tk.Menu(self.root)
        
        # Arquivo Menu
        file_menu = tk.Menu(self.menu_bar, tearoff=0)
        file_menu.add_command(label="Novo Fluxo", command=self.new_flow_action)
        file_menu.add_command(label="Abrir Fluxo...", command=self.load_flow_from_file)
        file_menu.add_command(label="Salvar", command=self.save_flow, accelerator="Ctrl+S")
        file_menu.add_command(label="Salvar Como...", command=self.save_flow_to_file)
        file_menu.add_separator()
        file_menu.add_command(label="Limpar Tudo", command=self.clear_flow)
        file_menu.add_command(label="Fechar Fluxo", command=self.close_flow)
        file_menu.add_separator()
        file_menu.add_command(label="Sair", command=self.root.quit)
        self.menu_bar.add_cascade(label="Arquivo", menu=file_menu)
        
        # Editar Menu
        edit_menu = tk.Menu(self.menu_bar, tearoff=0)
        edit_menu.add_command(label="Auto-Ajustar", command=self.auto_layout_nodes)
        edit_menu.add_command(label="Centralizar", command=self.center_view)
        self.menu_bar.add_cascade(label="Editar", menu=edit_menu)
        
        # Executar Menu
        run_menu = tk.Menu(self.menu_bar, tearoff=0)
        run_menu.add_command(label="Executar Fluxo", command=self.start_flow_execution)
        run_menu.add_command(label="Parar Execução", command=self.stop_flow_execution)
        self.menu_bar.add_cascade(label="Executar", menu=run_menu)
        
        # Configurações Button directly in menu bar
        self.menu_bar.add_command(label="Configurações", command=self.open_settings_dialog)
