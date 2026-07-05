import i18n
import os
import json

# Setup root and locales directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCALES_DIR = os.path.join(BASE_DIR, 'locales')
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')

# Create locales directory if it does not exist
os.makedirs(LOCALES_DIR, exist_ok=True)

# Set python-i18n options
i18n.set('file_format', 'json')
i18n.set('filename_format', '{locale}.{format}')
i18n.set('fallback', 'en')
i18n.load_path.append(LOCALES_DIR)

# Load selected language from configuration
def load_language_pref():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('language', 'en')
        except Exception:
            pass
    return 'en'

def save_language_pref(lang):
    try:
        config = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except Exception:
                pass
        config['language'] = lang
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
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
