import asyncio
import binascii
import ipaddress
import json
import os
import re
import socket
import ssl
import sys
import time
import uuid
import webbrowser
import requests
import websockets
from zeroconf import ServiceBrowser, Zeroconf

# Поддержка UTF-8 в консоли Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# --- КОНФИГУРАЦИЯ ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_ID = "23cabbbdc6cd418abb4b39c32c41195d"
CLIENT_SECRET = "53bc75238f0c4d08a118e51fe9203300"
TOKENS_FILE = os.path.join(BASE_DIR, "glagol_tokens.json")
AUTH_FILE = os.path.join(BASE_DIR, ".env")
QR_HTML_FILE = os.path.join(BASE_DIR, "yandex_qr.html")
QR_SVG_FILE = os.path.join(BASE_DIR, "yandex_qr.svg")

# Список поддерживаемых аппаратных платформ колонок
KNOWN_SPEAKER_PLATFORMS = {
    "yandexmini", "yandexmini_2", "cucumber", "yandexstation",
    "yandexmicro", "yandexmidi", "yandexmax", "yandexmodule",
    "yandexmodule_2", "light", "station", "station_2"
}

def get_x_token_from_env():
    env_paths = [
        AUTH_FILE,
        os.path.abspath(os.path.join(BASE_DIR, "..", ".env"))
    ]
    for p in env_paths:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("YANDEX_TOKEN="):
                        token = line.strip().split("=", 1)[1].strip()
                        if token:
                            return token
    return None

def qr_login_sync():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    })

    print("\n[1/4] Подготовка сессии авторизации Яндекс...")
    r = session.get("https://passport.yandex.ru/am?app_platform=android", timeout=10)
    m = re.search(r'"csrf_token" value="([^"]+)"', r.text)
    if not m:
        m = re.search(r'window\.__CSRF__\s*=\s*["\']([^"\']+)["\']', r.text)
    if not m:
        print("[-] Ошибка: Не удалось получить CSRF токен.")
        return None
    page_csrf = m.group(1)

    bff_headers = {
        "content-type": "application/json",
        "x-csrf-token": page_csrf,
        "origin": "https://passport.yandex.ru",
        "referer": "https://passport.yandex.ru/am?app_platform=android",
    }

    print("[2/4] Запрос QR-сессии...")
    r_qr = session.post(
        "https://passport.yandex.ru/pwl-yandex/api/passport/auth/password/submit",
        headers=bff_headers,
        json={"retpath": "https://passport.yandex.ru/profile", "with_code": True},
        timeout=10
    )
    if r_qr.status_code != 200:
        print(f"[-] Ошибка запроса QR: {r_qr.status_code} {r_qr.text[:100]}")
        return None

    qr_resp = r_qr.json()
    track_id = qr_resp.get("track_id")
    polling_csrf = qr_resp.get("csrf_token", page_csrf)
    if not track_id:
        print(f"[-] Ошибка: track_id не получен: {qr_resp}")
        return None

    # Получаем оригинальный SVG QR-код от Яндекс
    qr_url = f"https://passport.yandex.ru/auth/magic/code/?track_id={track_id}"
    r_svg = session.get(qr_url, timeout=10)
    
    if r_svg.status_code == 200 and "<svg" in r_svg.text:
        svg_content = r_svg.text
        # Сохраняем SVG файл
        with open(QR_SVG_FILE, "w", encoding="utf-8") as f:
            f.write(svg_content)

        # Формируем красивую HTML-страницу с QR-кодом
        html_page = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Вход в Яндекс — QR-код</title>
