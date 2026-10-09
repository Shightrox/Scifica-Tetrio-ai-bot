"""Small, versioned preferences. No capture regions, account data or armed state."""
import json
import math

ROTATION_KEYS = {'A':0x41, 'C':0x43, 'D':0x44, 'F':0x46, 'Q':0x51, 'E':0x45, 'Off':None}
DEFAULTS = {'key_rate': 30, 'humanization': 0, 'dynamic_tempo': 0, 'use_hold': True, 'swap_rotation': False, 'attack_priority': True, 'rotation_180':'A'}

def bounded(value, low, high, default):
    try:
        value = float(value)
        return max(low, min(high, value)) if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default

def sanitize(data):
    if not isinstance(data, dict): data = {}
    return {
        'key_rate': bounded(data.get('key_rate'), 2, 30, 30),
        'humanization': bounded(data.get('humanization'), 0, 100, 0),
        'dynamic_tempo': bounded(data.get('dynamic_tempo'), 0, 100, 0),
        'use_hold': data.get('use_hold') if isinstance(data.get('use_hold'), bool) else True,
        'swap_rotation': data.get('swap_rotation') if isinstance(data.get('swap_rotation'), bool) else False,
        'attack_priority': data.get('attack_priority') if isinstance(data.get('attack_priority'), bool) else True,
        'rotation_180': data.get('rotation_180') if isinstance(data.get('rotation_180'),str) and data['rotation_180'] in ROTATION_KEYS else 'A',
    }

def load(path):
    try: return sanitize(json.loads(path.read_text(encoding='utf-8')))
    except (OSError, ValueError): return dict(DEFAULTS)

def save(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'version': 1, **sanitize(data)}, indent=2)+'\n', encoding='utf-8')
    temporary.replace(path)
