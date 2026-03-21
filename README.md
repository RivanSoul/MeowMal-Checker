# 🎥 Crunchyroll Account Checker

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)


A high-performance, multi-threaded Crunchyroll account checker with proxy support (HTTP/Socks4/Socks5), detailed capture (Plan, Renewal, Payment, Country), and both Windows & Linux support.

## ✨ Features

- 🚀 **Multi-threaded**: Fast checking with configurable thread count.
- 🛡️ **Proxy Support**: Supports HTTP, Socks4, and Socks5 proxies.
- 🌍 **Country Detection**: accurately fetches the subscription country.
- 📝 **Detailed Capture**:
  - Plan (Fan, Mega Fan, Ultimate Fan)
  - Auto-Renew Status
  - Free Trial Status
  - Payment Method
  - Expiry Date
- 🐧 **Cross-Platform**: dedicated scripts for Windows (`main.py`) and Linux (`Main_Linux.py`).
- 📊 **Hit Counter**: Live and summary hit statistics.

## 🛠️ Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Ver3xl/Crunchyroll-Checker.git
   cd crunchyroll-checker
   ```

2. **Install dependencies:**
   ```bash
   pip install requests
   pip install pysocks # Required for Socks4/5 support
   ```

## ⚙️ Configuration

Edit `config.ini` to set your preferences:

```ini
[Settings]
threads = 100            # Number of threads to use
proxy_type = http        # Default proxy type: http, socks4, or socks5
```

- **threads**: Higher values are faster but require better proxies and CPU.
- **proxy_type**: The protocol to use if your proxies in `proxy.txt` are just `ip:port` or `ip:port:user:pass`.
    - If your proxies already have `socks5://` prefix, the script will detect it automatically.

## 🚀 Usage

1. **Add Accounts**: Place your combos in `accounts.txt` (Format: `email:password`).
2. **Add Proxies**: Place your proxies in `proxy.txt`.
3. **Run the script**:

   **Windows:**
   ```bash
   python main.py
   ```

   **Linux:**
   ```bash
   python3 Main_Linux.py
   ```

## 📂 Output

Hits are saved to `capture.txt` in the following pipe-separated format:
```text
email:pass | Country = US | Plan = Mega Fan Plan | Auto-Renew = true | Free-Trial = false | Payment-Methode = itunes | Expiry-Date = 2026-07-31 |
```

Valid logins are also saved to `hits.txt` (only `email:pass`).

## ⚠️ Disclaimer

This tool is for **educational purposes only**. The developer is not responsible for any misuse. Do not use this tool on accounts you do not own.

---

Made with ❤️ by MeowMal Dev's
