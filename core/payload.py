"""
Payload variable resolution helpers.

Provides functions for resolving nested dictionary paths and
interpolating placeholder variables in strings.
"""
import re


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
    if path == "payload":
        return payload
    if path.startswith("payload."):
        path = path[8:]
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
    """Resolves placeholders in format {{variable_path}} or {variable_path} using payload.
    If the value is purely a placeholder like '{{active_window.hwnd}}' or '{active_window.hwnd}'
    and resolves to a dict/int/float, returns the resolved type.
    Otherwise, returns interpolated string.
    """
    if not isinstance(val_str, str):
        return val_str
    
    # Check if it's exactly a single placeholder (double curly braces first)
    match_double = re.match(r'^\{\{([^{}]+)\}\}$', val_str)
    if match_double:
        path = match_double.group(1)
        resolved = get_payload_value(payload, path)
        if resolved is not None:
            return resolved
            
    match_single = re.match(r'^\{([^{}]+)\}$', val_str)
    if match_single:
        path = match_single.group(1)
        resolved = get_payload_value(payload, path)
        if resolved is not None:
            return resolved
    
    # Otherwise, do string interpolation for all placeholders
    formatted = val_str
    
    # Double curly braces: {{path}}
    placeholders_double = re.findall(r'\{\{([^{}]+)\}\}', val_str)
    for ph in placeholders_double:
        resolved = get_payload_value(payload, ph)
        if resolved is not None:
            formatted = formatted.replace(f"{{{{{ph}}}}}", str(resolved))
            
    # Single curly braces: {path}
    placeholders_single = re.findall(r'(?<!\{)\{([^{}]+)\}(?!\})', val_str)
    for ph in placeholders_single:
        resolved = get_payload_value(payload, ph)
        if resolved is not None:
            formatted = formatted.replace(f"{{{ph}}}", str(resolved))
            
    return formatted


def truncate_payload_data(val, limit=5):
    """Recursively truncates lists/arrays in a payload to a maximum limit to prevent file bloat."""
    if isinstance(val, dict):
        return {k: truncate_payload_data(v, limit) for k, v in val.items()}
    elif isinstance(val, list):
        return [truncate_payload_data(item, limit) for item in val[:limit]]
    return val
