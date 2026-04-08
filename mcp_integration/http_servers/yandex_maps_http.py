from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import json
import asyncio
import os
from dotenv import load_dotenv
from typing import Dict, Any

# Импорт tools из stdio сервера (adjust relative path if needed: from ..servers.yandex_maps_server import)
load_dotenv()
try:
    from ..servers.yandex_maps_server import (
        geocode_address, reverse_geocode, calculate_distance_simple
    )
except ImportError:
    # Fallback if path issue - define stubs or print error
    print("⚠️ Cannot import tools from yandex_maps_server.py - ensure file exists")

app = FastAPI(title="Yandex Maps MCP HTTP Server")

# MCP tools metadata
TOOLS = [
    {
        "name": "geocode_address",
        "description": "Преобразует адрес в координаты (широта, долгота).",
        "inputSchema": {
            "type": "object",
            "properties": {"address": {"type": "string", "description": "Адрес для геокодирования"}},
            "required": ["address"]
        }
    },
    {
        "name": "reverse_geocode",
        "description": "Преобразует координаты в адрес.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lat": {"type": "number", "description": "Широта"},
                "lon": {"type": "number", "description": "Долгота"}
            },
            "required": ["lat", "lon"]
        }
    },
    {
        "name": "calculate_distance_simple",
        "description": "Рассчитывает приблизительное расстояние между городами (по прямой).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_address": {"type": "string", "description": "Адрес/город отправления"},
                "to_address": {"type": "string", "description": "Адрес/город назначения"}
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
async def startup_event():
    if not os.getenv("YANDEX_MAPS_API_KEY"):
        print("⚠️ YANDEX_MAPS_API_KEY не найден в .env - tools не будут работать")

@app.post("/mcp")
async def mcp_endpoint(request: Request):
    try:
        body = await request.body()
        body_json = json.loads(body)
        method = body_json.get("method")
        params = body_json.get("params", {})
        req_id = body_json.get("id")

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

            if tool_name not in TOOL_MAP:
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "error": {"code": -32601, "message": f"Tool '{tool_name}' not found"},
                    "id": req_id
                }, status_code=400)

            # Проверяем импорт
            if tool_name not in globals():
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "error": {"code": -32603, "message": "Tool import failed"},
                    "id": req_id
                }, status_code=500)

            try:
                tool_func = globals()[tool_name]  # since imported
                result = await tool_func(**arguments)
            except Exception as e:
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "error": {"code": -32603, "message": str(e)},
                    "id": req_id
                }, status_code=500)

            return JSONResponse({
                "jsonrpc": "2.0",
                "result": {
                    "content": [{"type": "text", "text": result}]
                },
                "id": req_id
            })

        else:
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method '{method}' not implemented"},
                "id": req_id
            }, status_code=400)

    except json.JSONDecodeError:
        return JSONResponse({
            "jsonrpc": "2.0",
            "error": {"code": -32700, "message": "Invalid JSON"},
            "id": None
        }, status_code=400)
    except Exception as e:
        return JSONResponse({
            "jsonrpc": "2.0",
            "error": {"code": -32603, "message": str(e)},
            "id": req_id if 'req_id' in locals() else None
        }, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)