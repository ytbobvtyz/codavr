from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import json
import os
from dotenv import load_dotenv
import httpx
import asyncio
import math
from typing import Dict, Any, Optional

load_dotenv()

YANDEX_API_KEY = os.getenv("YANDEX_MAPS_API_KEY", "")

app = FastAPI(title="Yandex Maps MCP HTTP Server")

async def _call_yandex_geocode(geocode_query: str) -> Optional[Dict]:
    """Helper for Yandex Geocode API"""
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

async def geocode_address(address: str) -> str:
    """Преобразует адрес в координаты"""
    geo = await _call_yandex_geocode(address)
    if not geo:
        return f"❌ Адрес не найден: {address}"
    coordinates = geo["Point"]["pos"].split()
    lon, lat = coordinates[0], coordinates[1]
    full_address = geo["metaDataProperty"]["GeocoderMetaData"]["text"]
    
    return f"""📍 **Результат геокодирования:**
Адрес: {full_address}
Широта: {lat}
Долгота: {lon}"""

async def reverse_geocode(lat: float, lon: float) -> str:
    """Преобразует координаты в адрес"""
    geo = await _call_yandex_geocode(f"{lon},{lat}")
    if not geo:
        return f"❌ Координаты не найдены: {lat}, {lon}"
    address = geo["metaDataProperty"]["GeocoderMetaData"]["text"]
    
    return f"""📍 **Адрес по координатам:**
Координаты: {lat}, {lon}
Адрес: {address}"""

async def calculate_distance_simple(from_address: str, to_address: str) -> str:
    """Рассчитывает расстояние по прямой"""
    geo1 = await _call_yandex_geocode(from_address)
    geo2 = await _call_yandex_geocode(to_address)
    
    if not geo1 or not geo2:
        return "❌ Не удалось определить координаты одного из городов"
    
    coords1 = geo1["Point"]["pos"].split()
    coords2 = geo2["Point"]["pos"].split()
    lon1, lat1 = float(coords1[0]), float(coords1[1])
    lon2, lat2 = float(coords2[0]), float(coords2[1])
    
    # Haversine
    R = 6371
    lat1_r, lon1_r = math.radians(lat1), math.radians(lon1)
    lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)
    
    dlat, dlon = lat2_r - lat1_r, lon2_r - lon1_r
    a = math.sin(dlat / 2)**2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    
    return f"""🗺️ **Расстояние между городами (по прямой):**

📍 {from_address} → 📍 {to_address}

📏 Расстояние по прямой: {distance:.1f} км

⚠️ Это по прямой. По дорогам больше на 20-40%."""

TOOLS = [
    {
        "name": "geocode_address",
        "description": "Адрес в координаты (широта, долгота).",
        "inputSchema": {
            "type": "object",
            "properties": {"address": {"type": "string"}},
            "required": ["address"]
        }
    },
    {
        "name": "reverse_geocode",
        "description": "Координаты в адрес.",
        "inputSchema": {
            "type": "object",
            "properties": {"lat": {"type": "number"}, "lon": {"type": "number"}},
            "required": ["lat", "lon"]
        }
    },
    {
        "name": "calculate_distance_simple",
        "description": "Расстояние между городами по прямой.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_address": {"type": "string"},
                "to_address": {"type": "string"}
            },
            "required": ["from_address", "to_address"]
        }
    }
]

TOOL_MAP = {
    "geocode_address": geocode_address,
    "reverse_geocode": reverse_geocode,
    "calculate_distance_simple": calculate_distance_simple
}

@app.on_event("startup")
async def startup():
    if not YANDEX_API_KEY:
        print("⚠️ YANDEX_MAPS_API_KEY not set in .env")

@app.post("/mcp")
async def mcp_endpoint(request: Request):
    try:
        body = await request.body()
        body_json = json.loads(body)
        method = body_json.get("method")
        params = body_json.get("params", {})
        req_id = body_json.get("id", 1)

        if method == "initialize":
            return JSONResponse({
                "jsonrpc": "2.0",
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}}
                },
                "id": req_id
            })

        elif method == "tools/list":
            return JSONResponse({
                "jsonrpc": "2.0",
                "result": {"tools": TOOLS},
                "id": req_id
            })

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            print(f"🔍 HTTP MCP: Calling tool {tool_name} with {arguments}")

            if tool_name not in TOOL_MAP:
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "error": {"code": -32601, "message": f"Tool '{tool_name}' not found"},
                    "id": req_id
                }, status_code=400)

            try:
                tool_func = TOOL_MAP[tool_name]
                result = await tool_func(**arguments)
                print(f"🔍 HTTP MCP: Tool {tool_name} result: {result[:100]}...")
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "result": {
                        "content": [{"type": "text", "text": str(result)}]
                    },
                    "id": req_id
                })
            except Exception as e:
                print(f"🔍 HTTP MCP: Tool {tool_name} error: {e}")
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "error": {"code": -32603, "message": str(e)},
                    "id": req_id
                }, status_code=500)

        else:
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": "Method not implemented"},
                "id": req_id
            }, status_code=400)

    except json.JSONDecodeError:
        return JSONResponse({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Invalid JSON"}}, status_code=400)
    except Exception as e:
        print(f"🔍 HTTP MCP: General error: {e}")
        return JSONResponse({
            "jsonrpc": "2.0",
            "error": {"code": -32603, "message": str(e)},
            "id": req_id if 'req_id' in locals() else 1
        }, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)