"""
API connector — Executes HTTP requests (GET, POST, PUT, DELETE, PATCH).
"""
import json
import urllib.request
import urllib.parse
import urllib.error
import base64
from core.i18n_helper import t


class ApiMixin:
    """Mixin providing API request execution for the main app."""

    def run_api_request(self, conn_config, method, path_url, headers_json, body_text):
        base_url = ""
        auth_type = "None"
        auth_token = ""
        default_headers = {}
        
        if conn_config:
            base_url = conn_config.get("base_url", "")
            auth_type = conn_config.get("auth_type", "None")
            auth_token = conn_config.get("auth_token", "")
            def_headers_raw = conn_config.get("default_headers", "")
            if def_headers_raw:
                try:
                    default_headers = json.loads(def_headers_raw)
                except Exception:
                    pass
                    
        # Construct URL
        url = path_url
        if base_url:
            if base_url.endswith('/') and path_url.startswith('/'):
                url = base_url + path_url[1:]
            elif not base_url.endswith('/') and not path_url.startswith('/') and path_url:
                url = base_url + '/' + path_url
            else:
                url = base_url + path_url
        else:
            url = path_url
            
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "http://" + url
            
        # Parse extra headers
        req_headers = {}
        for k, v in default_headers.items():
            req_headers[str(k)] = str(v)
            
        if auth_type == "Bearer Token" and auth_token:
            req_headers["Authorization"] = f"Bearer {auth_token}"
        elif auth_type == "Basic Auth" and auth_token:
            if ":" in auth_token:
                encoded = base64.b64encode(auth_token.encode('utf-8')).decode('utf-8')
                req_headers["Authorization"] = f"Basic {encoded}"
            else:
                req_headers["Authorization"] = f"Basic {auth_token}"
        elif auth_type == "API Key" and auth_token:
            req_headers["X-API-Key"] = auth_token
            
        if headers_json:
            try:
                custom_h = json.loads(headers_json)
                for k, v in custom_h.items():
                    req_headers[str(k)] = str(v)
            except Exception as e:
                raise ValueError(t("messages.invalid_headers").format(str(e)))
                
        # Send Request
        data_bytes = None
        if method in ["POST", "PUT", "PATCH", "DELETE"] and body_text:
            data_bytes = body_text.encode('utf-8')
            if "Content-Type" not in req_headers:
                req_headers["Content-Type"] = "application/json"
                
        req = urllib.request.Request(url, data=data_bytes, headers=req_headers, method=method)
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                status_code = response.status
                res_headers = dict(response.info())
                res_body = response.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            status_code = e.code
            res_headers = dict(e.headers)
            res_body = e.read().decode('utf-8')
        except urllib.error.URLError as e:
            raise ConnectionError(t("messages.url_connection_error").format(e.reason))
            
        try:
            parsed_body = json.loads(res_body)
        except Exception:
            parsed_body = res_body
            
        return {
            "status_code": status_code,
            "headers": res_headers,
            "body": parsed_body,
            "status": "success" if (200 <= status_code < 300) else "error"
        }
