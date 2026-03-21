<div align="center">
  <h1>🐯 MeowMal Multi-Checker 🐯</h1>
  <p>
    <b>Advanced Microsoft & Minecraft Account Checker</b>
  </p>
  <p>
    <a href="https://t.me/meowleak">
      <img src="https://img.shields.io/badge/Telegram-Join%20Channel-blue?style=for-the-badge&logo=telegram" alt="Telegram">
    </a>
  </p>
  <p>
    <img src="https://img.shields.io/badge/Python-3.8+-yellow?style=flat-square&logo=python" alt="Python">
    <img src="https://img.shields.io/github/license/meowmal/checker?style=flat-square" alt="License">
  </p>
</div>

---

## ⚡ Features

MeowMal Checker is a powerful, multi-threaded tool designed to validate and capture details from Microsoft and Minecraft accounts.

### 🎮 **Minecraft Checking**
- **Hypixel Stats**: Rank, Level, Bedwars Stars, Skyblock Coins, First/Last Login.
- **Cosmetics**: Checks for Optifine Capes and Minecraft Capes (Migration, Minecon, etc.).
- **Bans**: Checks Hypixel ban status and duration.
- **NFA/SFA/FA**: Distinguishes between Non-Full Access, Semi-Full Access, and Full Access.
- **Donut SMP**: Checks access to Donut SMP.

### 💻 **Microsoft / Xbox Checking**
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

---

## 🚀 Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Ver3xl/MeowMal-Checker.git
   cd MeowMal-Checker
   ```

2. **Install dependencies:**
   Make sure you have Python installed. Then run:
   ```bash
   pip install -r requirements.txt
   ```

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

4. **Run:**
   ```bash
   python meow.py
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
- `Hits.txt`: Valid accounts.
- `Capture.txt`: Detailed capture information (Ranks, Coins, Bans, etc.).
- `Banned.txt`: Accounts banned on Hypixel.

---

## ⚠️ Disclaimer

This tool is for **educational purposes only**. The developer is not responsible for any misuse of this software. Please use it only on accounts you own or have explicit permission to test.

---

<div align="center">
  <p>Made with ❤️ by <b>MeowMal Dev's</b></p>
</div>
