import asyncio
import json
import ssl
import time
import uuid
import websockets
import os

TOKENS_FILE = "glagol_tokens.json"

async def send_glagol_command(device_id, payload_data):
    with open(TOKENS_FILE, "r", encoding="utf-8") as f:
        tokens = json.load(f)
    
    device = tokens.get(device_id)
    if not device or not device.get("ip"):
        print("Ошибка: Колонка не найдена или не имеет IP.")
        return

    print(f"Отправка команды на '{device['name']}' ({device['ip']})...")
    
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    try:
        async with websockets.connect(f"wss://{device['ip']}:1961", ssl=ssl_context) as ws:
            full_payload = {
                "conversationToken": device["glagol_token"],
                "id": str(uuid.uuid4()),
                "sentTime": int(round(time.time() * 1000)),
                "payload": payload_data
            }
            await ws.send(json.dumps(full_payload))
            print("  [+] Выполнено!")
    except Exception as e:
        print(f"  [-] Ошибка: {e}")

async def main():
    if not os.path.exists(TOKENS_FILE):
        print("Сначала запусти yandex_setup_full.py")
        return

    with open(TOKENS_FILE, "r", encoding="utf-8") as f:
        tokens = json.load(f)
    
    ids = list(tokens.keys())
    print("\nВЫБЕРИ КОЛОНКУ:")
    for i, d_id in enumerate(ids):
        print(f"{i+1}. {tokens[d_id]['name']}")
    
    try:
        idx = int(input("\nНомер колонки: ")) - 1
        target_id = ids[idx]
        
        print("\nДЕЙСТВИЕ:")
        print("1. Следующий трек (next)")
        print("2. Предыдущий трек (prev)")
        print("3. Пауза (stop)")
        print("4. Громкость (setVolume)")
        
        choice = input("Выбор: ")
        
        if choice == "1":
            await send_glagol_command(target_id, {"command": "next"})
        elif choice == "2":
            await send_glagol_command(target_id, {"command": "prev"})
        elif choice == "3":
            await send_glagol_command(target_id, {"command": "stop"})
        elif choice == "4":
            vol = float(input("Введи громкость от 0 до 10: ")) / 10.0
            if 0.0 <= vol <= 1.0:
                await send_glagol_command(target_id, {"command": "setVolume", "volume": vol})
            else:
                print("Ошибка: Громкость должна быть от 0 до 10.")
        else:
            print("Неверный выбор.")
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(main())
