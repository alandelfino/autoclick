"""
Menu bar — Application menu (File, Edit, Run, Settings).
"""
import tkinter as tk
from core.i18n_helper import t, get_current_language, change_language
from tkinter import messagebox


class MenuBarMixin:
    """Mixin providing the menu bar UI."""

    def setup_menu_bar(self):
        self.menu_bar = tk.Menu(self.root)
        
        # File Menu (Arquivo)
        file_menu = tk.Menu(self.menu_bar, tearoff=0)
        file_menu.add_command(label=t("menu.file_new"), command=self.new_flow_action)
        file_menu.add_command(label=t("menu.file_open"), command=self.load_flow_from_file)
        file_menu.add_command(label=t("menu.file_save"), command=self.save_flow, accelerator="Ctrl+S")
        file_menu.add_command(label=t("menu.file_save_as"), command=self.save_flow_to_file)
        file_menu.add_separator()
        file_menu.add_command(label=t("menu.file_clear"), command=self.clear_flow)
        file_menu.add_command(label=t("menu.file_close"), command=self.close_flow)
        file_menu.add_separator()
        file_menu.add_command(label=t("menu.file_exit"), command=self.root.quit)
        self.menu_bar.add_cascade(label=t("menu.file"), menu=file_menu)
        
        # Edit Menu (Editar)
        edit_menu = tk.Menu(self.menu_bar, tearoff=0)
        edit_menu.add_command(label=t("menu.edit_auto_layout"), command=self.auto_layout_nodes)
        edit_menu.add_command(label=t("menu.edit_center"), command=self.center_view)
        self.menu_bar.add_cascade(label=t("menu.edit"), menu=edit_menu)
        
        # Run Menu (Executar)
        run_menu = tk.Menu(self.menu_bar, tearoff=0)
        run_menu.add_command(label=t("menu.run_start"), command=self.start_flow_execution)
        run_menu.add_command(label=t("menu.run_stop"), command=self.stop_flow_execution)
        self.menu_bar.add_cascade(label=t("menu.run"), menu=run_menu)
        
        # Settings Menu (Configurações)
        settings_menu = tk.Menu(self.menu_bar, tearoff=0)
        settings_menu.add_command(label=t("menu.settings_app_settings"), command=self.open_settings_dialog)
        
        # Language submenu
        lang_menu = tk.Menu(settings_menu, tearoff=0)
        lang_menu.add_command(label="English", command=lambda: self.change_lang_action("en"))
        lang_menu.add_command(label="Português", command=lambda: self.change_lang_action("pt"))
        settings_menu.add_cascade(label=t("menu.settings_language"), menu=lang_menu)
        
        self.menu_bar.add_cascade(label=t("menu.settings"), menu=settings_menu)

    def change_lang_action(self, lang):
        if get_current_language() != lang:
            change_language(lang)
            messagebox.showinfo(t("messages.info"), t("messages.restart_prompt"))
