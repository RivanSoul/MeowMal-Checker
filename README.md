<div align="center">
  <h1>🐯 MeowMal Multi-Checker 🐯</h1>
  <p>
    <b>Advanced Microsoft & Minecraft Account Checker</b>
  </p>
  <p>
    <a href="https://t.me/meowleak">
      <img src="https://img.shields.io/badge/Telegram-Join%20Channel-blue?style=for-the-badge&logo=telegram" alt="Telegram">
    </a>
    <a href="https://discord.gg/D3FG34BFjS">
      <img src="https://img.shields.io/badge/Discord-Join%20Server-7289da?style=for-the-badge&logo=discord&logoColor=white" alt="Discord">
    </a>
  </p>
  <p>
    <img src="https://img.shields.io/badge/Python-3.8+-yellow?style=flat-square&logo=python" alt="Python">
    <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20Termux-blue?style=flat-square" alt="Platform">
    <img src="https://img.shields.io/github/license/meowmal/checker?style=flat-square" alt="License">
  </p>
</div>

---

**MeowMal Patch Update — Version 1.2**

• Fixed low hit rate *(depends on combo quality)*
• No more skipping valid emails
• Fixed “No Name Set” capture issue
• Added auto-payment support for DonutSMP
• Fixed InboxSearcher
• Increased overall speed
• Multiple bugs and issues resolved

Need cheap cloud with better hit rates?
Use **MeowPrivate Cloud** — low cost, 30+ hits possible.

## ⚡ Features

MeowMal Checker is a powerful, multi-threaded tool designed to validate and capture details from Microsoft and Minecraft accounts.

### 🎮 **Minecraft Checking**
- **Hypixel Stats**: Rank, Level, Bedwars Stars, Skyblock Coins, First/Last Login.
- **Cosmetics**: Checks for Optifine Capes and Minecraft Capes (Migration, Minecon, etc.).
- **Bans**: Checks Hypixel ban status and duration.
- **NFA/SFA/FA/MFA**: Distinguishes between Non-Full Access, Semi-Full Access, Full Access, and Mail Full Access.
- **Donut SMP**: Checks access to Donut SMP with auto-payment verification support.
- **Namechange Status**: Accurately reports if an account's name is changeable (or "NoMC" if no name is set).

### 💻 **Microsoft / Xbox Checking**
- **Inbox Searcher**: Scans the Outlook/Hotmail inbox for custom keywords (e.g., Steam, Discord, Netflix).
- **GamePass**: Detects active GamePass Ultimate/PC subscriptions.
- **Payment Methods**: Lists linked credit cards (masked) and billing details.
- **Balance**: Checks Microsoft account balance.
- **Rewards**: Checks Bing/Microsoft Rewards points.

### ⚙️ **Core Features**
- **Multi-threaded**: Blazing fast checking with configurable thread count.
- **Proxy Support**: Supports HTTP, SOCKS4, and SOCKS5 proxies (User:Pass or IP:Port and more).
- **Discord Webhook**: Sends beautiful, customizable embeds for hits directly to your Discord server.
- **Retry Logic**: Robust handling of network errors and ratelimits with auto-retry.
- **Configurable**: extensive `config.ini` to tweak every aspect of the checker.
- **Cross-Platform**: Runs on Windows (`meow.py`) and Linux / Termux / Android (`meow_LINUX.py`).

---

## 🚀 Installation

### 🪟 Windows

1. **Clone the repository:**
   ```bash
   git clone https://github.com/RivanSoul/MeowMal-Checker.git
   cd MeowMal-Checker
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

---

### 🐧 Linux / 📱 Termux (Android)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/RivanSoul/MeowMal-Checker.git
   cd MeowMal-Checker
   ```

2. **Install dependencies (Linux-safe — no `readchar`, no `pyCraft` build):**

   > **If you get `externally-managed-environment` error**, create a virtual environment first:
   > ```bash
   > python3 -m venv .venv && source .venv/bin/activate
   > ```

   ```bash
   pip install -r requirements_linux.txt
   ```

> ⚠️ **Termux users:** `pyCraft` (Hypixel ban checking) requires Rust to compile and will fail on Termux/Android. It is disabled by default in `requirements_linux.txt`. All other features work normally.

---

## 🛠️ Usage

1. **Add Combos:**
   Place your `email:password` combos in a text file (e.g., `combo.txt`).

2. **Add Proxies:**
   - Create a `proxies.txt` file in the root directory.
   - Add your proxies (one per line).
   - Supported formats: `ip:port` or `user:pass@ip:port` or `ip:port:user:pass`.

3. **Configure:**
   Edit `config.ini` to set up your preferences (threads, webhook, timeout, etc.).

4. **Run — Windows:**
   ```bash
   python meow.py
   ```

5. **Run — Linux / Termux:**
   ```bash
   python3 meow_LINUX.py
   ```

---

## ⚙️ Configuration (`config.ini`)

| Setting | Description |
| :--- | :--- |
| `threads` | Number of concurrent threads (Higher = Faster, requires good CPU/Proxies). |
| `discord_webhook_url` | Your Discord Webhook URL for hit notifications. |
| `use_proxies` | Set to `True` to enable proxy usage. |
| `check_hypixel_rank` | Enable/Disable Hypixel rank checking. |
| `check_gamepass` | Enable/Disable Xbox GamePass checking. |

*(See standard `config.ini` for full list of options)*

---

## 📊 Output

Results are saved in the `results/` folder, organized by date and time:
- `Hits.txt` / `Capture.txt`: Detailed capture information (Ranks, Coins, Bans, etc.).
- `Valid_Mail.txt`: Valid Microsoft accounts that do not own Minecraft.
- `MFA.txt` & `SFA.txt`: Accounts with successful IMAP email access (MFA) and those without (SFA).
- `Namechangeable.txt`: Full captures of accounts that are eligible for a Minecraft name change.
- `Unbanned.txt`: Full captures of accounts that are not banned on Hypixel.
- `Banned.txt`: Full captures of accounts that are banned on Hypixel.
- `Cards.txt`: Accounts that have a linked payment method (Visa, Mastercard, Amex, Discover).
- `donut_stats.txt`: Detailed Donut SMP server statistics (Rank, Balance, Tokens, Tags, Keys, PVs).
- `2fa.txt`: Accounts that are locked behind Two-Factor Authentication or require account recovery.

---

## ⚠️ Disclaimer

This tool is for **educational purposes only**. The developer is not responsible for any misuse of this software. Please use it only on accounts you own or have explicit permission to test.

---

<div align="center">
  <p>Made with ❤️ by <b>MeowMal Dev's</b></p>
</div>
