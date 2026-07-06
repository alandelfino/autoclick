"""
VisualNode — Graphical representation of a flow node on the canvas.

Handles drawing, port management, property defaults, execution logic,
and visual state (selection, highlight).
"""
import ctypes
import time
import json
import threading
import tkinter as tk

from core.automation import click_mouse, simulate_keypress, get_active_window_info, simulate_type_text
from core.payload import get_payload_value, resolve_value
from core.i18n_helper import t


class BreakLoopException(Exception):
    def __init__(self, loop_node_id):
        self.loop_node_id = loop_node_id


class ContinueLoopException(Exception):
    def __init__(self, loop_node_id):
        self.loop_node_id = loop_node_id


def get_cursor_name(h_cursor):
    if not h_cursor:
        return "Nenhum"
    
    cursor_ids = {
        32512: "Arrow",
        32513: "IBeam",
        32514: "Wait",
        32515: "Crosshair",
        32516: "UpArrow",
        32642: "SizeNWSE",
        32643: "SizeNESW",
        32644: "SizeWE",
        32645: "SizeNS",
        32646: "SizeAll",
        32648: "No",
        32649: "Hand",
        32650: "AppStarting",
        32651: "Help"
    }
    
    for cid, name in cursor_ids.items():
        sys_h_cursor = ctypes.windll.user32.LoadCursorW(None, ctypes.c_void_p(cid))
        if sys_h_cursor == h_cursor:
            return name
            
    return f"Desconhecido ({h_cursor})"


