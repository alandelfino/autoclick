"""
VisualNode — Graphical representation of a flow node on the canvas.

Handles drawing, port management, property defaults, execution logic,
and visual state (selection, highlight).
"""
import ctypes
import time
import json

from core.automation import click_mouse, simulate_keypress, get_active_window_info, simulate_type_text
from core.payload import get_payload_value, resolve_value
from core.i18n_helper import t


class BreakLoopException(Exception):
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
            'storage_var': {'header': '#ec4899', 'title': 'Var. Armazenamento'}
        }
        self.theme = self.themes.get(self.type, {'header': '#64748b', 'title': 'Nó'})

        # Setup Ports (positions relative to x, y)
        self.ports = {}
        self.setup_ports()

        # Canvas UI references
        self.tag = f"node_{self.id}"
        self.draw()

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
        elif self.type == 'break_loop':
            return {'loop_node_name': ''}
        elif self.type == 'storage_var':
            return {'variable_name': 'var_1', 'variable_value': ''}
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
        elif self.type == 'break_loop':
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
            summary = f"Parar Loop: {self.properties.get('loop_node_name', '')}"
        elif self.type == 'storage_var':
            summary = f"Var: {self.properties.get('variable_name', 'var_1')} = {self.properties.get('variable_value', '')}"
            
        self.summary_text_ui = self.canvas.create_text(
            self.x + 10, self.y + 75, text=summary, anchor="w",
            fill="#64748b", font=("Segoe UI", 8, "italic"), tags=self.tag, width=self.width - 20
        )

    def rename(self, new_name):
        self.name = new_name
        self.canvas.itemconfig(self.name_text_ui, text=new_name)

    def scale_fonts(self, scale):
        header_sz = max(int(8 * scale), 5)
        name_sz = max(int(10 * scale), 6)
        summary_sz = max(int(8 * scale), 5)
        port_sz = max(int(8 * scale), 5)
        
        self.canvas.itemconfig(self.header_text_ui, font=("Segoe UI", header_sz, "bold"))
        self.canvas.itemconfig(self.name_text_ui, font=("Segoe UI", name_sz, "bold"), width=max(int(self.width - 20), 10))
        
        if hasattr(self, 'summary_text_ui') and self.summary_text_ui:
            self.canvas.itemconfig(self.summary_text_ui, font=("Segoe UI", summary_sz, "italic"), width=max(int(self.width - 20), 10))
            
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
        color = "#2563eb" if selected else "#e2e8f0"
        width = 3 if selected else 2
        self.canvas.itemconfig(self.body_ui, outline=color, width=width)

    def highlight_execution(self, active):
        color = "#22c55e" if active else "#e2e8f0"
        width = 4 if active else 2
        self.canvas.itemconfig(self.body_ui, outline=color, width=width)

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
            if variable.startswith('{') and variable.endswith('}'):
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
                return 'out_item'
            else:
                log_func(t("logs.loop_end").format(self.name))
                payload[var_name]['status'] = 'done'
                return 'out_done'

        elif self.type == 'break_loop':
            loop_name = self.properties.get('loop_node_name', '')
            app = getattr(self.canvas, 'app', None)
            loop_node = None
            if app:
                for n in app.nodes.values():
                    if n.type == 'loop' and n.name == loop_name:
                        loop_node = n
                        break
            
            if not loop_node:
                log_func(t("logs.loop_break_warning").format(loop_name))
                return 'out'
                
            var_name = app.get_var_name(loop_node.name)
            if var_name in payload and isinstance(payload[var_name], dict):
                payload[var_name]['status'] = 'broken'
                
            log_func(t("logs.loop_break_executing").format(loop_name))
            raise BreakLoopException(loop_node.id)

        elif self.type == 'storage_var':
            var_name = self.properties.get('variable_name', 'var_1')
            var_val_raw = self.properties.get('variable_value', '')
            resolved_value = resolve_value(var_val_raw, payload)
            
            payload[var_name] = resolved_value
            log_func(t("logs.storage_set").format(var_name, resolved_value))
            return 'out'
            
        return None

    def delete(self):
        self.canvas.delete(self.tag)
        for p in self.ports.values():
            self.canvas.delete(p['tag'])
