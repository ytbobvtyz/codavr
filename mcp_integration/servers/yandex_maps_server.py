#!/usr/bin/env python3
"""
MCP сервер для Яндекс.Карт API — только работающие методы
"""

import os
import httpx
import math
from typing import Optional
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

YANDEX_API_KEY = os.getenv("YANDEX_MAPS_API_KEY", "")

if not YANDEX_API_KEY:
    print("⚠️ YANDEX_MAPS_API_KEY не найден в .env")

mcp = FastMCP("YandexMapsServer")

async def _call_yandex_geocode(geocode_query: str) -> Optional[dict]:
    """Вспомогательная функция для вызова Yandex Geocode API."""
    if not YANDEX_API_KEY:
        return None

    try:
        url = "https://geocode-maps.yandex.ru/1.x/"
        params = {
            "apikey": YANDEX_API_KEY,
            "geocode": geocode_query,
            "format": "json",
            "results": 1
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)

            if response.status_code != 200:
                return None

            data = response.json()

            if (
                "response" in data
                and "GeoObjectCollection" in data["response"]
                and "featureMember" in data["response"]["GeoObjectCollection"]
                and data["response"]["GeoObjectCollection"]["featureMember"]
            ):
                return data["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]
            return None
    except Exception as e:
        print(f"Geocode API error: {e}")
        return None

@mcp.tool()
async def geocode_address(address: str) -> str:
    """Преобразует адрес в координаты (широта, долгота)."""
    geo = await _call_yandex_geocode(address)
    if not geo:
        return f"❌ Адрес не найден: {address}"
    coordinates = geo["Point"]["pos"].split()
    lon, lat = coordinates[0], coordinates[1]
    full_address = geo["metaDataProperty"]["GeocoderMetaData"]["text"]

    return f"""📍 **Результат геокодирования:**
Адрес: {full_address}
Широта: {lat}
Долгота: {lon}
"""

@mcp.tool()
async def reverse_geocode(lat: float, lon: float) -> str:
    """Преобразует координаты в адрес."""
    geo = await _call_yandex_geocode(f"{lon},{lat}")
    if not geo:
        return f"❌ Координаты не найдены: {lat}, {lon}"
    address = geo["metaDataProperty"]["GeocoderMetaData"]["text"]

    return f"""📍 **Адрес по координатам:**
Координаты: {lat}, {lon}
Адрес: {address}
"""

@mcp.tool()
async def calculate_distance_simple(from_address: str, to_address: str) -> str:
    """Рассчитывает приблизительное расстояние между городами (по прямой)."""
    geo1 = await _call_yandex_geocode(from_address)
    geo2 = await _call_yandex_geocode(to_address)

    if not geo1 or not geo2:
        return "❌ Не удалось определить координаты одного из городов"

    coords1 = geo1["Point"]["pos"].split()
    coords2 = geo2["Point"]["pos"].split()
    lon1, lat1 = float(coords1[0]), float(coords1[1])
    lon2, lat2 = float(coords2[0]), float(coords2[1])

    # Расчет расстояния по формуле Гаверсина
    R = 6371  # Радиус Земли в км

    lat1_r = math.radians(lat1)
    lon1_r = math.radians(lon1)
    lat2_r = math.radians(lat2)
    lon2_r = math.radians(lon2)

    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c

    return f"""🗺️ **Расстояние между городами (по прямой):**

📍 {from_address} → 📍 {to_address}

📏 Расстояние по прямой: {distance:.1f} км

⚠️ Это расстояние по прямой. Реальное расстояние по дорогам может быть больше на 20-40%.
"""

if __name__ == "__main__":
    print("🚀 Запуск MCP сервера Яндекс.Карты (упрощённая версия)")
    print("Доступные инструменты:")
    print("  - geocode_address - адрес → координаты")
    print("  - reverse_geocode - координаты → адрес")
    print("  - calculate_distance_simple - расстояние между городами (по прямой)")
    mcp.run(transport="stdio")