"""
Payload variable resolution helpers.

Provides functions for resolving nested dictionary paths and
interpolating placeholder variables in strings.
"""
import re


def get_payload_value(payload, path):
    """Resolves nested path in dict. E.g. 'active_window.title' from payload."""
    parts = path.split('.')
    val = payload
    for part in parts:
        if isinstance(val, dict) and part in val:
            val = val[part]
        else:
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
