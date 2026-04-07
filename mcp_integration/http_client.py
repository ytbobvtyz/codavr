# mcp_integration/http_client.py
"""
HTTP/SSE клиент для подключения к удалённым MCP серверам
"""

import httpx
import json
from typing import Dict, Any, List, Optional
import asyncio


class RemoteMCPClient:
    """Клиент для подключения к удалённым MCP серверам через HTTP"""
    
    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip('/')
        self.session_id: Optional[str] = None
        self.tools: Dict[str, Dict] = {}
        self.connected = False
    
    async def connect(self) -> bool:
        """Подключается к удалённому MCP серверу"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Инициализация
                init_response = await client.post(
                    f"{self.server_url}/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {}
                        },
                        "id": 1
                    },
                    headers={"Content-Type": "application/json"}
                )
                
                if init_response.status_code != 200:
                    print(f"Init failed: {init_response.status_code}")
                    return False
                
                # Сохраняем session-id если есть
                if 'mcp-session-id' in init_response.headers:
                    self.session_id = init_response.headers['mcp-session-id']
                
                # Получаем список инструментов
                tools_response = await client.post(
                    f"{self.server_url}/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "method": "tools/list",
                        "id": 2
                    },
                    headers={
                        "Content-Type": "application/json",
                        "mcp-session-id": self.session_id if self.session_id else ""
                    }
                )
                
                if tools_response.status_code == 200:
                    result = tools_response.json()
                    if "result" in result and "tools" in result["result"]:
                        for tool in result["result"]["tools"]:
                            self.tools[tool["name"]] = {
                                "name": tool["name"],
                                "description": tool.get("description", "Нет описания"),
                                "input_schema": tool.get("inputSchema", {})
                            }
                    self.connected = True
                    return True
                
                return False
                
        except Exception as e:
            print(f"Connection error: {e}")
            return False
    
    def get_tools_list(self) -> List[Dict]:
        """Возвращает список инструментов"""
        return list(self.tools.values())
    
    def get_tools_info_text(self) -> str:
        """Возвращает информацию об инструментах в виде текста"""
        if not self.tools:
            return "Нет доступных инструментов"
        
        lines = [f"📦 MCP Server: {self.server_url}", "-" * 40]
        for name, info in self.tools.items():
            lines.append(f"🔧 {name}")
            lines.append(f"   {info['description'][:100]}")
        return "\n".join(lines)