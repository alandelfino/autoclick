"""
Payload variable resolution helpers.

Provides functions for resolving nested dictionary paths and
interpolating placeholder variables in strings.
"""
import re
import tokenize
import io
import math
import json
import datetime


class DictWrapper(dict):
    """Recursively wraps dictionary keys for dot attribute access."""
    def __init__(self, d):
        super().__init__()
        for k, v in d.items():
            self[k] = wrap_payload_value(v)

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(f"No attribute or key '{name}' found")

    def __setattr__(self, name, value):
        self[name] = value

    def __delattr__(self, name):
        try:
            del self[name]
        except KeyError:
            raise AttributeError(f"No attribute or key '{name}' found")


def wrap_payload_value(val):
    """Recursively wraps dictionary values with DictWrapper."""
    if isinstance(val, dict):
        return DictWrapper(val)
    if isinstance(val, list):
        return [wrap_payload_value(x) for x in val]
    return val


def replace_dollar_sign(expr_str, replacement="_payload"):
    """Replaces '$' with another variable name, preserving string literals and comments."""
    try:
        tokens = tokenize.generate_tokens(io.StringIO(expr_str).readline)
        result = []
        for toknum, tokval, start, end, line in tokens:
            if tokval == '$':
                result.append((toknum, replacement))
            else:
                result.append((toknum, tokval))
        res = tokenize.untokenize(result)
        if isinstance(res, bytes):
            res = res.decode('utf-8')
        return res
    except Exception:
        return expr_str.replace('$', replacement)


def parse_template(val_str):
    """Finds all non-overlapping double curly brace placeholders {{ ... }} in the string,
    safely handling nested curly braces and string literals inside them.
    """
    placeholders = []
    i = 0
    n = len(val_str)
    
    while i < n:
        if val_str[i:i+2] == '{{':
            start_idx = i
            expr_start = i + 2
            i += 2
            
            brace_depth = 2
            in_string = None
            escape = False
            
            while i < n:
                char = val_str[i]
                if in_string is not None:
                    if escape:
                        escape = False
                    elif char == '\\':
                        escape = True
                    else:
                        if in_string in ('"""', "'''"):
                            q_len = len(in_string)
                            if val_str[i:i+q_len] == in_string:
                                in_string = None
                                i += q_len - 1
                        elif char == in_string:
                            in_string = None
                else:
                    if val_str[i:i+3] in ('"""', "'''"):
                        in_string = val_str[i:i+3]
                        i += 2
                    elif char in ('"', "'"):
                        in_string = char
                    elif char == '{':
                        brace_depth += 1
                    elif char == '}':
                        brace_depth -= 1
                        if brace_depth == 0:
                            expr_str = val_str[expr_start : i-1]
                            placeholders.append({
                                'start': start_idx,
                                'end': i + 1,
                                'expr': expr_str
                            })
                            break
                i += 1
        else:
            i += 1
            
    return placeholders


def evaluate_expression(expr, payload):
    """Evaluates a single expression using safe globals and a wrapped payload."""
    wrapped_payload = wrap_payload_value(payload)
    expr_replaced = replace_dollar_sign(expr, "_payload")
    eval_globals = {
        'math': math,
        'json': json,
        'datetime': datetime,
        're': re,
        '_payload': wrapped_payload,
    }
    try:
        return eval(expr_replaced.strip(), eval_globals)
    except Exception as e:
        return f"<Erro: {e}>"


def infer_payload_schema(value, max_list_items=5):
    """Builds a lightweight schema from a real payload value."""
    if isinstance(value, dict):
        return {k: infer_payload_schema(v, max_list_items=max_list_items) for k, v in value.items()}
    if isinstance(value, list):
        if not value:
            return []
        item_schema = None
        for item in value[:max_list_items]:
            current_schema = infer_payload_schema(item, max_list_items=max_list_items)
            if item_schema is None:
                item_schema = current_schema
            else:
                item_schema = merge_payload_schemas(item_schema, current_schema)
        return [item_schema]
    if isinstance(value, bool):
        return "<Boolean>"
    if isinstance(value, int) or isinstance(value, float):
        return "<Número>"
    if value is None:
        return "<Nulo>"
    if isinstance(value, str):
        return "<Texto>"
    return f"<{type(value).__name__}>"


def merge_payload_schemas(target, source):
    """Returns a merged schema without mutating the inputs."""
    if isinstance(target, dict) and isinstance(source, dict):
        merged = dict(target)
        for key, value in source.items():
            if key in merged:
                merged[key] = merge_payload_schemas(merged[key], value)
            else:
                merged[key] = value
        return merged
    if isinstance(target, list) and isinstance(source, list):
        if not target:
            return source
        if not source:
            return target
        return [merge_payload_schemas(target[0], source[0])]
    if target == source:
        return target
    return "<Valor>"


def get_payload_value(payload, path):
    """Resolves nested path in dict. E.g. 'active_window.title' from payload."""
    if path == "payload" or path == "$":
        return payload
    if path.startswith("payload."):
        path = path[8:]
    elif path.startswith("$."):
        path = path[2:]
        
    if not path:
        return payload
            
    parts = path.split('.')
    val = payload
    for i, part in enumerate(parts):
        if isinstance(val, dict) and part in val:
            val = val[part]
        else:
            # Fallback for 'active_window' and 'flow' from start node alias
            if i == 0 and part in ['active_window', 'flow'] and isinstance(payload, dict):
                found = False
                for k, v in payload.items():
                    if isinstance(v, dict) and part in v:
                        val = v[part]
                        found = True
                        break
                if found:
                    continue
            return None
    return val


def resolve_value(val_str, payload):
    """Resolves expressions inside double curly braces {{ expression }} using payload.
    If the value is purely a single placeholder and evaluates to a non-string type,
    returns that type directly. Otherwise, returns a string with interpolated values.
    """
    if not isinstance(val_str, str):
        return val_str
        
    placeholders = parse_template(val_str)
    if not placeholders:
        return val_str
        
    if len(placeholders) == 1 and placeholders[0]['start'] == 0 and placeholders[0]['end'] == len(val_str):
        expr = placeholders[0]['expr']
        return evaluate_expression(expr, payload)
        
    result_chars = list(val_str)
    for ph in reversed(placeholders):
        start = ph['start']
        end = ph['end']
        expr = ph['expr']
        val = evaluate_expression(expr, payload)
        val_str_rep = str(val) if val is not None else ""
        result_chars[start:end] = list(val_str_rep)
        
    return "".join(result_chars)


def truncate_payload_data(val, limit=5):
    """Recursively truncates lists/arrays in a payload to a maximum limit to prevent file bloat."""
    if isinstance(val, dict):
        return {k: truncate_payload_data(v, limit) for k, v in val.items()}
    elif isinstance(val, list):
        return [truncate_payload_data(item, limit) for item in val[:limit]]
    return val
