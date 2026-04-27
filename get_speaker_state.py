import asyncio
import json
import ssl
import time
import uuid
import websockets
import os

TOKENS_FILE = "glagol_tokens.json"

async def get_speaker_status(device_id):
    with open(TOKENS_FILE, "r", encoding="utf-8") as f:
        tokens = json.load(f)
    
    device = tokens.get(device_id)
    if not device or not device.get("ip"):
        print("Ошибка: Колонка не найдена.")
        return

    print(f"Подключение к '{device['name']}' ({device['ip']})...")
    
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    try:
        # Используем asyncio.wait_for для таймаута подключения
        ws = await asyncio.wait_for(
            websockets.connect(f"wss://{device['ip']}:1961", ssl=ssl_context),
            timeout=5
        )
        async with ws:
            # Сначала отправляем "пустую" команду или просто авторизуемся, 
            # чтобы колонка прислала статус в ответ.
            # На самом деле, достаточно просто отправить валидный токен в любом сообщении.
            auth_payload = {
                "conversationToken": device["glagol_token"],
                "id": str(uuid.uuid4()),
                "sentTime": int(round(time.time() * 1000)),
                "payload": {"command": "ping"} # Просто пинг для пробуждения
            }
            await ws.send(json.dumps(auth_payload))
            
            # Ждем первое сообщение со статусом (обычно прилетает мгновенно)
            while True:
                response = await ws.recv()
                data = json.loads(response)
                
                if "state" in data:
                    state = data["state"]
                    print("\n--- ТЕКУЩЕЕ СОСТОЯНИЕ ---")
                    
                    # Громкость
                    vol = state.get("volume", 0)
                    print(f"Громкость: {int(vol * 100)}%")
                    
                    # Плеер
                    playing = state.get("playing", False)
                    print(f"Статус плеера: {'Играет' if playing else 'На паузе'}")
                    
                    # Что играет
                    player_state = state.get("playerState", {})
                    extra = player_state.get("extra", {})
                    
                    # Сначала ищем в корне playerState (для Моей волны и Радио)
                    title = player_state.get("title")
                    artist = player_state.get("subtitle")
                    
                    # Если там пусто, ищем в extra (для обычных треков)
                    if not title:
                        title = extra.get("title")
                        artist = extra.get("artist")
                    
                    if title:
                        artist_str = f"{artist} - " if artist else ""
                        print(f"Сейчас играет: {artist_str}{title}")
                        
                        # Обложка
                        cover_url = extra.get("coverURI")
                        if cover_url:
                            # Заменяем %% на размер, например 400x400
                            full_cover_url = "https://" + cover_url.replace("%%", "400x400")
                            print(f"Обложка: {full_cover_url}")
                    elif playing:
                        print("Сейчас играет: [Аудиопоток без метаданных]")
                    else:
                        print("Сейчас играет: [Ничего]")
                        
                    # Состояние Алисы
                    alice = state.get("aliceState", "UNKNOWN")
                    print(f"Состояние Алисы: {alice}")
                    print("-------------------------\n")
                    break
    except Exception as e:
        print(f"[-] Ошибка получения статуса: {e}")

async def main():
    if not os.path.exists(TOKENS_FILE):
        print("Сначала запусти yandex_setup_full.py")
        return

    with open(TOKENS_FILE, "r", encoding="utf-8") as f:
        tokens = json.load(f)
    
    ids = list(tokens.keys())
    print("\nВЫБЕРИ КОЛОНКУ ДЛЯ ОПРОСА:")
    for i, d_id in enumerate(ids):
        print(f"{i+1}. {tokens[d_id]['name']}")
    
    try:
        idx = int(input("\nНомер колонки: ")) - 1
        await get_speaker_status(ids[idx])
    except:
        pass

if __name__ == "__main__":
    asyncio.run(main())
