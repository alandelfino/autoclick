"""
Start screen — Welcome screen with New Flow / Open Flow buttons.
"""
import tkinter as tk
from core.i18n_helper import t


class StartScreenMixin:
    """Mixin providing the start/welcome screen UI."""

    def setup_start_screen(self):
        self.start_frame = tk.Frame(self.root, bg="#0f172a")
        
        # Central card container
        card = tk.Frame(self.start_frame, bg="#1e293b", padx=45, pady=45, highlightbackground="#38bdf8", highlightthickness=1)
        card.place(relx=0.5, rely=0.5, anchor="center")
        
        # Icon
        logo_lbl = tk.Label(card, text="⚙️", font=("Segoe UI", 52), fg="#38bdf8", bg="#1e293b")
        logo_lbl.pack(pady=(0, 10))
        
        # App Title
        title_lbl = tk.Label(
            card, text="AutoClick Flow Builder Pro", font=("Segoe UI", 22, "bold"),
            fg="#f8fafc", bg="#1e293b"
        )
        title_lbl.pack(pady=(0, 5))
        
        # Description
        desc_lbl = tk.Label(
            card, text=t("start_screen.desc"), font=("Segoe UI", 10),
            fg="#94a3b8", bg="#1e293b"
        )
        desc_lbl.pack(pady=(0, 35))
        
        # Buttons frame
        btn_frame = tk.Frame(card, bg="#1e293b")
        btn_frame.pack(fill="x")
        
        new_btn = tk.Button(
            btn_frame, text=t("start_screen.new_flow"), font=("Segoe UI", 11, "bold"),
            bg="#10b981", fg="#ffffff", activebackground="#059669", activeforeground="#ffffff",
            bd=0, padx=25, pady=12, cursor="hand2", command=self.new_flow_action
        )
        new_btn.pack(side="left", padx=10, expand=True, fill="x")
        
        load_btn = tk.Button(
            btn_frame, text=t("start_screen.open_flow"), font=("Segoe UI", 11, "bold"),
            bg="#3b82f6", fg="#ffffff", activebackground="#2563eb", activeforeground="#ffffff",
            bd=0, padx=25, pady=12, cursor="hand2", command=self.load_flow_action
        )
        load_btn.pack(side="right", padx=10, expand=True, fill="x")
        
        # Version footer
        footer_lbl = tk.Label(card, text="v2.0.0 • AutoClick Engine", font=("Segoe UI", 8), fg="#475569", bg="#1e293b")
        footer_lbl.pack(pady=(35, 0))
        
        self.start_frame.pack(fill="both", expand=True)
