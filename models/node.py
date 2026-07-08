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
import os
from PIL import Image, ImageTk

from core.automation import click_mouse, simulate_keypress, get_active_window_info, simulate_type_text, get_active_window_details
from core.payload import get_payload_value, resolve_value, truncate_payload_data
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


def get_rounded_rect_points(x, y, w, h, r=12, corners=(True, True, True, True), steps=10):
    import math
    points = []
    
    # Top-Left corner
    if corners[0]:
        for i in range(steps + 1):
            theta = math.pi + (i / steps) * (math.pi / 2)
            points.extend([x + r + r * math.cos(theta), y + r + r * math.sin(theta)])
    else:
        points.extend([x, y])
        
    # Top-Right corner
    if corners[1]:
        for i in range(steps + 1):
            theta = 1.5 * math.pi + (i / steps) * (math.pi / 2)
            points.extend([x + w - r + r * math.cos(theta), y + r + r * math.sin(theta)])
    else:
        points.extend([x + w, y])
        
    # Bottom-Right corner
    if corners[2]:
        for i in range(steps + 1):
            theta = 0.0 + (i / steps) * (math.pi / 2)
            points.extend([x + w - r + r * math.cos(theta), y + h - r + r * math.sin(theta)])
    else:
        points.extend([x + w, y + h])
        
    # Bottom-Left corner
    if corners[3]:
        for i in range(steps + 1):
            theta = 0.5 * math.pi + (i / steps) * (math.pi / 2)
            points.extend([x + r + r * math.cos(theta), y + h - r + r * math.sin(theta)])
    else:
        points.extend([x, y + h])
        
    return points


def get_recolored_icon(icon_name, color_hex, size=32):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(current_dir)
    icon_path = os.path.join(project_dir, "assets", "icons", f"{icon_name}.png")
    
    if not os.path.exists(icon_path):
        print(f"Icon path not found: {icon_path}")
        return None
        
    try:
        img = Image.open(icon_path).convert("RGBA")
        
        resample_filter = getattr(Image, 'LANCEZOS', getattr(Image, 'ANTIALIAS', 1))
        img = img.resize((size, size), resample_filter)
        
        hex_clean = color_hex.lstrip('#')
        r_target, g_target, b_target = tuple(int(hex_clean[i:i+2], 16) for i in (0, 2, 4))
        
        data = img.getdata()
        new_data = []
        for item in data:
            if item[3] > 0:
                new_data.append((r_target, g_target, b_target, item[3]))
            else:
                new_data.append(item)
                
        img.putdata(new_data)
        return ImageTk.PhotoImage(img)
    except Exception as e:
        print(f"Error loading and recoloring icon {icon_name}: {e}")
        return None


