"""
Canvas panel — Canvas setup, grid drawing, zoom/pan controls, and auto-layout.
"""
import tkinter as tk
from tkinter import ttk
from core.i18n_helper import t


class CanvasPanelMixin:
    """Mixin providing canvas setup, grid, zoom, pan, center, and auto-layout."""

    def setup_center_panel(self):
        # Create Notebook (Tabs)
        self.notebook = ttk.Notebook(self.center_panel)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Tab 1: Fluxo (Flow)
        self.tab_flow = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_flow, text=t("canvas.tab_flow"))
        
        # Tab 2: Conexões (Connections)
        self.tab_conn = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_conn, text=t("canvas.tab_conn"))
        
        # Create full window size canvas inside self.tab_flow (not packed yet)
        self.canvas = tk.Canvas(self.tab_flow, bg="#f1f5f9", highlightthickness=0)
        self.canvas.app = self # reference app on canvas
        
        # Zoom panel floating at the bottom right of the canvas (icons only)
        self.zoom_frame = tk.Frame(self.canvas, bg="#ffffff", bd=1, relief="solid", highlightthickness=0)
        self.zoom_frame.place(relx=0.98, rely=0.98, anchor="se")
        
        zoom_buttons = [
            ("➕", self.zoom_in),
            ("➖", self.zoom_out),
            ("🔄", self.reset_zoom),
            ("🎯", self.center_view),
            ("📐", self.auto_layout_nodes)
        ]
        
        for icon, cmd in zoom_buttons:
            btn = tk.Button(
                self.zoom_frame, text=icon, font=("Segoe UI", 11),
                bg="#ffffff", fg="#475569", activebackground="#f1f5f9", activeforeground="#475569",
                bd=0, padx=8, pady=4, cursor="hand2", command=cmd
            )
            btn.pack(side="left", padx=1, pady=1)
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg="#e2e8f0"))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg="#ffffff"))
            
        # Canvas mouse binding events
        self.canvas.bind("<Button-1>", self.on_click_canvas)
        self.canvas.bind("<Double-1>", self.on_double_click_canvas)
        self.canvas.bind("<B1-Motion>", self.on_drag_canvas)
        self.canvas.bind("<ButtonRelease-1>", self.on_release_canvas)
        
        # Mouse wheel zoom binding
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        
        # Panning bindings (Right click + Drag)
        self.canvas.bind("<ButtonPress-3>", self.on_pan_start)
        self.canvas.bind("<B3-Motion>", self.on_pan_drag)
        
        # Set up connections view in the Connections Tab
        self.setup_connections_tab()
        
        # Draw background grid lines
        self.draw_grid()

    def draw_grid(self):
        # Delete existing grid lines
        self.canvas.delete("grid")
        return

    # --- Canvas Zoom, Pan, Center, and Auto Layout ---

    def on_zoom(self, event):
        # Determine zoom direction
        if event.delta > 0:
            factor = 1.15
        else:
            factor = 0.85
        self.apply_zoom(factor, event.x, event.y)

    def zoom_in(self):
        vw = self.canvas.winfo_width()
        vh = self.canvas.winfo_height()
        self.apply_zoom(1.15, vw / 2.0, vh / 2.0)

    def zoom_out(self):
        vw = self.canvas.winfo_width()
        vh = self.canvas.winfo_height()
        self.apply_zoom(0.85, vw / 2.0, vh / 2.0)

    def reset_zoom(self):
        # Calculate factor to restore zoom to 1.0
        if self.zoom_scale == 0:
            return
        factor = 1.0 / self.zoom_scale
        vw = self.canvas.winfo_width()
        vh = self.canvas.winfo_height()
        self.apply_zoom(factor, vw / 2.0, vh / 2.0)
        self.zoom_scale = 1.0
        self.log_message(t("canvas.zoom_reset"))

    def apply_zoom(self, factor, ref_x, ref_y):
        new_scale = self.zoom_scale * factor
        # Constrain zoom bounds using configurable limits
        zoom_min = getattr(self, 'zoom_min_var', None)
        zoom_max = getattr(self, 'zoom_max_var', None)
        min_val = zoom_min.get() if zoom_min else 0.2
        max_val = zoom_max.get() if zoom_max else 3.0
        if new_scale < min_val or new_scale > max_val:
            return
            
        self.zoom_scale = new_scale
        
        # Convert screen coords to canvas coords for scaling anchor
        cx = self.canvas.canvasx(ref_x)
        cy = self.canvas.canvasy(ref_y)
        
        # Scale all canvas visual elements except grid lines
        for item_id in self.canvas.find_all():
            tags = self.canvas.gettags(item_id)
            if "grid" not in tags:
                self.canvas.scale(item_id, cx, cy, factor, factor)
        
        # Update node parameters: since canvas scale modifies coordinate values,
        # we adjust our node coordinate variables to match and scale font size.
        for n in self.nodes.values():
            n.x = cx + (n.x - cx) * factor
            n.y = cy + (n.y - cy) * factor
            n.width *= factor
            n.height *= factor
            n.scale_fonts(self.zoom_scale)
            n.update_outline()
            
        # Re-render lines to align cleanly
        for c in self.connections:
            c.update_line()
            
        # Redraw grid dynamically
        self.draw_grid()

    def on_pan_start(self, event):
        item = self.canvas.find_withtag("current")
        if item:
            tags = self.canvas.gettags(item[0])
            node_tag = [t for t in tags if t.startswith("node_") and not t.startswith("node_port_")]
            if node_tag:
                node_id = int(node_tag[0].split("_")[1])
                node = self.nodes.get(node_id)
                if node:
                    self.show_node_context_menu(event, node)
                    return
        self.canvas.scan_mark(event.x, event.y)

    def show_node_context_menu(self, event, node):
        menu = tk.Menu(self.root, tearoff=0)
        
        is_multi = (hasattr(self, 'selected_nodes') and len(self.selected_nodes) > 1 and node in self.selected_nodes)
        
        if is_multi:
            menu.add_command(
                label=t("canvas.context_delete_selected"),
                command=lambda: self.delete_multiple_nodes(list(self.selected_nodes))
            )
        else:
            if hasattr(self, 'selected_nodes') and node not in self.selected_nodes:
                self._clear_multi_selection_visuals()
                self.selected_nodes.clear()
            self.selected_node = node
            for n in self.nodes.values():
                n.update_outline()
                
            menu.add_command(label=t("canvas.context_edit"), command=lambda: self.open_node_config_window(node))
            if node.type != 'start':
                menu.add_command(label=t("canvas.context_delete"), command=lambda: self.delete_node_by_ref(node))
                
        menu.post(event.x_root, event.y_root)

    def on_pan_drag(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        self.draw_grid()

    def center_view(self):
        if not self.nodes:
            self.reset_zoom()
            return
            
        # Get bounding box of all nodes based on python node properties
        coords = [[n.x, n.y, n.x + n.width, n.y + n.height] for n in self.nodes.values()]
        min_x = min(c[0] for c in coords)
        min_y = min(c[1] for c in coords)
        max_x = max(c[2] for c in coords)
        max_y = max(c[3] for c in coords)
        
        center_x = (min_x + max_x) / 2.0
        center_y = (min_y + max_y) / 2.0
        
        # Viewport dimensions
        vw = self.canvas.winfo_width()
        vh = self.canvas.winfo_height()
        v_center_x = vw / 2.0
        v_center_y = vh / 2.0
        
        dx = v_center_x - center_x
        dy = v_center_y - center_y
        
        # Translate all elements except grid
        for item_id in self.canvas.find_all():
            tags = self.canvas.gettags(item_id)
            if "grid" not in tags:
                self.canvas.move(item_id, dx, dy)
                
        # Sync node and waypoint coordinate properties
        for n in self.nodes.values():
            n.x += dx
            n.y += dy
            
        # Refresh connection lines
        for c in self.connections:
            c.update_line()
            
        self.log_message(t("canvas.view_centered"))
        self.draw_grid()

    def auto_layout_nodes(self):
        if not self.nodes:
            return
            
        # Build adjacency graph
        adj = {nid: [] for nid in self.nodes}
        in_degree = {nid: 0 for nid in self.nodes}
        
        for conn in self.connections:
            src_id = conn.source.id
            tgt_id = conn.target.id
            if src_id in adj and tgt_id in adj:
                adj[src_id].append(tgt_id)
                in_degree[tgt_id] += 1
                
        # Determine layers using Breadth First Search starting from root nodes (in_degree=0)
        layers = {}
        visited = set()
        queue = []
        
        for nid in self.nodes:
            if in_degree[nid] == 0:
                queue.append((nid, 0))
                
        if not queue and self.nodes:
            # Fallback if cyclic dependency
            nid = min(self.nodes.keys())
            queue.append((nid, 0))
            
        while queue:
            nid, layer = queue.pop(0)
            if nid in visited:
                continue
            visited.add(nid)
            
            if layer not in layers:
                layers[layer] = []
            layers[layer].append(nid)
            
            for neighbor in adj[nid]:
                if neighbor not in visited:
                    queue.append((neighbor, layer + 1))
                    
        # Add remaining unreachable nodes
        remaining = set(self.nodes.keys()) - visited
        for nid in remaining:
            if 0 not in layers:
                layers[0] = []
            layers[0].append(nid)
            
        # Relocate nodes visually layer-by-layer
        for layer, nids in sorted(layers.items()):
            x_pos = 100 + layer * 250
            for idx, nid in enumerate(nids):
                y_pos = 100 + idx * 150
                node = self.nodes[nid]
                
                # Relocate node and sync variables
                dx = x_pos - node.x
                dy = y_pos - node.y
                node.move_by(dx, dy)
                
        # Reset overrides for all connections during auto-layout to avoid weird stretching
        for c in self.connections:
            c.offset_source_override = None
            c.offset_target_override = None
            c.mid_y_override = None
            c.update_line()
            
        self.log_message(t("canvas.auto_layout_complete"))
        self.center_view()
