# mcp/servers/echo_server.py
"""
Простой MCP сервер для тестирования.
Предоставляет базовые инструменты: echo, add, get_info.
"""

from mcp.server.fastmcp import FastMCP

# Создаём сервер
mcp = FastMCP("EchoTestServer")

@mcp.tool()
def echo(message: str) -> str:
    """Вернуть сообщение обратно с префиксом Echo"""
    return f"Echo: {message}"

@mcp.tool()
def add(a: int, b: int) -> int:
    """Сложить два числа"""
    return a + b

@mcp.tool()
def get_server_info() -> str:
    """Получить информацию о сервере"""
    return "Echo Test Server v1.0 - доступные инструменты: echo, add, get_server_info"

@mcp.tool()
def repeat(text: str, count: int = 3) -> str:
    """Повторить текст указанное количество раз"""
    return (text + " ") * count

if __name__ == "__main__":
    # Запуск через stdio (для локального подключения)
    mcp.run(transport="stdio")