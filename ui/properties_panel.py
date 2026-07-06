"""
Properties panel — Dynamic form builder for selected node properties,
payload tree display, and related helpers.
"""
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import re
import threading
import json

from core.payload import get_payload_value, resolve_value
from core.i18n_helper import t


class SQLAutocomplete:
    def __init__(self, text_widget, root):
        self.text_widget = text_widget
        self.root = root
        self.schema = {}  # Maps table -> [columns]
        
        self.suggest_box = None
        self.listbox = None
        self.suggestions = []
        
        # Bind events
        self.text_widget.bind("<KeyRelease>", self.on_key_release)
        self.text_widget.bind("<FocusOut>", self.hide_popup)
        self.text_widget.bind("<Button-1>", self.hide_popup)
        self.text_widget.bind("<KeyPress>", self.on_key_press)

    def on_key_press(self, event):
        if not self.suggest_box or not self.suggest_box.winfo_exists():
            return
            
        if event.keysym in ["Up", "Down", "Return", "Tab", "Escape"]:
            if event.keysym == "Up":
                self.move_selection(-1)
                return "break"
            elif event.keysym == "Down":
                self.move_selection(1)
                return "break"
            elif event.keysym in ["Return", "Tab"]:
                self.insert_selected()
                return "break"
            elif event.keysym == "Escape":
                self.hide_popup()
                return "break"

    def move_selection(self, direction):
        if not self.listbox:
            return
        curr = self.listbox.curselection()
        if not curr:
            index = 0 if direction > 0 else len(self.suggestions) - 1
        else:
            index = curr[0] + direction
            if index < 0:
                index = len(self.suggestions) - 1
            elif index >= len(self.suggestions):
                index = 0
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(index)
        self.listbox.activate(index)
        self.listbox.see(index)

    def insert_selected(self):
        if not self.listbox:
            return
        curr = self.listbox.curselection()
        if not curr:
            self.hide_popup()
            return
        val = self.suggestions[curr[0]]
        
        cursor_pos = self.text_widget.index(tk.INSERT)
        line, col = map(int, cursor_pos.split('.'))
        line_content = self.text_widget.get(f"{line}.0", cursor_pos)
        
        match = re.search(r'([a-zA-Z0-9_\.]+)$', line_content)
        if match:
            start_col = match.start()
            self.text_widget.delete(f"{line}.{start_col}", cursor_pos)
            self.text_widget.insert(f"{line}.{start_col}", val)
        else:
            self.text_widget.insert(tk.INSERT, val)
            
        self.hide_popup()
        self.text_widget.event_generate("<KeyRelease>")

    def on_key_release(self, event):
        if event.keysym in ["Up", "Down", "Return", "Tab", "Escape", "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"]:
            return
            
        if not self.schema:
            self.hide_popup()
            return
            
        cursor_pos = self.text_widget.index(tk.INSERT)
        line, col = map(int, cursor_pos.split('.'))
        line_content = self.text_widget.get(f"{line}.0", cursor_pos)
        
        match = re.search(r'([a-zA-Z0-9_\.]+)$', line_content)
        if not match:
            self.hide_popup()
            return
            
        word = match.group(1).lower()
        if not word:
            self.hide_popup()
            return
            
        self.suggestions = []
        candidates = []
        for t, cols in self.schema.items():
            candidates.append(t)
            for c in cols:
                candidates.append(f"{t}.{c}")
                candidates.append(c)
                
        for cand in candidates:
            if cand.lower().startswith(word) and cand.lower() != word:
                if cand not in self.suggestions:
                    self.suggestions.append(cand)
                    
        if not self.suggestions:
            self.hide_popup()
            return
            
        self.show_popup()

    def show_popup(self):
        if not self.suggest_box or not self.suggest_box.winfo_exists():
            self.suggest_box = tk.Toplevel(self.root)
            self.suggest_box.wm_overrideredirect(True)
            self.suggest_box.attributes("-topmost", True)
            
            frame = tk.Frame(self.suggest_box, bg="#cbd5e1", bd=1)
            frame.pack(fill="both", expand=True)
            
            self.listbox = tk.Listbox(
                frame, font=("Consolas", 9), bg="#ffffff", fg="#1e293b",
                selectbackground="#2563eb", selectforeground="#ffffff",
                bd=0, highlightthickness=0, height=min(8, len(self.suggestions))
            )
            self.listbox.pack(fill="both", expand=True)
            self.listbox.bind("<Button-1>", lambda e: self.root.after(50, self.insert_selected))
        else:
            self.listbox.delete(0, tk.END)
            self.listbox.config(height=min(8, len(self.suggestions)))
            
        for sug in self.suggestions:
            self.listbox.insert(tk.END, sug)
            
        self.listbox.selection_set(0)
        self.listbox.activate(0)
        
        bbox = self.text_widget.bbox(tk.INSERT)
        if bbox:
            rx, ry, rw, rh = bbox
            sx = self.text_widget.winfo_rootx() + rx
            sy = self.text_widget.winfo_rooty() + ry + rh
            
            max_len = max(len(s) for s in self.suggestions)
            width = max(150, max_len * 8 + 10)
            height = min(8, len(self.suggestions)) * 16 + 4
            
            self.suggest_box.geometry(f"{width}x{height}+{sx}+{sy}")

    def hide_popup(self, event=None):
        if self.suggest_box and self.suggest_box.winfo_exists():
            try:
                self.suggest_box.destroy()
            except Exception:
                pass
        self.suggest_box = None
        self.listbox = None