<style>
  body {{
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f0f2f5;
    color: #1a1a1a;
  }}
  .card {{
    background: #ffffff;
    padding: 36px 40px;
    border-radius: 20px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.08);
    text-align: center;
    max-width: 380px;
  }}
  h2 {{ margin: 0 0 10px 0; font-size: 22px; font-weight: 700; }}
  p {{ margin: 0 0 24px 0; font-size: 14px; color: #666; line-height: 1.4; }}
  .qr-box {{
    background: #ffffff;
    padding: 16px;
    border-radius: 14px;
    display: inline-block;
    border: 1px solid #e5e7eb;
  }}
  svg {{ display: block; width: 260px; height: 260px; }}
  .hint {{ margin-top: 20px; font-size: 12px; color: #999; }}
</style>
</head>
<body>
<div class="card">
  <h2>Авторизация Яндекс</h2>
  <p>Отсканируйте этот QR-код в приложении Яндекс, Алиса или камерой телефона</p>
  <div class="qr-box">
    {svg_content}
  </div>
  <div class="hint">Сессия действует 5 минут</div>
</div>
</body>
</html>"""
        with open(QR_HTML_FILE, "w", encoding="utf-8") as f:
            f.write(html_page)

        print(f"[+] QR-код сохранён в: {QR_HTML_FILE}")
        
        # Автоматически открываем страницу в браузере
        try:
            if sys.platform == "win32":
                os.startfile(QR_HTML_FILE)
            else:
                webbrowser.open(f"file:///{os.path.abspath(QR_HTML_FILE)}")
            print("[+] Страница с QR-кодом автоматически открыта в браузере!")
        except Exception:
            try:
                webbrowser.open(f"file:///{os.path.abspath(QR_HTML_FILE)}")
            except Exception:
                pass

    print("\n" + "=" * 65)
    print("ОТСКАНИРУЙ QR-КОД В ПРИЛОЖЕНИИ ЯНДЕКС (АЛИСА / КАМЕРА):")
    print(f"Файл QR-кода: {QR_HTML_FILE}")
    print(f"Прямая ссылка: {qr_url}")
    print("=" * 65 + "\n")
    print("Ожидание подтверждения (до 5 минут)...", flush=True)

    start_time = time.time()
    while time.time() - start_time < 300:
        try:
            status_r = session.post(
                "https://passport.yandex.ru/auth/new/magic/status/",
                data={"csrf_token": polling_csrf, "track_id": track_id},
                timeout=10
            )
            status_resp = status_r.json()
            if status_resp.get("status") == "ok":
                print("\n[!] Подтверждено! Получаем X-Token...")
                cookies_str = "; ".join([f"{k}={v}" for k, v in session.cookies.get_dict().items()])
                token_r = session.post(
                    "https://mobileproxy.passport.yandex.net/1/bundle/oauth/token_by_sessionid",
                    data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
                    headers={"Ya-Client-Host": "passport.yandex.ru", "Ya-Client-Cookie": cookies_str},
                    timeout=10
                )
                x_token = token_r.json().get("access_token")
                if x_token:
                    with open(AUTH_FILE, "w", encoding="utf-8") as f:
                        f.write(f"YANDEX_TOKEN={x_token}\n")
                    print("[+] Успех! Токен получен и сохранен в .env.")
                    # Удаляем временные файлы QR
                    for tmp in [QR_HTML_FILE, QR_SVG_FILE]:
                        if os.path.exists(tmp):
                            try:
                                os.remove(tmp)
                            except Exception:
                                pass
                    return x_token
            elif status_resp.get("status") == "wait":
                print(".", end="", flush=True)
        except Exception:
            pass
        time.sleep(3)
    return None

# --- ЛОГИКА ПОИСКА КОЛОНОК ---
class SpeakerDiscovery:
    def __init__(self):
        self.found_devices = {}

    def remove_service(self, zeroconf, type, name): pass
    def update_service(self, zeroconf, type, name): pass

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info:
            addresses = [str(ipaddress.ip_address(addr)) for addr in info.addresses]
            props = {k.decode(): v.decode() if isinstance(v, bytes) else v for k, v in info.properties.items()}
            device_id = props.get("deviceId")
            if device_id and addresses:
                self.found_devices[device_id] = {
                    "ip": addresses[0],
                    "port": info.port or 1961,
                    "platform": props.get("platform"),
                    "name": name.split(".")[0]
                }

def get_local_subnet():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ".".join(ip.split(".")[:3]) + "."
    except Exception:
        return "192.168.1."

async def scan_local_glagol_ports(subnet_prefix=None):
    """Быстрый fallback поиск устройств с открытым портом Glagol (1961)"""
    if not subnet_prefix:
        subnet_prefix = get_local_subnet()

    async def check_ip(ip):
        try:
            conn = asyncio.open_connection(ip, 1961)
            reader, writer = await asyncio.wait_for(conn, timeout=0.3)
            writer.close()
            await writer.wait_closed()
            return ip
        except Exception:
            return None

    tasks = [check_ip(f"{subnet_prefix}{i}") for i in range(1, 255)]
    results = await asyncio.gather(*tasks)
    return [ip for ip in results if ip]

async def discover_speakers(timeout=6):
    print(f"\n[2/4] Поиск колонок в локальной сети (mDNS + порт 1961, ждем {timeout} сек)...")
    zeroconf = Zeroconf()
    discovery = SpeakerDiscovery()
    browser = ServiceBrowser(zeroconf, "_yandexio._tcp.local.", discovery)
    await asyncio.sleep(timeout)
    zeroconf.close()
    
    found = discovery.found_devices
    print(f"  -> Найдено через mDNS: {len(found)}")
    
    # Скан подсети для поиска колонок, которые не ответили на mDNS
    try:
        active_ips = await scan_local_glagol_ports()
        for ip in active_ips:
            already_known = any(d.get("ip") == ip for d in found.values())
            if not already_known:
                found[f"discovered_{ip}"] = {"ip": ip, "port": 1961}
    except Exception:
        pass

    return found

# --- ЛОГИКА ПОЛУЧЕНИЯ ТОКЕНОВ ---
async def fetch_glagol_tokens(x_token, local_devices):
    print("\n[3/4] Запрос Glagol-токенов у Яндекса...")
    headers = {
        "Authorization": f"OAuth {x_token}",
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        "X-Yandex-Token": x_token
    }

    r = requests.get("https://quasar.yandex.ru/glagol/device_list", headers=headers, timeout=10)
    if r.status_code != 200:
        print(f"Ошибка получения списка (.ru): {r.status_code}. Пробуем .net...")
        r = requests.get("https://quasar.yandex.net/glagol/device_list", headers=headers, timeout=10)

    if r.status_code != 200:
        print(f"[-] Ошибка получения списка устройств Quasar: {r.status_code}")
        return {}

    quasar_list = r.json().get("devices", [])
    results = {}

    for q_dev in quasar_list:
        d_id = q_dev.get("id")
        name = (q_dev.get("name") or "").strip()
        platform = q_dev.get("platform")
        glagol_data = q_dev.get("glagol") or {}

        # Исключаем мобильные приложения и виджеты
        if platform.startswith(("iot_app", "weather_")):
            continue

        is_speaker = (
            platform in KNOWN_SPEAKER_PLATFORMS
            or bool(glagol_data.get("security"))
        )
        if not is_speaker:
            continue

        g_token = q_dev.get("glagol_token")
        if not g_token:
            url_single = f"https://quasar.yandex.ru/glagol/token?device_id={d_id}&platform={platform}"
            try:
                r_single = requests.get(url_single, headers=headers, timeout=5)
                if r_single.status_code == 200:
                    g_token = r_single.json().get("token")
            except Exception:
                pass

        if not g_token:
            continue

        # Сопоставляем IP
        assigned_ip = None
        if d_id in local_devices and local_devices[d_id].get("ip"):
            assigned_ip = local_devices[d_id]["ip"]
        else:
            for k, dev_info in list(local_devices.items()):
                if k.startswith("discovered_") and dev_info.get("ip"):
                    assigned_ip = dev_info["ip"]
                    del local_devices[k]
                    break

        results[d_id] = {
            "name": name,
            "glagol_token": g_token,
            "platform": platform,
            "ip": assigned_ip
        }

        status_str = f"IP: {assigned_ip}" if assigned_ip else "IP не обнаружен (выключена или в другой сети)"
        print(f"  [+] Колонка '{name}' ({platform}) -> {status_str}")

    with open(TOKENS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n[+] Сохранено колонок в {TOKENS_FILE}: {len(results)}")
    return results

# --- ЛОГИКА ТЕСТА ---
async def test_speaker(device_id, device_data):
    ip = device_data.get("ip")
    if not ip:
        print(f"\n[!] Ошибка: Неизвестен IP для колонки '{device_data['name']}'.")
        ip_input = input("Введи IP колонки вручную (или Enter для отмены): ").strip()
        if not ip_input:
            return
        ip = ip_input
        device_data["ip"] = ip
        try:
            with open(TOKENS_FILE, "r", encoding="utf-8") as f:
                cur = json.load(f)
            cur[device_id]["ip"] = ip
            with open(TOKENS_FILE, "w", encoding="utf-8") as f:
                json.dump(cur, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    print(f"\n[4/4] Тестируем колонку '{device_data['name']}' ({ip})...")
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    try:
        async with websockets.connect(f"wss://{ip}:1961", ssl=ssl_context) as ws:
            payload = {
                "conversationToken": device_data["glagol_token"],
                "id": str(uuid.uuid4()),
                "sentTime": int(round(time.time() * 1000)),
                "payload": {
                    "command": "sendText",
                    "text": "скажи локальное управление настроено успешно"
                }
            }
            await ws.send(json.dumps(payload))
            print("  [+] Команда отправлена. Слушай колонку!")
            await asyncio.sleep(2)
    except Exception as e:
        print(f"  [-] Ошибка теста: {e}")

# --- MAIN ---
async def main():
    print("=== YANDEX STATION SETUP TOOL ===")

    x_token = get_x_token_from_env()
    if x_token:
        print(f"[+] Найден сохранённый X-Token в .env: {x_token[:10]}...")
        # Спрашиваем пользователя: использовать текущий или войти заново
        ans = input("Использовать сохранённый токен? ([Д]а / [н]ет, получить новый QR): ").strip().lower()
        if ans in ("н", "n", "no", "нет"):
            x_token = None

    if not x_token:
        x_token = await asyncio.to_thread(qr_login_sync)

    if not x_token:
        print("[-] Ошибка: токен не получен.")
        return

    local_devices = await discover_speakers()
    glagol_data = await fetch_glagol_tokens(x_token, local_devices)

    if not glagol_data:
        print("[-] Не удалось получить данные о колонках.")
        return

    print("\nДОСТУПНЫЕ КОЛОНКИ:")
    ids = list(glagol_data.keys())
    for i, d_id in enumerate(ids):
        d = glagol_data[d_id]
        ip_str = f" [IP: {d['ip']}]" if d.get('ip') else " [IP НЕ НАЙДЕН]"
        print(f"{i+1}. {d['name']} ({d['platform']}){ip_str}")

    try:
        choice = input("\nВыбери номер колонки для теста (Enter - выход): ").strip()
        if choice:
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(ids):
                target_id = ids[choice_idx]
                await test_speaker(target_id, glagol_data[target_id])
    except Exception:
        pass

if __name__ == "__main__":
    asyncio.run(main())
