# mcp_integration/client.py
import asyncio
from typing import Dict, List, Any, Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.tools: Dict[str, Dict] = {}
        self.server_name: str = ""
    
    async def connect(self, server_script_path: str, server_name: str = "unknown") -> bool:
        self.server_name = server_name
        
        try:
            server_params = StdioServerParameters(
                command="python3",
                args=[server_script_path],
                env=None
            )
            
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            stdio, write = stdio_transport
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(stdio, write)
            )
            
            await self.session.initialize()
            
            tools_result = await self.session.list_tools()
            
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
            print(f"❌ Failed to connect: {e}")
            return False
    
    async def list_tools(self) -> List[Dict]:
        return list(self.tools.values())
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        if not self.session:
            raise RuntimeError("Not connected")
        
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found")
        
        result = await self.session.call_tool(tool_name, arguments=arguments)
        
        if result.content:
            return result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])
        return None
    
    async def cleanup(self):
        await self.exit_stack.aclose()
        print(f"🔌 Disconnected from MCP server: {self.server_name}")