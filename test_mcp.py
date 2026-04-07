# test_mcp.py
"""
Тестовый скрипт для проверки MCP клиента и сервера.
"""

import asyncio
import sys
import os

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(__file__))

from mcp_integration.manager import MCPManager


async def test_local_server():
    """Тестирует подключение к локальному echo серверу"""
    print("\n" + "="*50)
    print("🧪 TESTING LOCAL MCP SERVER")
    print("="*50)
    
    manager = MCPManager()
    
    # Подключаемся к echo серверу
    server_path = "mcp_integration/servers/echo_server.py"
    
    if not os.path.exists(server_path):
        print(f"❌ Server file not found: {server_path}")
        print("   Please create mcp_integration/servers/echo_server.py first")
        return
    
    success = await manager.connect_local(
        server_id="echo_test",
        script_path=server_path,
        name="Echo Test Server"
    )
    
    if not success:
        print("❌ Failed to connect to echo server")
        return
    
    # Показываем подключения
    print("\n📡 Active connections:")
    for conn in manager.get_connections_info():
        print(f"   - {conn['name']}: {conn['status']} ({conn['tools_count']} tools)")
    
    # Показываем все инструменты
    print("\n🔧 Available tools:")
    for tool in manager.get_all_tools():
        print(f"   - {tool['server_name']} :: {tool['tool_name']}")
        print(f"     {tool['description'][:60]}...")
    
    # Тестируем вызовы инструментов
    print("\n🧪 Testing tool calls:")
    
    # Тест echo
    result = await manager.call_tool("echo_test", "echo", {"message": "Hello MCP!"})
    print(f"   📢 echo('Hello MCP!') → {result}")
    
    # Тест add
    result = await manager.call_tool("echo_test", "add", {"a": 10, "b": 32})
    print(f"   ➕ add(10, 32) → {result}")
    
    # Тест repeat
    result = await manager.call_tool("echo_test", "repeat", {"text": "MCP", "count": 5})
    print(f"   🔁 repeat('MCP', 5) → {result}")
    
    # Тест get_server_info
    result = await manager.call_tool("echo_test", "get_server_info", {})
    print(f"   ℹ️ get_server_info() → {result}")
    
    # Отключаемся
    await manager.cleanup_all()
    print("\n✅ Test completed successfully!")


async def main():
    await test_local_server()


if __name__ == "__main__":
    asyncio.run(main())