from vkbottle import Bot
import dotenv
import os
import logging
import datetime
import aiohttp

logging.basicConfig(level=logging.INFO)

messages_data = {}
weather_data = {}

def main():
    dotenv.load_dotenv()
    
    vk_token = os.getenv('VK_API_KEY')
    mistral_key = os.getenv('MISTRAL_API_KEY')
    
    client = Bot(token=vk_token)

    async def get_weather(city):
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=ru&format=json"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(geo_url) as geo_resp:
                if geo_resp.status != 200:
                    return {"success": False, "error": "Город не найден"}
                
                geo_data = await geo_resp.json()
                if not geo_data.get('results'):
                    return {"success": False, "error": "Город не найден"}
                
                lat = geo_data['results'][0]['latitude']
                lon = geo_data['results'][0]['longitude']
                city_name = geo_data['results'][0]['name']
                
                weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&timezone=auto"
                
                async with session.get(weather_url) as weather_resp:
                    if weather_resp.status != 200:
                        return {"success": False, "error": "Ошибка погоды"}
                    
                    weather_data_raw = await weather_resp.json()
                    current = weather_data_raw.get('current_weather', {})
                    
                    return {
                        "success": True,
                        "city": city_name,
                        "temp": current.get('temperature', 'Нет'),
                        "wind": current.get('windspeed', 'Нет')
                    }

    async def ask_mistral(user_id, question):
        history = []
        if user_id in messages_data and messages_data[user_id]:
            for msg, _ in messages_data[user_id][-10:]:
                history.append({"role":"user", "content":msg})
        history.append({"role":"user", "content":question})
        
        weather = ""
        if user_id in weather_data and weather_data[user_id]:
            w = weather_data[user_id]
            weather = f"Погода в {w['city']}: {w['temp']} градусов, ветер {w['wind']} м/с. "
        
        prompt = f"""{weather}
Ты стилист. Отвечай как живой человек. Без приветствий, без звездочек, без маркированных списков. Просто совет. Если ты предполагаешь, что температура или скорость ветер может быть разными выбирай только одно - наименьшее значение"""
        
        url = "https://api.mistral.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {mistral_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "mistral-small-latest",
            "messages": [
                {"role": "system", "content": prompt},
                *history
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    answer = result["choices"][0]["message"]["content"]
                    answer = answer.replace('*', '').replace('#', '').replace('-', '')
                    return answer
                return "Что-то сломалось, попробуй еще раз"

    @client.on.private_message(text="Начать")
    async def start(message):
        user_id = message.from_id
        messages_data[user_id] = []
        await message.answer("Привет! Напиши город, и я подскажу что надеть.")

    @client.on.private_message(text="Очистка")
    async def clear(message):
        user_id = message.from_id
        messages_data[user_id] = []
        weather_data[user_id] = None
        await message.answer("Диалог очищен. Напиши город и начнем заново.")
        

    @client.on.private_message()    
    async def handle(message):
        user_id = message.from_id
        text = message.text.strip()
        
        if user_id not in messages_data:
            messages_data[user_id] = []
        
        if text.lower() == "очистка" or text.lower() == "начать":
            return
        
        messages_data[user_id].append((text, datetime.datetime.now().timestamp()))

        if user_id not in weather_data or not weather_data[user_id]:
            await message.answer(f"Смотрю погоду в {text}...")
            weather = await get_weather(text)
            
            if weather["success"]:
                weather_data[user_id] = weather
                await message.answer(f"В {weather['city']} сейчас {weather['temp']} градусов, ветер {weather['wind']} м/с.")
                answer = await ask_mistral(user_id, text)
                await message.answer(answer)
            else:
                await message.answer("Не нашел такой город. Попробуй Москва, Париж, Лондон.")
        else:
            answer = await ask_mistral(user_id, text)
            await message.answer(answer)

    print("Бот запущен")
    client.run_forever()

if __name__ == "__main__":
    main()
        
