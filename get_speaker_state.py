import asyncio
import json
import ssl
import time
import uuid
import websockets
import os
import sys

# Поддержка UTF-8 в консоли Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKENS_FILE = os.path.join(BASE_DIR, "glagol_tokens.json")

async def get_speaker_status(device_id):
    if not os.path.exists(TOKENS_FILE):
        print(f"[-] Файл {TOKENS_FILE} не найден. Сначала запусти yandex_setup_full.py")
        return

    with open(TOKENS_FILE, "r", encoding="utf-8") as f:
        tokens = json.load(f)

    device = tokens.get(device_id)
    if not device:
        print("[-] Ошибка: Колонка не найдена в базе.")
        return

    ip = device.get("ip")
    if not ip:
        print(f"[-] Ошибка: Для колонки '{device['name']}' неизвестен IP.")
        ip_input = input("Введи IP колонки вручную (или Enter для отмены): ").strip()
        if not ip_input:
            return
        ip = ip_input
        device["ip"] = ip
        tokens[device_id]["ip"] = ip
        with open(TOKENS_FILE, "w", encoding="utf-8") as f:
            json.dump(tokens, f, ensure_ascii=False, indent=2)

    print(f"Подключение к '{device['name']}' ({ip})...")

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    try:
        ws = await asyncio.wait_for(
            websockets.connect(f"wss://{ip}:1961", ssl=ssl_context),
            timeout=5
        )
        async with ws:
            auth_payload = {
                "conversationToken": device["glagol_token"],
                "id": str(uuid.uuid4()),
                "sentTime": int(round(time.time() * 1000)),
                "payload": {"command": "ping"}
            }
            await ws.send(json.dumps(auth_payload))

            # Ждем сообщение со статусом
            for _ in range(5):
                response = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(response)

                if "state" in data:
                    state = data.get("state") or {}
                    print("\n" + "=" * 25 + " ТЕКУЩЕЕ СОСТОЯНИЕ " + "=" * 25)

                    # Громкость
                    vol = state.get("volume", 0)
                    print(f"Громкость:        {int(vol * 100)}%")

                    # Плеер
                    playing = state.get("playing", False)
                    print(f"Статус плеера:    {'▶ Играет' if playing else '⏸ На паузе / Остановлен'}")

                    # Что играет (безопасное извлечение playerState)
                    player_state = state.get("playerState") or {}
                    extra = player_state.get("extra") or {}

                    title = player_state.get("title")
                    artist = player_state.get("subtitle")

                    if not title:
                        title = extra.get("title")
                        artist = extra.get("artist")

                    if title:
                        artist_str = f"{artist} - " if artist else ""
                        print(f"Сейчас играет:    {artist_str}{title}")

                        # Обложка
                        cover_url = extra.get("coverURI")
                        if cover_url:
                            if not cover_url.startswith("http"):
                                cover_url = "https://" + cover_url
                            full_cover_url = cover_url.replace("%%", "400x400")
                            print(f"Обложка:          {full_cover_url}")
                    elif playing:
                        print("Сейчас играет:    [Аудиопоток без метаданных / Радио]")
                    else:
                        print("Сейчас играет:    [Ничего не воспроизводится]")

                    # Состояние Алисы
                    alice = state.get("aliceState", "IDLE")
                    print(f"Состояние Алисы:  {alice}")
                    print("=" * 69 + "\n")
                    break
    except Exception as e:
        print(f"[-] Ошибка получения статуса: {e}")

async def main():
    if not os.path.exists(TOKENS_FILE):
        print(f"[-] Файл {TOKENS_FILE} не найден. Сначала запусти yandex_setup_full.py")
        return

    with open(TOKENS_FILE, "r", encoding="utf-8") as f:
        tokens = json.load(f)

    # Показываем только аппаратные колонки
    speaker_keys = [
        k for k, v in tokens.items()
        if not v.get("platform", "").startswith(("iot_app", "weather_"))
    ]
    if not speaker_keys:
        speaker_keys = list(tokens.keys())

    print("\nВЫБЕРИ КОЛОНКУ ДЛЯ ОПРОСА СТАТУСА:")
    for i, d_id in enumerate(speaker_keys):
        dev = tokens[d_id]
        ip_str = f" [IP: {dev['ip']}]" if dev.get('ip') else " [IP НЕ НАЙДЕН]"
        print(f"{i+1}. {dev['name']} ({dev.get('platform')}){ip_str}")

    try:
        idx_input = input("\nНомер колонки (Enter - отмена): ").strip()
        if idx_input:
            idx = int(idx_input) - 1
            if 0 <= idx < len(speaker_keys):
                await get_speaker_status(speaker_keys[idx])
    except Exception as e:
        print(f"Ошибка ввода: {e}")

if __name__ == "__main__":
    asyncio.run(main())
