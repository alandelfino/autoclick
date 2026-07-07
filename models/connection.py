"""
VisualConnection — Graphical representation of a connection line between two nodes.
"""
import tkinter as tk
from tkinter import messagebox
from core.i18n_helper import t


def compute_catmull_rom_chain(points_list, steps=15):
    """Generates dense point coordinate list along a Catmull-Rom spline passing exactly through points."""
    if len(points_list) < 2:
        return []
        
    # Duplicate boundary points
    p = [points_list[0]] + points_list + [points_list[-1]]
    
    curve_points = []
    for i in range(1, len(p) - 2):
        p0 = p[i-1]
        p1 = p[i]
        p2 = p[i+1]
        p3 = p[i+2]
        
        for step in range(steps):
            t = step / float(steps)
            t2 = t * t
            t3 = t2 * t
            
            x = 0.5 * (
                (2.0 * p1[0]) +
                (-p0[0] + p2[0]) * t +
                (2.0 * p0[0] - 5.0 * p1[0] + 4.0 * p2[0] - p3[0]) * t2 +
                (-p0[0] + 3.0 * p1[0] - 3.0 * p2[0] + p3[0]) * t3
            )
            y = 0.5 * (
                (2.0 * p1[1]) +
                (-p0[1] + p2[1]) * t +
                (2.0 * p0[1] - 5.0 * p1[1] + 4.0 * p2[1] - p3[1]) * t2 +
                (-p0[1] + 3.0 * p1[1] - 3.0 * p2[1] + p3[1]) * t3
            )
            curve_points.extend([x, y])
            
    curve_points.extend(points_list[-1])
    return curve_points


def generate_rounded_path(raw_pts, r=16.0):
    """
    Generates a dense list of coordinates representing straight segments with rounded corners.
    raw_pts: list of [x, y] coordinates
    r: corner rounding radius
    """
    if len(raw_pts) < 3:
        # Just return the points flattened
        flat = []
        for p in raw_pts:
            flat.extend(p)
        return flat
        
    path = [raw_pts[0][0], raw_pts[0][1]]
    
    for i in range(1, len(raw_pts) - 1):
        A = raw_pts[i-1]
        B = raw_pts[i]
        C = raw_pts[i+1]
        
        # Vectors from B to A and B to C
        v1_x, v1_y = A[0] - B[0], A[1] - B[1]
        v2_x, v2_y = C[0] - B[0], C[1] - B[1]
        
        d1 = (v1_x**2 + v1_y**2)**0.5
        d2 = (v2_x**2 + v2_y**2)**0.5
        
        if d1 == 0 or d2 == 0:
            path.extend(B)
            continue
            
        actual_r = min(r, d1 / 2.0, d2 / 2.0)
        if actual_r <= 0:
            path.extend(B)
            continue
            
        # Start and end points of the corner arc
        p0_x = B[0] + (v1_x / d1) * actual_r
        p0_y = B[1] + (v1_y / d1) * actual_r
        
        p2_x = B[0] + (v2_x / d2) * actual_r
        p2_y = B[1] + (v2_y / d2) * actual_r
        
        # Add the straight line segment start point of the corner
        path.extend([p0_x, p0_y])
        
        # Generate quadratic Bezier curve points using B as the control point
        steps = 8
        for s in range(1, steps):
            t = s / float(steps)
            t_inv = 1.0 - t
            
            px = (t_inv ** 2) * p0_x + 2 * t_inv * t * B[0] + (t ** 2) * p2_x
            py = (t_inv ** 2) * p0_y + 2 * t_inv * t * B[1] + (t ** 2) * p2_y
            path.extend([px, py])
            
        # Add the end point of the corner arc
        path.extend([p2_x, p2_y])
        
    path.extend([raw_pts[-1][0], raw_pts[-1][1]])
    return path


