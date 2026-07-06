import i18n
import os
import json
import sys

# Setup root and locales directory
if getattr(sys, 'frozen', False):
    # Under PyInstaller, sys._MEIPASS is the temporary/internal directory where assets are unpacked
    BASE_DIR = sys._MEIPASS
    CONFIG_FILE = os.path.join(os.path.dirname(sys.executable), 'config.json')
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')

LOCALES_DIR = os.path.join(BASE_DIR, 'locales')

# Create locales directory if it does not exist (only in development)
if not getattr(sys, 'frozen', False):
    os.makedirs(LOCALES_DIR, exist_ok=True)

# Set python-i18n options
i18n.set('file_format', 'json')
i18n.set('filename_format', '{locale}.{format}')
i18n.set('fallback', 'en')
i18n.load_path.append(LOCALES_DIR)

def get_user_config_path():
    """Returns the path to the user's config file in %APPDATA% as a writable fallback."""
    appdata = os.environ.get('APPDATA')
    if appdata:
        user_dir = os.path.join(appdata, 'AutoClick')
        return os.path.join(user_dir, 'config.json')
    return None

# Load selected language from configuration
def load_language_pref():
    # 1. Try to load from user's AppData configuration first (takes precedence)
    user_config = get_user_config_path()
    if user_config and os.path.exists(user_config):
        try:
            with open(user_config, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('language', 'en')
        except Exception:
            pass

    # 2. Fall back to reading from local app directory CONFIG_FILE (e.g. written by installer)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('language', 'en')
        except Exception:
            pass
            
    return 'en'

def save_language_pref(lang):
    config = {}
    
    # 1. Try to load existing local config
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception:
            pass
            
    config['language'] = lang

    # 2. Try to write to local directory CONFIG_FILE
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
        return
    except (PermissionError, IOError):
        # If we don't have permission (e.g., installed in Program Files), write to AppData instead
        pass
    except Exception:
        pass

    # 3. Fallback: Write to user's AppData directory
    user_config = get_user_config_path()
    if user_config:
        try:
            os.makedirs(os.path.dirname(user_config), exist_ok=True)
            with open(user_config, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        except Exception:
            pass

# Initialize language
current_lang = load_language_pref()
i18n.set('locale', current_lang)

def t(key, **kwargs):
    """Translate a key using the active language configuration."""
    return i18n.t(key, **kwargs)

def get_current_language():
    return i18n.get('locale')

def change_language(lang):
    """Set language preference and update configuration file."""
    i18n.set('locale', lang)
    save_language_pref(lang)