class VisualNode:
    ICON_MAPPING = {
        'start': 'play',
        'click': 'mouse-pointer',
        'capture': 'camera',
        'condition': 'question',
        'key': 'keyboard-o',
        'type_text': 'font',
        'delay': 'clock-o',
        'move_mouse': 'arrows',
        'postgres': 'database',
        'mysql': 'database',
        'sqlite': 'database',
        'api': 'globe',
        'loop': 'refresh',
        'break_loop': 'ban',
        'continue_loop': 'arrow-right',
        'storage_var': 'cube',
        'confirm_dialog': 'comments-o',
        'alert_dialog': 'exclamation-triangle',
        'switch': 'random',
        'js': 'code',
        'python': 'terminal'
    }

    def __init__(self, canvas, node_id, node_type, name, x, y, properties=None):
        self.canvas = canvas
        self.id = node_id
        self.type = node_type # 'click', 'capture', 'condition', 'key'
        self.name = name
        self.x = x
        self.y = y
        self.width = 68
        self.height = 68
        
        # Load default properties if none provided
        self.properties = properties if properties is not None else self.get_default_properties()
        
        # Ensure alias is set (especially when loading saved/external flows)
        if 'alias' not in self.properties:
            alias_map = {
                'start': 'inicio', 'click': 'clique', 'capture': 'captura', 'condition': 'condicao',
                'key': 'tecla', 'type_text': 'digitar', 'delay': 'delay', 'move_mouse': 'mover',
                'postgres': 'postgres', 'mysql': 'mysql', 'sqlite': 'sqlite', 'api': 'api',
                'loop': 'loop', 'break_loop': 'break', 'continue_loop': 'continue',
                'storage_var': 'var', 'confirm_dialog': 'confirmar', 'alert_dialog': 'alerta',
                'switch': 'switch', 'js': 'js', 'python': 'python'
            }
            prefix = alias_map.get(self.type, self.type)
            self.properties['alias'] = 'inicio' if self.type == 'start' else f"{prefix}_{self.id}"
        
        if self.type == 'switch':
            cases = self.properties.get('cases', [])
            self.height = max(68, 30 * (len(cases) + 1))
        elif self.type == 'condition':
            else_ifs = self.properties.get('else_ifs', [])
            self.height = max(68, 30 * (len(else_ifs) + 2))
        
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
            'alert_dialog': {'header': '#e11d48', 'title': t("toolbox.nodes.alert_dialog")},
            'switch': {'header': '#4f46e5', 'title': t("toolbox.nodes.switch")},
            'js': {'header': '#ca8a04', 'title': 'JavaScript'},
            'python': {'header': '#2b5b84', 'title': 'Python'}
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
        
        # Initialize plus handles only if zoom scale is 1.0 (to avoid double scaling on initial load)
        app = getattr(self.canvas, 'app', None)
        zoom_scale = getattr(app, 'zoom_scale', 1.0) if app else 1.0
        if zoom_scale == 1.0:
            self.update_plus_handles()

    def get_default_properties(self):
        alias_map = {
            'start': 'inicio', 'click': 'clique', 'capture': 'captura', 'condition': 'condicao',
            'key': 'tecla', 'type_text': 'digitar', 'delay': 'delay', 'move_mouse': 'mover',
            'postgres': 'postgres', 'mysql': 'mysql', 'sqlite': 'sqlite', 'api': 'api',
            'loop': 'loop', 'break_loop': 'break', 'continue_loop': 'continue',
            'storage_var': 'var', 'confirm_dialog': 'confirmar', 'alert_dialog': 'alerta',
            'switch': 'switch', 'js': 'js', 'python': 'python'
        }
        prefix = alias_map.get(self.type, self.type)
        alias_val = 'inicio' if self.type == 'start' else f"{prefix}_{self.id}"
        
        props = {}
        if self.type == 'click':
            props = {'x': 0, 'y': 0}
        elif self.type == 'capture':
            props = {'capture_type': 'Dados da Janela Ativa'}
        elif self.type == 'condition':
            props = {'variable': 'active_window.title', 'operator': 'contém', 'value': '', 'else_ifs': []}
        elif self.type == 'key':
            props = {'key': 'enter', 'count': 1}
        elif self.type == 'type_text':
            props = {'text': ''}
        elif self.type == 'delay':
            props = {'seconds': 1.0}
        elif self.type == 'move_mouse':
            props = {'x': 0, 'y': 0}
        elif self.type == 'start':
            props = {'loop_mode': 'Executar 1 vez', 'loop_count': 5}
        elif self.type in ['postgres', 'mysql', 'sqlite']:
            props = {'connection_name': '', 'sql': 'SELECT 1;', 'sample_payload': None}
        elif self.type == 'api':
            props = {'connection_name': '', 'method': 'GET', 'path': '', 'headers': '', 'body': '', 'sample_payload': None}
        elif self.type == 'loop':
            props = {'array_data': '[]'}
        elif self.type in ['break_loop', 'continue_loop']:
            props = {}
        elif self.type == 'storage_var':
            props = {'variable_name': 'var_1', 'variable_value': ''}
        elif self.type == 'confirm_dialog':
            props = {
                'title': 'Confirmação',
                'message': 'Você deseja continuar?',
                'btn_true_text': 'Sim',
                'btn_false_text': 'Não',
                'payload_var': 'confirm_result'
            }
        elif self.type == 'alert_dialog':
            props = {
                'title': 'Alerta',
                'message': 'Fluxo interrompido!',
                'btn_ok_text': 'OK'
            }
        elif self.type == 'switch':
            props = {
                'variable': 'active_window.title',
                'cases': ['Opção A', 'Opção B']
            }
        elif self.type == 'js':
            props = {'code': '// JavaScript\npayload.resultado = "sucesso JS";\nlog("Executou JS: " + payload.resultado);'}
        elif self.type == 'python':
            props = {'code': '# Python\npayload[\'resultado\'] = "sucesso Python"\nprint("Executou Python:", payload[\'resultado\'])'}
        else:
            props = {}
            
        props['alias'] = alias_val
        return props

    def setup_ports(self):
        # All nodes have 1 Input port on the left center EXCEPT the 'start' node
        if self.type != 'start':
            self.ports['in'] = {
                'rel_x': 0, 'rel_y': self.height // 2,
                'type': 'input', 'color': '#64748b',
                'tag': f"port_in_{self.id}"
            }
        
        if self.type == 'condition':
            else_ifs = self.properties.get('else_ifs', [])
            if not else_ifs:
                # Conditional node has 2 outputs (True/False)
                self.ports['out_true'] = {
                    'rel_x': self.width, 'rel_y': 20,
                    'type': 'output', 'color': '#22c55e', # Green
                    'label': t('properties.out_true'), 'tag': f"port_out_true_{self.id}"
                }
                self.ports['out_false'] = {
                    'rel_x': self.width, 'rel_y': 48,
                    'type': 'output', 'color': '#ef4444', # Red
                    'label': t('properties.out_false'), 'tag': f"port_out_false_{self.id}"
                }
            else:
                num_ports = len(else_ifs) + 2
                self.ports['out_true'] = {
                    'rel_x': self.width, 'rel_y': 20,
                    'type': 'output', 'color': '#22c55e',
                    'label': 'If', 'tag': f"port_out_true_{self.id}"
                }
                for i, else_if in enumerate(else_ifs):
                    rel_y = 20 + (self.height - 40) * (i + 1) // (num_ports - 1)
                    label_text = else_if.get('title', '').strip() or f'Else If {i+1}'
                    self.ports[f'out_else_if_{i}'] = {
                        'rel_x': self.width, 'rel_y': rel_y,
                        'type': 'output', 'color': '#0ea5e9',
                        'label': label_text, 'tag': f"port_out_else_if_{i}_{self.id}"
                    }
                self.ports['out_false'] = {
                    'rel_x': self.width, 'rel_y': self.height - 20,
                    'type': 'output', 'color': '#ef4444',
                    'label': 'Else', 'tag': f"port_out_false_{self.id}"
                }
        elif self.type == 'start':
            # Start node has 1 output on the right center
            self.ports['out'] = {
                'rel_x': self.width, 'rel_y': self.height // 2,
                'type': 'output', 'color': '#6366f1',
                'tag': f"port_out_{self.id}"
            }
        elif self.type == 'loop':
            self.ports['out_item'] = {
                'rel_x': self.width, 'rel_y': 20,
                'type': 'output', 'color': '#2563eb',
                'label': t('properties.loop_next_item'), 'tag': f"port_out_item_{self.id}"
            }
            self.ports['out_done'] = {
                'rel_x': self.width, 'rel_y': 48,
                'type': 'output', 'color': '#64748b',
                'label': t('properties.loop_done'), 'tag': f"port_out_done_{self.id}"
            }
        elif self.type in ['break_loop', 'continue_loop']:
            # No output ports
            pass
        elif self.type == 'switch':
            cases = self.properties.get('cases', [])
            num_ports = len(cases) + 1
            for i, case in enumerate(cases):
                rel_y = 20 + (self.height - 40) * i // (num_ports - 1) if num_ports > 1 else self.height // 2
                self.ports[f'out_case_{i}'] = {
                    'rel_x': self.width, 'rel_y': rel_y,
                    'type': 'output', 'color': '#3b82f6',
                    'label': str(case), 'tag': f"port_out_case_{i}_{self.id}"
                }
            rel_y_default = self.height - 20 if num_ports > 1 else self.height // 2
            self.ports['out_default'] = {
                'rel_x': self.width, 'rel_y': rel_y_default,
                'type': 'output', 'color': '#64748b',
                'label': 'Default', 'tag': f"port_out_default_{self.id}"
            }
        else:
            # Standard nodes have 1 output on the right center
            self.ports['out'] = {
                'rel_x': self.width, 'rel_y': self.height // 2,
                'type': 'output', 'color': '#3b82f6',
                'tag': f"port_out_{self.id}"
            }

    def draw(self):
        # 1. Main body card (rounded square card)
        r = 12
        points = get_rounded_rect_points(self.x, self.y, self.width, self.height, r, corners=(True, True, True, True))
        self.body_ui = self.canvas.create_polygon(
            points, fill="#ffffff", outline="#e2e8f0", width=2, tags=(self.tag, "node_body")
        )
        
        # Placeholder header references to prevent errors in other scripts
        self.header_ui = None
        self.header_text_ui = None
        
        # 2. Representative Icon (Image)
        icon_name = self.ICON_MAPPING.get(self.type, 'question')
        icon_color = self.theme.get('header', '#64748b')
        
        app = getattr(self.canvas, 'app', None)
        zoom_scale = getattr(app, 'zoom_scale', 1.0) if app else 1.0
        icon_sz = max(8, int(round(32 * zoom_scale)))
        
        self.icon_photo = get_recolored_icon(icon_name, icon_color, icon_sz)
        
        if self.icon_photo:
            self.icon_ui = self.canvas.create_image(
                self.x + self.width / 2, self.y + self.height / 2,
                image=self.icon_photo, tags=self.tag
            )
        else:
            self.icon_ui = self.canvas.create_text(
                self.x + self.width / 2, self.y + self.height / 2,
                text="?", fill=icon_color, font=("Segoe UI", 24, "bold"), tags=self.tag
            )
        
        # 3. Body Name Text (Editable by user) - placed outside node (below it)
        self.name_text_ui = self.canvas.create_text(
            self.x + self.width / 2, self.y + self.height + 12, text=self.name, anchor="n",
            fill="#1e293b", font=("Segoe UI", 9), tags=self.tag, width=120, justify="center"
        )
        
        # Placeholder summary text reference
        self.summary_text_ui = None
        
        # 4. Draw ports (circles and optional labels)
        for port_name, p in self.ports.items():
            px = self.x + p['rel_x']
            py = self.y + p['rel_y']
            
            # Draw port circle
            p['ui_circle'] = self.canvas.create_oval(
                px - 6, py - 6, px + 6, py + 6,
                fill="#ffffff", outline="#cbd5e1", width=2,
                tags=(p['tag'], "port", f"node_port_{self.id}_{port_name}")
            )
            
            # Draw text label if conditional
            if 'label' in p:
                is_right_side = (p['rel_x'] >= self.width / 2)
                text_anchor = "w" if is_right_side else "e"
                tx_offset = 10 if is_right_side else -10
                p['ui_label'] = self.canvas.create_text(
                    px + tx_offset, py, text=p['label'], anchor=text_anchor,
                    fill="#64748b", font=("Segoe UI", 8, "bold"), tags=self.tag
                )
                


    def update_summary_text(self):
        pass

    def rename(self, new_name):
        self.name = new_name
        self.canvas.itemconfig(self.name_text_ui, text=new_name)

    def scale_fonts(self, scale):
        name_sz = max(int(9 * scale), 1)
        port_sz = max(int(8 * scale), 1)
        icon_sz = max(8, int(round(32 * scale)))
        
        icon_name = self.ICON_MAPPING.get(self.type, 'question')
        icon_color = self.theme.get('header', '#64748b')
        
        self.icon_photo = get_recolored_icon(icon_name, icon_color, icon_sz)
        
        if self.icon_photo and hasattr(self, 'icon_ui') and self.icon_ui:
            self.canvas.itemconfig(self.icon_ui, image=self.icon_photo)
            
        if hasattr(self, 'name_text_ui') and self.name_text_ui:
            self.canvas.itemconfig(self.name_text_ui, font=("Segoe UI", name_sz), width=max(int(120 * scale), 5))
            
        for p in self.ports.values():
            if 'ui_label' in p and p['ui_label']:
                self.canvas.itemconfig(p['ui_label'], font=("Segoe UI", port_sz, "bold"))
                
        # Recreate plus handles for correct zoom scale positioning and styling
        self.update_plus_handles()

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
        is_multi_selected = (app and hasattr(app, 'selected_nodes') and self in app.selected_nodes)
        
        if self.is_executing:
            color = "#22c55e"
            width = 4
        elif is_selected:
            color = "#2563eb"
            width = 3
        elif is_multi_selected:
            color = "#3b82f6"
            width = 3
        elif getattr(self, 'is_hovered', False):
            color = "#3b82f6"
            width = 3
        else:
            color = "#e2e8f0"
            width = 2
            
        zoom_scale = getattr(app, 'zoom_scale', 1.0) if app else 1.0
        scaled_width = max(1, int(round(width * zoom_scale)))
        self.canvas.itemconfig(self.body_ui, outline=color, width=scaled_width)

    def on_enter(self, event):
        self.is_hovered = True
        self.update_outline()

    def on_leave(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        
        overlapping = self.canvas.find_overlapping(cx, cy, cx, cy)
        node_items = self.canvas.find_withtag(self.tag)
        is_still_over_node = any(item in overlapping for item in node_items)
        is_over_port = any("port" in self.canvas.gettags(item) for item in overlapping)
        
        if is_still_over_node and not is_over_port:
            return
            
        self.is_hovered = False
        self.update_outline()

    def update_plus_handles(self):
        # 1. Clean up existing plus handles
        if hasattr(self, 'plus_handles'):
            for item_ids in list(self.plus_handles.values()):
                for iid in item_ids:
                    try:
                        self.canvas.delete(iid)
                    except Exception:
                        pass
            self.plus_handles.clear()
        else:
            self.plus_handles = {}

        app = getattr(self.canvas, 'app', None)
        if not app:
            return

        zoom_scale = getattr(app, 'zoom_scale', 1.0)
        
        # 2. Iterate output ports
        for port_name, p in self.ports.items():
            if p.get('type') == 'output':
                # Check if this port is connected
                connected = False
                for conn in app.connections:
                    if conn.source == self and conn.source_port == port_name:
                        connected = True
                        break
                
                if not connected:
                    px, py = self.get_port_center(port_name)
                    
                    line_len = 30 * zoom_scale
                    box_sz = 16 * zoom_scale
                    r_corner = 4 * zoom_scale
                    
                    # Connection line segment
                    line_id = self.canvas.create_line(
                        px, py, px + line_len, py,
                        fill="#cbd5e1", width=max(1, int(round(2 * zoom_scale))), tags=(self.tag, "plus_handle")
                    )
                    
                    # Rounded box (16x16)
                    bx1, by1 = px + line_len, py - box_sz / 2
                    
                    points = get_rounded_rect_points(bx1, by1, box_sz, box_sz, r=r_corner)
                    box_id = self.canvas.create_polygon(
                        points, fill="#e2e8f0", outline="#cbd5e1", width=max(1, int(round(1 * zoom_scale))),
                        tags=(self.tag, f"plus_btn_{self.id}_{port_name}", "plus_handle")
                    )
                    
                    # Plus text (centered)
                    plus_font_sz = max(1, int(round(10 * zoom_scale)))
                    text_id = self.canvas.create_text(
                        bx1 + box_sz / 2, py + (0.5 * zoom_scale), text="+", fill="#475569",
                        font=("Segoe UI", plus_font_sz, "bold"), anchor="center",
                        tags=(self.tag, f"plus_btn_{self.id}_{port_name}", "plus_handle")
                    )
                    
                    self.plus_handles[port_name] = [line_id, box_id, text_id]
                    
                    # Bind click and hover events to the box and text
                    tag_name = f"plus_btn_{self.id}_{port_name}"
                    self.canvas.tag_bind(tag_name, "<Button-1>", lambda event, pn=port_name: self.on_click_plus_handle(pn))
                    self.canvas.tag_bind(tag_name, "<Enter>", lambda event, tn=tag_name: self.canvas.config(cursor="hand2"))
                    self.canvas.tag_bind(tag_name, "<Leave>", lambda event: self.canvas.config(cursor=""))
                    
        # Raise port text labels to be drawn on top of the plus handles
        for p in self.ports.values():
            if 'ui_label' in p and p['ui_label']:
                self.canvas.tag_raise(p['ui_label'])

    def on_click_plus_handle(self, port_name):
        app = getattr(self.canvas, 'app', None)
        if app and hasattr(app, 'slide_panel_in'):
            app.slide_panel_in(self, port_name)

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
        
        is_multi = (app and hasattr(app, 'selected_nodes') and len(app.selected_nodes) > 1 and self in app.selected_nodes)
        
        if is_multi:
            menu.add_command(
                label=t("canvas.context_delete_selected"),
                command=lambda: app.delete_multiple_nodes(list(app.selected_nodes))
            )
        else:
            if app and hasattr(app, 'selected_nodes') and self not in app.selected_nodes:
                app._clear_multi_selection_visuals()
                app.selected_nodes.clear()
            if app:
                app.selected_node = self
                for n in app.nodes.values():
                    n.update_outline()
            
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
        alias = self.properties.get('alias', f"node_{self.id}")
        
        if self.type == 'start':
            log_func(t("logs.start_executing"))
            win_details = get_active_window_details()
            
            app = getattr(self.canvas, 'app', None)
            run_idx = getattr(app, 'current_run', 1)
            total_runs = getattr(app, 'max_runs', 1)
            
            payload.clear()
            payload[alias] = {
                'active_window': {
                    'title': win_details['title'],
                    'width': win_details['width'],
                    'height': win_details['height'],
                    'hwnd': win_details['hwnd']
                },
                'flow': {
                    'index': run_idx,
                    'total_execution': total_runs
                }
            }
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
            result = {'x': x, 'y': y}
            payload[alias] = result
            return 'out'
            
        elif self.type == 'capture':
            capture_type = self.properties.get('capture_type', 'Active Window Data')
            if capture_type in ['Dados da Janela Ativa', 'Janela Ativa', 'Active Window Data']:
                win_details = get_active_window_details()
                title, hwnd = win_details['title'], win_details['hwnd']
                log_func(t("logs.capture_window_success").format(title, hwnd))
                result = {'title': title, 'hwnd': hwnd}
                payload[alias] = result
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
                result = {'x': x, 'y': y, 'cursor_name': cursor_name, 'cursor_handle': h_cursor}
                payload[alias] = result
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
            result = {'key': key, 'count': count}
            payload[alias] = result
            return 'out'
            
        elif self.type == 'type_text':
            raw_text = self.properties.get('text', '')
            formatted_text = str(resolve_value(raw_text, payload))
            log_func(t("logs.text_typing").format(formatted_text))
            simulate_type_text(formatted_text)
            payload[alias] = formatted_text
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
            payload[alias] = {'seconds': secs}
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
            result = {'x': x, 'y': y}
            payload[alias] = result
            return 'out'
            
        elif self.type == 'condition':
            variable_raw = self.properties.get('variable', '')
            operator = self.properties.get('operator', 'equals')
            target_value_raw = self.properties.get('value', '')
            
            if '{' in variable_raw or '}' in variable_raw:
                actual_value = resolve_value(variable_raw, payload)
            else:
                actual_value = get_payload_value(payload, variable_raw)
                if actual_value is None:
                    actual_value = variable_raw
            if actual_value is None:
                actual_value = ""
                
            target_value = resolve_value(str(target_value_raw), payload)
            
            log_func(t("logs.condition_current_val").format(variable_raw, actual_value))
            log_func(t("logs.condition_comparing").format(actual_value, operator, target_value))
            
            def evaluate(act_val, op, tgt_val):
                res = False
                str_act = str(act_val).lower()
                str_tgt = str(tgt_val).lower()
                if op in ['igual', 'equals']:
                    res = str_act == str_tgt
                elif op in ['diferente', 'different']:
                    res = str_act != str_tgt
                elif op in ['contém', 'contains']:
                    res = str_tgt in str_act
                elif op in ['maior que', 'greater than']:
                    try:
                        res = float(act_val) > float(tgt_val)
                    except ValueError:
                        res = False
                return res

            result = evaluate(actual_value, operator, target_value)
            log_func(t("logs.condition_result").format(result))
            
            # Else If checks
            matched_port = 'out_false'
            if result:
                matched_port = 'out_true'
            else:
                else_ifs = self.properties.get('else_ifs', [])
                for i, else_if in enumerate(else_ifs):
                    var_else_if_raw = else_if.get('variable', '')
                    if '{' in var_else_if_raw or '}' in var_else_if_raw:
                        act_val_else_if = resolve_value(var_else_if_raw, payload)
                    else:
                        act_val_else_if = get_payload_value(payload, var_else_if_raw)
                        if act_val_else_if is None:
                            act_val_else_if = var_else_if_raw
                    if act_val_else_if is None:
                        act_val_else_if = ""
                        
                    op_else_if = else_if.get('operator', 'equals')
                    tgt_val_else_if_raw = else_if.get('value', '')
                    tgt_val_else_if = resolve_value(str(tgt_val_else_if_raw), payload)
                    
                    log_func(f" -> Else If {i+1}: valor atual de '{var_else_if_raw}' = '{act_val_else_if}'")
                    log_func(f" -> Comparando Else If {i+1}: '{act_val_else_if}' {op_else_if} '{tgt_val_else_if}'")
                    
                    res_else_if = evaluate(act_val_else_if, op_else_if, tgt_val_else_if)
                    log_func(f" -> Resultado do Else If {i+1}: {res_else_if}")
                    if res_else_if:
                        matched_port = f'out_else_if_{i}'
                        break
            
            payload[alias] = matched_port == 'out_true' or matched_port.startswith('out_else_if_')
            return matched_port
            
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
                        self.properties['sample_payload'] = truncate_payload_data(result)
                        payload[alias] = result
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
                        self.properties['sample_payload'] = truncate_payload_data(result)
                        payload[alias] = result
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
                        self.properties['sample_payload'] = truncate_payload_data(result)
                        payload[alias] = result
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
                    self.properties['sample_payload'] = truncate_payload_data(result)
                    payload[alias] = result
                    log_func(t("logs.api_ok").format(result['status_code']))
                except Exception as e:
                    log_func(t("logs.api_error").format(str(e)))
                    raise e
            return 'out'

        elif self.type == 'js':
            code_raw = self.properties.get('code', '')
            code_resolved = resolve_value(code_raw, payload)
            
            log_func(t("logs.js_executing").format(self.name))
            
            import subprocess
            import tempfile
            import os
            
            use_node = False
            try:
                res = subprocess.run(["node", "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=1)
                if res.returncode == 0:
                    use_node = True
            except Exception:
                pass
                
            payload_json = json.dumps(payload, ensure_ascii=False)
            
            wrapper = f"""
var payload = {payload_json};
function log(msg) {{
    if (typeof console !== 'undefined') {{
        console.log("LOG:" + msg);
    }} else {{
        WScript.Echo("LOG:" + msg);
    }}
}}
var __result = (function() {{
    try {{
        {code_resolved}
    }} catch(e) {{
        if (typeof console !== 'undefined') {{
            console.log("ERROR:" + (e.stack || e.message || e));
        }} else {{
            WScript.Echo("ERROR:" + (e.message || e));
        }}
    }}
}})();

if (typeof JSON !== 'undefined') {{
    var out = "PAYLOAD_RESULT:" + JSON.stringify({{ payload: payload, result: __result }});
    if (typeof console !== 'undefined') {{
        console.log(out);
    }} else {{
        WScript.Echo(out);
    }}
}} else {{
    var parts = [];
    for (var k in payload) {{
        if (payload.hasOwnProperty(k)) {{
            var v = payload[k];
            var vStr = "";
            if (typeof v === "string") vStr = '"' + v.replace(/"/g, '\\\\"') + '"';
            else if (typeof v === "object") vStr = "null";
            else vStr = String(v);
            parts.push('"' + k + '":' + vStr);
        }}
    }}
    var out = "PAYLOAD_RESULT:{{\\"payload\\":{{" + parts.join(",") + "}},\\"result\\":null}}";
    if (typeof console !== 'undefined') {{
        console.log(out);
    }} else {{
        WScript.Echo(out);
    }}
}}
"""
            temp_dir = tempfile.gettempdir()
            temp_file_path = os.path.join(temp_dir, f"autoclick_js_{self.id}_{int(time.time())}.js")
            
            with open(temp_file_path, "w", encoding="utf-8") as f:
                f.write(wrapper)
                
            try:
                if use_node:
                    cmd = ["node", temp_file_path]
                else:
                    cmd = ["cscript", "//Nologo", temp_file_path]
                    
                process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
                stdout = process.stdout
                stderr = process.stderr
                
                for line in stdout.splitlines():
                    if line.startswith("LOG:"):
                        log_func(f"[JS] {line[4:]}")
                    elif line.startswith("ERROR:"):
                        log_func(f"[JS Error] {line[6:]}")
                    elif line.startswith("PAYLOAD_RESULT:"):
                        try:
                            output_data = json.loads(line[15:])
                            new_payload = output_data.get("payload", {})
                            js_result = output_data.get("result")
                            
                            payload.clear()
                            payload.update(new_payload)
                            
                            payload[alias] = js_result
                        except Exception as ex:
                            log_func(f"[JS] Error parsing updated payload: {ex}")
                            
                if stderr:
                    log_func(f"[JS StdErr] {stderr.strip()}")
            except Exception as e:
                log_func(f"[JS] Execution failed: {e}")
                raise e
            finally:
                try:
                    os.remove(temp_file_path)
                except Exception:
                    pass
            return 'out'

        elif self.type == 'python':
            code_raw = self.properties.get('code', '')
            code_resolved = resolve_value(code_raw, payload)
            
            log_func(t("logs.python_executing").format(self.name))
            
            local_scope = {
                'payload': payload,
                'log': log_func,
                'print': lambda *args: log_func("[Python] " + " ".join(str(a) for a in args))
            }
            
            if not code_resolved.strip():
                indented_code = "    pass"
            else:
                indented_lines = []
                for line in code_resolved.splitlines():
                    indented_lines.append("    " + line)
                indented_code = "\n".join(indented_lines)
            
            wrapper_code = f"""
def __user_function():
{indented_code}

__result = __user_function()
"""
            try:
                exec(wrapper_code, {}, local_scope)
                py_result = local_scope.get('__result')
                
                payload[alias] = py_result
                    
            except Exception as e:
                log_func(f"[Python Error] {e}")
                raise e
            return 'out'

        elif self.type == 'loop':
            app = getattr(self.canvas, 'app', None)
            if not app:
                return 'out_done'
                
            var_name = app.get_var_name(self.name)
            
            # Check if interrupted
            if alias in payload and isinstance(payload[alias], dict):
                if payload[alias].get('status') == 'broken':
                    log_func(t("logs.loop_break_detect").format(self.name))
                    payload[alias]['status'] = 'done'
                    if var_name in payload and isinstance(payload[var_name], dict):
                        payload[var_name]['status'] = 'done'
                    if '__active_loops__' in payload and self.id in payload['__active_loops__']:
                        payload['__active_loops__'].remove(self.id)
                    return 'out_done'
            elif var_name in payload and isinstance(payload[var_name], dict):
                if payload[var_name].get('status') == 'broken':
                    log_func(t("logs.loop_break_detect").format(self.name))
                    payload[var_name]['status'] = 'done'
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
            if alias in payload and isinstance(payload[alias], dict):
                if payload[alias].get('status') == 'running':
                    is_running = True
            elif var_name in payload and isinstance(payload[var_name], dict):
                if payload[var_name].get('status') == 'running':
                    is_running = True
            
            if not is_running:
                log_func(t("logs.loop_start").format(self.name, len(items)))
                loop_state = {
                    'item': None,
                    'index': 0,
                    'total': len(items),
                    'status': 'running'
                }
            else:
                if alias in payload and isinstance(payload[alias], dict):
                    curr_idx_val = payload[alias]['index'] + 1
                else:
                    curr_idx_val = payload[var_name]['index'] + 1
                loop_state = {
                    'item': None,
                    'index': curr_idx_val,
                    'total': len(items),
                    'status': 'running'
                }
                
            curr_idx = loop_state['index']
            if curr_idx < len(items):
                loop_state['item'] = items[curr_idx]
                log_func(t("logs.loop_iteration").format(self.name, curr_idx + 1, len(items), items[curr_idx]))
                payload[alias] = loop_state
                payload[var_name] = loop_state
                if '__active_loops__' not in payload:
                    payload['__active_loops__'] = []
                if self.id not in payload['__active_loops__']:
                    payload['__active_loops__'].append(self.id)
                return 'out_item'
            else:
                log_func(t("logs.loop_end").format(self.name))
                loop_state['status'] = 'done'
                payload[alias] = loop_state
                payload[var_name] = loop_state
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
                loop_alias = loop_node.properties.get('alias', f"node_{loop_node_id}")
                if loop_alias in payload and isinstance(payload[loop_alias], dict):
                    payload[loop_alias]['status'] = 'broken'
                if var_name in payload and isinstance(payload[var_name], dict):
                    payload[var_name]['status'] = 'broken'
                    
            log_func(t("logs.loop_break_executing").format(loop_name))
            payload[alias] = True
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
            payload[alias] = True
            raise ContinueLoopException(loop_node_id)

        elif self.type == 'storage_var':
            var_val_raw = self.properties.get('variable_value', '')
            resolved_value = resolve_value(var_val_raw, payload)
            
            payload[alias] = resolved_value
            log_func(t("logs.storage_set").format(alias, resolved_value))
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
            payload[alias] = val
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
            payload[alias] = True
            return 'out'
            
        elif self.type == 'switch':
            variable = self.properties.get('variable', '')
            while variable.startswith('{') and variable.endswith('}'):
                variable = variable[1:-1]
            
            actual_value = get_payload_value(payload, variable)
            if actual_value is None:
                actual_value = ""
                
            cases = self.properties.get('cases', [])
            str_actual = str(actual_value).strip().lower()
            
            log_func(f" -> Switch: valor atual de '{variable}' = '{actual_value}'")
            
            matched_port = 'out_default'
            for i, case in enumerate(cases):
                if str(case).strip().lower() == str_actual:
                    matched_port = f'out_case_{i}'
                    log_func(f" -> Switch correspondência encontrada: '{case}' (Porta: {matched_port})")
                    break
            
            if matched_port == 'out_default':
                log_func(f" -> Switch nenhuma correspondência encontrada. Indo pelo caminho Default.")
            
            payload[alias] = actual_value
            return matched_port
            
        return None

    def delete(self):
        self.canvas.delete(self.tag)
        for p in self.ports.values():
            self.canvas.delete(p['tag'])
            if 'ui_label' in p:
                self.canvas.delete(p['ui_label'])

    def redraw(self):
        self.canvas.delete(self.tag)
        for p in self.ports.values():
            self.canvas.delete(p['tag'])
            if 'ui_label' in p:
                self.canvas.delete(p['ui_label'])
        
        # Clean up plus handles too
        if hasattr(self, 'plus_handles'):
            for item_ids in list(self.plus_handles.values()):
                for iid in item_ids:
                    try:
                        self.canvas.delete(iid)
                    except Exception:
                        pass
            self.plus_handles.clear()
        
        if self.type == 'switch':
            cases = self.properties.get('cases', [])
            self.height = max(68, 30 * (len(cases) + 1))
        elif self.type == 'condition':
            else_ifs = self.properties.get('else_ifs', [])
            self.height = max(68, 30 * (len(else_ifs) + 2))
            
        self.ports = {}
        self.setup_ports()
        self.draw()
        
        app = getattr(self.canvas, 'app', None)
        zoom_scale = getattr(app, 'zoom_scale', 1.0) if app else 1.0
        if zoom_scale != 1.0:
            cx, cy = self.x, self.y
            self.canvas.scale(self.tag, cx, cy, zoom_scale, zoom_scale)
            for p in self.ports.values():
                self.canvas.scale(p['tag'], cx, cy, zoom_scale, zoom_scale)
            self.scale_fonts(zoom_scale)
        else:
            self.update_plus_handles()
        
        self.canvas.tag_bind(self.tag, "<Enter>", self.on_enter)
        self.canvas.tag_bind(self.tag, "<Leave>", self.on_leave)
        self.canvas.tag_bind(self.tag, "<Button-3>", self.on_right_click_node)
        self.canvas.tag_bind(self.tag, "<Button-2>", self.on_right_click_node)
