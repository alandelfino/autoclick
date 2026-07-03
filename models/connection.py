"""
VisualConnection — Graphical representation of a connection line between two nodes.
"""
import tkinter as tk
from tkinter import messagebox


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
        self.waypoints.append([cx, cy])
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
            label="Excluir Ponto de Intersecção",
            command=lambda: self.confirm_delete_waypoint(idx)
        )
        menu.post(event.x_root, event.y_root)

    def confirm_delete_waypoint(self, idx):
        if messagebox.askyesno("Confirmar Exclusão", "Deseja realmente excluir este ponto de intersecção?"):
            if 0 <= idx < len(self.waypoints):
                self.waypoints.pop(idx)
                self.update_line()
                self.save_app_flow()

    def save_app_flow(self):
        app = getattr(self.canvas, 'app', None)
        if app and getattr(app, 'current_filepath', None):
            app.save_flow_to_filepath(app.current_filepath, show_popup=False)

    def delete(self):
        self.canvas.delete(self.line_id)
        for h in self.waypoint_handles:
            self.canvas.delete(h)
        self.waypoint_handles.clear()
