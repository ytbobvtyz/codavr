# test_geocode.py
import httpx
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("YANDEX_MAPS_API_KEY")

async def test_geocode():
    url = "https://geocode-maps.yandex.ru/1.x/"
    params = {
        "apikey": API_KEY,
        "geocode": "Москва, Красная площадь",
        "format": "json",
        "results": 1
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            try:
                geo = data["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]
                coords = geo["Point"]["pos"].split()
                print(f"✅ Координаты: {coords[1]}, {coords[0]}")
                print(f"📍 Адрес: {geo['metaDataProperty']['GeocoderMetaData']['text']}")
            except:
                print("❌ Не удалось распарсить ответ")
        else:
            print(f"❌ Ошибка: {response.text[:200]}")

asyncio.run(test_geocode())