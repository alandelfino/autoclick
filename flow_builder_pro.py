"""
AutoClick Visual Flow Editor - Profissional
============================================

Main application entry point. The FlowBuilderProApp class composes
functionality from multiple UI mixins and connector mixins.
"""

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
        self.is_running = False
        self.is_paused = False
        self.tray_icon = None
        self.zoom_scale = 1.0
        self.is_panning_with_ctrl = False
        self.execution_history = {}
        self.last_run_payload = {}
        self.active_text_widget = None
        self.current_filepath = None
        
        # GUI Interaction states
        self.drag_data = {'x': 0, 'y': 0}
        self.active_port_drag = None  # (source_node, source_port_name)
        self.temp_line_id = None
        self.load_connections()
        
        self.setup_ui()
        
        # Root keyboard shortcuts
        self.root.bind("<Control-s>", lambda event: self.save_flow())
        self.root.bind("<Control-S>", lambda event: self.save_flow())

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
        
        # Setup top menu (not configured on root yet)
        self.setup_menu_bar()
        
        # Setup start/welcome screen
        self.setup_start_screen()

    # --- Logging ---

    def log_message(self, message):
        """Append thread-safe logs into the side text panel."""
        def append():
            self.log_text.config(state="normal")
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state="disabled")
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

    def save_flow_to_filepath(self, filepath, show_popup=True):
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
                    'waypoints': getattr(c, 'waypoints', []),
                    'is_auto_loop': getattr(c, 'is_auto_loop', False)
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
                    is_canvas_coords=True
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
                        conn_data['target_port'],
                        waypoints=conn_data.get('waypoints', [])
                    )
                    new_conn.is_auto_loop = conn_data.get('is_auto_loop', False)
                    self.connections.append(new_conn)
                    
            start_exists = any(n.type == 'start' for n in self.nodes.values())
            if not start_exists:
                self.create_start_node()
                
            self.current_filepath = filepath
            self.auto_connect_loops()
            
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
            
        except Exception as e:
            self.log_message(f"{t('messages.error_load').format(str(e))}")
            messagebox.showerror(t("messages.error"), f"{t('messages.error_load').format(str(e))}")

    # --- Node Creation and Management ---

    def create_node(self, node_type, name=None, x=150, y=120, properties=None, is_canvas_coords=False):
        self.node_counter += 1
        node_id = self.node_counter
        
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
                'alert_dialog': f"Alerta {node_id}"
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
        return new_node

    def create_start_node(self):
        for n in list(self.nodes.values()):
            if n.type == 'start':
                return n
        return self.create_node('start', name="Início do Fluxo", x=80, y=200)

    def select_node(self, node):
        if self.selected_node:
            self.selected_node.select(False)
            
        self.selected_node = node
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
            self.auto_connect_loops()

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

    # --- Flow Execution Engine (Async Execution Thread) ---

    def start_flow_execution(self):
        if self.is_running:
            return
            
        if not self.nodes:
            messagebox.showwarning(t("messages.warning"), "No nodes in canvas to execute.")
            return
            
        # 1. Ask for confirmation
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
        current_run = 0
        self.log_message("=== STARTING FLOW EXECUTION ===")
        self.log_message(f"Initial Payload: {json.dumps(payload)}")
        
        self.start_hotkey_listener()
        last_node = None
        
        try:
            while self.is_running:
                current_run += 1
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
                        
                        self.log_message(f"Payload updated: {json.dumps(payload, ensure_ascii=False)}")
                        
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
                        
                        from models.node import BreakLoopException
                        if isinstance(e, BreakLoopException):
                            # Show highlight on the break node briefly
                            time.sleep(1.2)
                            
                            # Find loop out_done connection
                            next_node = None
                            for conn in self.connections:
                                if conn.source.id == e.loop_node_id and conn.source_port == 'out_done':
                                    next_node = conn.target
                                    break
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
            self.log_message(f"Final Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
            if self.selected_node and self.properties_container:
                self.build_properties_panel(self.selected_node)
            
        self.root.after(0, reset_ui)

    def auto_connect_loops(self):
        # Find all loop nodes
        loop_nodes = [n for n in self.nodes.values() if n.type == 'loop']
        if not loop_nodes:
            return
            
        for loop_node in loop_nodes:
            # Determine loop body nodes: reachable from out_item port of loop_node
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
                        # Exclude connection back to loop node itself
                        if conn.target.id != loop_node.id:
                            if conn.target.id not in visited:
                                visited.add(conn.target.id)
                                queue.append(conn.target.id)
            
            # Now, for each node in the loop body, check if it's a leaf node.
            # A node in loop_body_nodes is a leaf node if it has no outgoing connections,
            # OR all its outgoing connections are to nodes that are not in the loop_body_nodes (excluding the loop_node).
            for node_id in loop_body_nodes:
                node = self.nodes[node_id]
                outgoing = [c for c in self.connections if c.source.id == node_id]
                non_loop_outgoing = [c for c in outgoing if c.target.id in loop_body_nodes]
                
                # If there are no outgoing connections to other nodes in the loop body:
                if len(non_loop_outgoing) == 0:
                    # It must connect back to loop_node.
                    # Check if a connection already exists to loop_node's 'in' port
                    has_conn = any(c.source.id == node_id and c.target.id == loop_node.id for c in self.connections)
                    if not has_conn:
                        # Determine correct output port to use (default: out)
                        port_to_use = 'out'
                        if 'out' not in node.ports:
                            out_ports = [p_name for p_name, p_info in node.ports.items() if p_info['type'] == 'output']
                            if out_ports:
                                port_to_use = out_ports[0]
                                
                        # Auto-create the connection
                        new_conn = VisualConnection(self.canvas, node, port_to_use, loop_node, 'in')
                        new_conn.is_auto_loop = True
                        self.connections.append(new_conn)
                        self.log_message(f"Conexão de loop automática criada: {node.name} -> {loop_node.name}")

    def open_settings_dialog(self):
        settings_win = tk.Toplevel(self.root)
        settings_win.title("Configurações")
        settings_win.transient(self.root)
        settings_win.grab_set()
        
        # Center settings window
        win_w = 360
        win_h = 240
        scr_w = self.root.winfo_screenwidth()
        scr_h = self.root.winfo_screenheight()
        x = (scr_w - win_w) // 2
        y = (scr_h - win_h) // 2
        settings_win.geometry(f"{win_w}x{win_h}+{x}+{y}")
        settings_win.configure(bg="#f8fafc")
        
        # Temp vars
        temp_hide_var = tk.BooleanVar(value=self.hide_window_var.get())
        
        main_frame = ttk.Frame(settings_win, padding=20)
        main_frame.pack(fill="both", expand=True)
        
        chk_hide = ttk.Checkbutton(
            main_frame, text=t("menu.settings_hide_window"), 
            variable=temp_hide_var
        )
        chk_hide.pack(anchor="w", pady=(0, 15))
        
        lbl_countdown = tk.Label(
            main_frame, text=t("menu.settings_countdown"), 
            font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc"
        )
        lbl_countdown.pack(anchor="w", pady=(0, 5))
        
        ent_countdown = ttk.Spinbox(main_frame, from_=0, to=60, width=10)
        ent_countdown.set(str(self.countdown_seconds_var.get()))
        ent_countdown.pack(anchor="w", pady=(0, 20))
        
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
                
            self.hide_window_var.set(temp_hide_var.get())
            self.countdown_seconds_var.set(sec)
            self.log_message(t("menu.settings_applied_log").format(temp_hide_var.get(), sec))
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


if __name__ == "__main__":
    root = tk.Tk()
    app = FlowBuilderProApp(root)
    root.mainloop()
