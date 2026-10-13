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

async def send_glagol_command(device_id, payload_data):
    if not os.path.exists(TOKENS_FILE):
        print(f"[-] Файл {TOKENS_FILE} не найден. Сначала запусти yandex_setup_full.py")
        return False

    with open(TOKENS_FILE, "r", encoding="utf-8") as f:
        tokens = json.load(f)

    device = tokens.get(device_id)
    if not device:
        print("[-] Ошибка: Колонка не найдена в базе.")
        return False

    ip = device.get("ip")
    if not ip:
        print(f"[-] Ошибка: Для колонки '{device['name']}' неизвестен IP.")
        ip_input = input("Введи IP колонки вручную (или Enter для отмены): ").strip()
        if not ip_input:
            return False
        ip = ip_input
        device["ip"] = ip
        tokens[device_id]["ip"] = ip
        with open(TOKENS_FILE, "w", encoding="utf-8") as f:
            json.dump(tokens, f, ensure_ascii=False, indent=2)

    print(f"Отправка команды на '{device['name']}' ({ip})...")

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    try:
        ws = await asyncio.wait_for(
            websockets.connect(f"wss://{ip}:1961", ssl=ssl_context),
            timeout=5
        )
        async with ws:
            full_payload = {
                "conversationToken": device["glagol_token"],
                "id": str(uuid.uuid4()),
                "sentTime": int(round(time.time() * 1000)),
                "payload": payload_data
            }
            await ws.send(json.dumps(full_payload))
            print("  [+] Команда успешно отправлена!")
            await asyncio.sleep(0.5)
            return True
    except Exception as e:
        print(f"  [-] Ошибка отправки: {e}")
        return False

async def main():
    if not os.path.exists(TOKENS_FILE):
        print(f"[-] Файл {TOKENS_FILE} не найден. Сначала запусти yandex_setup_full.py")
        return

    with open(TOKENS_FILE, "r", encoding="utf-8") as f:
        tokens = json.load(f)

    # Отображаем только аппаратные колонки
    speaker_keys = [
        k for k, v in tokens.items()
        if not v.get("platform", "").startswith(("iot_app", "weather_"))
    ]
    if not speaker_keys:
        speaker_keys = list(tokens.keys())

    print("\nВЫБЕРИ КОЛОНКУ:")
    for i, d_id in enumerate(speaker_keys):
        dev = tokens[d_id]
        ip_str = f" [IP: {dev['ip']}]" if dev.get('ip') else " [IP НЕ НАЙДЕН]"
        print(f"{i+1}. {dev['name']} ({dev.get('platform')}){ip_str}")

    try:
        idx_input = input("\nНомер колонки (Enter - выход): ").strip()
        if not idx_input:
            return
        idx = int(idx_input) - 1
        if not (0 <= idx < len(speaker_keys)):
            print("Неверный номер.")
            return

        target_id = speaker_keys[idx]

        print("\nДЕЙСТВИЕ:")
        print("1. Следующий трек (next)")
        print("2. Предыдущий трек (prev)")
        print("3. Пауза (stop)")
        print("4. Воспроизведение (play)")
        print("5. Громкость (setVolume)")
        print("6. Озвучить текст / команда Алисе (sendText)")

        choice = input("\nВыбор (1-6): ").strip()

        if choice == "1":
            await send_glagol_command(target_id, {"command": "next"})
        elif choice == "2":
            await send_glagol_command(target_id, {"command": "prev"})
        elif choice == "3":
            await send_glagol_command(target_id, {"command": "stop"})
        elif choice == "4":
            await send_glagol_command(target_id, {"command": "play"})
        elif choice == "5":
            vol_str = input("Введи громкость от 0 до 10: ").strip()
            try:
                vol_num = float(vol_str)
                if 0.0 <= vol_num <= 10.0:
                    await send_glagol_command(target_id, {"command": "setVolume", "volume": vol_num / 10.0})
                else:
                    print("Ошибка: Громкость должна быть от 0 до 10.")
            except ValueError:
                print("Некорректное число.")
        elif choice == "6":
            text = input("Введите текст или команду для Алисы: ").strip()
            if text:
                await send_glagol_command(target_id, {"command": "sendText", "text": text})
        else:
            print("Неверный выбор.")
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(main())
