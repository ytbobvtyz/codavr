# app2.py
import streamlit as st
import asyncio
import os
from dotenv import load_dotenv
from mcp_integration.manager import MCPManager

load_dotenv()

st.set_page_config(page_title="MCP Geolocation Test", layout="wide")
st.title("🗺️ Тест MCP Геолокации (Yandex API)")

# Инициализация MCP Manager
if "mcp_manager" not in st.session_state:
    st.session_state.mcp_manager = MCPManager()
    st.session_state.connected = False
    st.session_state.url = "http://localhost:8000/mcp"

# UI для подключения
st.header("🔌 Подключение к MCP Серверу")
col1, col2 = st.columns(2)

with col1:
    url = st.text_input("URL сервера", value=st.session_state.url, key="mcp_url")

with col2:
    if st.button("Подключить Yandex MCP"):
        with st.spinner("Подключение..."):
            success = asyncio.run(st.session_state.mcp_manager.connect_remote('yandex', url, 'Yandex Maps'))
            if success:
                st.session_state.connected = True
                st.session_state.url = url
                st.success("✅ Подключено к Yandex MCP!")
                st.rerun()
            else:
                st.error("❌ Ошибка подключения. Проверьте сервер и API ключ в .env")
                st.session_state.connected = False

if st.session_state.connected:
    st.success("✅ Сервер подключён. Доступны tools: geocode_address, reverse_geocode, calculate_distance_simple")

    # Disconnect button
    if st.button("🔌 Отключить"):
        asyncio.run(st.session_state.mcp_manager.disconnect('yandex'))
        st.session_state.connected = False
        st.success("🔌 Отключено")
        st.rerun()

    st.divider()

    # Тесты
    st.header("🧪 Тесты Tools")

    tab1, tab2, tab3 = st.tabs(["Геокодирование (Адрес → Координаты)", "Обратное Геокодирование", "Расстояние между Городами"])

    with tab1:
        address = st.text_input("Адрес:", value="Москва, Красная площадь", key="geocode_addr")
        if st.button("📍 Геокодировать") and st.session_state.connected:
            with st.spinner("Запрос к API..."):
                try:
                    result = asyncio.run(st.session_state.mcp_manager.call_tool('yandex', "geocode_address", {"address": address}))
                    st.markdown("**Результат:**")
                    st.success(result)
                except Exception as e:
                    st.error(f"❌ Ошибка: {e}")

    with tab2:
        lat = st.number_input("Широта (lat):", value=55.7558, key="rev_lat")
        lon = st.number_input("Долгота (lon):", value=37.6176, key="rev_lon")
        if st.button("🔄 Обратное Геокодирование") and st.session_state.connected:
            with st.spinner("Запрос к API..."):
                try:
                    result = asyncio.run(st.session_state.mcp_manager.call_tool('yandex', "reverse_geocode", {"lat": lat, "lon": lon}))
                    st.markdown("**Результат:**")
                    st.success(result)
                except Exception as e:
                    st.error(f"❌ Ошибка: {e}")

    with tab3:
        from_city = st.text_input("От города:", value="Москва", key="dist_from")
        to_city = st.text_input("До города:", value="Санкт-Петербург", key="dist_to")
        if st.button("🗺️ Рассчитать Расстояние") and st.session_state.connected:
            with st.spinner("Запрос к API..."):
                try:
                    result = asyncio.run(st.session_state.mcp_manager.call_tool('yandex', "calculate_distance_simple", {"from_address": from_city, "to_address": to_city}))
                    st.markdown("**Результат:**")
                    st.info(result)
                except Exception as e:
                    st.error(f"❌ Ошибка: {e}")

else:
    st.warning("⚠️ Подключитесь к серверу для тестов. Убедитесь, что HTTP MCP сервер запущен на указанном URL (например, uvicorn mcp_integration.http_servers.yandex_maps_http:app --port 8000).")
    st.info("Также проверьте .env: YANDEX_MAPS_API_KEY=ваш_ключ_от_яндекса.")

st.divider()
st.caption("Этот упрощённый app тестирует только MCP подключение и Yandex tools. Без агента и памяти.")