class VisualConnection:
    def __init__(self, canvas, source_node, source_port, target_node, target_port, waypoints=None):
        self.canvas = canvas
        self.source = source_node
        self.source_port = source_port
        self.target = target_node
        self.target_port = target_port
        self.is_hovered = False
        
        self.offset_source_override = None
        self.offset_target_override = None
        self.mid_y_override = None
        self.dragged_segment = None
        self.handle_ids = []
        
        self.tag = f"conn_{self.source.id}_{self.source_port}_to_{self.target.id}_{self.target_port}"
        
        app = getattr(self.canvas, 'app', None)
        line_color = app.connection_color_var.get() if (app and hasattr(app, 'connection_color_var')) else "#94a3b8"
        line_width = app.connection_width_var.get() if (app and hasattr(app, 'connection_width_var')) else 3
        
        self.line_id = self.canvas.create_line(
            0, 0, 0, 0,
            fill=line_color, width=line_width, smooth=True, arrow=tk.LAST,
            arrowshape=(10, 12, 5), tags=(self.tag, "connection"),
            capstyle="round", joinstyle="round", splinesteps=36
        )
        self.canvas.tag_lower(self.line_id)
        if self.canvas.find_withtag("grid"):
            self.canvas.tag_raise(self.line_id, "grid")
        
        # Bind hover events
        self.canvas.tag_bind(self.tag, "<Enter>", self.on_enter)
        self.canvas.tag_bind(self.tag, "<Leave>", self.on_leave)
        
        # Bind right click events
        self.canvas.tag_bind(self.tag, "<Button-3>", self.on_right_click_line)
        self.canvas.tag_bind(self.tag, "<Button-2>", self.on_right_click_line)
        
        self.update_line()
        if self.source:
            self.source.update_plus_handles()

    def update_line(self):
        x1, y1 = self.source.get_port_center(self.source_port)
        x2, y2 = self.target.get_port_center(self.target_port)
        
        app = getattr(self.canvas, 'app', None)
        zoom_scale = getattr(app, 'zoom_scale', 1.0) if app else 1.0
        
        # Load dynamic width and color from settings
        config_width = app.connection_width_var.get() if (app and hasattr(app, 'connection_width_var')) else 3
        line_color = app.connection_color_var.get() if (app and hasattr(app, 'connection_color_var')) else "#94a3b8"
        
        base_width = config_width + 2 if getattr(self, 'is_hovered', False) else config_width
        scaled_width = max(1, int(round(base_width * zoom_scale)))
        
        arrow_d1 = max(2.0, 10.0 * zoom_scale)
        arrow_d2 = max(2.0, 12.0 * zoom_scale)
        arrow_d3 = max(1.0, 5.0 * zoom_scale)
        scaled_arrowshape = (arrow_d1, arrow_d2, arrow_d3)
        
        self.canvas.itemconfig(
            self.line_id,
            fill=line_color,
            width=scaled_width,
            arrowshape=scaled_arrowshape
        )
        
        # Check if the connection needs to contour (target is to the left or overlapping)
        if self.target.x <= self.source.x + self.source.width:
            # Contour routing (n8n-style orthogonal line)
            offset_source = (self.offset_source_override * zoom_scale) if self.offset_source_override is not None else (40.0 * zoom_scale)
            offset_target = (self.offset_target_override * zoom_scale) if self.offset_target_override is not None else (40.0 * zoom_scale)
            
            if self.mid_y_override is not None:
                mid_y = y1 + (self.mid_y_override * zoom_scale)
            else:
                if abs(y2 - y1) >= 150.0 * zoom_scale:
                    mid_y = (y1 + y2) / 2.0
                else:
                    mid_y = max(y1, y2) + 100.0 * zoom_scale
                    
            raw_pts = [
                [x1, y1],
                [x1 + offset_source, y1],
                [x1 + offset_source, mid_y],
                [x2 - offset_target, mid_y],
                [x2 - offset_target, y2],
                [x2, y2]
            ]
            points = generate_rounded_path(raw_pts, r=16.0 * zoom_scale)
            self.canvas.itemconfig(self.line_id, smooth=False)
            self.canvas.coords(self.line_id, *points)
            
            # Draw/update the three segment drag handles ("pequenas luvas")
            h1_x, h1_y = x1 + offset_source, (y1 + mid_y) / 2.0
            h2_x, h2_y = (x1 + offset_source + x2 - offset_target) / 2.0, mid_y
            h3_x, h3_y = x2 - offset_target, (mid_y + y2) / 2.0
            # Calculate pipe dimensions aligned to segments - shrink proportionally down to 1px
            w_vert = max(1.0, 6.0 * zoom_scale)
            h_vert = max(1.0, 16.0 * zoom_scale)
            w_horz = max(1.0, 16.0 * zoom_scale)
            h_horz = max(1.0, 6.0 * zoom_scale)
            
            show_handles = getattr(self, 'is_hovered', False) or (getattr(self, 'dragged_segment', None) is not None)
            
            if show_handles:
                if hasattr(self, 'handle_ids') and len(self.handle_ids) == 3:
                    # Update coordinate and sizes of existing handle shapes
                    self.canvas.coords(self.handle_ids[0], h1_x - w_vert/2, h1_y - h_vert/2, h1_x + w_vert/2, h1_y + h_vert/2)
                    self.canvas.coords(self.handle_ids[1], h2_x - w_horz/2, h2_y - h_horz/2, h2_x + w_horz/2, h2_y + h_horz/2)
                    self.canvas.coords(self.handle_ids[2], h3_x - w_vert/2, h3_y - h_vert/2, h3_x + w_vert/2, h3_y + h_vert/2)
                    for h in self.handle_ids:
                        self.canvas.itemconfig(h, width=max(1.0, 1.5 * zoom_scale))
                else:
                    # Clean up old handle shapes
                    if hasattr(self, 'handle_ids'):
                        for h in self.handle_ids:
                            self.canvas.delete(h)
                    
                    # Create three handles as rectangles ("canos")
                    h1 = self.canvas.create_rectangle(
                        h1_x - w_vert/2, h1_y - h_vert/2, h1_x + w_vert/2, h1_y + h_vert/2,
                        fill="#ffffff", outline="#3b82f6", width=max(1.0, 1.5 * zoom_scale),
                        tags=("drag_handle",)
                    )
                    h2 = self.canvas.create_rectangle(
                        h2_x - w_horz/2, h2_y - h_horz/2, h2_x + w_horz/2, h2_y + h_horz/2,
                        fill="#ffffff", outline="#3b82f6", width=max(1.0, 1.5 * zoom_scale),
                        tags=("drag_handle",)
                    )
                    h3 = self.canvas.create_rectangle(
                        h3_x - w_vert/2, h3_y - h_vert/2, h3_x + w_vert/2, h3_y + h_vert/2,
                        fill="#ffffff", outline="#3b82f6", width=max(1.0, 1.5 * zoom_scale),
                        tags=("drag_handle",)
                    )
                    
                    self.handle_ids = [h1, h2, h3]
                    for h in self.handle_ids:
                        self.canvas.tag_raise(h)
                        
                    # Bind handle dragging events
                    self.canvas.tag_bind(h1, "<Button-1>", lambda event: self.on_handle_click(event, 1))
                    self.canvas.tag_bind(h1, "<B1-Motion>", self.on_handle_drag)
                    self.canvas.tag_bind(h1, "<ButtonRelease-1>", self.on_handle_release)
                    self.canvas.tag_bind(h1, "<Enter>", lambda event: self.on_handle_enter(event, "size_we"))
                    self.canvas.tag_bind(h1, "<Leave>", self.on_leave)
                    
                    self.canvas.tag_bind(h2, "<Button-1>", lambda event: self.on_handle_click(event, 2))
                    self.canvas.tag_bind(h2, "<B1-Motion>", self.on_handle_drag)
                    self.canvas.tag_bind(h2, "<ButtonRelease-1>", self.on_handle_release)
                    self.canvas.tag_bind(h2, "<Enter>", lambda event: self.on_handle_enter(event, "size_ns"))
                    self.canvas.tag_bind(h2, "<Leave>", self.on_leave)
                    
                    self.canvas.tag_bind(h3, "<Button-1>", lambda event: self.on_handle_click(event, 3))
                    self.canvas.tag_bind(h3, "<B1-Motion>", self.on_handle_drag)
                    self.canvas.tag_bind(h3, "<ButtonRelease-1>", self.on_handle_release)
                    self.canvas.tag_bind(h3, "<Enter>", lambda event: self.on_handle_enter(event, "size_we"))
                    self.canvas.tag_bind(h3, "<Leave>", self.on_leave)
            else:
                # Remove handles if hover is inactive and we are not dragging
                if hasattr(self, 'handle_ids'):
                    for h in self.handle_ids:
                        self.canvas.delete(h)
                    self.handle_ids.clear()
        else:
            # Common forward connection (standard Bezier S-curve)
            dx = abs(x2 - x1)
            cx1 = x1 + dx * 0.4
            cy1 = y1
            cx2 = x2 - dx * 0.4
            cy2 = y2
            self.canvas.itemconfig(self.line_id, smooth=True)
            self.canvas.coords(self.line_id, x1, y1, cx1, cy1, cx2, cy2, x2, y2)
            
            # Clean up old handle ovals
            if hasattr(self, 'handle_ids'):
                for h in self.handle_ids:
                    self.canvas.delete(h)
                self.handle_ids.clear()

    def on_enter(self, event):
        self.is_hovered = True
        self.update_line()

    def on_handle_enter(self, event, cursor_shape):
        self.is_hovered = True
        self.canvas.config(cursor=cursor_shape)

    def on_leave(self, event):
        # Find what items are actually under the mouse coordinate (2x2 bounding box)
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        overlapping = self.canvas.find_overlapping(cx - 1, cy - 1, cx + 1, cy + 1)
        
        # If the mouse is over a port, we've left the connection
        for item_id in overlapping:
            if "port" in self.canvas.gettags(item_id):
                self.is_hovered = False
                self.canvas.config(cursor="")
                self.update_line()
                return
                
        # If the mouse moved to one of our own handles or the line itself, do nothing!
        if self.line_id in overlapping or (hasattr(self, 'handle_ids') and any(h in overlapping for h in self.handle_ids)):
            if self.line_id in overlapping:
                self.canvas.config(cursor="")
            return
                
        self.is_hovered = False
        self.canvas.config(cursor="")
        self.update_line()

    def on_right_click_line(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        
        app = getattr(self.canvas, 'app', None)
        if app:
            app.select_node(None)
            
        menu = tk.Menu(self.canvas, tearoff=0)
        menu.add_command(
            label=t("connection.delete_connection"),
            command=self.confirm_delete_connection
        )
        menu.add_separator()
        
        # Add Node submenu
        add_node_menu = tk.Menu(menu, tearoff=0)
        
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
        
        app = getattr(self.canvas, 'app', None)
        
        for category_name, nodes in node_groups:
            cat_menu = tk.Menu(add_node_menu, tearoff=0)
            for node_label, node_type in nodes:
                def make_cmd(ntype=node_type):
                    if app:
                        app.create_node(ntype, x=cx, y=cy, is_canvas_coords=True)
                cat_menu.add_command(label=node_label, command=make_cmd)
            add_node_menu.add_cascade(label=category_name, menu=cat_menu)
            
        menu.add_cascade(label=t("connection.add_node"), menu=add_node_menu)
        menu.post(event.x_root, event.y_root)

    def confirm_delete_connection(self):
        app = getattr(self.canvas, 'app', None)
        if app:
            if messagebox.askyesno(t("connection_dialogs.confirm_delete_title"), t("connection.delete_connection_msg")):
                self.delete()
                if self in app.connections:
                    app.connections.remove(self)
                app.trigger_auto_save()

    def save_app_flow(self):
        app = getattr(self.canvas, 'app', None)
        if app:
            app.trigger_auto_save()

    def delete(self):
        self.canvas.delete(self.line_id)
        if hasattr(self, 'handle_ids'):
            for h in self.handle_ids:
                self.canvas.delete(h)
            self.handle_ids.clear()
        if self.source:
            self.canvas.after(10, self.source.update_plus_handles)

    def on_handle_click(self, event, idx):
        self.dragged_segment = idx
        app = getattr(self.canvas, 'app', None)
        if app:
            app.select_node(None)
        
    def on_handle_drag(self, event):
        if self.dragged_segment is None:
            return
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        
        app = getattr(self.canvas, 'app', None)
        zoom_scale = getattr(app, 'zoom_scale', 1.0) if app else 1.0
        
        x1, y1 = self.source.get_port_center(self.source_port)
        x2, y2 = self.target.get_port_center(self.target_port)
        
        if self.dragged_segment == 1:
            self.offset_source_override = max(10.0, cx - x1) / zoom_scale
        elif self.dragged_segment == 2:
            self.mid_y_override = (cy - y1) / zoom_scale
        elif self.dragged_segment == 3:
            self.offset_target_override = max(10.0, x2 - cx) / zoom_scale
            
        self.update_line()
        
    def on_handle_release(self, event):
        self.dragged_segment = None
        self.save_app_flow()
