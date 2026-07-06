"""
Canvas interactions — Drag & drop, click handling, connection drag, context menu.
"""
import tkinter as tk
from tkinter import messagebox

from models.connection import VisualConnection


class CanvasInteractionsMixin:
    """Mixin providing canvas interaction handlers (click, drag, release)."""

    def on_click_canvas(self, event):
        # 0. Check if Control key is held down to initiate panning gesture
        if event.state & 0x0004:
            self.is_panning_with_ctrl = True
            self.canvas.scan_mark(event.x, event.y)
            return

        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        
        item = self.canvas.find_withtag("current")
        if not item:
            # Clicked empty canvas space
            self.select_node(None)
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
            # Locate node and port info from tag list
            port_tag = [t for t in tags if t.startswith("node_port_")][0]
            parts = port_tag.split("_")
            source_id = int(parts[2])
            port_name = "_".join(parts[3:]) # handle double values like 'out_true'
            
            source_node = self.nodes[source_id]
            
            # We can only drag link FROM output ports
            if source_node.ports[port_name]['type'] == 'output':
                self.active_port_drag = (source_node, port_name)
                px, py = source_node.get_port_center(port_name)
                # Create a visual helper link line
                self.temp_line_id = self.canvas.create_line(
                    px, py, cx, cy,
                    fill="#3b82f6", width=2, dash=(4, 4), tags="temp_conn"
                )
            return
            
        # 2. Clicked on Node Body
        node_tag = [t for t in tags if t.startswith("node_")]
        if node_tag:
            node_id = int(node_tag[0].split("_")[1])
            node = self.nodes[node_id]
            self.select_node(node)
            
            # Cache drag coordinates in canvas space
            self.drag_data['x'] = cx
            self.drag_data['y'] = cy

    def on_drag_canvas(self, event):
        # 0. Check if panning with control is active
        if getattr(self, 'is_panning_with_ctrl', False):
            self.canvas.scan_dragto(event.x, event.y, gain=1)
            self.draw_grid()
            return

        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        
        # 1. Processing connecting line drag
        if self.active_port_drag and self.temp_line_id:
            src_node, port_name = self.active_port_drag
            px, py = src_node.get_port_center(port_name)
            self.canvas.coords(self.temp_line_id, px, py, cx, cy)
            return
            
        # 2. Processing node movements
        if self.selected_node and not self.active_port_drag and not getattr(self, 'is_dragging_waypoint', False):
            dx = cx - self.drag_data['x']
            dy = cy - self.drag_data['y']
            
            self.selected_node.move_by(dx, dy)
            
            # Re-draw lines connected to the selected node
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
        
        # Clean temporary helper line
        if self.temp_line_id:
            self.canvas.delete(self.temp_line_id)
            self.temp_line_id = None
            
        if self.active_port_drag:
            src_node, src_port = self.active_port_drag
            
            # Find item overlapping drop location (in canvas space)
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
                
                # Verify logic validations
                is_valid = (
                    tgt_node.ports[target_port]['type'] == 'input' and # Must connect to an Input port
                    src_node.id != tgt_node.id # Can't connect to self
                )
                
                if is_valid:
                    # Enforce Rule: An OUTPUT port can only connect to a single input port
                    existing_conn = None
                    for c in self.connections:
                        if c.source.id == src_node.id and c.source_port == src_port:
                            existing_conn = c
                            break
                            
                    if existing_conn:
                        # Clear old connection from this output port
                        existing_conn.delete()
                        self.connections.remove(existing_conn)
                        self.log_message(f"Conexão anterior saindo de {src_node.name} ({src_port}) substituída.")
                        
                    # Check if this exact new connection duplicate exists
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
