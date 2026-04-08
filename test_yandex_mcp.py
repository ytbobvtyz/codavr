#!/usr/bin/env python3
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from mcp_integration.client import MCPClient


async def test_yandex_mcp():
    print("\n" + "="*60)
    print("🧪 ТЕСТ MCP СЕРВЕРА ЯНДЕКС.КАРТЫ")
    print("="*60)
    
    client = MCPClient()
    server_path = "mcp_integration/servers/yandex_maps_server.py"
    
    success = await client.connect(server_path, "Yandex Maps")
    if not success:
        print("❌ Не удалось подключиться")
        return
    
    print("\n✅ Сервер подключен!")
    
    print("\n" + "="*60)
    print("🎯 ТЕСТ 1: geocode_address")
    print("="*60)
    result = await client.call_tool("geocode_address", {"address": "Москва, Красная площадь"})
    print(result)
    
    print("\n" + "="*60)
    print("🎯 ТЕСТ 2: reverse_geocode")
    print("="*60)
    result = await client.call_tool("reverse_geocode", {"lat": 55.753544, "lon": 37.621202})
    print(result)
    
    print("\n" + "="*60)
    print("🎯 ТЕСТ 3: calculate_distance_simple")
    print("="*60)
    result = await client.call_tool("calculate_distance_simple", {
        "from_address": "Москва",
        "to_address": "Пермь"
    })
    print(result)
    
    await client.cleanup()
    print("\n✅ Тестирование завершено!")


if __name__ == "__main__":
    asyncio.run(test_yandex_mcp())