class PropertiesPanelMixin:
    """Mixin providing the properties panel, payload trees, and payload helpers."""

    def show_no_node_selected_message(self):
        if not hasattr(self, 'properties_container') or not self.properties_container:
            return
        
        # Clean widgets in all containers
        for container in [self.properties_container, self.input_payload_container, self.output_payload_container]:
            if container:
                try:
                    for widget in container.winfo_children():
                        widget.destroy()
                except Exception:
                    pass
            
        lbl1 = tk.Label(
            self.properties_container, 
            text=t("properties.no_node_selected"), 
            font=("Segoe UI", 9, "italic"), fg="#64748b", bg="#f8fafc", justify="center", wraplength=350
        )
        lbl1.pack(pady=40)
        
        lbl2 = tk.Label(
            self.input_payload_container,
            text=t("properties.select_node_input"),
            font=("Segoe UI", 9, "italic"), fg="#64748b", bg="#f8fafc", justify="center", wraplength=350
        )
        lbl2.pack(pady=40)
        
        lbl3 = tk.Label(
            self.output_payload_container,
            text=t("properties.select_node_output"),
            font=("Segoe UI", 9, "italic"), fg="#64748b", bg="#f8fafc", justify="center", wraplength=350
        )
        lbl3.pack(pady=40)

    # --- Dynamic Form Builder for the Selected Node Properties ---
    def build_properties_panel(self, node):
        # Reset active widget to prevent stale widget manipulation on double click
        self.active_text_widget = None
        # Clean current inspector widgets
        for widget in self.properties_container.winfo_children():
            widget.destroy()
            
        # Ensure temp variables are initialized defensively
        if not hasattr(self, 'temp_properties') or self.temp_properties is None:
            import copy
            self.temp_properties = copy.deepcopy(node.properties)
        if not hasattr(self, 'temp_node_name') or self.temp_node_name is None:
            self.temp_node_name = node.name
            
        # Determine predecessors and merge their output schemas
        predecessors = self.get_predecessors(node.id)
        input_schema = {}
        for pred_id in predecessors:
            pred_node = self.nodes[pred_id]
            pred_schema = self.get_node_output_schema(pred_node, visited={node.id})
            self.deep_merge_dict(input_schema, pred_schema)
            
        # Get real payloads
        real_input = None
        real_output = None
        if node.id in self.execution_history:
            real_input = self.execution_history[node.id].get("input")
            real_output = self.execution_history[node.id].get("output")
            
        if not real_input and self.last_run_payload:
            real_input = self.last_run_payload
            
        # Resolve payloads (Schema + Real)
        input_data = self.get_resolved_payload(input_schema, real_input)
        
        output_schema = self.get_node_output_schema(node)
        output_data = self.get_resolved_payload(output_schema, real_output) if (real_output or output_schema) else {}
        
        is_mock_input = (real_input is None or not real_input)
        is_mock_output = (real_output is None or not real_output)
        
        self.build_payload_tree(
            self.input_payload_container, 
            input_data, 
            t("properties.no_input_params"), 
            is_mock=is_mock_input if input_data else False
        )
        self.build_payload_tree(
            self.output_payload_container, 
            output_data, 
            t("properties.no_output_params"), 
            is_mock=is_mock_output if output_data else False
        )
        lbl_name = tk.Label(self.properties_container, text=t("properties.node_name"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
        lbl_name.pack(anchor="w", pady=(0, 2))
        
        ent_name = ttk.Entry(self.properties_container, font=("Segoe UI", 9))
        ent_name.insert(0, self.temp_node_name)
        ent_name.pack(fill="x", pady=(0, 15))
        self.name_entry_widget = ent_name
        
        def update_name(event):
            self.temp_node_name = ent_name.get()
            
        ent_name.bind("<KeyRelease>", update_name)
        
        # 2. Node Specific Properties
        if node.type == 'click':
            # Fields: X, Y
            lbl_x = tk.Label(self.properties_container, text=t("properties.coord_x"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_x.pack(anchor="w", pady=(0, 2))
            
            ent_x = ttk.Entry(self.properties_container, font=("Segoe UI", 9))
            ent_x.insert(0, str(self.temp_properties.get('x', 0)))
            ent_x.pack(fill="x", pady=(0, 8))
            ent_x.property_key = 'x'
            
            lbl_y = tk.Label(self.properties_container, text=t("properties.coord_y"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_y.pack(anchor="w", pady=(0, 2))
            
            ent_y = ttk.Entry(self.properties_container, font=("Segoe UI", 9))
            ent_y.insert(0, str(self.temp_properties.get('y', 0)))
            ent_y.pack(fill="x", pady=(0, 15))
            ent_y.property_key = 'y'
            
            def save_coords(event=None):
                val_x = ent_x.get()
                val_y = ent_y.get()
                try:
                    self.temp_properties['x'] = int(val_x)
                except ValueError:
                    self.temp_properties['x'] = val_x
                try:
                    self.temp_properties['y'] = int(val_y)
                except ValueError:
                    self.temp_properties['y'] = val_y
                
            ent_x.bind("<KeyRelease>", save_coords)
            ent_y.bind("<KeyRelease>", save_coords)
            
            # Smart coordinate capturing helper
            btn_capture = tk.Button(
                self.properties_container, text=t("properties.capture_coordinates"), font=("Segoe UI", 9, "bold"),
                bg="#3b82f6", fg="#ffffff", activebackground="#2563eb", activeforeground="#ffffff",
                bd=0, pady=8, cursor="hand2", command=lambda: self.launch_coordinate_capture(ent_x, ent_y)
            )
            btn_capture.pack(fill="x", pady=5)
            
        elif node.type == 'capture':
            # Fields: Capture Type (Combobox)
            lbl_type = tk.Label(self.properties_container, text=t("properties.capture_type"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_type.pack(anchor="w", pady=(0, 2))
            
            cb_type = ttk.Combobox(self.properties_container, values=[t("properties.capture_active_window"), t("properties.capture_mouse_only")], state="readonly")
            initial_val = self.temp_properties.get('capture_type', 'Active Window Data')
            if initial_val in ['Janela Ativa', 'Dados da Janela Ativa', 'Active Window Data']:
                initial_val = t("properties.capture_active_window")
            elif initial_val in ['Posição do Mouse', 'Janela e Mouse', 'Dados do Mouse somente', 'Mouse Data Only']:
                initial_val = t("properties.capture_mouse_only")
            cb_type.set(initial_val)
            cb_type.pack(fill="x", pady=(0, 15))
            cb_type.property_key = 'capture_type'
            
            def save_capture_type(event):
                sel = cb_type.get()
                if sel == t("properties.capture_active_window"):
                    self.temp_properties['capture_type'] = 'Active Window Data'
                else:
                    self.temp_properties['capture_type'] = 'Mouse Data Only'
                
            cb_type.bind("<<ComboboxSelected>>", save_capture_type)
            
        elif node.type == 'condition':
            # Fields: Variable, Operator, Value
            lbl_var = tk.Label(self.properties_container, text=t("properties.payload_var"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_var.pack(anchor="w", pady=(0, 2))
            
            lbl_var_hint = tk.Label(self.properties_container, text=t("properties.payload_var_hint"), font=("Segoe UI", 8, "italic"), fg="#64748b", bg="#f8fafc")
            lbl_var_hint.pack(anchor="w", pady=(0, 2))
            
            ent_var = ttk.Entry(self.properties_container, font=("Segoe UI", 9))
            ent_var.is_payload_var_field = True
            ent_var.insert(0, self.temp_properties.get('variable', ''))
            ent_var.pack(fill="x", pady=(0, 10))
            ent_var.property_key = 'variable'
            
            lbl_op = tk.Label(self.properties_container, text=t("properties.operation"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_op.pack(anchor="w", pady=(0, 2))
            
            cb_op = ttk.Combobox(self.properties_container, values=[t("properties.op_equals"), t("properties.op_different"), t("properties.op_contains"), t("properties.op_greater_than")], state="readonly")
            initial_op = self.temp_properties.get('operator', 'equals')
            if initial_op in ['igual', 'equals']:
                initial_op = t("properties.op_equals")
            elif initial_op in ['diferente', 'different']:
                initial_op = t("properties.op_different")
            elif initial_op in ['contém', 'contains']:
                initial_op = t("properties.op_contains")
            elif initial_op in ['maior que', 'greater than']:
                initial_op = t("properties.op_greater_than")
            cb_op.set(initial_op)
            cb_op.pack(fill="x", pady=(0, 10))
            cb_op.property_key = 'operator'
            
            lbl_val = tk.Label(self.properties_container, text=t("properties.comp_value"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_val.pack(anchor="w", pady=(0, 2))
            
            ent_val = ttk.Entry(self.properties_container, font=("Segoe UI", 9))
            ent_val.insert(0, self.temp_properties.get('value', ''))
            ent_val.pack(fill="x", pady=(0, 15))
            ent_val.property_key = 'value'
            
            # Interactive Variable Value Preview
            preview_frame = tk.LabelFrame(self.properties_container, text=t("properties.payload_preview"), font=("Segoe UI", 8, "bold"), fg="#1e293b", bg="#f8fafc", padx=5, pady=5)
            preview_frame.pack(fill="x", pady=(5, 10))
            
            preview_lbl = tk.Label(preview_frame, text="", font=("Consolas", 9), fg="#16a34a", bg="#f8fafc", anchor="w", justify="left", wraplength=350)
            preview_lbl.pack(fill="x", expand=True)
            
            def update_preview(event=None):
                var_name = ent_var.get().strip()
                if not var_name:
                    preview_lbl.config(text="[Enter variable name]")
                    return
                val = get_payload_value(input_data, var_name)
                if val is not None:
                    formatted_val = self.format_preview_value(val)
                    preview_lbl.config(text=f"{formatted_val} ({type(val).__name__})")
                else:
                    preview_lbl.config(text=f"[Not found in payload]")
            
            def save_condition_fields(event=None):
                self.temp_properties['variable'] = ent_var.get().strip()
                sel_op = cb_op.get()
                if sel_op == t("properties.op_equals"):
                    self.temp_properties['operator'] = 'equals'
                elif sel_op == t("properties.op_different"):
                    self.temp_properties['operator'] = 'different'
                elif sel_op == t("properties.op_contains"):
                    self.temp_properties['operator'] = 'contains'
                elif sel_op == t("properties.op_greater_than"):
                    self.temp_properties['operator'] = 'greater than'
                else:
                    self.temp_properties['operator'] = sel_op
                self.temp_properties['value'] = ent_val.get()
                update_preview()
                
            self.preview_timer = None
            def debounce_update(event=None):
                if hasattr(self, 'preview_timer') and self.preview_timer:
                    try:
                        self.root.after_cancel(self.preview_timer)
                    except Exception:
                        pass
                self.preview_timer = self.root.after(300, save_condition_fields)
            
            ent_var.bind("<KeyRelease>", debounce_update)
            cb_op.bind("<<ComboboxSelected>>", debounce_update)
            ent_val.bind("<KeyRelease>", debounce_update)
            update_preview()
            
        elif node.type == 'key':
            # Fields: Key, Count
            lbl_key = tk.Label(self.properties_container, text=t("properties.key"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_key.pack(anchor="w", pady=(0, 2))
            
            cb_key = ttk.Combobox(self.properties_container, values=[
                "enter", "tab", "space", "backspace", "escape", "up", "down", "left", "right", "ctrl", "alt", "shift"
            ])
            cb_key.set(self.temp_properties.get('key', 'enter'))
            cb_key.pack(fill="x", pady=(0, 10))
            cb_key.property_key = 'key'
            
            lbl_cnt = tk.Label(self.properties_container, text=t("properties.quantity"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_cnt.pack(anchor="w", pady=(0, 2))
            
            ent_cnt = ttk.Spinbox(self.properties_container, from_=1, to=999, width=10)
            ent_cnt.set(str(self.temp_properties.get('count', 1)))
            ent_cnt.pack(anchor="w", pady=(0, 15))
            ent_cnt.property_key = 'count'
            
            def save_key_fields(event=None):
                self.temp_properties['key'] = cb_key.get()
                val_cnt = ent_cnt.get()
                try:
                    self.temp_properties['count'] = int(val_cnt)
                except ValueError:
                    self.temp_properties['count'] = val_cnt
                
            cb_key.bind("<KeyRelease>", save_key_fields)
            cb_key.bind("<<ComboboxSelected>>", save_key_fields)
            ent_cnt.bind("<KeyRelease>", save_key_fields)
            ent_cnt.bind("<Button-1>", lambda e: self.root.after(50, save_key_fields))
            
        elif node.type == 'type_text':
            # Fields: Text
            lbl_txt = tk.Label(self.properties_container, text=t("properties.text_to_type"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_txt.pack(anchor="w", pady=(0, 2))
            
            lbl_hint = tk.Label(
                self.properties_container, 
                text=t("properties.text_to_type_hint"), 
                font=("Segoe UI", 8, "italic"), fg="#64748b", bg="#f8fafc", justify="left"
            )
            lbl_hint.pack(anchor="w", pady=(0, 5))
            
            txt_area = tk.Text(self.properties_container, font=("Segoe UI", 9), height=5, bd=1, relief="solid", width=40)
            txt_area.insert("1.0", self.temp_properties.get('text', ''))
            txt_area.pack(fill="x", pady=(0, 15))
            txt_area.property_key = 'text'
            
            # Interactive Expression Preview
            preview_frame = tk.LabelFrame(self.properties_container, text=t("properties.preview_result"), font=("Segoe UI", 8, "bold"), fg="#1e293b", bg="#f8fafc", padx=5, pady=5)
            preview_frame.pack(fill="x", pady=(5, 10))
            
            preview_lbl = tk.Label(preview_frame, text="", font=("Consolas", 9), fg="#16a34a", bg="#f8fafc", anchor="w", justify="left", wraplength=350)
            preview_lbl.pack(fill="x", expand=True)
            
            def update_preview(event=None):
                raw_text = txt_area.get("1.0", "end-1c")
                formatted_text = raw_text
                placeholders = re.findall(r'\{([^}]+)\}', raw_text)
                
                for ph in placeholders:
                    val = get_payload_value(input_data, ph)
                    if val is not None:
                        formatted_text = formatted_text.replace(f"{{{ph}}}", self.format_preview_value(val))
                    else:
                        formatted_text = formatted_text.replace(f"{{{ph}}}", f"[Undefined: {ph}]")
                
                preview_lbl.config(text=formatted_text)
            
            def save_text_field(event=None):
                self.temp_properties['text'] = txt_area.get("1.0", "end-1c")
                update_preview()
                
            self.preview_timer_text = None
            def debounce_update_text(event=None):
                if hasattr(self, 'preview_timer_text') and self.preview_timer_text:
                    try:
                        self.root.after_cancel(self.preview_timer_text)
                    except Exception:
                        pass
                self.preview_timer_text = self.root.after(300, save_text_field)
                
            txt_area.bind("<KeyRelease>", debounce_update_text)
            update_preview()
            
        elif node.type == 'start':
            # Section: Configuração de Loop
            lbl_loop_title = tk.Label(
                self.properties_container, 
                text=t("properties.loop_settings"), 
                font=("Segoe UI", 10, "bold"), fg="#1e293b", bg="#f8fafc"
            )
            lbl_loop_title.pack(anchor="w", pady=(0, 10))
            
            lbl_mode = tk.Label(self.properties_container, text=t("properties.execution_mode"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_mode.pack(anchor="w", pady=(0, 2))
            
            loop_mode_cb = ttk.Combobox(self.properties_container, values=[t("properties.loop_mode_once"), t("properties.loop_mode_n_times"), t("properties.loop_mode_infinite")], state="readonly")
            initial_mode = self.temp_properties.get('loop_mode', 'Run once')
            if initial_mode in ['Executar 1 vez', 'Run once']:
                initial_mode = t("properties.loop_mode_once")
            elif initial_mode in ['Executar N vezes', 'Run N times']:
                initial_mode = t("properties.loop_mode_n_times")
            elif initial_mode in ['Loop Infinito', 'Infinite Loop']:
                initial_mode = t("properties.loop_mode_infinite")
            loop_mode_cb.set(initial_mode)
            loop_mode_cb.pack(fill="x", pady=(0, 10))
            loop_mode_cb.property_key = 'loop_mode'
            
            # Spinbox container for loop count
            loop_count_frame = tk.Frame(self.properties_container, bg="#f8fafc")
            loop_count_frame.pack(fill="x", pady=(0, 15))
            
            lbl_count = tk.Label(loop_count_frame, text=t("properties.execution_rounds"), fg="#475569", bg="#f8fafc", font=("Segoe UI", 9, "bold"))
            lbl_count.pack(side="left")
            
            loop_count_spin = ttk.Spinbox(loop_count_frame, from_=1, to=9999, width=8)
            loop_count_spin.set(str(self.temp_properties.get('loop_count', 5)))
            loop_count_spin.pack(side="right")
            loop_count_spin.property_key = 'loop_count'
            
            def save_loop_fields(event=None):
                sel = loop_mode_cb.get()
                if sel == t("properties.loop_mode_once"):
                    self.temp_properties['loop_mode'] = 'Run once'
                elif sel == t("properties.loop_mode_n_times"):
                    self.temp_properties['loop_mode'] = 'Run N times'
                else:
                    self.temp_properties['loop_mode'] = 'Infinite Loop'
                try:
                    self.temp_properties['loop_count'] = int(loop_count_spin.get())
                except ValueError:
                    self.temp_properties['loop_count'] = 5
            
            def update_spin_state(*args):
                if loop_mode_cb.get() == t("properties.loop_mode_n_times"):
                    loop_count_spin.config(state="normal")
                else:
                    loop_count_spin.config(state="disabled")
                    
            loop_mode_cb.bind("<<ComboboxSelected>>", lambda e: [save_loop_fields(), update_spin_state()])
            loop_count_spin.bind("<KeyRelease>", save_loop_fields)
            loop_count_spin.bind("<Button-1>", lambda e: self.root.after(50, save_loop_fields))
            
            update_spin_state()
        elif node.type in ['postgres', 'mysql', 'sqlite']:
            # Select connection
            lbl_conn = tk.Label(self.properties_container, text=t("properties.saved_conn"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_conn.pack(anchor="w", pady=(0, 2))
            
            db_type = 'sqlite' if node.type == 'sqlite' else ('postgres' if node.type == 'postgres' else 'mysql')
            available_conns = [name for name, c in self.saved_connections.items() if c.get('type') == db_type]
            
            cb_conn = ttk.Combobox(self.properties_container, values=available_conns, state="readonly")
            cb_conn.set(self.temp_properties.get('connection_name', ''))
            cb_conn.pack(fill="x", pady=(0, 10))
            cb_conn.property_key = 'connection_name'
            
            # SQL Command
            lbl_sql = tk.Label(self.properties_container, text=t("properties.sql_command"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_sql.pack(anchor="w", pady=(0, 2))
            
            sql_text = tk.Text(self.properties_container, font=("Consolas", 9), height=10, bd=1, relief="solid", width=40)
            sql_text.insert("1.0", self.temp_properties.get('sql', ''))
            sql_text.pack(fill="x", pady=(0, 10))
            sql_text.property_key = 'sql'
            
            # Autocomplete initialization
            autocomplete = SQLAutocomplete(sql_text, self.root)
            
            # DB Schema Preview Frame
            schema_frame = tk.LabelFrame(
                self.properties_container, text=t("properties.db_tables_preview"),
                font=("Segoe UI", 8, "bold"), fg="#1e293b", bg="#f8fafc", padx=5, pady=5
            )
            schema_frame.pack(fill="x", pady=(0, 15))
            
            # Inside schema_frame, add Treeview with scrollbar
            tree_scroll_frame = ttk.Frame(schema_frame)
            tree_scroll_frame.pack(fill="both", expand=True)
            
            schema_tree = ttk.Treeview(tree_scroll_frame, show="tree", height=5)
            vsb_schema = ttk.Scrollbar(tree_scroll_frame, orient="vertical", command=schema_tree.yview)
            schema_tree.configure(yscrollcommand=vsb_schema.set)
            
            vsb_schema.pack(side="right", fill="y")
            schema_tree.pack(side="left", fill="both", expand=True)
            
            def save_db_fields(event=None):
                self.temp_properties['connection_name'] = cb_conn.get()
                self.temp_properties['sql'] = sql_text.get("1.0", "end-1c")
                
            def update_schema_preview():
                schema_tree.delete(*schema_tree.get_children())
                conn_name = cb_conn.get()
                if not conn_name:
                    return
                
                conn_info = self.saved_connections.get(conn_name, {})
                schema = conn_info.get("schema", {})
                
                if not schema:
                    schema_tree.insert("", "end", text=t("properties.db_schema_not_loaded"))
                    return
                    
                for table, columns in sorted(schema.items()):
                    table_id = schema_tree.insert("", "end", text=table, open=False)
                    for col in columns:
                        schema_tree.insert(table_id, "end", text=col)
                        
            def on_connection_change(event=None):
                save_db_fields()
                update_schema_preview()
                
                # Update autocomplete schema
                conn_name = cb_conn.get()
                autocomplete.schema = self.saved_connections.get(conn_name, {}).get('schema', {})
                
            def on_schema_double_click(event):
                sel = schema_tree.selection()
                if not sel:
                    return
                item_id = sel[0]
                parent_id = schema_tree.parent(item_id)
                text = schema_tree.item(item_id, "text")
                if text.startswith("Esquema não carregado"):
                    return
                    
                if parent_id:  # It is a column/field
                    parent_text = schema_tree.item(parent_id, "text")
                    insert_text = f"{parent_text}.{text}"
                else:  # It is a table
                    insert_text = text
                    
                sql_text.insert(tk.INSERT, insert_text)
                sql_text.event_generate("<KeyRelease>")
                
            cb_conn.bind("<<ComboboxSelected>>", on_connection_change)
            sql_text.bind("<KeyRelease>", save_db_fields)
            schema_tree.bind("<Double-1>", on_schema_double_click)
            
            # Initial load of schema preview and autocomplete
            update_schema_preview()
            conn_name = cb_conn.get()
            if conn_name:
                autocomplete.schema = self.saved_connections.get(conn_name, {}).get('schema', {})
            
            def run_capture_db():
                conn_name = cb_conn.get()
                query = sql_text.get("1.0", "end-1c")
                if not conn_name:
                    messagebox.showwarning(t("messages.warning"), t("connection_dialogs.select_connection"))
                    return
                
                btn_run_db.config(state="disabled", text="⌛ Running...")
                self.log_message(f">> Running test query for node '{node.name}'...")
                
                def thread_target():
                    try:
                        conn_config = self.saved_connections.get(conn_name)
                        resolved_sql = resolve_value(query, input_data)
                        result = self.run_db_query(db_type, conn_config, resolved_sql)
                        
                        self.temp_properties['sample_payload'] = result
                        self.log_message(f">> Test executed successfully for node '{node.name}'.")
                        
                        def update_ui():
                            self.build_payload_tree(
                                self.output_payload_container,
                                result,
                                t("properties.no_output_params"),
                                is_mock=False
                            )
                            btn_run_db.config(state="normal", text=t("properties.run_test"))
                        self.root.after(0, update_ui)
                        
                    except Exception as e:
                        err_msg = str(e)
                        self.log_message(f">> Error in node '{node.name}' test: {err_msg}")
                        def err_ui():
                            messagebox.showerror(t("messages.error"), t("messages.query_error").format(err_msg))
                            btn_run_db.config(state="normal", text=t("properties.run_test"))
                        self.root.after(0, err_ui)
                        
                threading.Thread(target=thread_target, daemon=True).start()
                
            btn_run_db = tk.Button(
                self.properties_container, text=t("properties.run_test"), font=("Segoe UI", 9, "bold"),
                bg="#22c55e", fg="#ffffff", activebackground="#16a34a", activeforeground="#ffffff",
                bd=0, pady=8, cursor="hand2", command=run_capture_db
            )
            btn_run_db.pack(fill="x", pady=5)
 
        elif node.type == 'api':
            lbl_conn = tk.Label(self.properties_container, text=t("properties.api_conn"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_conn.pack(anchor="w", pady=(0, 2))
            
            api_conns = [""] + [name for name, c in self.saved_connections.items() if c.get('type') == 'api']
            cb_conn = ttk.Combobox(self.properties_container, values=api_conns, state="readonly")
            cb_conn.set(self.temp_properties.get('connection_name', ''))
            cb_conn.pack(fill="x", pady=(0, 10))
            cb_conn.property_key = 'connection_name'
            
            lbl_method = tk.Label(self.properties_container, text=t("properties.http_method"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_method.pack(anchor="w", pady=(0, 2))
            
            cb_method = ttk.Combobox(self.properties_container, values=["GET", "POST", "PUT", "DELETE", "PATCH"], state="readonly")
            cb_method.set(self.temp_properties.get('method', 'GET'))
            cb_method.pack(fill="x", pady=(0, 10))
            cb_method.property_key = 'method'
            
            lbl_path = tk.Label(self.properties_container, text=t("properties.endpoint_url"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_path.pack(anchor="w", pady=(0, 2))
            
            ent_path = ttk.Entry(self.properties_container, font=("Segoe UI", 9))
            ent_path.insert(0, self.temp_properties.get('path', ''))
            ent_path.pack(fill="x", pady=(0, 10))
            ent_path.property_key = 'path'
            
            lbl_headers = tk.Label(self.properties_container, text=t("properties.additional_headers"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_headers.pack(anchor="w", pady=(0, 2))
            
            headers_text = tk.Text(self.properties_container, font=("Consolas", 9), height=3, bd=1, relief="solid", width=40)
            headers_text.insert("1.0", self.temp_properties.get('headers', ''))
            headers_text.pack(fill="x", pady=(0, 10))
            headers_text.property_key = 'headers'
            
            lbl_body = tk.Label(self.properties_container, text=t("properties.request_body"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_body.pack(anchor="w", pady=(0, 2))
            
            body_text = tk.Text(self.properties_container, font=("Consolas", 9), height=5, bd=1, relief="solid", width=40)
            body_text.insert("1.0", self.temp_properties.get('body', ''))
            body_text.pack(fill="x", pady=(0, 15))
            body_text.property_key = 'body'
            
            def save_api_fields(event=None):
                self.temp_properties['connection_name'] = cb_conn.get()
                self.temp_properties['method'] = cb_method.get()
                self.temp_properties['path'] = ent_path.get()
                self.temp_properties['headers'] = headers_text.get("1.0", "end-1c")
                self.temp_properties['body'] = body_text.get("1.0", "end-1c")
                
            cb_conn.bind("<<ComboboxSelected>>", save_api_fields)
            cb_method.bind("<<ComboboxSelected>>", save_api_fields)
            ent_path.bind("<KeyRelease>", save_api_fields)
            headers_text.bind("<KeyRelease>", save_api_fields)
            body_text.bind("<KeyRelease>", save_api_fields)
            
            def run_capture_api():
                conn_name = cb_conn.get()
                method = cb_method.get()
                path = ent_path.get()
                headers = headers_text.get("1.0", "end-1c")
                body = body_text.get("1.0", "end-1c")
                
                btn_run_api.config(state="disabled", text="⌛ Sending...")
                self.log_message(f">> Sending test API request for node '{node.name}'...")
                
                def thread_target():
                    try:
                        conn_config = self.saved_connections.get(conn_name) if conn_name else None
                        resolved_path = resolve_value(path, input_data)
                        resolved_headers = resolve_value(headers, input_data)
                        resolved_body = resolve_value(body, input_data)
                        
                        result = self.run_api_request(conn_config, method, resolved_path, resolved_headers, resolved_body)
                        self.temp_properties['sample_payload'] = result
                        self.log_message(f">> API test completed successfully (HTTP {result['status_code']}).")
                        
                        def update_ui():
                            self.build_payload_tree(
                                self.output_payload_container,
                                result,
                                t("properties.no_output_params"),
                                is_mock=False
                            )
                            btn_run_api.config(state="normal", text=t("properties.run_test"))
                        self.root.after(0, update_ui)
                        
                    except Exception as e:
                        err_msg = str(e)
                        self.log_message(f">> Error in node '{node.name}' API request: {err_msg}")
                        def err_ui():
                            messagebox.showerror(t("messages.error"), t("messages.api_error").format(err_msg))
                            btn_run_api.config(state="normal", text=t("properties.run_test"))
                        self.root.after(0, err_ui)
                        
                threading.Thread(target=thread_target, daemon=True).start()
                
            btn_run_api = tk.Button(
                self.properties_container, text=t("properties.run_test"), font=("Segoe UI", 9, "bold"),
                bg="#22c55e", fg="#ffffff", activebackground="#16a34a", activeforeground="#ffffff",
                bd=0, pady=8, cursor="hand2", command=run_capture_api
            )
            btn_run_api.pack(fill="x", pady=5)
 
        elif node.type == 'delay':
            lbl_sec = tk.Label(self.properties_container, text=t("properties.wait_time"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_sec.pack(anchor="w", pady=(0, 2))
            
            ent_sec = ttk.Entry(self.properties_container, font=("Segoe UI", 9))
            ent_sec.insert(0, str(self.temp_properties.get('seconds', 1.0)))
            ent_sec.pack(fill="x", pady=(0, 15))
            ent_sec.property_key = 'seconds'
            
            def save_delay_field(event=None):
                val_sec = ent_sec.get()
                try:
                    self.temp_properties['seconds'] = float(val_sec)
                except ValueError:
                    self.temp_properties['seconds'] = val_sec
                
            ent_sec.bind("<KeyRelease>", save_delay_field)
  
        elif node.type == 'move_mouse':
            lbl_x = tk.Label(self.properties_container, text=t("properties.coord_x"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_x.pack(anchor="w", pady=(0, 2))
            
            ent_x = ttk.Entry(self.properties_container, font=("Segoe UI", 9))
            ent_x.insert(0, str(self.temp_properties.get('x', 0)))
            ent_x.pack(fill="x", pady=(0, 8))
            ent_x.property_key = 'x'
            
            lbl_y = tk.Label(self.properties_container, text=t("properties.coord_y"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_y.pack(anchor="w", pady=(0, 2))
            
            ent_y = ttk.Entry(self.properties_container, font=("Segoe UI", 9))
            ent_y.insert(0, str(self.temp_properties.get('y', 0)))
            ent_y.pack(fill="x", pady=(0, 15))
            ent_y.property_key = 'y'
            
            def save_coords(event=None):
                val_x = ent_x.get()
                val_y = ent_y.get()
                try:
                    self.temp_properties['x'] = int(val_x)
                except ValueError:
                    self.temp_properties['x'] = val_x
                try:
                    self.temp_properties['y'] = int(val_y)
                except ValueError:
                    self.temp_properties['y'] = val_y
                
            ent_x.bind("<KeyRelease>", save_coords)
            ent_y.bind("<KeyRelease>", save_coords)
            
            btn_capture = tk.Button(
                self.properties_container, text=t("properties.capture_coordinates"), font=("Segoe UI", 9, "bold"),
                bg="#3b82f6", fg="#ffffff", activebackground="#2563eb", activeforeground="#ffffff",
                bd=0, pady=8, cursor="hand2", command=lambda: self.launch_coordinate_capture(ent_x, ent_y)
            )
            btn_capture.pack(fill="x", pady=5)

        elif node.type == 'loop':
            lbl_val = tk.Label(self.properties_container, text=t("properties.val_array"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_val.pack(anchor="w", pady=(0, 2))
            
            lbl_hint = tk.Label(
                self.properties_container, 
                text=t("properties.val_array_hint"), 
                font=("Segoe UI", 8, "italic"), fg="#64748b", bg="#f8fafc"
            )
            lbl_hint.pack(anchor="w", pady=(0, 5))
            
            ent_val = ttk.Entry(self.properties_container, font=("Segoe UI", 9))
            ent_val.insert(0, self.temp_properties.get('array_data', '[]'))
            ent_val.pack(fill="x", pady=(0, 15))
            ent_val.property_key = 'array_data'
            
            def update_loop_temp(event=None):
                self.temp_properties['array_data'] = ent_val.get()
                
            ent_val.bind("<KeyRelease>", update_loop_temp)
            
        elif node.type == 'break_loop':
            lbl_loop = tk.Label(self.properties_container, text=t("properties.select_loop_to_interrupt"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_loop.pack(anchor="w", pady=(0, 2))
            
            loop_nodes = [n.name for n in self.nodes.values() if n.type == 'loop']
            cb_loop = ttk.Combobox(self.properties_container, values=loop_nodes, state="readonly")
            cb_loop.set(self.temp_properties.get('loop_node_name', ''))
            cb_loop.pack(fill="x", pady=(0, 10))
            cb_loop.property_key = 'loop_node_name'
            
            def save_break_loop(event=None):
                self.temp_properties['loop_node_name'] = cb_loop.get()
                
            cb_loop.bind("<<ComboboxSelected>>", save_break_loop)
            
        elif node.type == 'storage_var':
            lbl_var_name = tk.Label(self.properties_container, text=t("properties.storage_var_name"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_var_name.pack(anchor="w", pady=(0, 2))
            
            ent_var_name = ttk.Entry(self.properties_container, font=("Segoe UI", 9))
            ent_var_name.insert(0, self.temp_properties.get('variable_name', 'var_1'))
            ent_var_name.pack(fill="x", pady=(0, 10))
            ent_var_name.property_key = 'variable_name'
            
            lbl_var_val = tk.Label(self.properties_container, text=t("properties.storage_var_value"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_var_val.pack(anchor="w", pady=(0, 2))
            
            lbl_val_hint = tk.Label(self.properties_container, text=t("properties.storage_var_hint"), font=("Segoe UI", 8, "italic"), fg="#64748b", bg="#f8fafc")
            lbl_val_hint.pack(anchor="w", pady=(0, 2))
            
            ent_var_val = ttk.Entry(self.properties_container, font=("Segoe UI", 9))
            ent_var_val.insert(0, self.temp_properties.get('variable_value', ''))
            ent_var_val.pack(fill="x", pady=(0, 15))
            ent_var_val.property_key = 'variable_value'
            
            def save_storage_var(event=None):
                self.temp_properties['variable_name'] = ent_var_name.get().strip()
                self.temp_properties['variable_value'] = ent_var_val.get()
                
            ent_var_name.bind("<KeyRelease>", save_storage_var)
            ent_var_val.bind("<KeyRelease>", save_storage_var)

        elif node.type == 'confirm_dialog':
            lbl_title = tk.Label(self.properties_container, text=t("properties.dialog_title"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_title.pack(anchor="w", pady=(0, 2))
            ent_title = ttk.Entry(self.properties_container, font=("Segoe UI", 9))
            ent_title.insert(0, self.temp_properties.get('title', 'Confirmação'))
            ent_title.pack(fill="x", pady=(0, 10))
            ent_title.property_key = 'title'
            
            lbl_msg = tk.Label(self.properties_container, text=t("properties.dialog_message"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_msg.pack(anchor="w", pady=(0, 2))
            ent_msg = ttk.Entry(self.properties_container, font=("Segoe UI", 9))
            ent_msg.insert(0, self.temp_properties.get('message', 'Você deseja continuar?'))
            ent_msg.pack(fill="x", pady=(0, 10))
            ent_msg.property_key = 'message'
            
            lbl_true = tk.Label(self.properties_container, text=t("properties.btn_true_text"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_true.pack(anchor="w", pady=(0, 2))
            ent_true = ttk.Entry(self.properties_container, font=("Segoe UI", 9))
            ent_true.insert(0, self.temp_properties.get('btn_true_text', 'Sim'))
            ent_true.pack(fill="x", pady=(0, 10))
            ent_true.property_key = 'btn_true_text'
            
            lbl_false = tk.Label(self.properties_container, text=t("properties.btn_false_text"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_false.pack(anchor="w", pady=(0, 2))
            ent_false = ttk.Entry(self.properties_container, font=("Segoe UI", 9))
            ent_false.insert(0, self.temp_properties.get('btn_false_text', 'Não'))
            ent_false.pack(fill="x", pady=(0, 10))
            ent_false.property_key = 'btn_false_text'
            
            lbl_var = tk.Label(self.properties_container, text=t("properties.payload_var_dest"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_var.pack(anchor="w", pady=(0, 2))
            ent_var = ttk.Entry(self.properties_container, font=("Segoe UI", 9))
            ent_var.insert(0, self.temp_properties.get('payload_var', 'confirm_result'))
            ent_var.pack(fill="x", pady=(0, 15))
            ent_var.property_key = 'payload_var'
            
            ent_title.is_payload_var_field = False
            ent_msg.is_payload_var_field = False
            ent_true.is_payload_var_field = False
            ent_false.is_payload_var_field = False
            ent_var.is_payload_var_field = True
            
            def save_confirm_fields(event=None):
                self.temp_properties['title'] = ent_title.get()
                self.temp_properties['message'] = ent_msg.get()
                self.temp_properties['btn_true_text'] = ent_true.get()
                self.temp_properties['btn_false_text'] = ent_false.get()
                self.temp_properties['payload_var'] = ent_var.get().strip()
                
            ent_title.bind("<KeyRelease>", save_confirm_fields)
            ent_msg.bind("<KeyRelease>", save_confirm_fields)
            ent_true.bind("<KeyRelease>", save_confirm_fields)
            ent_false.bind("<KeyRelease>", save_confirm_fields)
            ent_var.bind("<KeyRelease>", save_confirm_fields)
            
        elif node.type == 'alert_dialog':
            lbl_title = tk.Label(self.properties_container, text=t("properties.dialog_title"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_title.pack(anchor="w", pady=(0, 2))
            ent_title = ttk.Entry(self.properties_container, font=("Segoe UI", 9))
            ent_title.insert(0, self.temp_properties.get('title', 'Alerta'))
            ent_title.pack(fill="x", pady=(0, 10))
            ent_title.property_key = 'title'
            
            lbl_msg = tk.Label(self.properties_container, text=t("properties.dialog_message"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_msg.pack(anchor="w", pady=(0, 2))
            ent_msg = ttk.Entry(self.properties_container, font=("Segoe UI", 9))
            ent_msg.insert(0, self.temp_properties.get('message', 'Fluxo interrompido!'))
            ent_msg.pack(fill="x", pady=(0, 10))
            ent_msg.property_key = 'message'
            
            lbl_btn = tk.Label(self.properties_container, text=t("properties.btn_ok_text"), font=("Segoe UI", 9, "bold"), fg="#475569", bg="#f8fafc")
            lbl_btn.pack(anchor="w", pady=(0, 2))
            ent_btn = ttk.Entry(self.properties_container, font=("Segoe UI", 9))
            ent_btn.insert(0, self.temp_properties.get('btn_ok_text', 'OK'))
            ent_btn.pack(fill="x", pady=(0, 15))
            ent_btn.property_key = 'btn_ok_text'
            
            ent_title.is_payload_var_field = False
            ent_msg.is_payload_var_field = False
            ent_btn.is_payload_var_field = False
            
            def save_alert_fields(event=None):
                self.temp_properties['title'] = ent_title.get()
                self.temp_properties['message'] = ent_msg.get()
                self.temp_properties['btn_ok_text'] = ent_btn.get()
                
            ent_title.bind("<KeyRelease>", save_alert_fields)
            ent_msg.bind("<KeyRelease>", save_alert_fields)
            ent_btn.bind("<KeyRelease>", save_alert_fields)

        # Recursively bind FocusIn to all input fields
        def bind_focus_in(widget):
            if isinstance(widget, (tk.Entry, ttk.Entry, tk.Text, ttk.Spinbox)):
                widget.bind("<FocusIn>", lambda e: self.set_active_widget(e.widget))
            for child in widget.winfo_children():
                bind_focus_in(child)
        bind_focus_in(self.properties_container)

    # --- Payload Tree Helpers ---

    def format_preview_value(self, val):
        if isinstance(val, dict):
            keys = list(val.keys())
            if len(keys) > 10:
                keys_str = ", ".join(str(k) for k in keys[:10]) + ", ..."
            else:
                keys_str = ", ".join(str(k) for k in keys)
            return f"dict ({len(val)} items: {{{keys_str}}})"
        elif isinstance(val, list):
            return f"list ({len(val)} items)"
        else:
            val_str = str(val)
            if len(val_str) > 200:
                return val_str[:200] + "..."
            return val_str

    def set_active_widget(self, widget):
        self.active_text_widget = widget

    def get_mock_payload(self):
        return {
            "active_window": {
                "title": "Documento - Google Chrome",
                "hwnd": 196804
            },
            "captured_mouse": {
                "x": 840,
                "y": 420,
                "cursor_handle": 65536
            },
            "last_click": {
                "x": 500,
                "y": 300
            },
            "last_key": {
                "key": "enter",
                "count": 1
            },
            "last_typed": "Texto digitado de exemplo",
            "last_mouse_pos": {
                "x": 840,
                "y": 420
            }
        }

    def populate_tree(self, tree, parent_iid, key, val, path=""):
        child_path = f"{path}.{key}" if path else key
        type_str = type(val).__name__
        
        if isinstance(val, dict):
            node_id = tree.insert(parent_iid, "end", iid=child_path, text=key, values=("", f"dict ({len(val)})"))
            tree.item(node_id, open=True)
            for k, v in val.items():
                self.populate_tree(tree, node_id, k, v, child_path)
        elif isinstance(val, list):
            node_id = tree.insert(parent_iid, "end", iid=child_path, text=key, values=("", f"list ({len(val)})"))
            tree.item(node_id, open=True)
            for idx, v in enumerate(val):
                self.populate_tree(tree, node_id, str(idx), v, child_path)
        else:
            val_str = str(val)
            if type_str == "str" and len(val_str) > 80:
                val_str = val_str[:80] + "..."
            tree.insert(parent_iid, "end", iid=child_path, text=key, values=(val_str, type_str))

    def on_tree_double_click(self, event, tree):
        selected_item = tree.focus()
        if not selected_item:
            return
        
        path = selected_item
        if self.active_text_widget:
            try:
                # Defensively verify that the active widget still exists
                if not self.active_text_widget.winfo_exists():
                    self.active_text_widget = None
                    return
            except tk.TclError:
                self.active_text_widget = None
                return
                
            try:
                if isinstance(self.active_text_widget, tk.Text):
                    self.active_text_widget.insert(tk.INSERT, f"{{{path}}}")
                elif isinstance(self.active_text_widget, ttk.Entry) or isinstance(self.active_text_widget, tk.Entry):
                    if getattr(self.active_text_widget, 'is_payload_var_field', False):
                        self.active_text_widget.delete(0, tk.END)
                        self.active_text_widget.insert(0, path)
                    else:
                        insert_pos = self.active_text_widget.index(tk.INSERT)
                        self.active_text_widget.insert(insert_pos, f"{{{path}}}")
                    
                self.active_text_widget.event_generate("<KeyRelease>")
            except Exception:
                self.active_text_widget = None

    def build_payload_tree(self, container, data, title_msg, is_mock=False):
        for widget in container.winfo_children():
            widget.destroy()
            
        if not data:
            lbl = tk.Label(
                container, 
                text=title_msg, 
                font=("Segoe UI", 9, "italic"), fg="#64748b", bg="#f8fafc", justify="center", wraplength=350
            )
            lbl.pack(pady=40)
            return

        if is_mock:
            warn_lbl = tk.Label(
                container,
                text="⚠️ Mostrando dados simulados (execute para obter dados reais)",
                font=("Segoe UI", 8, "bold"), fg="#b45309", bg="#fef3c7", pady=4, padx=8, bd=1, relief="solid"
            )
            warn_lbl.pack(fill="x", pady=(0, 5))
        else:
            info_lbl = tk.Label(
                container,
                text="✅ Dados reais da última execução",
                font=("Segoe UI", 8, "bold"), fg="#15803d", bg="#dcfce7", pady=4, padx=8, bd=1, relief="solid"
            )
            info_lbl.pack(fill="x", pady=(0, 5))
            
        tree_frame = ttk.Frame(container)
        tree_frame.pack(fill="both", expand=True)
        
        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        vsb.pack(side="right", fill="y")
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")
        hsb.pack(side="bottom", fill="x")
        
        tree = ttk.Treeview(
            tree_frame, 
            columns=("Valor", "Tipo"), 
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set
        )
        tree.heading("#0", text="Chave / Propriedade", anchor="w")
        tree.heading("Valor", text="Valor", anchor="w")
        tree.heading("Tipo", text="Tipo", anchor="w")
        
        tree.column("#0", width=160, minwidth=100)
        tree.column("Valor", width=160, minwidth=100)
        tree.column("Tipo", width=60, minwidth=40)
        
        tree.pack(fill="both", expand=True, side="left")
        
        vsb.config(command=tree.yview)
        hsb.config(command=tree.xview)
        
        for k, v in data.items():
            self.populate_tree(tree, "", k, v, "")
            
        tree.bind("<Double-1>", lambda e: self.on_tree_double_click(e, tree))

    def get_predecessors(self, node_id):
        rev_adj = {nid: [] for nid in self.nodes}
        for conn in self.connections:
            rev_adj[conn.target.id].append(conn.source.id)
            
        visited = set()
        queue = [node_id]
        while queue:
            curr = queue.pop(0)
            for parent in rev_adj.get(curr, []):
                if parent not in visited:
                    visited.add(parent)
                    queue.append(parent)
        return visited

    def get_node_output_schema(self, node, visited=None):
        if visited is None:
            visited = set()
        if node.id in visited:
            return {}
        visited.add(node.id)
        schema = {}
        if node.type == 'click':
            schema['last_click'] = {'x': '<Número>', 'y': '<Número>'}
        elif node.type == 'capture':
            capture_type = node.properties.get('capture_type', 'Dados da Janela Ativa')
            if capture_type in ['Dados da Janela Ativa', 'Janela Ativa']:
                schema['active_window'] = {'title': '<Texto>', 'hwnd': '<Número>'}
            else:
                schema['captured_mouse'] = {'x': '<Número>', 'y': '<Número>', 'cursor_name': '<Texto>', 'cursor_handle': '<Número>'}
        elif node.type == 'key':
            schema['last_key'] = {'key': '<Texto>', 'count': '<Número>'}
        elif node.type == 'type_text':
            schema['last_typed'] = '<Texto>'
        elif node.type == 'move_mouse':
            schema['last_mouse_pos'] = {'x': '<Número>', 'y': '<Número>'}
        elif node.type in ['postgres', 'mysql', 'sqlite', 'api']:
            var_name = self.get_var_name(node.name)
            sample = node.properties.get('sample_payload')
            if sample:
                schema[var_name] = sample
            else:
                if node.type == 'api':
                    schema[var_name] = {
                        "status_code": 200,
                        "status": "success",
                        "body": {},
                        "headers": {}
                    }
                else:
                    schema[var_name] = {
                        "status": "success",
                        "rows_affected": 0,
                        "rows": []
                    }
        elif node.type == 'loop':
            var_name = self.get_var_name(node.name)
            item_schema = {}
            ds = node.properties.get('data_source', 'Manual (JSON)')
            if ds == 'Manual (JSON)':
                manual = node.properties.get('manual_data', '[]')
                try:
                    data = json.loads(manual)
                    if isinstance(data, list) and len(data) > 0:
                        first_item = data[0]
                        if isinstance(first_item, dict):
                            item_schema = {k: f"<{type(v).__name__}>" for k, v in first_item.items()}
                        else:
                            item_schema = f"<{type(first_item).__name__}>"
                except Exception:
                    pass
            else:
                p_var = node.properties.get('payload_variable', '')
                predecessors = self.get_predecessors(node.id)
                input_schema = {}
                for pred_id in predecessors:
                    pred_node = self.nodes[pred_id]
                    pred_schema = self.get_node_output_schema(pred_node, visited)
                    self.deep_merge_dict(input_schema, pred_schema)
                
                resolved_val = get_payload_value(input_schema, p_var)
                if isinstance(resolved_val, dict):
                    if "rows" in resolved_val and isinstance(resolved_val["rows"], list):
                        resolved_val = resolved_val["rows"]
                    elif "body" in resolved_val and isinstance(resolved_val["body"], list):
                        resolved_val = resolved_val["body"]
                    elif "body" in resolved_val and isinstance(resolved_val["body"], dict) and "rows" in resolved_val["body"] and isinstance(resolved_val["body"]["rows"], list):
                        resolved_val = resolved_val["body"]["rows"]

                if isinstance(resolved_val, list):
                    if len(resolved_val) > 0:
                        first_item = resolved_val[0]
                        if isinstance(first_item, dict):
                            item_schema = {k: (v if isinstance(v, dict) else str(v)) for k, v in first_item.items()}
                        else:
                            item_schema = str(first_item)
                    else:
                        item_schema = "<Qualquer>"
                else:
                    item_schema = "<Qualquer>"
            
            schema[var_name] = {
                'item': item_schema,
                'index': '<Número>',
                'total': '<Número>'
            }
        elif node.type == 'storage_var':
            var_name = node.properties.get('variable_name', 'var_1')
            var_val = node.properties.get('variable_value', '')
            schema[var_name] = var_val or '<Valor>'
        elif node.type == 'confirm_dialog':
            payload_var = node.properties.get('payload_var', 'confirm_result')
            schema[payload_var] = '<Boolean>'
        elif node.type == 'break_loop':
            pass
            
        return schema

    def deep_merge_dict(self, target, source):
        for k, v in source.items():
            if isinstance(v, dict):
                if k not in target or not isinstance(target[k], dict):
                    target[k] = {}
                self.deep_merge_dict(target[k], v)
            else:
                target[k] = v

    def get_resolved_payload(self, schema, real_payload):
        resolved = {}
        # 1. Fill with schema and overlay with real_payload if available
        for k, v in schema.items():
            if isinstance(v, dict):
                sub_payload = real_payload.get(k) if isinstance(real_payload, dict) else None
                resolved[k] = self.get_resolved_payload(v, sub_payload)
            else:
                if isinstance(real_payload, dict) and k in real_payload:
                    resolved[k] = real_payload[k]
                else:
                    resolved[k] = v
        # 2. Add any extra keys present in real_payload but not in schema
        if isinstance(real_payload, dict):
            for k, v in real_payload.items():
                if k not in resolved:
                    resolved[k] = v
        return resolved

    def get_var_name(self, node_name):
        # Normalizes name to a clean, lowercase variable name
        import re as _re
        name = _re.sub(r'[^a-zA-Z0-9\s]', '', node_name)
        return name.strip().lower().replace(' ', '_')

    def save_properties_from_widgets(self):
        if not hasattr(self, 'properties_container') or not self.properties_container:
            return
            
        def scan_widgets(parent):
            for child in parent.winfo_children():
                prop_key = getattr(child, 'property_key', None)
                if prop_key is not None:
                    if isinstance(child, tk.Text):
                        val = child.get("1.0", "end-1c")
                    elif isinstance(child, (ttk.Combobox, ttk.Entry, tk.Entry, ttk.Spinbox)):
                        val = child.get()
                    else:
                        scan_widgets(child)
                        continue
                        
                    # Perform conversions
                    if self.selected_node.type in ['click', 'move_mouse'] and prop_key in ['x', 'y']:
                        try:
                            val = int(val)
                        except ValueError:
                            pass
                    elif self.selected_node.type == 'key' and prop_key == 'count':
                        try:
                            val = int(val)
                        except ValueError:
                            pass
                    elif self.selected_node.type == 'start' and prop_key == 'loop_count':
                        try:
                            val = int(val)
                        except ValueError:
                            val = 5
                    elif self.selected_node.type == 'delay' and prop_key == 'seconds':
                        try:
                            val = float(val)
                        except ValueError:
                            pass
                            
                    self.temp_properties[prop_key] = val
                scan_widgets(child)
                
        scan_widgets(self.properties_container)
        
        if hasattr(self, 'name_entry_widget') and self.name_entry_widget:
            try:
                if self.name_entry_widget.winfo_exists():
                    self.temp_node_name = self.name_entry_widget.get()
            except Exception:
                pass

