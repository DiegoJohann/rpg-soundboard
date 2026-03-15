import os
import json

CONFIG_PATH = os.path.expanduser("~/.rpg_soundboard_config.json")


def load_config():
    """
        Estrutura do config resultante (exemplo):
        {
          "trilhas_dir": "",
          "efeitos_dir": "",
          "default_volume": 80,
          "hotkeys": {
             "Ctrl+1": "/caminho/critico.wav"
          },
          "favorites": ["/caminho/foo.mp3"]
        }
        """
    default = {
        "trilhas_dir": "",
        "efeitos_dir": "",
        "default_volume": 80,
        "favorites": [],
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            default.update(data)
        except Exception:
            pass
    return default


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass
