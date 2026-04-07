# mcp_integration/client.py
"""
MCP Клиент для подключения к локальным и удалённым серверам.
"""

import asyncio
import json
from typing import Dict, List, Any, Optional
from contextlib import AsyncExitStack

# Правильный импорт из установленного пакета mcp
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClient:
    """
    Клиент для подключения к MCP серверам через stdio (локальные процессы).
    """
    
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.tools: Dict[str, Dict] = {}
        self.server_name: str = ""
    
    async def connect(self, server_script_path: str, server_name: str = "unknown") -> bool:
        """
        Подключается к локальному MCP серверу через stdio.
        """
        self.server_name = server_name
        
        try:
            server_params = StdioServerParameters(
                command="python",
                args=[server_script_path],
                env=None
            )
            
            # Создаём клиентское подключение
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            stdio, write = stdio_transport
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(stdio, write)
            )
            
            # Инициализируем сессию
            await self.session.initialize()
            
            # Получаем список доступных инструментов
            tools_result = await self.session.list_tools()
            
            # Сохраняем инструменты
            self.tools = {}
            for tool in tools_result.tools:
                self.tools[tool.name] = {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema if hasattr(tool, 'inputSchema') else {}
                }
            
            print(f"✅ Connected to MCP server: {server_name}")
            print(f"📦 Tools: {list(self.tools.keys())}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to connect to {server_name}: {e}")
            return False
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """Возвращает список доступных инструментов"""
        return list(self.tools.values())
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Вызывает инструмент на MCP сервере."""
        if not self.session:
            raise RuntimeError(f"Not connected to MCP server: {self.server_name}")
        
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found. Available: {list(self.tools.keys())}")
        
        result = await self.session.call_tool(tool_name, arguments=arguments)
        
        # Извлекаем текст из результата
        if result.content:
            return result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])
        return None
    
    async def get_tools_info(self) -> str:
        """Возвращает информацию о всех инструментах в виде строки"""
        if not self.tools:
            return "No tools available"
        
        lines = [f"📦 MCP Server: {self.server_name}", "-" * 30]
        for name, info in self.tools.items():
            lines.append(f"🔧 {name}")
            lines.append(f"   {info['description'][:80]}...")
        return "\n".join(lines)
    
    async def cleanup(self):
        """Закрывает соединение"""
        await self.exit_stack.aclose()
        print(f"🔌 Disconnected from MCP server: {self.server_name}")