class VisualNode:
    def __init__(self, canvas, node_id, node_type, name, x, y, properties=None):
        self.canvas = canvas
        self.id = node_id
        self.type = node_type # 'click', 'capture', 'condition', 'key'
        self.name = name
        self.x = x
        self.y = y
        self.width = 180
        self.height = 100
        
        # Load default properties if none provided
        self.properties = properties if properties is not None else self.get_default_properties()
        
        # Define visual themes per node type
        self.themes = {
            'start': {'header': '#6366f1', 'title': 'Início'},
            'click': {'header': '#a855f7', 'title': 'Clique'},
            'capture': {'header': '#f97316', 'title': 'Capturar Dados'},
            'condition': {'header': '#0d9488', 'title': 'Condicional'},
            'key': {'header': '#db2777', 'title': 'Pressionar Tecla'},
            'type_text': {'header': '#10b981', 'title': 'Digitar Texto'},
            'delay': {'header': '#f59e0b', 'title': 'Aguardar / Delay'},
            'move_mouse': {'header': '#06b6d4', 'title': 'Mover Cursor'},
            'postgres': {'header': '#336791', 'title': 'PostgreSQL'},
            'mysql': {'header': '#00758f', 'title': 'MySQL'},
            'sqlite': {'header': '#003b57', 'title': 'SQLite'},
            'api': {'header': '#0284c7', 'title': 'Requisição API'},
            'loop': {'header': '#8b5cf6', 'title': 'Loop'},
            'break_loop': {'header': '#a21caf', 'title': 'Interromper Loop'},
            'continue_loop': {'header': '#0ea5e9', 'title': t("toolbox.nodes.continue_loop")},
            'storage_var': {'header': '#ec4899', 'title': 'Var. Armazenamento'},
            'confirm_dialog': {'header': '#f43f5e', 'title': t("toolbox.nodes.confirm_dialog")},
            'alert_dialog': {'header': '#e11d48', 'title': t("toolbox.nodes.alert_dialog")}
        }
        self.theme = self.themes.get(self.type, {'header': '#64748b', 'title': 'Nó'})

        self.is_executing = False
        self.is_hovered = False

        # Setup Ports (positions relative to x, y)
        self.ports = {}
        self.setup_ports()

        # Canvas UI references
        self.tag = f"node_{self.id}"
        self.draw()
        
        # Bind hover events
        self.canvas.tag_bind(self.tag, "<Enter>", self.on_enter)
        self.canvas.tag_bind(self.tag, "<Leave>", self.on_leave)
        
        # Bind right-click events
        self.canvas.tag_bind(self.tag, "<Button-3>", self.on_right_click_node)
        self.canvas.tag_bind(self.tag, "<Button-2>", self.on_right_click_node)

    def get_default_properties(self):
        if self.type == 'click':
            return {'x': 0, 'y': 0}
        elif self.type == 'capture':
            return {'capture_type': 'Dados da Janela Ativa'}
        elif self.type == 'condition':
            return {'variable': 'active_window.title', 'operator': 'contém', 'value': ''}
        elif self.type == 'key':
            return {'key': 'enter', 'count': 1}
        elif self.type == 'type_text':
            return {'text': ''}
        elif self.type == 'delay':
            return {'seconds': 1.0}
        elif self.type == 'move_mouse':
            return {'x': 0, 'y': 0}
        elif self.type == 'start':
            return {'loop_mode': 'Executar 1 vez', 'loop_count': 5}
        elif self.type in ['postgres', 'mysql', 'sqlite']:
            return {'connection_name': '', 'sql': 'SELECT 1;', 'sample_payload': None}
        elif self.type == 'api':
            return {'connection_name': '', 'method': 'GET', 'path': '', 'headers': '', 'body': '', 'sample_payload': None}
        elif self.type == 'loop':
            return {'array_data': '[]'}
        elif self.type in ['break_loop', 'continue_loop']:
            return {}
        elif self.type == 'storage_var':
            return {'variable_name': 'var_1', 'variable_value': ''}
        elif self.type == 'confirm_dialog':
            return {
                'title': 'Confirmação',
                'message': 'Você deseja continuar?',
                'btn_true_text': 'Sim',
                'btn_false_text': 'Não',
                'payload_var': 'confirm_result'
            }
        elif self.type == 'alert_dialog':
            return {
                'title': 'Alerta',
                'message': 'Fluxo interrompido!',
                'btn_ok_text': 'OK'
            }
        return {}

    def setup_ports(self):
        # All nodes have 1 Input port on the left center EXCEPT the 'start' node
        if self.type != 'start':
            self.ports['in'] = {
                'rel_x': 0, 'rel_y': self.height // 2,
                'type': 'input', 'color': '#64748b',
                'tag': f"port_in_{self.id}"
            }
        
        if self.type == 'condition':
            # Conditional node has 2 outputs (True/False)
            self.ports['out_true'] = {
                'rel_x': self.width, 'rel_y': 30,
                'type': 'output', 'color': '#22c55e', # Green
                'label': 'True', 'tag': f"port_out_true_{self.id}"
            }
            self.ports['out_false'] = {
                'rel_x': self.width, 'rel_y': 70,
                'type': 'output', 'color': '#ef4444', # Red
                'label': 'False', 'tag': f"port_out_false_{self.id}"
            }
        elif self.type == 'start':
            # Start node has 1 output on the right center (colored Indigo)
            self.ports['out'] = {
                'rel_x': self.width, 'rel_y': self.height // 2,
                'type': 'output', 'color': '#6366f1', # Indigo
                'tag': f"port_out_{self.id}"
            }
        elif self.type == 'loop':
            self.ports['out_item'] = {
                'rel_x': self.width, 'rel_y': 30,
                'type': 'output', 'color': '#2563eb', # Blue
                'label': 'Next Item', 'tag': f"port_out_item_{self.id}"
            }
            self.ports['out_done'] = {
                'rel_x': self.width, 'rel_y': 70,
                'type': 'output', 'color': '#64748b', # Slate
                'label': 'Done', 'tag': f"port_out_done_{self.id}"
            }
        elif self.type in ['break_loop', 'continue_loop']:
            # No output ports
            pass
        else:
            # Standard nodes have 1 output on the right center
            self.ports['out'] = {
                'rel_x': self.width, 'rel_y': self.height // 2,
                'type': 'output', 'color': '#3b82f6', # Blue
                'tag': f"port_out_{self.id}"
            }

    def draw(self):
        # 1. Main body card
        self.body_ui = self.canvas.create_rectangle(
            self.x, self.y, self.x + self.width, self.y + self.height,
            fill="#ffffff", outline="#e2e8f0", width=2, tags=(self.tag, "node_body")
        )
        
        # 2. Header Bar
        self.header_ui = self.canvas.create_rectangle(
            self.x, self.y, self.x + self.width, self.y + 26,
            fill=self.theme['header'], outline=self.theme['header'], tags=self.tag
        )
        
        # 3. Header Text (Type description)
        self.header_text_ui = self.canvas.create_text(
            self.x + 10, self.y + 13, text=self.theme['title'].upper(), anchor="w",
            fill="#ffffff", font=("Segoe UI", 8, "bold"), tags=self.tag
        )
        
        # 4. Body Name Text (Editable by user)
        self.name_text_ui = self.canvas.create_text(
            self.x + 10, self.y + 50, text=self.name, anchor="w",
            fill="#1e293b", font=("Segoe UI", 10, "bold"), tags=self.tag, width=self.width - 20
        )
        
        # 5. Display brief summary of properties
        self.update_summary_text()
        
        # 6. Draw ports (circles and optional labels)
        for port_name, p in self.ports.items():
            px = self.x + p['rel_x']
            py = self.y + p['rel_y']
            
            # Draw port circle
            p['ui_circle'] = self.canvas.create_oval(
                px - 6, py - 6, px + 6, py + 6,
                fill=p['color'], outline="#ffffff", width=2,
                tags=(p['tag'], "port", f"node_port_{self.id}_{port_name}")
            )
            
            # Draw text label if conditional
            if 'label' in p:
                text_anchor = "e" if p['rel_x'] == self.width else "w"
                tx_offset = -12 if p['rel_x'] == self.width else 12
                p['ui_label'] = self.canvas.create_text(
                    px + tx_offset, py, text=p['label'], anchor=text_anchor,
                    fill="#64748b", font=("Segoe UI", 8, "bold"), tags=self.tag
                )

    def update_summary_text(self):
        # Remove old summary text if exists
        if hasattr(self, 'summary_text_ui'):
            self.canvas.delete(self.summary_text_ui)
            
        summary = ""
        if self.type == 'click':
            summary = f"X: {self.properties.get('x', 0)}, Y: {self.properties.get('y', 0)}"
        elif self.type == 'capture':
            summary = f"Tipo: {self.properties.get('capture_type', '')}"
        elif self.type == 'condition':
            summary = f"{self.properties.get('variable', '')[:10]}... {self.properties.get('operator', '')}"
        elif self.type == 'key':
            summary = f"Tecla: {self.properties.get('key', '')} ({self.properties.get('count', 1)}x)"
        elif self.type == 'type_text':
            summary = f"Texto: {self.properties.get('text', '')[:15]}..."
        elif self.type == 'delay':
            summary = f"Espera: {self.properties.get('seconds', 1.0)}s"
        elif self.type == 'move_mouse':
            summary = f"Para X: {self.properties.get('x', 0)}, Y: {self.properties.get('y', 0)}"
        elif self.type == 'start':
            mode = self.properties.get('loop_mode', 'Executar 1 vez')
            if mode == 'Executar N vezes':
                summary = f"Loop: {self.properties.get('loop_count', 5)} vezes"
            elif mode == 'Loop Infinito':
                summary = "Loop Infinito"
            else:
                summary = "Executar 1 vez"
        elif self.type == 'sqlite':
            summary = f"SQLite: {self.properties.get('connection_name', '')}"
        elif self.type == 'postgres':
            summary = f"Postgres: {self.properties.get('connection_name', '')}"
        elif self.type == 'mysql':
            summary = f"MySQL: {self.properties.get('connection_name', '')}"
        elif self.type == 'api':
            summary = f"API: {self.properties.get('method', 'GET')} {self.properties.get('path', '')}"
        elif self.type == 'loop':
            summary = f"Loop: {self.properties.get('array_data', '[]')[:15]}..."
        elif self.type == 'break_loop':
            summary = t("toolbox.nodes.break_loop")
        elif self.type == 'continue_loop':
            summary = t("toolbox.nodes.continue_loop")
        elif self.type == 'storage_var':
            summary = f"Var: {self.properties.get('variable_name', 'var_1')} = {self.properties.get('variable_value', '')}"
        elif self.type == 'confirm_dialog':
            summary = f"Título: {self.properties.get('title', '')}"
        elif self.type == 'alert_dialog':
            summary = f"Título: {self.properties.get('title', '')}"
            
        self.summary_text_ui = self.canvas.create_text(
            self.x + 10, self.y + 75, text=summary, anchor="w",
            fill="#64748b", font=("Segoe UI", 8, "italic"), tags=self.tag, width=self.width - 20
        )

    def rename(self, new_name):
        self.name = new_name
        self.canvas.itemconfig(self.name_text_ui, text=new_name)

    def scale_fonts(self, scale):
        header_sz = max(int(8 * scale), 4)
        name_sz = max(int(10 * scale), 5)
        summary_sz = max(int(8 * scale), 4)
        port_sz = max(int(8 * scale), 4)
        
        self.canvas.itemconfig(self.header_text_ui, font=("Segoe UI", header_sz, "bold"))
        self.canvas.itemconfig(self.name_text_ui, font=("Segoe UI", name_sz, "bold"), width=max(int(self.width - 8 * scale), 10))
        
        if hasattr(self, 'summary_text_ui') and self.summary_text_ui:
            self.canvas.itemconfig(self.summary_text_ui, font=("Segoe UI", summary_sz, "italic"), width=max(int(self.width - 8 * scale), 10))
            
        for p in self.ports.values():
            if 'ui_label' in p and p['ui_label']:
                self.canvas.itemconfig(p['ui_label'], font=("Segoe UI", port_sz, "bold"))

    def move_by(self, dx, dy):
        self.x += dx
        self.y += dy
        self.canvas.move(self.tag, dx, dy)
        
        # Move port graphics
        for p in self.ports.values():
            self.canvas.move(p['tag'], dx, dy)

    def get_port_center(self, port_name):
        p = self.ports[port_name]
        coords = self.canvas.coords(p['ui_circle'])
        if len(coords) == 4:
            # Circle bounding box: x1, y1, x2, y2
            return (coords[0] + coords[2]) / 2.0, (coords[1] + coords[3]) / 2.0
        return self.x + p['rel_x'], self.y + p['rel_y']

    def select(self, selected):
        self.update_outline()

    def highlight_execution(self, active):
        self.is_executing = active
        self.update_outline()

    def update_outline(self):
        app = getattr(self.canvas, 'app', None)
        is_selected = (app and app.selected_node == self)
        
        if self.is_executing:
            color = "#22c55e"
            width = 4
        elif is_selected:
            color = "#2563eb"
            width = 3
        elif getattr(self, 'is_hovered', False):
            color = "#3b82f6"
            width = 3
        else:
            color = "#e2e8f0"
            width = 2
            
        self.canvas.itemconfig(self.body_ui, outline=color, width=width)

    def on_enter(self, event):
        self.is_hovered = True
        self.update_outline()

    def on_leave(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        margin = 2
        inside = (self.x - margin <= cx <= self.x + self.width + margin and
                  self.y - margin <= cy <= self.y + self.height + margin)
        if inside:
            return
        self.is_hovered = False
        self.update_outline()

    def get_first_output_port(self):
        if 'out' in self.ports:
            return 'out'
        elif 'out_true' in self.ports:
            return 'out_true'
        elif 'out_item' in self.ports:
            return 'out_item'
        elif self.ports:
            for p_name, p in self.ports.items():
                if p['type'] == 'output':
                    return p_name
        return None

    def on_right_click_node(self, event):
        app = getattr(self.canvas, 'app', None)
        if not app:
            return
            
        menu = tk.Menu(self.canvas, tearoff=0)
        
        menu.add_command(
            label=t("canvas.context_delete"),
            command=lambda: app.delete_node_by_ref(self)
        )
        menu.add_separator()
        
        node_groups = [
            ("INTERAÇÃO E ENTRADA", [
                (t("toolbox.nodes.click"), "click"),
                (t("toolbox.nodes.move_mouse"), "move_mouse"),
                (t("toolbox.nodes.key"), "key"),
                (t("toolbox.nodes.type_text"), "type_text"),
                (t("toolbox.nodes.capture"), "capture"),
            ]),
            ("CONTROLE E FLUXO", [
                (t("toolbox.nodes.condition"), "condition"),
                (t("toolbox.nodes.delay"), "delay"),
                (t("toolbox.nodes.loop"), "loop"),
                (t("toolbox.nodes.continue_loop"), "continue_loop"),
                (t("toolbox.nodes.break_loop"), "break_loop"),
            ]),
            ("DADOS E CONEXÕES", [
                (t("toolbox.nodes.postgres"), "postgres"),
                (t("toolbox.nodes.mysql"), "mysql"),
                (t("toolbox.nodes.sqlite"), "sqlite"),
                (t("toolbox.nodes.api"), "api"),
                (t("toolbox.nodes.storage_var"), "storage_var"),
            ]),
            ("DIÁLOGOS E TELAS", [
                (t("toolbox.nodes.confirm_dialog"), "confirm_dialog"),
                (t("toolbox.nodes.alert_dialog"), "alert_dialog"),
            ])
        ]
        
        # "Adicionar Nó Antes" Submenu
        before_menu = tk.Menu(menu, tearoff=0)
        for cat_name, nodes in node_groups:
            cat_menu = tk.Menu(before_menu, tearoff=0)
            for label, ntype in nodes:
                def make_before_cmd(node_type=ntype):
                    self.insert_node_before(node_type)
                cat_menu.add_command(label=label, command=make_before_cmd)
            before_menu.add_cascade(label=cat_name, menu=cat_menu)
        menu.add_cascade(label=t("node.add_before"), menu=before_menu)
        
        # "Adicionar Nó Depois" Submenu
        after_menu = tk.Menu(menu, tearoff=0)
        for cat_name, nodes in node_groups:
            cat_menu = tk.Menu(after_menu, tearoff=0)
            for label, ntype in nodes:
                def make_after_cmd(node_type=ntype):
                    self.insert_node_after(node_type)
                cat_menu.add_command(label=label, command=make_after_cmd)
            after_menu.add_cascade(label=cat_name, menu=cat_menu)
        menu.add_cascade(label=t("node.add_after"), menu=after_menu)
        
        menu.post(event.x_root, event.y_root)

    def insert_node_before(self, node_type):
        app = getattr(self.canvas, 'app', None)
        if not app:
            return
            
        from models.connection import VisualConnection
        
        incoming = [c for c in app.connections if c.target == self and c.target_port == 'in']
        
        if incoming:
            avg_x = sum(c.source.x for c in incoming) / len(incoming)
            avg_y = sum(c.source.y for c in incoming) / len(incoming)
            new_x = (avg_x + self.x) / 2
            new_y = (avg_y + self.y) / 2
        else:
            new_x = self.x - 220
            new_y = self.y
            
        new_node = app.create_node(node_type, x=new_x, y=new_y, is_canvas_coords=True)
        if not new_node:
            return
            
        if incoming:
            for c in incoming:
                src = c.source
                src_port = c.source_port
                c.delete()
                app.connections.remove(c)
                new_conn1 = VisualConnection(self.canvas, src, src_port, new_node, 'in')
                app.connections.append(new_conn1)
                
        new_node_out = new_node.get_first_output_port()
        if new_node_out:
            new_conn2 = VisualConnection(self.canvas, new_node, new_node_out, self, 'in')
            app.connections.append(new_conn2)
            
        app.trigger_auto_save()

    def insert_node_after(self, node_type):
        app = getattr(self.canvas, 'app', None)
        if not app:
            return
            
        from models.connection import VisualConnection
        
        outgoing = [c for c in app.connections if c.source == self]
        
        if outgoing:
            avg_x = sum(c.target.x for c in outgoing) / len(outgoing)
            avg_y = sum(c.target.y for c in outgoing) / len(outgoing)
            new_x = (self.x + avg_x) / 2
            new_y = (self.y + avg_y) / 2
        else:
            new_x = self.x + 220
            new_y = self.y
            
        new_node = app.create_node(node_type, x=new_x, y=new_y, is_canvas_coords=True)
        if not new_node:
            return
            
        if outgoing:
            created_in_ports = set()
            for c in outgoing:
                src_port = c.source_port
                tgt = c.target
                tgt_port = c.target_port
                
                c.delete()
                app.connections.remove(c)
                
                if src_port not in created_in_ports:
                    new_conn1 = VisualConnection(self.canvas, self, src_port, new_node, 'in')
                    app.connections.append(new_conn1)
                    created_in_ports.add(src_port)
                    
                new_node_out = new_node.get_first_output_port()
                if new_node_out:
                    new_conn2 = VisualConnection(self.canvas, new_node, new_node_out, tgt, tgt_port)
                    app.connections.append(new_conn2)
        else:
            self_out = self.get_first_output_port()
            if self_out:
                new_conn = VisualConnection(self.canvas, self, self_out, new_node, 'in')
                app.connections.append(new_conn)
                
        app.trigger_auto_save()

    def execute(self, payload, log_func):
        """Runs the action of the node, writes to log, updates payload, and returns next port path."""
        log_func(t("logs.node_executing").format(self.name, self.type.upper()))
        
        if self.type == 'start':
            log_func(t("logs.start_executing"))
            return 'out'
            
        elif self.type == 'click':
            x_raw = self.properties.get('x', 0)
            y_raw = self.properties.get('y', 0)
            x_resolved = resolve_value(str(x_raw), payload)
            y_resolved = resolve_value(str(y_raw), payload)
            try:
                x = int(x_resolved)
            except ValueError:
                x = 0
            try:
                y = int(y_resolved)
            except ValueError:
                y = 0
            log_func(t("logs.click_executing").format(x, y))
            click_mouse(x, y)
            payload['last_click'] = {'x': x, 'y': y}
            return 'out'
            
        elif self.type == 'capture':
            capture_type = self.properties.get('capture_type', 'Active Window Data')
            if capture_type in ['Dados da Janela Ativa', 'Janela Ativa', 'Active Window Data']:
                title, hwnd = get_active_window_info()
                log_func(t("logs.capture_window_success").format(title, hwnd))
                payload['active_window'] = {'title': title, 'hwnd': hwnd}
            else:
                class POINT(ctypes.Structure):
                    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
                class CURSORINFO(ctypes.Structure):
                    _fields_ = [
                        ("cbSize", ctypes.c_uint),
                        ("flags", ctypes.c_uint),
                        ("hCursor", ctypes.c_void_p),
                        ("ptScreenPos", POINT)
                    ]
                ci = CURSORINFO()
                ci.cbSize = ctypes.sizeof(CURSORINFO)
                ctypes.windll.user32.GetCursorInfo(ctypes.byref(ci))
                x = ci.ptScreenPos.x
                y = ci.ptScreenPos.y
                h_cursor = ci.hCursor
                cursor_name = get_cursor_name(h_cursor)
                log_func(t("logs.capture_mouse_success").format(x, y, cursor_name, h_cursor))
                payload['captured_mouse'] = {'x': x, 'y': y, 'cursor_name': cursor_name, 'cursor_handle': h_cursor}
            return 'out'
            
        elif self.type == 'key':
            key_raw = self.properties.get('key', 'enter')
            key = str(resolve_value(str(key_raw), payload))
            count_raw = self.properties.get('count', 1)
            count_resolved = resolve_value(str(count_raw), payload)
            try:
                count = int(count_resolved)
            except ValueError:
                count = 1
            log_func(t("logs.key_pressing").format(key, count))
            simulate_keypress(key, count)
            payload['last_key'] = {'key': key, 'count': count}
            return 'out'
            
        elif self.type == 'type_text':
            raw_text = self.properties.get('text', '')
            formatted_text = str(resolve_value(raw_text, payload))
            log_func(t("logs.text_typing").format(formatted_text))
            simulate_type_text(formatted_text)
            payload['last_typed'] = formatted_text
            return 'out'
            
        elif self.type == 'delay':
            secs_raw = self.properties.get('seconds', 1.0)
            secs_resolved = resolve_value(str(secs_raw), payload)
            try:
                secs = float(secs_resolved)
            except ValueError:
                secs = 1.0
            log_func(t("logs.delay_waiting").format(secs))
            time.sleep(secs)
            return 'out'
            
        elif self.type == 'move_mouse':
            x_raw = self.properties.get('x', 0)
            y_raw = self.properties.get('y', 0)
            x_resolved = resolve_value(str(x_raw), payload)
            y_resolved = resolve_value(str(y_raw), payload)
            try:
                x = int(x_resolved)
            except ValueError:
                x = 0
            try:
                y = int(y_resolved)
            except ValueError:
                y = 0
            log_func(t("logs.move_mouse_executing").format(x, y))
            ctypes.windll.user32.SetCursorPos(x, y)
            payload['last_mouse_pos'] = {'x': x, 'y': y}
            return 'out'
            
        elif self.type == 'condition':
            variable = self.properties.get('variable', '')
            while variable.startswith('{') and variable.endswith('}'):
                variable = variable[1:-1]
            operator = self.properties.get('operator', 'equals')
            target_value_raw = self.properties.get('value', '')
            
            # Resolve value from payload
            actual_value = get_payload_value(payload, variable)
            if actual_value is None:
                actual_value = ""
                
            target_value = resolve_value(str(target_value_raw), payload)
            
            log_func(t("logs.condition_current_val").format(variable, actual_value))
            log_func(t("logs.condition_comparing").format(actual_value, operator, target_value))
            
            # Perform evaluation
            result = False
            str_actual = str(actual_value).lower()
            str_target = str(target_value).lower()
            
            if operator in ['igual', 'equals']:
                result = str_actual == str_target
            elif operator in ['diferente', 'different']:
                result = str_actual != str_target
            elif operator in ['contém', 'contains']:
                result = str_target in str_actual
            elif operator in ['maior que', 'greater than']:
                try:
                    result = float(actual_value) > float(target_value)
                except ValueError:
                    result = False
                    
            log_func(t("logs.condition_result").format(result))
            return 'out_true' if result else 'out_false'
            
        elif self.type == 'sqlite':
            conn_name = self.properties.get('connection_name', '')
            sql_raw = self.properties.get('sql', '')
            sql = resolve_value(sql_raw, payload)
            log_func(t("logs.db_sqlite_executing").format(conn_name))
            app = getattr(self.canvas, 'app', None)
            if app:
                conn_config = app.saved_connections.get(conn_name)
                if conn_config:
                    try:
                        result = app.run_db_query('sqlite', conn_config, sql)
                        var_name = app.get_var_name(self.name)
                        payload[var_name] = result
                        payload['last_db_result'] = result
                        log_func(t("logs.db_sqlite_ok"))
                    except Exception as e:
                        log_func(t("logs.db_sqlite_error").format(str(e)))
                        raise e
                else:
                    log_func(t("logs.db_sqlite_not_found"))
                    raise ValueError("SQLite connection not found.")
            return 'out'

        elif self.type == 'postgres':
            conn_name = self.properties.get('connection_name', '')
            sql_raw = self.properties.get('sql', '')
            sql = resolve_value(sql_raw, payload)
            log_func(t("logs.db_postgres_executing").format(conn_name))
            app = getattr(self.canvas, 'app', None)
            if app:
                conn_config = app.saved_connections.get(conn_name)
                if conn_config:
                    try:
                        result = app.run_db_query('postgres', conn_config, sql)
                        var_name = app.get_var_name(self.name)
                        payload[var_name] = result
                        payload['last_db_result'] = result
                        log_func(t("logs.db_postgres_ok"))
                    except Exception as e:
                        log_func(t("logs.db_postgres_error").format(str(e)))
                        raise e
                else:
                    log_func(t("logs.db_postgres_not_found"))
                    raise ValueError("PostgreSQL connection not found.")
            return 'out'

        elif self.type == 'mysql':
            conn_name = self.properties.get('connection_name', '')
            sql_raw = self.properties.get('sql', '')
            sql = resolve_value(sql_raw, payload)
            log_func(t("logs.db_mysql_executing").format(conn_name))
            app = getattr(self.canvas, 'app', None)
            if app:
                conn_config = app.saved_connections.get(conn_name)
                if conn_config:
                    try:
                        result = app.run_db_query('mysql', conn_config, sql)
                        var_name = app.get_var_name(self.name)
                        payload[var_name] = result
                        payload['last_db_result'] = result
                        log_func(t("logs.db_mysql_ok"))
                    except Exception as e:
                        log_func(t("logs.db_mysql_error").format(str(e)))
                        raise e
                else:
                    log_func(t("logs.db_mysql_not_found"))
                    raise ValueError("MySQL connection not found.")
            return 'out'

        elif self.type == 'api':
            conn_name = self.properties.get('connection_name', '')
            method = self.properties.get('method', 'GET')
            path_raw = self.properties.get('path', '')
            path_url = resolve_value(path_raw, payload)
            headers_raw = self.properties.get('headers', '')
            headers_json = resolve_value(headers_raw, payload)
            body_raw = self.properties.get('body', '')
            body_text = resolve_value(body_raw, payload)
            
            log_func(t("logs.api_executing").format(method, conn_name or 'URL Direta'))
            app = getattr(self.canvas, 'app', None)
            if app:
                conn_config = app.saved_connections.get(conn_name) if conn_name else None
                try:
                    result = app.run_api_request(conn_config, method, path_url, headers_json, body_text)
                    var_name = app.get_var_name(self.name)
                    payload[var_name] = result
                    payload['last_api_result'] = result
                    log_func(t("logs.api_ok").format(result['status_code']))
                except Exception as e:
                    log_func(t("logs.api_error").format(str(e)))
                    raise e
            return 'out'

        elif self.type == 'loop':
            app = getattr(self.canvas, 'app', None)
            if not app:
                return 'out_done'
                
            var_name = app.get_var_name(self.name)
            
            # Check if interrupted
            if var_name in payload and isinstance(payload[var_name], dict):
                if payload[var_name].get('status') == 'broken':
                    log_func(t("logs.loop_break_detect").format(self.name))
                    payload[var_name]['status'] = 'done'
                    # Remove from active loops
                    if '__active_loops__' in payload and self.id in payload['__active_loops__']:
                        payload['__active_loops__'].remove(self.id)
                    return 'out_done'
            
            # Load loop items
            items = []
            array_data = self.properties.get('array_data', '[]')
            resolved = resolve_value(array_data, payload)
            
            if isinstance(resolved, list):
                items = resolved
            elif isinstance(resolved, dict):
                # Smart extraction of arrays from database and API wrappers
                if "rows" in resolved and isinstance(resolved["rows"], list):
                    items = resolved["rows"]
                elif "body" in resolved and isinstance(resolved["body"], list):
                    items = resolved["body"]
                elif "body" in resolved and isinstance(resolved["body"], dict) and "rows" in resolved["body"] and isinstance(resolved["body"]["rows"], list):
                    items = resolved["body"]["rows"]
                else:
                    items = [resolved]
            elif isinstance(resolved, str):
                try:
                    parsed = json.loads(resolved)
                    if isinstance(parsed, list):
                        items = parsed
                    else:
                        items = [parsed]
                except Exception:
                    items = [resolved]
            elif resolved is not None:
                items = [resolved]
            else:
                items = []
            
            is_running = False
            if var_name in payload and isinstance(payload[var_name], dict):
                if payload[var_name].get('status') == 'running':
                    is_running = True
            
            if not is_running:
                log_func(t("logs.loop_start").format(self.name, len(items)))
                payload[var_name] = {
                    'item': None,
                    'index': 0,
                    'total': len(items),
                    'status': 'running'
                }
            else:
                payload[var_name]['index'] += 1
                
            curr_idx = payload[var_name]['index']
            if curr_idx < len(items):
                payload[var_name]['item'] = items[curr_idx]
                log_func(t("logs.loop_iteration").format(self.name, curr_idx + 1, len(items), items[curr_idx]))
                # Ensure loop is in active loops stack
                if '__active_loops__' not in payload:
                    payload['__active_loops__'] = []
                if self.id not in payload['__active_loops__']:
                    payload['__active_loops__'].append(self.id)
                return 'out_item'
            else:
                log_func(t("logs.loop_end").format(self.name))
                payload[var_name]['status'] = 'done'
                # Remove from active loops
                if '__active_loops__' in payload and self.id in payload['__active_loops__']:
                    payload['__active_loops__'].remove(self.id)
                return 'out_done'

        elif self.type == 'break_loop':
            active_loops = payload.get('__active_loops__', [])
            if not active_loops:
                log_func(t("logs.loop_continue_warning"))
                return 'out'
                
            loop_node_id = active_loops[-1]
            app = getattr(self.canvas, 'app', None)
            loop_node = app.nodes.get(loop_node_id) if app else None
            loop_name = loop_node.name if loop_node else f"ID {loop_node_id}"
            
            if loop_node and app:
                var_name = app.get_var_name(loop_node.name)
                if var_name in payload and isinstance(payload[var_name], dict):
                    payload[var_name]['status'] = 'broken'
                    
            log_func(t("logs.loop_break_executing").format(loop_name))
            raise BreakLoopException(loop_node_id)

        elif self.type == 'continue_loop':
            active_loops = payload.get('__active_loops__', [])
            if not active_loops:
                log_func(t("logs.loop_continue_warning"))
                return 'out'
                
            loop_node_id = active_loops[-1]
            app = getattr(self.canvas, 'app', None)
            loop_node = app.nodes.get(loop_node_id) if app else None
            loop_name = loop_node.name if loop_node else f"ID {loop_node_id}"
            
            log_func(t("logs.loop_continue_executing").format(loop_name))
            raise ContinueLoopException(loop_node_id)

        elif self.type == 'storage_var':
            var_name = self.properties.get('variable_name', 'var_1')
            var_val_raw = self.properties.get('variable_value', '')
            resolved_value = resolve_value(var_val_raw, payload)
            
            payload[var_name] = resolved_value
            log_func(t("logs.storage_set").format(var_name, resolved_value))
            return 'out'
            
        elif self.type == 'confirm_dialog':
            title_raw = self.properties.get('title', 'Confirmação')
            message_raw = self.properties.get('message', 'Você deseja continuar?')
            btn_true_raw = self.properties.get('btn_true_text', 'Sim')
            btn_false_raw = self.properties.get('btn_false_text', 'Não')
            payload_var = self.properties.get('payload_var', 'confirm_result')
            
            title = str(resolve_value(title_raw, payload))
            message = str(resolve_value(message_raw, payload))
            btn_true = str(resolve_value(btn_true_raw, payload))
            btn_false = str(resolve_value(btn_false_raw, payload))
            
            log_func(f"Aguardando resposta da caixa de confirmação: '{title}'...")
            
            result_container = []
            event = threading.Event()
            
            def show_dialog():
                dialog = tk.Toplevel()
                dialog.title(title)
                dialog.configure(bg="#1e293b")
                dialog.resizable(False, False)
                dialog.attributes("-topmost", True)
                dialog.grab_set()
                
                dialog_width = 380
                dialog_height = 160
                screen_w = dialog.winfo_screenwidth()
                screen_h = dialog.winfo_screenheight()
                rx = (screen_w - dialog_width) // 2
                ry = (screen_h - dialog_height) // 2
                dialog.geometry(f"{dialog_width}x{dialog_height}+{rx}+{ry}")
                dialog.lift()
                dialog.focus_force()
                
                msg_lbl = tk.Label(
                    dialog, text=message, font=("Segoe UI", 10), fg="#f8fafc", bg="#1e293b",
                    wraplength=340, justify="center"
                )
                msg_lbl.pack(pady=(25, 20), padx=20, fill="both", expand=True)
                
                btn_frame = tk.Frame(dialog, bg="#1e293b")
                btn_frame.pack(fill="x", side="bottom", pady=(0, 20))
                
                def on_click(val):
                    result_container.append(val)
                    try:
                        dialog.grab_release()
                    except Exception:
                        pass
                    dialog.destroy()
                    event.set()
                
                btn_yes = tk.Button(
                    btn_frame, text=btn_true, font=("Segoe UI", 9, "bold"),
                    bg="#10b981", fg="#ffffff", activebackground="#059669", activeforeground="#ffffff",
                    bd=0, width=12, pady=6, cursor="hand2", command=lambda: on_click(True)
                )
                btn_yes.pack(side="left", padx=(50, 10), expand=True)
                
                btn_no = tk.Button(
                    btn_frame, text=btn_false, font=("Segoe UI", 9, "bold"),
                    bg="#64748b", fg="#ffffff", activebackground="#475569", activeforeground="#ffffff",
                    bd=0, width=12, pady=6, cursor="hand2", command=lambda: on_click(False)
                )
                btn_no.pack(side="right", padx=(10, 50), expand=True)
                
                dialog.protocol("WM_DELETE_WINDOW", lambda: on_click(False))
                
            self.canvas.after(0, show_dialog)
            event.wait()
            
            val = result_container[0] if result_container else False
            payload[payload_var] = val
            log_func(f"Caixa de confirmação respondida: {val}")
            return 'out'
            
        elif self.type == 'alert_dialog':
            title_raw = self.properties.get('title', 'Alerta')
            message_raw = self.properties.get('message', 'Fluxo interrompido!')
            btn_ok_raw = self.properties.get('btn_ok_text', 'OK')
            
            title = str(resolve_value(title_raw, payload))
            message = str(resolve_value(message_raw, payload))
            btn_ok = str(resolve_value(btn_ok_raw, payload))
            
            log_func(f"Aguardando fechamento da caixa de alerta: '{title}'...")
            
            event = threading.Event()
            
            def show_dialog():
                dialog = tk.Toplevel()
                dialog.title(title)
                dialog.configure(bg="#1e293b")
                dialog.resizable(False, False)
                dialog.attributes("-topmost", True)
                dialog.grab_set()
                
                dialog_width = 380
                dialog_height = 160
                screen_w = dialog.winfo_screenwidth()
                screen_h = dialog.winfo_screenheight()
                rx = (screen_w - dialog_width) // 2
                ry = (screen_h - dialog_height) // 2
                dialog.geometry(f"{dialog_width}x{dialog_height}+{rx}+{ry}")
                dialog.lift()
                dialog.focus_force()
                
                msg_lbl = tk.Label(
                    dialog, text=message, font=("Segoe UI", 10), fg="#f8fafc", bg="#1e293b",
                    wraplength=340, justify="center"
                )
                msg_lbl.pack(pady=(25, 20), padx=20, fill="both", expand=True)
                
                btn_frame = tk.Frame(dialog, bg="#1e293b")
                btn_frame.pack(fill="x", side="bottom", pady=(0, 20))
                
                def on_click():
                    try:
                        dialog.grab_release()
                    except Exception:
                        pass
                    dialog.destroy()
                    event.set()
                
                btn_btn = tk.Button(
                    btn_frame, text=btn_ok, font=("Segoe UI", 9, "bold"),
                    bg="#3b82f6", fg="#ffffff", activebackground="#2563eb", activeforeground="#ffffff",
                    bd=0, width=12, pady=6, cursor="hand2", command=on_click
                )
                btn_btn.pack(pady=5)
                
                dialog.protocol("WM_DELETE_WINDOW", on_click)
                
            self.canvas.after(0, show_dialog)
            event.wait()
            log_func("Caixa de alerta fechada.")
            return 'out'
            
        return None

    def delete(self):
        self.canvas.delete(self.tag)
        for p in self.ports.values():
            self.canvas.delete(p['tag'])
