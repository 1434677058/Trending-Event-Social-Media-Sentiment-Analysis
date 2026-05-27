import json
import os


CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
CONFIG_PATH = os.path.join(CONFIG_DIR, 'crawler_config.json')


def _load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_config(config):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_bilibili_cookie():
    return str(_load_config().get('bilibili_cookie') or '').strip()


def get_platform_cookie(platform):
    return get_bilibili_cookie()


def set_bilibili_cookie(cookie):
    cookie = str(cookie or '').strip()
    config = _load_config()
    if cookie:
        config['bilibili_cookie'] = cookie
    else:
        config.pop('bilibili_cookie', None)
    _save_config(config)


def set_platform_cookie(platform, cookie):
    set_bilibili_cookie(cookie)


def clear_bilibili_cookie():
    config = _load_config()
    config.pop('bilibili_cookie', None)
    _save_config(config)


def clear_platform_cookie(platform):
    clear_bilibili_cookie()


def get_cookie_status(platform='bilibili'):
    cookie = get_platform_cookie(platform)
    if not cookie:
        return {
            'configured': False,
            'preview': '',
            'length': 0,
            'platform': platform,
        }

    return {
        'configured': True,
        'preview': _mask_cookie(cookie),
        'length': len(cookie),
        'platform': platform,
    }


def _mask_cookie(cookie):
    visible = cookie[:16]
    return f'{visible}...' if len(cookie) > len(visible) else visible
