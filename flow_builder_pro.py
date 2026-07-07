"""
AutoClick Visual Flow Editor - Profissional
============================================

Main application entry point. The FlowBuilderProApp class composes
functionality from multiple UI mixins and connector mixins.
"""

# Enable High-DPI awareness on Windows before importing tkinter
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(2) # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import copy
import threading
import time
import re

# --- Models ---
from models.node import VisualNode
from models.connection import VisualConnection
from core.i18n_helper import t

# --- Connectors (Mixins) ---
from connectors.database import DatabaseMixin
from connectors.api import ApiMixin

# --- UI Mixins ---
from ui.start_screen import StartScreenMixin
from ui.left_panel import LeftPanelMixin
from ui.menu_bar import MenuBarMixin
from ui.canvas_panel import CanvasPanelMixin
from ui.canvas_interactions import CanvasInteractionsMixin
from ui.node_config_window import NodeConfigWindowMixin
from ui.properties_panel import PropertiesPanelMixin
from ui.coordinate_capture import CoordinateCaptureMixin
from ui.connections_tab import ConnectionsTabMixin
from ui.connection_dialogs import ConnectionDialogsMixin
from ui.tray_icon import TrayIconMixin


class FlowBuilderProApp(
    # Connectors
    DatabaseMixin,
    ApiMixin,
    # UI Mixins
    StartScreenMixin,
    LeftPanelMixin,
    MenuBarMixin,
    CanvasPanelMixin,
    CanvasInteractionsMixin,
    NodeConfigWindowMixin,
    PropertiesPanelMixin,
    CoordinateCaptureMixin,
    ConnectionsTabMixin,
    ConnectionDialogsMixin,
    TrayIconMixin,
):
    def __init__(self, root):
        self.root = root
        self.root.title(t("app.title"))
        
        # Maximized full size
        try:
            self.root.state('zoomed')
        except Exception:
            # Fallback
            screen_width = root.winfo_screenwidth()
            screen_height = root.winfo_screenheight()
            window_height = int(screen_height * 0.82)
            root.geometry(f"{screen_width}x{window_height}+0+40")
        
        # Data storage
        self.nodes = {}
        self.connections = []
        self.node_counter = 0
        self.selected_node = None
        self.selected_nodes = set()
        self.is_running = False
        self.is_paused = False
        self.tray_icon = None
        self.zoom_scale = 1.0
        self.is_panning_with_ctrl = False
        self.execution_history = {}
        self.last_run_payload = {}
        self.active_text_widget = None
        self.current_filepath = None
        
        # Undo/Redo stacks
        self.undo_stack = []
        self.redo_stack = []
        self.is_undo_redo_or_loading = False
        
        # GUI Interaction states
        self.drag_data = {'x': 0, 'y': 0}
        self.active_port_drag = None  # (source_node, source_port_name)
        self.temp_line_id = None
        self.marquee_data = None  # For marquee/lasso selection
        self.marquee_rect_id = None
        self.load_connections()
        
        self.setup_ui()
        
        # Push initial state to undo stack
        self.undo_stack.append(self.serialize_flow())
        
        # Root keyboard shortcuts
        self.root.bind("<Control-s>", lambda event: self.save_flow())
        self.root.bind("<Control-S>", lambda event: self.save_flow())
        self.root.bind("<Control-z>", lambda event: self.undo_action())
        self.root.bind("<Control-Z>", lambda event: self.undo_action())
        self.root.bind("<Control-y>", lambda event: self.redo_action())
        self.root.bind("<Control-Y>", lambda event: self.redo_action())

    def setup_ui(self):
        # Main Layout Styling
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Dark panel style
        self.style.configure("Dark.TFrame", background="#0f172a")
        self.style.configure("Light.TFrame", background="#f8fafc")
        
        self.center_panel = ttk.Frame(self.root)
        
        # Create Topbar frame (not packed yet)
        self.top_bar = tk.Frame(self.root, bg="#0f172a", height=55)
        self.top_bar.pack_propagate(False)
        
        # Logo / Title in Topbar
        self.logo_label = tk.Label(
            self.top_bar, text="⚙️ AUTOCLICK PRO", font=("Segoe UI", 13, "bold"),
            fg="#38bdf8", bg="#0f172a"
        )
        self.logo_label.pack(side="left", padx=20, pady=10)
        
        # Run button inside Topbar
        self.run_btn = tk.Button(
            self.top_bar, text="▶ EXECUTAR FLUXO", font=("Segoe UI", 9, "bold"),
            bg="#22c55e", fg="#ffffff", activebackground="#16a34a", activeforeground="#ffffff",
            bd=0, padx=15, pady=6, cursor="hand2", command=self.start_flow_execution
        )
        self.run_btn.pack(side="right", padx=15, pady=10)
        
        # Stop button inside Topbar
        self.stop_btn = tk.Button(
            self.top_bar, text="■ PARAR", font=("Segoe UI", 9, "bold"),
            bg="#ef4444", fg="#ffffff", activebackground="#dc2626", activeforeground="#ffffff",
            bd=0, padx=15, pady=6, cursor="hand2", state="disabled", command=self.stop_flow_execution
        )
        self.stop_btn.pack(side="right", padx=(5, 10), pady=10)
        
        # Initialize node window references as None
        self.node_window = None
        self.properties_container = None
        self.input_payload_container = None
        self.output_payload_container = None
        
        # Draw center panel (includes notebook and tabs)
        self.setup_center_panel()
        
        # Initialize left panel (sidebar) inside self.tab_flow
        self.left_panel = ttk.Frame(self.tab_flow, style="Dark.TFrame", width=250)
        self.left_panel.pack_propagate(False)
        
        # Draw left panel contents (toolbox and console logs)
        self.setup_left_panel()
        
        # Pack left panel to the left of the flow tab
        self.left_panel.pack(side="left", fill="y")
        
        # Pack the canvas to fill the remaining space of the flow tab
        self.canvas.pack(side="right", fill="both", expand=True)
        
        # Initialize slide panel (collapsible nodes sidebar)
        self.slide_panel = tk.Frame(self.tab_flow, width=280, bg="#0f172a", bd=1, relief="solid")
        self.slide_panel.place(relx=1.0, x=0, y=0, relheight=1.0, anchor="nw")
        self.setup_slide_panel()
        
        # Setup top menu (not configured on root yet)
        self.setup_menu_bar()
        
        # Setup start/welcome screen
        self.setup_start_screen()

    # --- Logging ---

    def log_message(self, message):
        """Append thread-safe logs into the side text panel."""
        # Prevent UI freezing/lag from extremely large messages (e.g. massive DB rows or API responses)
        max_log_len = 2000
        if len(message) > max_log_len:
            message = message[:max_log_len] + "... (truncated due to size)"

        def append():
            self.log_text.config(state="normal")
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state="disabled")
            
            if getattr(self, 'expanded_log_text', None) and self.expanded_log_text.winfo_exists():
                self.expanded_log_text.config(state="normal")
                self.expanded_log_text.insert(tk.END, message + "\n")
                self.expanded_log_text.see(tk.END)
                self.expanded_log_text.config(state="disabled")
        self.root.after(0, append)

    # --- Flow Actions (Start Screen, New, Load, Close, Save) ---

    def new_flow_action(self):
        self.start_frame.pack_forget()
        self.top_bar.pack(side="top", fill="x")
        self.center_panel.pack(side="bottom", fill="both", expand=True)
        self.root.config(menu=self.menu_bar)
        
        self.clear_flow(ask=False, recreate_start=True)
        self.current_filepath = None
        self.root.update()
        self.draw_grid()

    def load_flow_action(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("Arquivos de Fluxo", "*.flow"), ("Todos os Arquivos", "*.*")],
            title="Carregar Fluxo Local"
        )
        if not filepath:
            return
            
        self.start_frame.pack_forget()
        self.top_bar.pack(side="top", fill="x")
        self.center_panel.pack(side="bottom", fill="both", expand=True)
        self.root.config(menu=self.menu_bar)
        self.root.update()
        
        self.load_flow_from_filepath(filepath)

    def close_flow(self):
        if messagebox.askyesno(t("menu.file_close"), t("messages.confirm_close")):
            self.clear_flow(ask=False, recreate_start=False)
            self.current_filepath = None
            
            # Hide panels
            self.top_bar.pack_forget()
            self.center_panel.pack_forget()
            
            # Hide menu
            self.root.config(menu="")
            
            # Show start frame
            self.start_frame.pack(fill="both", expand=True)

    def save_flow(self):
        if getattr(self, 'current_filepath', None):
            self.save_flow_to_filepath(self.current_filepath)
        else:
            self.save_flow_to_file()

    def save_flow_to_filepath(self, filepath, show_popup=False):
        try:
            flow_data = {
                'nodes': [],
                'connections': [],
                'saved_connections': getattr(self, 'saved_connections', {}),
                'zoom_scale': getattr(self, 'zoom_scale', 1.0),
                'scroll_x': self.canvas.canvasx(0),
                'scroll_y': self.canvas.canvasy(0)
            }
            
            for n in self.nodes.values():
                flow_data['nodes'].append({
                    'id': n.id,
                    'type': n.type,
                    'name': n.name,
                    'x': n.x,
                    'y': n.y,
                    'properties': n.properties
                })
                
            for c in self.connections:
                flow_data['connections'].append({
                    'source_id': c.source.id,
                    'source_port': c.source_port,
                    'target_id': c.target.id,
                    'target_port': c.target_port,
                    'waypoints': [],
                    'is_auto_loop': getattr(c, 'is_auto_loop', False),
                    'offset_source_override': getattr(c, 'offset_source_override', None),
                    'offset_target_override': getattr(c, 'offset_target_override', None),
                    'mid_y_override': getattr(c, 'mid_y_override', None)
                })
                
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(flow_data, f, indent=4, ensure_ascii=False)
                
            self.current_filepath = filepath
            self.log_message(t("messages.save_success").format(filepath))
            if show_popup:
                messagebox.showinfo(t("messages.success"), t("messages.save_success").format(filepath))
        except Exception as e:
            self.log_message(f"{t('messages.error_save').format(str(e))}")
            messagebox.showerror(t("messages.error"), f"{t('messages.error_save').format(str(e))}")

    def trigger_auto_save(self):
        # Record state for undo/redo
        self.push_undo()
        
        if getattr(self, 'is_undo_redo_or_loading', False):
            return
            
        if not getattr(self, 'auto_save_var', None) or not self.auto_save_var.get():
            return
        if not getattr(self, 'current_filepath', None):
            return
            
        if getattr(self, '_auto_save_timer', None) is not None:
            try:
                self.root.after_cancel(self._auto_save_timer)
            except Exception:
                pass
                
        def perform_auto_save():
            self._auto_save_timer = None
            if getattr(self, 'current_filepath', None):
                self.save_flow_to_filepath(self.current_filepath, show_popup=False)
                
        self._auto_save_timer = self.root.after(1500, perform_auto_save)

    def serialize_flow(self):
        flow_data = {
            'nodes': [],
            'connections': [],
            'saved_connections': copy.deepcopy(getattr(self, 'saved_connections', {})),
            'zoom_scale': getattr(self, 'zoom_scale', 1.0),
            'scroll_x': self.canvas.canvasx(0),
            'scroll_y': self.canvas.canvasy(0)
        }
        for n in self.nodes.values():
            flow_data['nodes'].append({
                'id': n.id,
                'type': n.type,
                'name': n.name,
                'x': n.x,
                'y': n.y,
                'properties': copy.deepcopy(n.properties)
            })
        for c in self.connections:
            flow_data['connections'].append({
                'source_id': c.source.id,
                'source_port': c.source_port,
                'target_id': c.target.id,
                'target_port': c.target_port,
                'waypoints': [],
                'is_auto_loop': getattr(c, 'is_auto_loop', False),
                'offset_source_override': getattr(c, 'offset_source_override', None),
                'offset_target_override': getattr(c, 'offset_target_override', None),
                'mid_y_override': getattr(c, 'mid_y_override', None)
            })
        return flow_data

    def deserialize_flow(self, flow_data):
        self.clear_flow(ask=False, recreate_start=False)
        self.saved_connections = copy.deepcopy(flow_data.get('saved_connections', {}))
        if hasattr(self, 'populate_connections_list'):
            self.populate_connections_list()
            
        self.zoom_scale = flow_data.get('zoom_scale', 1.0)
        
        max_id = 0
        for node_data in flow_data.get('nodes', []):
            nid = node_data['id']
            self.create_node(
                node_type=node_data['type'],
                name=node_data['name'],
                x=node_data['x'],
                y=node_data['y'],
                properties=copy.deepcopy(node_data['properties']),
                is_canvas_coords=True,
                node_id=nid
            )
            if nid > max_id:
                max_id = nid
        self.node_counter = max_id
        
        for conn_data in flow_data.get('connections', []):
            src_node = self.nodes.get(conn_data['source_id'])
            tgt_node = self.nodes.get(conn_data['target_id'])
            if src_node and tgt_node:
                new_conn = VisualConnection(
                    self.canvas, 
                    src_node, 
                    conn_data['source_port'], 
                    tgt_node, 
                    conn_data['target_port']
                )
                new_conn.is_auto_loop = conn_data.get('is_auto_loop', False)
                new_conn.offset_source_override = conn_data.get('offset_source_override')
                new_conn.offset_target_override = conn_data.get('offset_target_override')
                new_conn.mid_y_override = conn_data.get('mid_y_override')
                self.connections.append(new_conn)
                
        start_exists = any(n.type == 'start' for n in self.nodes.values())
        if not start_exists:
            self.create_start_node()
            
        # Restore viewport scroll position
        saved_x = flow_data.get('scroll_x', 0.0)
        saved_y = flow_data.get('scroll_y', 0.0)
        cur_x = self.canvas.canvasx(0)
        cur_y = self.canvas.canvasy(0)
        self.canvas.scan_mark(0, 0)
        self.canvas.scan_dragto(int(cur_x - saved_x), int(cur_y - saved_y), gain=1)
        
        self.select_node(None)
        self.draw_grid()

    def push_undo(self):
        if getattr(self, 'is_undo_redo_or_loading', False):
            return
            
        state = self.serialize_flow()
        
        # Avoid pushing identical consecutive states
        if self.undo_stack and self.undo_stack[-1] == state:
            return
            
        self.undo_stack.append(state)
        if len(self.undo_stack) > 21:
            self.undo_stack.pop(0)
            
        self.redo_stack.clear()

    def undo_action(self):
        if len(self.undo_stack) > 1:
            self.is_undo_redo_or_loading = True
            try:
                # Pop current state and push to redo stack
                current_state = self.undo_stack.pop()
                self.redo_stack.append(current_state)
                
                # Load the previous state
                prev_state = self.undo_stack[-1]
                self.deserialize_flow(prev_state)
                
                self.log_message("Desfazer (Undo) realizado.")
                
                # Perform auto save if enabled
                if getattr(self, 'auto_save_var', None) and self.auto_save_var.get() and getattr(self, 'current_filepath', None):
                    self.save_flow_to_filepath(self.current_filepath, show_popup=False)
            finally:
                self.is_undo_redo_or_loading = False

    def redo_action(self):
        if self.redo_stack:
            self.is_undo_redo_or_loading = True
            try:
                # Pop state from redo stack and push to undo stack
                next_state = self.redo_stack.pop()
                self.undo_stack.append(next_state)
                
                # Load this state
                self.deserialize_flow(next_state)
                
                self.log_message("Refazer (Redo) realizado.")
                
                # Perform auto save if enabled
                if getattr(self, 'auto_save_var', None) and self.auto_save_var.get() and getattr(self, 'current_filepath', None):
                    self.save_flow_to_filepath(self.current_filepath, show_popup=False)
            finally:
                self.is_undo_redo_or_loading = False

    def expand_log_console(self):
        # If already open, raise/focus it
        if getattr(self, 'expanded_log_win', None) and self.expanded_log_win.winfo_exists():
            self.expanded_log_win.deiconify()
            self.expanded_log_win.focus_force()
            return
            
        self.expanded_log_win = tk.Toplevel(self.root)
        self.expanded_log_win.title(t("toolbox.debug_console"))
        self.expanded_log_win.geometry("800x600")
        self.expanded_log_win.configure(bg="#0f172a")
        
        # Frame for top bar/controls
        control_frame = tk.Frame(self.expanded_log_win, bg="#0f172a")
        control_frame.pack(fill="x", padx=10, pady=10)
        
        title_label = tk.Label(
            control_frame, text=t("toolbox.debug_console"), font=("Segoe UI", 12, "bold"),
            fg="#38bdf8", bg="#0f172a"
        )
        title_label.pack(side="left")
        
        clear_btn = tk.Button(
            control_frame, text=t("canvas.clear"), font=("Segoe UI", 9, "bold"),
            bg="#ef4444", fg="#ffffff", activebackground="#dc2626", activeforeground="#ffffff",
            bd=0, padx=10, pady=5, cursor="hand2", command=self.clear_expanded_log
        )
        clear_btn.pack(side="right", padx=5)
        
        # Text widget + Scrollbar
        text_frame = tk.Frame(self.expanded_log_win, bg="#1e293b")
        text_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")
        
        self.expanded_log_text = tk.Text(
            text_frame, bg="#1e293b", fg="#e2e8f0", bd=0,
            font=("Consolas", 10), wrap="word", yscrollcommand=scrollbar.set
        )
        self.expanded_log_text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.expanded_log_text.yview)
        
        # Populate text widget with current contents of the main log
        main_log_content = self.log_text.get(1.0, tk.END).strip()
        if main_log_content:
            self.expanded_log_text.insert(tk.END, main_log_content + "\n")
            
        self.expanded_log_text.see(tk.END)
        self.expanded_log_text.config(state="disabled")

    def clear_expanded_log(self):
        # Clear main log
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state="disabled")
        
        # Clear expanded log
        if getattr(self, 'expanded_log_text', None) and self.expanded_log_text.winfo_exists():
            self.expanded_log_text.config(state="normal")
            self.expanded_log_text.delete(1.0, tk.END)
            self.expanded_log_text.config(state="disabled")

    def save_flow_to_file(self):
        filepath = filedialog.asksaveasfilename(
            defaultextension=".flow",
            filetypes=[("Flow Files", "*.flow"), ("All Files", "*.*")],
            title=t("menu.file_save_as")
        )
        if not filepath:
            return
        self.save_flow_to_filepath(filepath)

    def load_flow_from_file(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("Flow Files", "*.flow"), ("All Files", "*.*")],
            title=t("menu.file_open")
        )
        if not filepath:
            return
        self.load_flow_from_filepath(filepath)

    def load_flow_from_filepath(self, filepath):
        self.is_undo_redo_or_loading = True
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                flow_data = json.load(f)
                
            self.clear_flow(ask=False, recreate_start=False)
            
            # Load saved connections local to flow
            self.saved_connections = flow_data.get('saved_connections', {})
            if hasattr(self, 'populate_connections_list'):
                self.populate_connections_list()
                
            self.zoom_scale = flow_data.get('zoom_scale', 1.0)
            
            max_id = 0
            for node_data in flow_data.get('nodes', []):
                nid = node_data['id']
                self.create_node(
                    node_type=node_data['type'],
                    name=node_data['name'],
                    x=node_data['x'],
                    y=node_data['y'],
                    properties=node_data['properties'],
                    is_canvas_coords=True,
                    node_id=nid
                )
                if nid > max_id:
                    max_id = nid
                    
            self.node_counter = max_id
            
            for conn_data in flow_data.get('connections', []):
                src_node = self.nodes.get(conn_data['source_id'])
                tgt_node = self.nodes.get(conn_data['target_id'])
                
                if src_node and tgt_node:
                    new_conn = VisualConnection(
                        self.canvas, 
                        src_node, 
                        conn_data['source_port'], 
                        tgt_node, 
                        conn_data['target_port']
                    )
                    new_conn.is_auto_loop = conn_data.get('is_auto_loop', False)
                    new_conn.offset_source_override = conn_data.get('offset_source_override')
                    new_conn.offset_target_override = conn_data.get('offset_target_override')
                    new_conn.mid_y_override = conn_data.get('mid_y_override')
                    self.connections.append(new_conn)
                    
            start_exists = any(n.type == 'start' for n in self.nodes.values())
            if not start_exists:
                self.create_start_node()
                
            self.current_filepath = filepath
            
            # Restore viewport scroll position
            saved_x = flow_data.get('scroll_x', 0.0)
            saved_y = flow_data.get('scroll_y', 0.0)
            cur_x = self.canvas.canvasx(0)
            cur_y = self.canvas.canvasy(0)
            self.canvas.scan_mark(0, 0)
            self.canvas.scan_dragto(int(cur_x - saved_x), int(cur_y - saved_y), gain=1)
            
            self.log_message(t("messages.success") + f": {filepath}")
            self.select_node(None)
            self.draw_grid()
            
            # Reset undo/redo stacks for the newly loaded flow
            self.undo_stack = [self.serialize_flow()]
            self.redo_stack = []
            
        except Exception as e:
            self.log_message(f"{t('messages.error_load').format(str(e))}")
            messagebox.showerror(t("messages.error"), f"{t('messages.error_load').format(str(e))}")
        finally:
            self.is_undo_redo_or_loading = False

    # --- Node Creation and Management ---

    def create_node(self, node_type, name=None, x=150, y=120, properties=None, is_canvas_coords=False, node_id=None):
        if node_id is None:
            self.node_counter += 1
            node_id = self.node_counter
        else:
            self.node_counter = max(self.node_counter, node_id)
        
        if is_canvas_coords:
            cx = x
            cy = y
        else:
            # Convert visible screen coordinates (x, y) to canvas coordinates
            cx = self.canvas.canvasx(x)
            cy = self.canvas.canvasy(y)
        
        if not name:
            default_names = {
                'start': "Início",
                'click': f"Clique Coord {node_id}",
                'capture': f"Capturar Dados {node_id}",
                'condition': f"Condicional {node_id}",
                'key': f"Press Tecla {node_id}",
                'type_text': f"Digitar Texto {node_id}",
                'delay': f"Delay {node_id}",
                'move_mouse': f"Mover Cursor {node_id}",
                'postgres': f"PostgreSQL {node_id}",
                'mysql': f"MySQL {node_id}",
                'sqlite': f"SQLite {node_id}",
                'api': f"API Requisição {node_id}",
                'confirm_dialog': f"Confirmar {node_id}",
                'alert_dialog': f"Alerta {node_id}",
                'js': f"JS Código {node_id}",
                'python': f"Python Código {node_id}"
            }
            name = default_names.get(node_type, f"Nó {node_id}")
            
        new_node = VisualNode(self.canvas, node_id, node_type, name, cx, cy, properties)
        
        # Scale newly created node to match current zoom scale
        if self.zoom_scale != 1.0:
            self.canvas.scale(new_node.tag, cx, cy, self.zoom_scale, self.zoom_scale)
            for p in new_node.ports.values():
                self.canvas.scale(p['tag'], cx, cy, self.zoom_scale, self.zoom_scale)
            new_node.width *= self.zoom_scale
            new_node.height *= self.zoom_scale
            new_node.scale_fonts(self.zoom_scale)
            
        self.nodes[node_id] = new_node
        
        # Auto select the newly created node
        self.select_node(new_node)
        self.trigger_auto_save()
        return new_node

    def create_start_node(self):
        for n in list(self.nodes.values()):
            if n.type == 'start':
                return n
        return self.create_node('start', name="Início do Fluxo", x=80, y=200)

    def select_node(self, node):
        old_selected = self.selected_node
        self.selected_node = node
        
        # Clear multi-selection when selecting a single node normally
        if hasattr(self, 'selected_nodes') and self.selected_nodes:
            old_multi = list(self.selected_nodes)
            self.selected_nodes.clear()  # Clear first, so update_outline sees them as not multi-selected
            for n in old_multi:
                n.update_outline()
        
        if old_selected:
            old_selected.select(False)
            
        if node:
            node.select(True)
        else:
            if hasattr(self, 'node_window') and self.node_window:
                try:
                    self.node_window.destroy()
                except Exception:
                    pass
                self.node_window = None
                self.properties_container = None
                self.input_payload_container = None
                self.output_payload_container = None
            self.show_no_node_selected_message()

    def clear_multi_selection(self):
        """Clear all multi-selected nodes and refresh their outlines."""
        if hasattr(self, 'selected_nodes') and self.selected_nodes:
            old_multi = list(self.selected_nodes)
            self.selected_nodes.clear()  # Clear first
            for n in old_multi:
                n.update_outline()

    def toggle_node_multi_select(self, node):
        """Toggle a node in/out of the multi-selection set (Ctrl+Click)."""
        if node in self.selected_nodes:
            self.selected_nodes.discard(node)
        else:
            self.selected_nodes.add(node)
        # Also add current single-selected node to the set if it exists
        if self.selected_node and self.selected_node not in self.selected_nodes:
            self.selected_nodes.add(self.selected_node)
        self.selected_node = None
        # Refresh all outlines
        for n in self.nodes.values():
            n.update_outline()

    def delete_node_by_ref(self, node):
        if node.type == 'start':
            return
        if messagebox.askyesno(t("messages.warning"), f"{t('canvas.context_delete')} '{node.name}'?"):
            node_id = node.id
            if self.selected_node == node:
                self.close_node_window()
            conns_to_remove = [c for c in self.connections if c.source.id == node_id or c.target.id == node_id]
            for conn in conns_to_remove:
                conn.delete()
                self.connections.remove(conn)
            node.delete()
            if node_id in self.nodes:
                del self.nodes[node_id]
            self.log_message(f"Node {node_id} ('{node.name}') removed.")
            self.trigger_auto_save()

    def delete_multiple_nodes(self, nodes_to_delete):
        # Filter out the start node as it cannot be deleted
        nodes_to_delete = [n for n in nodes_to_delete if n.type != 'start']
        if not nodes_to_delete:
            return
            
        title = t("messages.warning") or "Aviso"
        msg = (t("messages.confirm_delete_nodes") or "Deseja realmente excluir os {} nós selecionados?").format(len(nodes_to_delete))
        if messagebox.askyesno(title, msg):
            if self.selected_node in nodes_to_delete:
                self.close_node_window()
                self.selected_node = None
                
            node_ids = {n.id for n in nodes_to_delete}
            
            # Find and remove connections linked to any of these nodes
            conns_to_remove = [c for c in self.connections if c.source.id in node_ids or c.target.id in node_ids]
            for conn in conns_to_remove:
                conn.delete()
                if conn in self.connections:
                    self.connections.remove(conn)
            
            # Delete nodes
            for node in nodes_to_delete:
                node.delete()
                if node.id in self.nodes:
                    del self.nodes[node.id]
                if hasattr(self, 'selected_nodes') and node in self.selected_nodes:
                    self.selected_nodes.discard(node)
            
            self.select_node(None)
            self.log_message(f"{len(nodes_to_delete)} nós removidos.")
            self.trigger_auto_save()

    def delete_node_from_config(self):
        if not self.selected_node:
            return
        self.delete_node_by_ref(self.selected_node)

    def delete_selected_node(self):
        if not self.selected_node:
            messagebox.showwarning(t("messages.warning"), "Please select a node to delete.")
            return
            
        node = self.selected_node
        if node.type == 'start':
            messagebox.showwarning(t("messages.warning"), "The Start node cannot be deleted.")
            return
            
        node_id = node.id
        
        # Remove all connections linked to this node
        conns_to_remove = [c for c in self.connections if c.source.id == node_id or c.target.id == node_id]
        for conn in conns_to_remove:
            conn.delete()
            self.connections.remove(conn)
            
        # Delete visual node elements
        node.delete()
        del self.nodes[node_id]
        
        self.select_node(None)
        self.log_message(f"Node {node_id} successfully removed.")
        self.trigger_auto_save()

    def clear_flow(self, ask=True, recreate_start=True):
        if ask and not messagebox.askyesno(t("messages.warning"), t("messages.confirm_clear")):
            return
            
        for node in list(self.nodes.values()):
            node.delete()
        for conn in list(self.connections):
            conn.delete()
            
        self.nodes.clear()
        self.connections.clear()
        self.node_counter = 0
        self.zoom_scale = 1.0
        self.select_node(None)
        
        # Reset local saved connections
        self.saved_connections = {}
        if hasattr(self, 'populate_connections_list'):
            self.populate_connections_list()
        
        # Clear log console
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state="disabled")
        
        if recreate_start:
            self.create_start_node()
            
        self.log_message("Canvas cleared. New flow started.")
        self.draw_grid()
        
        if not getattr(self, 'is_undo_redo_or_loading', False):
            self.undo_stack = [self.serialize_flow()]
            self.redo_stack = []

    # --- Flow Execution Engine (Async Execution Thread) ---

    def start_flow_execution(self):
        if self.is_running:
            return
            
        if not self.nodes:
            messagebox.showwarning(t("messages.warning"), "No nodes in canvas to execute.")
            return
            
        # 1. Check loop unconnected nodes
        unconnected_loops = self.check_unconnected_loop_nodes()
        if unconnected_loops:
            msg_lines = []
            for loop_node, nodes_list in unconnected_loops.items():
                unique_nodes = list(dict.fromkeys(nodes_list))
                nodes_str = "\n".join(f"  * {name}" for name in unique_nodes)
                msg_lines.append(f"- Loop '{loop_node.name}':\n{nodes_str}")
            
            formatted_list = "\n\n".join(msg_lines)
            warning_msg = t("messages.loop_unconnected_nodes_warning").format(formatted_list)
            
            if not messagebox.askyesno(t("messages.warning"), warning_msg):
                return
        else:
            # Ask for standard confirmation
            if not messagebox.askyesno("Confirm Execution", "Do you really want to start executing the flow?"):
                return
            
        # 2. Check countdown config
        countdown_secs = self.countdown_seconds_var.get()
        if countdown_secs > 0:
            self.show_countdown_splash(countdown_secs)
        else:
            self.proceed_with_flow_execution()

    def show_countdown_splash(self, seconds):
        splash = tk.Toplevel(self.root)
        splash.wm_overrideredirect(True)
        splash.attributes("-topmost", True)
        
        # Center splash
        w, h = 280, 280
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        splash.geometry(f"{w}x{h}+{x}+{y}")
        splash.configure(bg="#0f172a")
        
        lbl_title = tk.Label(
            splash, text="PREPARANDO EXECUÇÃO", 
            font=("Segoe UI", 10, "bold"), fg="#3b82f6", bg="#0f172a"
        )
        lbl_title.pack(pady=(40, 10))
        
        lbl_num = tk.Label(
            splash, text=str(seconds), 
            font=("Segoe UI", 80, "bold"), fg="#ffffff", bg="#0f172a"
        )
        lbl_num.pack()
        
        lbl_sub = tk.Label(
            splash, text="Iniciando...", 
            font=("Segoe UI", 10), fg="#94a3b8", bg="#0f172a"
        )
        lbl_sub.pack(pady=(10, 0))
        
        def count_down(current_val):
            if current_val > 1:
                new_val = current_val - 1
                lbl_num.config(text=str(new_val))
                splash.after(1000, lambda: count_down(new_val))
            else:
                splash.destroy()
                self.proceed_with_flow_execution()
                
        splash.after(1000, lambda: count_down(seconds))

    def proceed_with_flow_execution(self):
        # Find start node
        start_node = None
        for n in self.nodes.values():
            if n.type == 'start':
                start_node = n
                break
                
        if not start_node:
            start_node = self.create_start_node()
            
        self.log_message(f"Starting execution of the flow from the start node: '{start_node.name}'")

        # Determine loop configuration
        loop_mode = start_node.properties.get('loop_mode', 'Run once')
        loop_count_val = start_node.properties.get('loop_count', 5)
        if loop_mode in ["Executar 1 vez", "Run once"]:
            max_runs = 1
        elif loop_mode in ["Executar N vezes", "Run N times"]:
            try:
                max_runs = int(loop_count_val)
            except ValueError:
                max_runs = 1
        else:
            max_runs = -1  # Infinite

        # Set running state UI
        self.is_running = True
        self.is_paused = False
        self.run_btn.config(state="disabled", text=f"⚡ {t('menu.run_start').upper()}...")
        self.stop_btn.config(state="normal")
        
        # System Tray icon integration
        if self.hide_window_var.get():
            self.root.after(100, self.root.withdraw)
            self.create_tray_icon()

        # Start background executor thread
        self.exec_thread = threading.Thread(target=self.run_flow_thread, args=(start_node, max_runs))
        self.exec_thread.daemon = True
        self.exec_thread.start()

    def stop_flow_execution(self):
        if not self.is_running:
            return
        self.is_running = False
        self.is_paused = False
        self.log_message(">> Stop request received. Interrupting flow...")

    def toggle_pause(self):
        if not self.is_running:
            return
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.log_message(">> EXECUTION PAUSADA. Press [Ctrl+P] to resume.")
            self.root.after(0, lambda: self.run_btn.config(text="⏸ PAUSED"))
        else:
            self.log_message(">> EXECUTION RESUMED.")
            self.root.after(0, lambda: self.run_btn.config(text=f"⚡ {t('menu.run_start').upper()}..."))

    def run_flow_thread(self, start_node, max_runs):
        payload = {}
        self.current_run = 0
        self.max_runs = max_runs
        self.log_message("=== STARTING FLOW EXECUTION ===")
        self.log_message(f"Initial Payload: {json.dumps(payload)}")
        
        self.start_hotkey_listener()
        last_node = None
        
        try:
            while self.is_running:
                self.current_run += 1
                current_run = self.current_run
                if max_runs != -1 and current_run > max_runs:
                    break
                    
                self.log_message(f"--- Round {current_run} " + (f"of {max_runs}" if max_runs != -1 else "(Infinite Loop)") + " ---")
                
                current_node = start_node
                while current_node and self.is_running:
                    # Handle execution pause state
                    while self.is_paused and self.is_running:
                        time.sleep(0.1)
                        
                    if not self.is_running:
                        break
                        
                    # GUI Highlight current node
                    last_node = current_node
                    self.root.after(0, lambda n=current_node: n.highlight_execution(True))
                    
                    # Perform execution
                    self.execution_history[current_node.id] = {
                        "input": copy.deepcopy(payload)
                    }
                    
                    try:
                        next_port = current_node.execute(payload, self.log_message)
                        self.execution_history[current_node.id]["output"] = copy.deepcopy(payload)
                        self.last_run_payload = copy.deepcopy(payload)
                        
                        payload_str = json.dumps(payload, ensure_ascii=False)
                        if len(payload_str) > 1000:
                            payload_str = payload_str[:1000] + "... (truncated due to size)"
                        self.log_message(f"Payload updated: {payload_str}")
                        
                        # Pause brief moment (1.2s) to show visual highlights
                        time.sleep(1.2)
                        
                        # Remove highlight
                        self.root.after(0, lambda n=current_node: n.highlight_execution(False))
                        
                        if not self.is_running:
                            break
                            
                        # Traverse connections to locate next node matching the returned port
                        next_node = None
                        for conn in self.connections:
                            if conn.source.id == current_node.id and conn.source_port == next_port:
                                next_node = conn.target
                                break
                                
                        current_node = next_node
                    except Exception as e:
                        # Clean up visual highlight
                        self.root.after(0, lambda n=current_node: n.highlight_execution(False))
                        
                        from models.node import BreakLoopException, ContinueLoopException
                        if isinstance(e, BreakLoopException):
                            # Show highlight on the break node briefly
                            time.sleep(1.2)
                            
                            # Clean up the active loops stack: remove the broken loop and any nested loops inside it
                            active_loops = payload.get('__active_loops__', [])
                            if e.loop_node_id in active_loops:
                                idx = active_loops.index(e.loop_node_id)
                                payload['__active_loops__'] = active_loops[:idx]
                            
                            # Find loop out_done connection
                            next_node = None
                            for conn in self.connections:
                                if conn.source.id == e.loop_node_id and conn.source_port == 'out_done':
                                    next_node = conn.target
                                    break
                            current_node = next_node
                        elif isinstance(e, ContinueLoopException):
                            # Show highlight on the continue node briefly
                            time.sleep(1.2)
                            
                            # Go directly back to the loop node to trigger the next iteration
                            next_node = self.nodes.get(e.loop_node_id)
                            current_node = next_node
                        else:
                            raise e
                    
                # Short delay between loop runs
                if self.is_running and (max_runs == -1 or current_run < max_runs):
                    self.log_message("Waiting 1s before restarting round...")
                    time.sleep(1.0)
                
        except Exception as e:
            self.log_message(f"ERROR during execution: {str(e)}")
            if last_node:
                self.root.after(0, lambda n=last_node: n.highlight_execution(False))
                
        # Reset execution UI state
        def reset_ui():
            self.is_running = False
            self.is_paused = False
            self.run_btn.config(state="normal", text="▶ " + t("menu.run_start").upper())
            self.stop_btn.config(state="disabled")
            
            # Stop tray icon and restore window if hidden
            if self.tray_icon:
                self.tray_icon.stop()
                self.tray_icon = None
            self.root.after(0, self.root.deiconify)
            self.root.after(0, lambda: self.root.state('zoomed'))
            
            self.log_message("=== FLOW EXECUTION FINISHED ===")
            final_payload_str = json.dumps(payload, ensure_ascii=False, indent=2)
            if len(final_payload_str) > 1500:
                final_payload_str = final_payload_str[:1500] + "\n... (truncated due to size)"
            self.log_message(f"Final Payload: {final_payload_str}")
            if self.selected_node and self.properties_container:
                self.build_properties_panel(self.selected_node)
            
        self.root.after(0, reset_ui)

    def check_unconnected_loop_nodes(self):
        """
        Verifies if there are any unconnected end nodes inside loop bodies.
        Returns a dict mapping loop_node -> list of unconnected_node names.
        """
        unconnected_by_loop = {}
        loop_nodes = [n for n in self.nodes.values() if n.type == 'loop']
        if not loop_nodes:
            return unconnected_by_loop
            
        for loop_node in loop_nodes:
            # 1. Find all nodes in this loop's body (reachable from out_item)
            loop_body_nodes = set()
            start_targets = []
            for conn in self.connections:
                if conn.source.id == loop_node.id and conn.source_port == 'out_item':
                    start_targets.append(conn.target.id)
            
            queue = list(start_targets)
            visited = set(start_targets)
            while queue:
                curr_id = queue.pop(0)
                loop_body_nodes.add(curr_id)
                for conn in self.connections:
                    if conn.source.id == curr_id:
                        # Exclude traversal back to the loop node itself
                        if conn.target.id != loop_node.id:
                            if conn.target.id not in visited:
                                visited.add(conn.target.id)
                                queue.append(conn.target.id)
            
            # 2. For each node in the loop body, check if it's an unconnected end node
            unconnected = []
            for node_id in loop_body_nodes:
                node = self.nodes[node_id]
                if node.type in ['break_loop', 'continue_loop']:
                    continue
                
                # Check output ports
                out_ports = [p_name for p_name, p_info in node.ports.items() if p_info['type'] == 'output']
                if not out_ports:
                    unconnected.append(node.name)
                    continue
                
                for port in out_ports:
                    # Find connections from this port
                    port_conns = [c for c in self.connections if c.source.id == node.id and c.source_port == port]
                    if not port_conns:
                        # Port is not connected to anything (leaf node of this branch)
                        unconnected.append(node.name)
                        break
                    else:
                        # Verify if at least one connection target leads back to loop_node or its break_loop
                        # Or if target is a node in loop_body_nodes
                        valid = False
                        for conn in port_conns:
                            tgt = conn.target
                            if tgt.id == loop_node.id or tgt.id in loop_body_nodes:
                                valid = True
                                break
                            if tgt.type in ['break_loop', 'continue_loop']:
                                valid = True
                                break
                        if not valid:
                            unconnected.append(node.name)
                            break
                            
            if unconnected:
                unconnected_by_loop[loop_node] = unconnected
                
        return unconnected_by_loop

    def open_settings_dialog(self):
        settings_win = tk.Toplevel(self.root)
        settings_win.title("Configurações")
        settings_win.transient(self.root)
        settings_win.grab_set()
        
        # Center settings window
        win_w = 360
        win_h = 490
        scr_w = self.root.winfo_screenwidth()
        scr_h = self.root.winfo_screenheight()
        x = (scr_w - win_w) // 2
        y = (scr_h - win_h) // 2
        settings_win.geometry(f"{win_w}x{win_h}+{x}+{y}")
        settings_win.configure(bg="#f8fafc")
        
        # Temp vars
        temp_hide_var = tk.BooleanVar(value=self.hide_window_var.get())
        temp_auto_save_var = tk.BooleanVar(value=self.auto_save_var.get())
        
        main_frame = ttk.Frame(settings_win, padding=20)
        main_frame.pack(fill="both", expand=True)
        
        chk_hide = ttk.Checkbutton(
            main_frame, text=t("menu.settings_hide_window"), 
            variable=temp_hide_var
        )
        chk_hide.pack(anchor="w", pady=(0, 10))
        
        chk_auto_save = ttk.Checkbutton(
            main_frame, text=t("menu.settings_auto_save"), 
            variable=temp_auto_save_var
        )
        chk_auto_save.pack(anchor="w", pady=(0, 15))
        
        lbl_countdown = tk.Label(
            main_frame, text=t("menu.settings_countdown"), 
            font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc"
        )
        lbl_countdown.pack(anchor="w", pady=(0, 5))
        
        ent_countdown = ttk.Spinbox(main_frame, from_=0, to=60, width=10)
        ent_countdown.set(str(self.countdown_seconds_var.get()))
        ent_countdown.pack(anchor="w", pady=(0, 15))
        
        # --- Zoom Limits ---
        zoom_frame = tk.Frame(main_frame, bg="#f8fafc")
        zoom_frame.pack(fill="x", pady=(0, 15))
        
        lbl_zoom_min = tk.Label(
            zoom_frame, text=t("menu.settings_zoom_min"),
            font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc"
        )
        lbl_zoom_min.grid(row=0, column=0, sticky="w", pady=(0, 5))
        
        ent_zoom_min = ttk.Spinbox(zoom_frame, from_=0.1, to=1.0, increment=0.1, width=8, format="%.1f")
        ent_zoom_min.set(f"{self.zoom_min_var.get():.1f}")
        ent_zoom_min.grid(row=0, column=1, padx=(10, 0), pady=(0, 5))
        
        lbl_zoom_max = tk.Label(
            zoom_frame, text=t("menu.settings_zoom_max"),
            font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc"
        )
        lbl_zoom_max.grid(row=1, column=0, sticky="w", pady=(0, 5))
        
        ent_zoom_max = ttk.Spinbox(zoom_frame, from_=1.0, to=5.0, increment=0.1, width=8, format="%.1f")
        ent_zoom_max.set(f"{self.zoom_max_var.get():.1f}")
        ent_zoom_max.grid(row=1, column=1, padx=(10, 0), pady=(0, 5))
        
        # --- Connection Style ---
        conn_frame = tk.Frame(main_frame, bg="#f8fafc")
        conn_frame.pack(fill="x", pady=(0, 15))
        
        lbl_conn_width = tk.Label(
            conn_frame, text=t("menu.settings_connection_width"),
            font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc"
        )
        lbl_conn_width.grid(row=0, column=0, sticky="w", pady=(0, 5))
        
        ent_conn_width = ttk.Spinbox(conn_frame, from_=1, to=10, width=8)
        ent_conn_width.set(str(self.connection_width_var.get()))
        ent_conn_width.grid(row=0, column=1, padx=(10, 0), pady=(0, 5))
        
        lbl_conn_color = tk.Label(
            conn_frame, text=t("menu.settings_connection_color"),
            font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc"
        )
        lbl_conn_color.grid(row=1, column=0, sticky="w", pady=(0, 5))
        
        temp_conn_color_var = tk.StringVar(value=self.connection_color_var.get())
        
        def choose_connection_color():
            from tkinter import colorchooser
            color_code = colorchooser.askcolor(initialcolor=temp_conn_color_var.get(), title="Cor da Conexão")[1]
            if color_code:
                temp_conn_color_var.set(color_code)
                btn_color_indicator.config(bg=color_code)
                
        btn_color_indicator = tk.Button(
            conn_frame, width=8, bg=temp_conn_color_var.get(), bd=1, relief="solid",
            cursor="hand2", command=choose_connection_color
        )
        btn_color_indicator.grid(row=1, column=1, padx=(10, 0), pady=(0, 5))
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", side="bottom")
        
        def apply_settings():
            try:
                sec = int(ent_countdown.get())
                if sec < 0:
                    raise ValueError()
            except ValueError:
                messagebox.showerror(t("messages.error"), t("menu.settings_error_countdown"))
                return
            
            try:
                z_min = float(ent_zoom_min.get())
                z_max = float(ent_zoom_max.get())
                if z_min <= 0 or z_max <= 0 or z_min >= z_max:
                    raise ValueError()
            except ValueError:
                messagebox.showerror(t("messages.error"), t("menu.settings_error_zoom"))
                return
                
            try:
                c_width = int(ent_conn_width.get())
                if not (1 <= c_width <= 10):
                    raise ValueError()
            except ValueError:
                messagebox.showerror(t("messages.error"), t("menu.settings_error_connection_width"))
                return
                
            self.hide_window_var.set(temp_hide_var.get())
            self.auto_save_var.set(temp_auto_save_var.get())
            self.countdown_seconds_var.set(sec)
            self.zoom_min_var.set(z_min)
            self.zoom_max_var.set(z_max)
            self.connection_width_var.set(c_width)
            self.connection_color_var.set(temp_conn_color_var.get())
            
            # Save configuration to file
            from core.i18n_helper import save_app_settings
            save_app_settings({
                'hide_window': temp_hide_var.get(),
                'auto_save': temp_auto_save_var.get(),
                'countdown_seconds': sec,
                'zoom_min': z_min,
                'zoom_max': z_max,
                'connection_width': c_width,
                'connection_color': temp_conn_color_var.get()
            })
            
            # Update all active connection lines
            for conn in self.connections:
                conn.update_line()
            
            self.log_message(t("menu.settings_applied_log").format(temp_hide_var.get(), sec, temp_auto_save_var.get(), z_min, z_max))
            settings_win.destroy()
            
        btn_apply = tk.Button(
            btn_frame, text=t("menu.settings_apply"), font=("Segoe UI", 9, "bold"),
            bg="#22c55e", fg="#ffffff", activebackground="#16a34a", activeforeground="#ffffff",
            bd=0, padx=15, pady=6, cursor="hand2", command=apply_settings
        )
        btn_apply.pack(side="right", padx=(5, 0))
        
        btn_cancel = tk.Button(
            btn_frame, text=t("menu.settings_cancel"), font=("Segoe UI", 9, "bold"),
            bg="#94a3b8", fg="#ffffff", activebackground="#64748b", activeforeground="#ffffff",
            bd=0, padx=15, pady=6, cursor="hand2", command=settings_win.destroy
        )
        btn_cancel.pack(side="right")

    def setup_slide_panel(self):
        # Title area
        title_frame = tk.Frame(self.slide_panel, bg="#1e293b", height=50)
        title_frame.pack(fill="x", side="top", ipady=5)
        
        lbl_title = tk.Label(
            title_frame, text="Adicionar Nó", font=("Segoe UI", 11, "bold"),
            fg="#f8fafc", bg="#1e293b"
        )
        lbl_title.pack(side="left", padx=15, pady=10)
        
        # Close button (X)
        btn_close = tk.Button(
            title_frame, text="✕", font=("Segoe UI", 10, "bold"),
            fg="#94a3b8", bg="#1e293b", activeforeground="#f8fafc", activebackground="#1e293b",
            bd=0, cursor="hand2", command=self.slide_panel_out
        )
        btn_close.pack(side="right", padx=15, pady=10)
        
        # Scrollable container
        container = tk.Frame(self.slide_panel, bg="#0f172a")
        container.pack(fill="both", expand=True)
        
        canvas = tk.Canvas(container, bg="#0f172a", bd=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        scrollable_frame = tk.Frame(canvas, bg="#0f172a")
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        canvas.bind("<Configure>", lambda event: canvas.itemconfig(canvas_window, width=event.width))
        
        def configure_scrollregion(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        scrollable_frame.bind("<Configure>", configure_scrollregion)
        
        # Bind MouseWheel to scroll the canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            
        canvas.bind("<MouseWheel>", _on_mousewheel)
        scrollable_frame.bind("<MouseWheel>", _on_mousewheel)
        
        # Group list
        from core.i18n_helper import t
        from models.node import get_recolored_icon
        
        node_groups = [
            ("INTERAÇÃO E ENTRADA", [
                (t("toolbox.nodes.click"), "click", "#a855f7"),
                (t("toolbox.nodes.move_mouse"), "move_mouse", "#06b6d4"),
                (t("toolbox.nodes.key"), "key", "#db2777"),
                (t("toolbox.nodes.type_text"), "type_text", "#10b981"),
                (t("toolbox.nodes.capture"), "capture", "#f97316"),
            ]),
            ("CONTROLE E FLUXO", [
                (t("toolbox.nodes.condition"), "condition", "#0d9488"),
                (t("toolbox.nodes.delay"), "delay", "#f59e0b"),
                (t("toolbox.nodes.loop"), "loop", "#8b5cf6"),
                (t("toolbox.nodes.continue_loop"), "continue_loop", "#0284c7"),
                (t("toolbox.nodes.break_loop"), "break_loop", "#a21caf"),
                (t("toolbox.nodes.switch"), "switch", "#4f46e5"),
            ]),
            ("DADOS E CONEXÕES", [
                (t("toolbox.nodes.postgres"), "postgres", "#336791"),
                (t("toolbox.nodes.mysql"), "mysql", "#00758f"),
                (t("toolbox.nodes.sqlite"), "sqlite", "#003b57"),
                (t("toolbox.nodes.api"), "api", "#0284c7"),
                (t("toolbox.nodes.storage_var"), "storage_var", "#ec4899"),
            ]),
            ("CÓDIGO E SCRIPTS", [
                (t("toolbox.nodes.js"), "js", "#ca8a04"),
                (t("toolbox.nodes.python"), "python", "#2b5b84"),
            ]),
            ("DIÁLOGOS E TELAS", [
                (t("toolbox.nodes.confirm_dialog"), "confirm_dialog", "#f43f5e"),
                (t("toolbox.nodes.alert_dialog"), "alert_dialog", "#e11d48"),
            ])
        ]
        
        # Keep photo images in list to prevent garbage collection
        self._slide_icons = []
        
        icon_mapping = {
            'start': 'play', 'click': 'mouse-pointer', 'capture': 'camera',
            'condition': 'question', 'key': 'keyboard-o', 'type_text': 'font',
            'delay': 'clock-o', 'move_mouse': 'arrows', 'postgres': 'database',
            'mysql': 'database', 'sqlite': 'database', 'api': 'globe',
            'loop': 'refresh', 'break_loop': 'ban', 'continue_loop': 'arrow-right',
            'storage_var': 'cube', 'confirm_dialog': 'comments-o',
            'alert_dialog': 'exclamation-triangle', 'switch': 'random',
            'js': 'code', 'python': 'terminal'
        }
        
        for group_title, nodes in node_groups:
            # Section Header
            lbl_sec = tk.Label(
                scrollable_frame, text=group_title, font=("Segoe UI", 8, "bold"),
                fg="#64748b", bg="#0f172a"
            )
            lbl_sec.pack(anchor="w", pady=(15, 5), padx=15)
            
            for name, n_type, color in nodes:
                # Add node button
                btn_frame = tk.Frame(scrollable_frame, bg="#0f172a")
                btn_frame.pack(fill="x", padx=10, pady=2)
                
                # Retrieve and recolor icon for list
                icon_file = icon_mapping.get(n_type, 'question')
                photo = get_recolored_icon(icon_file, color, size=18)
                self._slide_icons.append(photo) # keep ref
                
                # Node item as a hoverable button
                btn_item = tk.Button(
                    btn_frame, text=f"  {name}", image=photo, compound="left",
                    font=("Segoe UI", 9, "bold"), fg="#e2e8f0", bg="#1e293b",
                    activeforeground="#ffffff", activebackground="#334155",
                    bd=0, padx=10, pady=8, cursor="hand2", anchor="w",
                    command=lambda nt=n_type, nm=name: self.on_select_slide_node(nt, nm)
                )
                btn_item.pack(fill="x", expand=True)
                
                # Bind hover effects
                def on_enter(e, widget=btn_item):
                    widget.config(bg="#334155")
                def on_leave(e, widget=btn_item):
                    widget.config(bg="#1e293b")
                    
                btn_item.bind("<Enter>", on_enter)
                btn_item.bind("<Leave>", on_leave)

    def slide_panel_in(self, source_node, source_port):
        self.plus_btn_source_node = source_node
        self.plus_btn_source_port = source_port
        
        self.slide_panel.lift()
        self.animate_slide(-280, 0, step=30)
        
    def slide_panel_out(self):
        self.animate_slide(0, -280, step=30)
        
    def animate_slide(self, target_x, current_x, step=30):
        if target_x < current_x:
            new_x = max(target_x, current_x - step)
            self.slide_panel.place(relx=1.0, x=new_x, y=0, relheight=1.0, anchor="nw")
            self.root.after(8, lambda: self.animate_slide(target_x, new_x, step))
        elif target_x > current_x:
            new_x = min(target_x, current_x + step)
            self.slide_panel.place(relx=1.0, x=new_x, y=0, relheight=1.0, anchor="nw")
            self.root.after(8, lambda: self.animate_slide(target_x, new_x, step))

    def on_select_slide_node(self, node_type, name):
        self.slide_panel_out()
        
        src_node = getattr(self, 'plus_btn_source_node', None)
        src_port = getattr(self, 'plus_btn_source_port', None)
        if not src_node or not src_port:
            return
            
        port_info = src_node.ports.get(src_port)
        rel_y = port_info['rel_y'] if port_info else (src_node.height // 2)
        
        # Position of the new node: 180px to the right of the source node
        # We align the vertical center of the new node with the source port center!
        new_x = src_node.x + 180
        new_y = src_node.y + rel_y - 34 # 34 is 68 / 2
        
        new_node = self.create_node(node_type, x=new_x, y=new_y, is_canvas_coords=True)
        
        # Find the target input port
        target_port = 'in' if 'in' in new_node.ports else None
        if target_port is None:
            for p_name, p in new_node.ports.items():
                if p['type'] == 'input':
                    target_port = p_name
                    break
                    
        if target_port:
            from models.connection import VisualConnection
            new_conn = VisualConnection(self.canvas, src_node, src_port, new_node, target_port)
            self.connections.append(new_conn)
            new_conn.update_line()
            
        # Refresh the source node's plus handles
        src_node.update_plus_handles()
        
        # Clear references
        self.plus_btn_source_node = None
        self.plus_btn_source_port = None


if __name__ == "__main__":
    root = tk.Tk()
    app = FlowBuilderProApp(root)
    root.mainloop()
