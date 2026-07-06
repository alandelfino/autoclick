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


class VisualConnection:
    def __init__(self, canvas, source_node, source_port, target_node, target_port, waypoints=None):
        self.canvas = canvas
        self.source = source_node
        self.source_port = source_port
        self.target = target_node
        self.target_port = target_port
        self.waypoints = waypoints or [] # List of [x, y] coordinates
        self.waypoint_handles = [] # List of canvas oval element IDs
        
        self.tag = f"conn_{self.source.id}_{self.source_port}_to_{self.target.id}_{self.target_port}"
        
        # Color matches the output port color
        line_color = self.source.ports[self.source_port]['color']
        
        self.line_id = self.canvas.create_line(
            0, 0, 0, 0,
            fill=line_color, width=3, smooth=True, arrow=tk.LAST,
            arrowshape=(10, 12, 5), tags=(self.tag, "connection")
        )
        
        # Bind double click on connection line to add waypoints
        self.canvas.tag_bind(self.tag, "<Double-1>", self.on_double_click_line)
        
        # Bind hover events
        self.canvas.tag_bind(self.tag, "<Enter>", self.on_enter)
        self.canvas.tag_bind(self.tag, "<Leave>", self.on_leave)
        
        # Bind right click events
        self.canvas.tag_bind(self.tag, "<Button-3>", self.on_right_click_line)
        self.canvas.tag_bind(self.tag, "<Button-2>", self.on_right_click_line)
        
        self.update_line()

    def update_line(self):
        x1, y1 = self.source.get_port_center(self.source_port)
        x2, y2 = self.target.get_port_center(self.target_port)
        
        if self.waypoints:
            raw_points = [(x1, y1)] + self.waypoints + [(x2, y2)]
            # Draw smooth curve passing exactly through the waypoints
            points = compute_catmull_rom_chain(raw_points, steps=15)
            self.canvas.itemconfig(self.line_id, smooth=False)
            self.canvas.coords(self.line_id, *points)
            
            # Recreate handles if counts mismatch (added/deleted)
            if len(self.waypoints) != len(self.waypoint_handles):
                for h in self.waypoint_handles:
                    self.canvas.delete(h)
                self.waypoint_handles.clear()
                
                for idx, wp in enumerate(self.waypoints):
                    wx, wy = wp
                    r = 6 # radius
                    h_id = self.canvas.create_oval(
                        wx - r, wy - r, wx + r, wy + r,
                        fill="#3b82f6", outline="#ffffff", width=2,
                        tags=(f"wp_{self.tag}_{idx}", "waypoint")
                    )
                    self.waypoint_handles.append(h_id)
                    
                    # Bind dragging, double-click, and right-click context menu
                    self.canvas.tag_bind(h_id, "<B1-Motion>", lambda event, i=idx: self.on_drag_waypoint(event, i))
                    self.canvas.tag_bind(h_id, "<ButtonRelease-1>", self.on_release_waypoint)
                    self.canvas.tag_bind(h_id, "<Double-1>", lambda event, i=idx: self.on_double_click_waypoint(event, i))
                    self.canvas.tag_bind(h_id, "<Button-3>", lambda event, i=idx: self.on_right_click_waypoint(event, i))
                    self.canvas.tag_bind(h_id, "<Button-2>", lambda event, i=idx: self.on_right_click_waypoint(event, i))
            else:
                # Just update coordinates of existing handles
                for idx, wp in enumerate(self.waypoints):
                    wx, wy = wp
                    r = 6
                    self.canvas.coords(self.waypoint_handles[idx], wx - r, wy - r, wx + r, wy + r)
        else:
            # Clear handles if no waypoints
            for h in self.waypoint_handles:
                self.canvas.delete(h)
            self.waypoint_handles.clear()
            
            # Calculate Bezier control points for custom aesthetic curves
            dx = abs(x2 - x1)
            cx1 = x1 + dx * 0.4
            cy1 = y1
            cx2 = x2 - dx * 0.4
            cy2 = y2
            self.canvas.itemconfig(self.line_id, smooth=True)
            self.canvas.coords(self.line_id, x1, y1, cx1, cy1, cx2, cy2, x2, y2)

    def on_double_click_line(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        self.add_segment_at(cx, cy)

    def add_segment_at(self, cx, cy):
        # Determine the insertion index for the new waypoint
        x1, y1 = self.source.get_port_center(self.source_port)
        x2, y2 = self.target.get_port_center(self.target_port)
        
        points = [(x1, y1)] + self.waypoints + [(x2, y2)]
        
        best_idx = 0
        min_dist = float('inf')
        
        # Iterate over all segments
        for i in range(len(points) - 1):
            A = points[i]
            B = points[i+1]
            # Vector AB
            vx = B[0] - A[0]
            vy = B[1] - A[1]
            # Vector AP
            wx = cx - A[0]
            wy = cy - A[1]
            
            ab_len_sq = vx * vx + vy * vy
            if ab_len_sq == 0:
                t_val = 0.0
            else:
                t_val = (wx * vx + wy * vy) / ab_len_sq
                t_val = max(0.0, min(1.0, t_val))
            
            # Closest point on segment
            proj_x = A[0] + t_val * vx
            proj_y = A[1] + t_val * vy
            
            # Distance from P to closest point
            dx = cx - proj_x
            dy = cy - proj_y
            dist = (dx * dx + dy * dy) ** 0.5
            
            if dist < min_dist:
                min_dist = dist
                best_idx = i
        
        # Insert the waypoint at the best index
        self.waypoints.insert(best_idx, [cx, cy])
        self.update_line()
        self.save_app_flow()

    def on_drag_waypoint(self, event, idx):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        if 0 <= idx < len(self.waypoints):
            self.waypoints[idx] = [cx, cy]
            self.update_line()

    def on_release_waypoint(self, event):
        self.save_app_flow()

    def on_double_click_waypoint(self, event, idx):
        self.confirm_delete_waypoint(idx)

    def on_right_click_waypoint(self, event, idx):
        menu = tk.Menu(self.canvas, tearoff=0)
        menu.add_command(
            label=t("connection.delete_waypoint"),
            command=lambda: self.confirm_delete_waypoint(idx)
        )
        menu.post(event.x_root, event.y_root)

    def confirm_delete_waypoint(self, idx):
        if messagebox.askyesno(t("connection_dialogs.confirm_delete_title"), t("connection.delete_waypoint_msg")):
            if 0 <= idx < len(self.waypoints):
                self.waypoints.pop(idx)
                self.update_line()
                self.save_app_flow()

    def on_enter(self, event):
        self.canvas.itemconfig(self.line_id, width=5)

    def on_leave(self, event):
        item = self.canvas.find_withtag("current")
        if item:
            tags = self.canvas.gettags(item[0])
            # If the cursor moved to a waypoint of this connection, keep the highlight
            if any(t.startswith(f"wp_{self.tag}_") for t in tags):
                return
        self.canvas.itemconfig(self.line_id, width=3)

    def on_right_click_line(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        
        menu = tk.Menu(self.canvas, tearoff=0)
        menu.add_command(
            label=t("connection.add_segment"),
            command=lambda: self.add_segment_at(cx, cy)
        )
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
        for h in self.waypoint_handles:
            self.canvas.delete(h)
        self.waypoint_handles.clear()
