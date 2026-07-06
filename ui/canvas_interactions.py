"""
Canvas interactions — Drag & drop, click handling, connection drag, context menu,
marquee selection, Shift+Click multi-select, and multi-node dragging.
"""
import tkinter as tk
from tkinter import messagebox

from models.connection import VisualConnection


class CanvasInteractionsMixin:
    """Mixin providing canvas interaction handlers (click, drag, release)."""

    def on_click_canvas(self, event):
        is_ctrl = bool(event.state & 0x0004)
        is_shift = bool(event.state & 0x0001)

        # 0. Ctrl on empty canvas = pan
        if is_ctrl:
            cx = self.canvas.canvasx(event.x)
            cy = self.canvas.canvasy(event.y)
            item = self.canvas.find_withtag("current")
            if item:
                tags = self.canvas.gettags(item[0])
                node_tag = [t for t in tags if t.startswith("node_") and not t.startswith("node_port_")]
                if node_tag:
                    node_id = int(node_tag[0].split("_")[1])
                    node = self.nodes[node_id]
                    self.toggle_node_multi_select(node)
                    return
            # Ctrl on empty canvas = pan
            self.is_panning_with_ctrl = True
            self.canvas.scan_mark(event.x, event.y)
            return

        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        
        item = self.canvas.find_withtag("current")
        if not item:
            # Clicked empty canvas space — start marquee selection
            self._start_marquee(cx, cy)
            return
            
        tags = self.canvas.gettags(item[0])
        
        # Check if clicked on a Waypoint
        if "waypoint" in tags:
            self.is_dragging_waypoint = True
            self.drag_data['x'] = cx
            self.drag_data['y'] = cy
            return
        
        # 1. Clicked on a Port
        if "port" in tags:
            port_tag = [t for t in tags if t.startswith("node_port_")][0]
            parts = port_tag.split("_")
            source_id = int(parts[2])
            port_name = "_".join(parts[3:])
            
            source_node = self.nodes[source_id]
            
            if source_node.ports[port_name]['type'] == 'output':
                self.active_port_drag = (source_node, port_name)
                px, py = source_node.get_port_center(port_name)
                zoom_scale = getattr(self, 'zoom_scale', 1.0)
                scaled_width = max(1, int(round(2 * zoom_scale)))
                dash_len = max(1, int(round(4 * zoom_scale)))
                scaled_dash = (dash_len, dash_len)
                self.temp_line_id = self.canvas.create_line(
                    px, py, cx, cy,
                    fill="#3b82f6", width=scaled_width, dash=scaled_dash, tags="temp_conn",
                    capstyle="round", joinstyle="round"
                )
            return
            
        # 2. Clicked on Node Body
        node_tag = [t for t in tags if t.startswith("node_") and not t.startswith("node_port_")]
        if node_tag:
            node_id = int(node_tag[0].split("_")[1])
            node = self.nodes[node_id]
            
            # Shift+Click — add/remove from multi-selection
            if is_shift:
                self._shift_click_node(node)
                self.drag_data['x'] = cx
                self.drag_data['y'] = cy
                return
            
            # If clicking a node that is already in multi-selection, start multi-drag
            if node in self.selected_nodes:
                self.drag_data['x'] = cx
                self.drag_data['y'] = cy
                self._is_multi_dragging = True
                return
            
            # Regular single-node select (this clears multi-selection)
            self._clear_multi_selection_visuals()
            self.selected_nodes.clear()
            self.selected_node = node
            
            # Deselect previous
            for n in self.nodes.values():
                if n != node:
                    n.update_outline()
            node.select(True)
            
            self._is_multi_dragging = False
            self.drag_data['x'] = cx
            self.drag_data['y'] = cy

    def _shift_click_node(self, node):
        """Shift+Click: toggle node in/out of the multi-selection set."""
        if node in self.selected_nodes:
            self.selected_nodes.discard(node)
        else:
            self.selected_nodes.add(node)
        # Also add current single-selected node to set if exists
        if self.selected_node and self.selected_node not in self.selected_nodes:
            self.selected_nodes.add(self.selected_node)
        self.selected_node = None
        # Refresh all outlines
        for n in self.nodes.values():
            n.update_outline()

    def _clear_multi_selection_visuals(self):
        """Refresh outlines for all previously multi-selected nodes."""
        if self.selected_nodes:
            for n in list(self.selected_nodes):
                n.update_outline()

    def _start_marquee(self, cx, cy):
        """Begin marquee (lasso) selection on the canvas."""
        # Clear ALL selections first
        self._clear_multi_selection_visuals()
        self.selected_nodes.clear()
        if self.selected_node:
            self.selected_node.select(False)
            self.selected_node = None
        
        self.marquee_data = {'x1': cx, 'y1': cy, 'x2': cx, 'y2': cy}
        self.marquee_rect_id = self.canvas.create_rectangle(
            cx, cy, cx, cy,
            outline="#3b82f6", width=2, dash=(4, 4),
            fill="#3b82f6", stipple="gray12",
            tags="marquee_rect"
        )

    def on_drag_canvas(self, event):
        # 0. Check if panning with control is active
        if getattr(self, 'is_panning_with_ctrl', False):
            self.canvas.scan_dragto(event.x, event.y, gain=1)
            self.draw_grid()
            return

        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        
        # Marquee selection drag
        if getattr(self, 'marquee_data', None) and self.marquee_rect_id:
            self.marquee_data['x2'] = cx
            self.marquee_data['y2'] = cy
            self.canvas.coords(
                self.marquee_rect_id,
                self.marquee_data['x1'], self.marquee_data['y1'],
                cx, cy
            )
            return
        
        # 1. Processing connecting line drag
        if self.active_port_drag and self.temp_line_id:
            src_node, port_name = self.active_port_drag
            px, py = src_node.get_port_center(port_name)
            self.canvas.coords(self.temp_line_id, px, py, cx, cy)
            return
        
        # 2. Multi-node dragging
        if getattr(self, '_is_multi_dragging', False) and self.selected_nodes:
            dx = cx - self.drag_data['x']
            dy = cy - self.drag_data['y']
            
            for node in self.selected_nodes:
                node.move_by(dx, dy)
            
            selected_ids = {n.id for n in self.selected_nodes}
            for conn in self.connections:
                if conn.source.id in selected_ids or conn.target.id in selected_ids:
                    conn.update_line()
            
            self.drag_data['x'] = cx
            self.drag_data['y'] = cy
            return
            
        # 3. Processing single node movements
        if self.selected_node and not self.active_port_drag and not getattr(self, 'is_dragging_waypoint', False):
            dx = cx - self.drag_data['x']
            dy = cy - self.drag_data['y']
            
            self.selected_node.move_by(dx, dy)
            
            for conn in self.connections:
                if conn.source.id == self.selected_node.id or conn.target.id == self.selected_node.id:
                    conn.update_line()
                    
            self.drag_data['x'] = cx
            self.drag_data['y'] = cy

    def on_release_canvas(self, event):
        self.is_dragging_waypoint = False
        
        # 0. Check if panning with control is active
        if getattr(self, 'is_panning_with_ctrl', False):
            self.is_panning_with_ctrl = False
            return

        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        
        # Finish marquee selection
        if getattr(self, 'marquee_data', None) is not None:
            self._finish_marquee()
            self._is_multi_dragging = False
            return
        
        # Reset multi-drag flag
        if getattr(self, '_is_multi_dragging', False):
            self._is_multi_dragging = False
            self.trigger_auto_save()
            return
        
        # Clean temporary helper line
        if self.temp_line_id:
            self.canvas.delete(self.temp_line_id)
            self.temp_line_id = None
            
        if self.active_port_drag:
            src_node, src_port = self.active_port_drag
            
            items = self.canvas.find_overlapping(cx - 6, cy - 6, cx + 6, cy + 6)
            target_node_id = None
            target_port = None
            
            for item_id in items:
                tags = self.canvas.gettags(item_id)
                port_tag = [t for t in tags if t.startswith("node_port_")]
                if port_tag:
                    parts = port_tag[0].split("_")
                    target_node_id = int(parts[2])
                    target_port = "_".join(parts[3:])
                    break
                    
            if target_node_id and target_port:
                tgt_node = self.nodes[target_node_id]
                
                is_valid = (
                    tgt_node.ports[target_port]['type'] == 'input' and
                    src_node.id != tgt_node.id
                )
                
                if is_valid:
                    existing_conn = None
                    for c in self.connections:
                        if c.source.id == src_node.id and c.source_port == src_port:
                            existing_conn = c
                            break
                            
                    if existing_conn:
                        existing_conn.delete()
                        self.connections.remove(existing_conn)
                        self.log_message(f"Conexão anterior saindo de {src_node.name} ({src_port}) substituída.")
                        
                    duplicate = any(
                        c.source.id == src_node.id and c.source_port == src_port and
                        c.target.id == tgt_node.id and c.target_port == target_port
                        for c in self.connections
                    )
                    
                    if not duplicate:
                        new_conn = VisualConnection(self.canvas, src_node, src_port, tgt_node, target_port)
                        self.connections.append(new_conn)
                        self.log_message(f"Conexão criada: {src_node.name} ({src_port}) -> {tgt_node.name}")
                    else:
                        messagebox.showwarning("Aviso", "Esta conexão específica já existe.")
                        
            self.active_port_drag = None
        self.trigger_auto_save()

    def _finish_marquee(self):
        """Complete marquee selection — find all nodes within the rectangle."""
        md = self.marquee_data
        if md is None:
            return
            
        x1 = min(md['x1'], md['x2'])
        y1 = min(md['y1'], md['y2'])
        x2 = max(md['x1'], md['x2'])
        y2 = max(md['y1'], md['y2'])
        
        # Remove the visual marquee rectangle
        if self.marquee_rect_id:
            self.canvas.delete(self.marquee_rect_id)
            self.marquee_rect_id = None
        self.marquee_data = None
        
        # If the marquee is too small (just a click), treat as full deselect
        if abs(x2 - x1) < 5 and abs(y2 - y1) < 5:
            # Already cleared in _start_marquee, ensure outlines are refreshed
            for n in self.nodes.values():
                n.update_outline()
            return
        
        # Find all nodes whose body center is within the marquee rectangle
        selected = set()
        for node in self.nodes.values():
            try:
                coords = self.canvas.coords(node.body_ui)
                if len(coords) == 4:
                    nx1, ny1, nx2, ny2 = coords
                    node_cx = (nx1 + nx2) / 2.0
                    node_cy = (ny1 + ny2) / 2.0
                    if x1 <= node_cx <= x2 and y1 <= node_cy <= y2:
                        selected.add(node)
            except Exception:
                pass
        
        # Apply selection
        self.selected_nodes = selected
        # Refresh ALL node outlines to ensure clean state
        for node in self.nodes.values():
            node.update_outline()
