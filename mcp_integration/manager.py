# mcp_integration/manager.py
"""
Менеджер MCP подключений для управления несколькими серверами.
"""

import asyncio
from typing import Dict, List, Any, Optional
from mcp_integration.client import MCPClient


class MCPManager:
    """
    Управляет несколькими MCP подключениями (локальные и удалённые серверы).
    """
    
    def __init__(self):
        self.connections: Dict[str, Dict] = {}  # server_id -> {client, tools, status}
    
    async def connect_local(self, server_id: str, script_path: str, name: str = None) -> bool:
        """
        Подключает локальный MCP сервер.
        """
        if server_id in self.connections:
            print(f"⚠️ Server {server_id} already connected")
            return False
        
        client = MCPClient()
        success = await client.connect(script_path, name or server_id)
        
        if success:
            self.connections[server_id] = {
                "client": client,
                "tools": client.tools,
                "status": "connected",
                "name": name or server_id,
                "type": "local"
            }
            print(f"✅ Server '{server_id}' connected with {len(client.tools)} tools")
        
        return success
    
    async def disconnect(self, server_id: str) -> bool:
        """Отключает сервер"""
        if server_id not in self.connections:
            return False
        
        conn = self.connections[server_id]
        await conn["client"].cleanup()
        del self.connections[server_id]
        print(f"🔌 Server '{server_id}' disconnected")
        return True
    
    def get_connection_status(self, server_id: str) -> Optional[str]:
        """Возвращает статус подключения"""
        if server_id in self.connections:
            return self.connections[server_id]["status"]
        return None
    
    def get_all_tools(self) -> List[Dict]:
        """Собирает все инструменты со всех подключённых серверов"""
        all_tools = []
        for server_id, conn in self.connections.items():
            for tool_name, tool_info in conn["tools"].items():
                all_tools.append({
                    "server_id": server_id,
                    "server_name": conn["name"],
                    "tool_name": tool_name,
                    "description": tool_info.get("description", ""),
                    "input_schema": tool_info.get("input_schema", {})
                })
        return all_tools
    
    def get_connections_info(self) -> List[Dict]:
        """Возвращает информацию о всех подключениях для UI"""
        return [
            {
                "id": server_id,
                "name": conn["name"],
                "status": conn["status"],
                "type": conn["type"],
                "tools_count": len(conn["tools"])
            }
            for server_id, conn in self.connections.items()
        ]
    
    async def call_tool(self, server_id: str, tool_name: str, arguments: Dict) -> Any:
        """Вызывает инструмент на указанном сервере"""
        if server_id not in self.connections:
            raise ValueError(f"Server '{server_id}' not connected")
        
        conn = self.connections[server_id]
        return await conn["client"].call_tool(tool_name, arguments)
    
    async def cleanup_all(self):
        """Отключает все серверы"""
        for server_id in list(self.connections.keys()):
            await self.disconnect(server_id)

    async def connect_remote(self, server_id: str, url: str, name: str = None) -> bool:
        """
        Подключается к удалённому MCP серверу через HTTP
        """
        from mcp_integration.http_client import RemoteMCPClient
        
        if server_id in self.connections:
            print(f"⚠️ Server {server_id} already connected")
            return False
        
        client = RemoteMCPClient(url)
        success = await client.connect()
        
        if success:
            self.connections[server_id] = {
                "client": client,
                "tools": client.tools,
                "status": "connected",
                "name": name or server_id,
                "type": "remote",
                "url": url
            }
            print(f"✅ Remote server '{server_id}' connected with {len(client.tools)} tools")
        
        return success