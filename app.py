# app.py
import streamlit as st
import asyncio
import os
from agent import CodeAssistant
from memory.persistence import PersistenceManager
from mcp_integration.manager import MCPManager

st.set_page_config(page_title="CODAVR BETA", layout="wide")

# Инициализация менеджера сессий
if "persistence" not in st.session_state:
    st.session_state.persistence = PersistenceManager()

# Функция для переключения сессии
def switch_session(session_id: str):
    st.session_state.current_session_id = session_id
    st.session_state.assistant = CodeAssistant(
        session_id=session_id,
        profile_id=st.session_state.assistant.get_current_profile_id()
    )
    st.session_state.messages = []
    
    profile_id = st.session_state.assistant.get_current_profile_id()
    saved_messages = st.session_state.assistant.persistence.load_conversation(
        session_id=session_id,
        profile_id=profile_id
    )
    for msg in saved_messages:
        if msg is None:
            continue
        st.session_state.messages.append({
            "role": msg.get("role", "unknown"),
            "content": msg.get("content") or ""
        })
    st.rerun()
    
def load_sessions_for_profile(profile_id: str):
    """Загружает только сессии текущего профиля"""
    return st.session_state.persistence.list_sessions(
        profile_id=profile_id,
        limit=20
    )
def create_new_session():
    profile_id = st.session_state.assistant.get_current_profile_id()
    new_id = st.session_state.persistence.create_session(
        "New conversation",
        profile_id=profile_id
    )
    switch_session(new_id)

def delete_session(session_id: str):
    if session_id == st.session_state.current_session_id:
        st.warning("Cannot delete current session. Switch to another first.")
        return
    
    profile_id = st.session_state.assistant.get_current_profile_id()
    st.session_state.persistence.delete_session(session_id, profile_id=profile_id)
    st.rerun()

# В sidebar, при загрузке списка сессий:
    # Список всех сессий ТОЛЬКО для текущего профиля
    profile_id = st.session_state.assistant.get_current_profile_id()
    sessions = st.session_state.persistence.list_sessions(
        profile_id=profile_id,
        limit=20
    )
# Инициализация текущей сессии
if "current_session_id" not in st.session_state:
    # Пытаемся загрузить последнюю сессию
    sessions = st.session_state.persistence.list_sessions(limit=1)
    if sessions:
        st.session_state.current_session_id = sessions[0]["session_id"]
    else:
        st.session_state.current_session_id = st.session_state.persistence.create_session("New conversation")
    
    st.session_state.assistant = CodeAssistant(session_id=st.session_state.current_session_id)
    st.session_state.messages = []
    
    saved_messages = st.session_state.assistant.persistence.load_conversation(
        session_id=st.session_state.current_session_id
    )
    for msg in saved_messages:
        if msg is None:
            continue
        st.session_state.messages.append({
            "role": msg.get("role", "unknown"),
            "content": msg.get("content") or ""
        })

# ===== SIDEBAR =====
with st.sidebar:
    # ===== СЕССИИ =====
    st.title("💬 Conversations")
    
    # Кнопка новой сессии
    if st.button("➕ New Conversation", use_container_width=True):
        create_new_session()
    
    st.divider()
    
    # Список всех сессий
    profile_id = st.session_state.assistant.get_current_profile_id()
    sessions = load_sessions_for_profile(profile_id)
    
    for sess in sessions:
        col1, col2 = st.columns([4, 1])
        with col1:
            # Форматируем дату
            created = sess["created_at"][:16] if sess["created_at"] else "unknown"
            # Показываем первые 5 слов первого сообщения
            preview = sess["first_preview"] or "Empty conversation"
            preview_short = preview[:50] + "..." if len(preview) > 50 else preview
            
            # Подсветка активной сессии
            if sess["session_id"] == st.session_state.current_session_id:
                st.markdown(f"**→ {preview_short}**")
                st.caption(f"📅 {created} | {sess['message_count']} msgs")
            else:
                st.markdown(f"📄 {preview_short}")
                st.caption(f"📅 {created}")
        
        with col2:
            if st.button("🗑️", key=f"del_{sess['session_id']}"):
                delete_session(sess["session_id"])
        
        if st.button("Open", key=f"open_{sess['session_id']}", use_container_width=True):
            switch_session(sess["session_id"])
        
        st.divider()
    
    st.divider()
    
    # ===== ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ =====
    st.title("👤 Profile")
    
    # Получаем текущий профиль
    profiles = st.session_state.assistant.list_profiles()
    active_profile_id = st.session_state.assistant.get_current_profile_id()
    
    # Отображаем текущий профиль
    active_profile = next((p for p in profiles if p["id"] == active_profile_id), None)
    if active_profile:
        if active_profile["is_custom"]:
            st.info(f"**Active:** {active_profile['name']} (custom)")
        else:
            st.info(f"**Active:** {active_profile['name']}")
    
    # Управление профилями
    with st.expander("📋 Manage Profiles", expanded=False):
        for profile in profiles:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                if profile["id"] == active_profile_id:
                    st.markdown(f"**→ {profile['name']}**")
                else:
                    st.write(profile["name"])
                st.caption(profile["description"][:50] if profile["description"] else "")
            
            with col2:
                if profile["id"] != active_profile_id:
                    if st.button("Switch", key=f"switch_{profile['id']}"):
                        st.session_state.assistant.switch_profile(profile["id"])
                        
                        # Загружаем сессии нового профиля
                        new_profile_id = profile["id"]
                        sessions = st.session_state.persistence.list_sessions(
                            profile_id=new_profile_id,
                            limit=1
                        )
                        
                        if sessions:
                            switch_session(sessions[0]["session_id"])
                        else:
                            new_session_id = st.session_state.persistence.create_session(
                                "New conversation",
                                profile_id=new_profile_id
                            )
                            switch_session(new_session_id)
                        
                        st.rerun()
            
            with col3:
                if profile["is_custom"] and profile["id"] != active_profile_id:
                    if st.button("🗑️", key=f"del_{profile['id']}"):
                        st.session_state.assistant.profile_manager.delete_profile(profile["id"])
                        st.rerun()
            
            # Кнопка редактирования для активного пользовательского профиля
            if profile["id"] == active_profile_id and profile["is_custom"]:
                with st.popover("✏️ Edit Profile"):
                    current = st.session_state.assistant.profile_manager.get_profile_content(active_profile_id)
                    
                    new_style = st.text_area(
                        "Style (communication, code preferences)",
                        value=current.get("style.md", ""),
                        height=200
                    )
                    new_constraints = st.text_area(
                        "Constraints (tech stack, limitations)",
                        value=current.get("constraint.md", ""),
                        height=150
                    )
                    new_context = st.text_area(
                        "Context (project, role, goals)",
                        value=current.get("context.md", ""),
                        height=150
                    )
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Save Changes"):
                            st.session_state.assistant.profile_manager.update_profile(
                                active_profile_id,
                                style=new_style,
                                constraints=new_constraints,
                                context=new_context
                            )
                            st.success("Profile updated!")
                            st.rerun()
                    
                    with col2:
                        if st.button("Reset to Default"):
                            st.session_state.assistant.profile_manager.reset_to_default(active_profile_id)
                            st.success("Reset to default!")
                            st.rerun()
            
            st.divider()
    
    # Создание нового профиля
    with st.expander("✨ Create New Profile", expanded=False):
        new_id = st.text_input("Profile ID (lowercase, no spaces)", key="new_profile_id")
        new_name = st.text_input("Display Name", key="new_profile_name")
        
        default_content = st.session_state.assistant.profile_manager._get_default_content()
        
        edit_mode = st.checkbox("Edit before creating")
        
        if edit_mode:
            new_style = st.text_area("Style", value=default_content.get("style.md", ""), height=150)
            new_constraints = st.text_area("Constraints", value=default_content.get("constraint.md", ""), height=150)
            new_context = st.text_area("Context", value=default_content.get("context.md", ""), height=150)
        else:
            new_style = default_content.get("style.md", "")
            new_constraints = default_content.get("constraint.md", "")
            new_context = default_content.get("context.md", "")
        
        if st.button("Create Profile"):
            if new_id and new_name:
                success = st.session_state.assistant.profile_manager.create_profile(
                    new_id, new_name,
                    style=new_style,
                    constraints=new_constraints,
                    context=new_context
                )
                if success:
                    st.success(f"Profile '{new_name}' created!")
                    st.rerun()
                else:
                    st.error("Profile ID already exists")
            else:
                st.error("Profile ID and Name are required")
    
    st.divider()

  # ===== ВЫБОР MCP =====
    st.divider()
    st.title("🔌 MCP Connections")

    # Инициализация в session_state
    if "mcp_local_client" not in st.session_state:
        st.session_state.mcp_local_client = None
        st.session_state.mcp_local_tools = []
        st.session_state.mcp_local_connected = False
    
    if "mcp_remote_tools" not in st.session_state:
        st.session_state.mcp_remote_tools = []
        st.session_state.mcp_remote_connected = False
        st.session_state.mcp_remote_url = ""

    # Вкладки для разных типов подключений
    tab_local, tab_remote = st.tabs(["💻 Local MCP Server (stdio)", "🌐 Remote MCP Server (HTTP)"])

    # ========== ЛОКАЛЬНЫЙ СЕРВЕР ==========
    with tab_local:
        st.markdown("### Подключение к локальному MCP серверу")
        
        server_path = st.text_input(
            "Путь к скрипту сервера",
            value="mcp_integration/servers/echo_server.py",
            help="Укажи полный путь к Python файлу с MCP сервером"
        )
        
        server_name = st.text_input("Имя сервера", value="Echo Server")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔌 Подключить локальный сервер", key="connect_local_btn"):
                if not os.path.exists(server_path):
                    st.error(f"❌ Файл не найден: {server_path}")
                else:
                    with st.spinner(f"Подключение к {server_path}..."):
                        try:
                            import asyncio
                            from mcp_integration.client import MCPClient
                            
                            async def connect_local():
                                client = MCPClient()
                                success = await client.connect(server_path, server_name)
                                return client, success
                            
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            client, success = loop.run_until_complete(connect_local())
                            loop.close()
                            
                            if success:
                                st.session_state.mcp_local_client = client
                                st.session_state.mcp_local_tools = list(client.tools.values())
                                st.session_state.mcp_local_connected = True
                                st.success(f"✅ Подключено к {server_name}")
                                st.rerun()
                            else:
                                st.error("❌ Не удалось подключиться")
                        except Exception as e:
                            st.error(f"❌ Ошибка: {e}")
        
        with col2:
            if st.session_state.mcp_local_connected and st.button("🔌 Отключить локальный сервер", key="disconnect_local_btn"):
                async def disconnect_local():
                    if st.session_state.mcp_local_client:
                        await st.session_state.mcp_local_client.cleanup()
                
                try:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(disconnect_local())
                    loop.close()
                except:
                    pass
                
                st.session_state.mcp_local_client = None
                st.session_state.mcp_local_tools = []
                st.session_state.mcp_local_connected = False
                st.success("🔌 Отключено")
                st.rerun()
        
        # Отображение статуса и инструментов локального сервера
        if st.session_state.mcp_local_connected:
            st.success(f"✅ **Статус:** Подключено к {server_name}")
            
            tools = st.session_state.mcp_local_tools
            if tools:
                st.markdown(f"### 🔧 Доступные инструменты ({len(tools)})")
                for tool in tools:
                    with st.expander(f"🔧 {tool['name']}"):
                        st.markdown(f"**Описание:** {tool.get('description', 'Нет описания')}")
                        if tool.get('input_schema'):
                            st.markdown("**Параметры:**")
                            st.json(tool['input_schema'])
            else:
                st.warning("Нет доступных инструментов")
        else:
            st.info("⚪ Не подключено. Нажми 'Подключить локальный сервер'")

    # ========== УДАЛЁННЫЙ СЕРВЕР ==========
    with tab_remote:
        st.markdown("### Подключение к удалённому MCP серверу")
        
        # Предустановленные тестовые серверы
        test_servers = {
            "Выбрать из списка": "",
            "Anthropic Test Server": "https://example-server.modelcontextprotocol.io/mcp",
            "MCP Echo Server": "https://mcp-echo-server.fly.dev/mcp",
        }
        
        selected_preset = st.selectbox(
            "Выбери тестовый сервер или введи свой URL",
            list(test_servers.keys())
        )
        
        if selected_preset != "Выбрать из списка":
            remote_url = test_servers[selected_preset]
            st.info(f"📡 URL: {remote_url}")
        else:
            remote_url = st.text_input(
                "Введите URL MCP сервера",
                placeholder="https://example.com/mcp",
                help="URL должен заканчиваться на /mcp или быть корневым эндпоинтом"
            )
        
        remote_name = st.text_input("Отображаемое имя", value="Remote MCP Server")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🌐 Подключить удалённый сервер", key="connect_remote_btn"):
                if not remote_url:
                    st.warning("Введите URL сервера")
                else:
                    with st.spinner(f"Подключение к {remote_url}..."):
                        try:
                            import httpx
                            import asyncio
                            
                            async def test_remote_connection():
                                async with httpx.AsyncClient(timeout=30.0) as client:
                                    # Инициализация
                                    init_resp = await client.post(
                                        remote_url,
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
                                    
                                    if init_resp.status_code != 200:
                                        return None, f"Init failed: {init_resp.status_code}"
                                    
                                    # Получаем инструменты
                                    tools_resp = await client.post(
                                        remote_url,
                                        json={"jsonrpc": "2.0", "method": "tools/list", "id": 2},
                                        headers={"Content-Type": "application/json"}
                                    )
                                    
                                    if tools_resp.status_code == 200:
                                        result = tools_resp.json()
                                        if "result" in result and "tools" in result["result"]:
                                            return result["result"]["tools"], None
                                        return None, "Invalid response format"
                                    return None, f"Tools request failed: {tools_resp.status_code}"
                            
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            tools, error = loop.run_until_complete(test_remote_connection())
                            loop.close()
                            
                            if tools is not None:
                                st.session_state.mcp_remote_tools = tools
                                st.session_state.mcp_remote_connected = True
                                st.session_state.mcp_remote_url = remote_url
                                st.success(f"✅ Подключено к {remote_url}")
                                st.rerun()
                            else:
                                st.error(f"❌ Ошибка: {error}")
                        except Exception as e:
                            st.error(f"❌ Ошибка подключения: {e}")
        
        with col2:
            if st.session_state.mcp_remote_connected and st.button("🔌 Отключить удалённый сервер", key="disconnect_remote_btn"):
                st.session_state.mcp_remote_tools = []
                st.session_state.mcp_remote_connected = False
                st.session_state.mcp_remote_url = ""
                st.success("🔌 Отключено")
                st.rerun()
        
        # Отображение статуса и инструментов удалённого сервера
        if st.session_state.mcp_remote_connected:
            st.success(f"✅ **Статус:** Подключено к {st.session_state.mcp_remote_url}")
            st.info(f"📡 **Сервер:** {remote_name}")
            
            tools = st.session_state.mcp_remote_tools
            if tools:
                st.markdown(f"### 🔧 Доступные инструменты ({len(tools)})")
                for tool in tools:
                    with st.expander(f"🔧 {tool.get('name', 'Unknown')}"):
                        st.markdown(f"**Описание:** {tool.get('description', 'Нет описания')}")
                        if tool.get('inputSchema'):
                            st.markdown("**Параметры:**")
                            st.json(tool['inputSchema'])
            else:
                st.warning("Нет доступных инструментов")
        else:
            st.info("⚪ Не подключено. Введи URL и нажми 'Подключить удалённый сервер'")
    
    # Показываем все активные инструменты в одном месте
    all_tools_count = len(st.session_state.mcp_local_tools) + len(st.session_state.mcp_remote_tools)
    if all_tools_count > 0:
        with st.expander(f"📦 Все активные инструменты ({all_tools_count})", expanded=False):
            if st.session_state.mcp_local_tools:
                st.markdown("**💻 Локальный сервер:**")
                for tool in st.session_state.mcp_local_tools:
                    st.caption(f"• {tool['name']} - {tool.get('description', '')[:60]}")
            
            if st.session_state.mcp_remote_tools:
                st.markdown("**🌐 Удалённый сервер:**")
                for tool in st.session_state.mcp_remote_tools:
                    st.caption(f"• {tool.get('name', 'unknown')} - {tool.get('description', '')[:60]}")
                
    # ===== КРАТКОСРОЧНАЯ ПАМЯТЬ =====
    with st.expander("📝 Short-Term Memory", expanded=True):
        assistant = st.session_state.assistant
        
        summary = assistant.short_term.summary
        if summary:
            st.markdown("**📋 Summary of earlier conversation:**")
            st.info(summary[:300] + "..." if len(summary) > 300 else summary)
        else:
            st.caption("No summary yet (need more than 5 messages)")
        
        st.markdown(f"**💬 Last {min(5, assistant.short_term.total_messages)} messages:**")
        recent = assistant.short_term.get_recent_window()
        if recent:
            for msg in recent[-5:]:
                if msg is None:
                    continue
                role_icon = "👤" if msg.get("role") == "user" else "🤖"
                content = msg.get("content") or ""
                preview = content[:100] + "..." if len(content) > 100 else content
                st.caption(f"{role_icon} **{msg.get('role', 'unknown')}:** {preview}")
        else:
            st.caption("No messages yet")
        
        st.markdown(f"*Total messages in session: {assistant.short_term.total_messages}*")
    
    # ===== РАБОЧАЯ ПАМЯТЬ =====
    with st.expander("⚙️ Working Memory", expanded=True):
        working = assistant.working
        task = working.task  # TaskContext объект
        
        # Цель задачи
        if task.goal:
            st.markdown(f"**🎯 Goal:** {task.goal}")
        else:
            st.caption("No active goal")
        
        # Состояние Task State Machine
        st.markdown("**🔄 Task State:**")
        state_icons = {"planning": "📋", "execution": "⚙️", "validation": "🔍", "done": "✅"}
        state_icon = state_icons.get(task.state.value, "📌")
        st.markdown(f"{state_icon} **{task.state.value.upper()}**")
        
        # Текущий и следующий шаг
        if task.current_step:
            st.markdown(f"**📍 Current step:** {task.current_step}")
        
        if task.next_step:
            st.markdown(f"**➡️ Next step:** {task.next_step}")
        
        # Ожидание от пользователя
        if task.expected_from_user:
            st.info(f"⏳ Expected: {task.expected_from_user}")
        
        # Подзадачи (subtasks)
        if task.subtasks:
            st.markdown("**✅ Subtasks:**")
            for subtask in task.subtasks:
                icon = "✅" if subtask["status"] == "done" else "🔄" if subtask["status"] == "in_progress" else "⏳"
                st.text(f"{icon} {subtask['name']} ({subtask['status']})")
        
        # Файлы
        if working.files:
            st.markdown("**📁 Files:**")
            for f in working.files:
                st.code(f, language="python")
        
        # Блокеры
        if working.blockers:
            st.warning(f"⚠️ Blockers: {', '.join(working.blockers)}")
        
        # Кнопки управления
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Reset Working Memory"):
                assistant.reset_working_memory()
                st.rerun()
        with col2:
            if st.button("🗑️ Clear Short-term"):
                assistant.clear_short_term()
                st.rerun()
        
        # Дополнительная информация (опционально)
        with st.expander("📊 Task Progress", expanded=False):
            # Прогресс по подзадачам
            if task.subtasks:
                done_count = sum(1 for t in task.subtasks if t["status"] == "done")
                total_count = len(task.subtasks)
                st.progress(done_count / total_count if total_count > 0 else 0)
                st.caption(f"Progress: {done_count}/{total_count} subtasks completed")
            
            # История переходов
            if task.transitions:
                st.markdown("**Transition History:**")
                for t in task.transitions[-5:]:  # последние 5
                    st.caption(f"  {t['from']} → {t['to']} ({t['timestamp'][:16]})")

    # ===== ДОЛГОВРЕМЕННАЯ ПАМЯТЬ =====
    with st.expander("💾 Long-Term Memory", expanded=False):
        memory_types = ["user_preference", "code_pattern", "arch_decision", "lesson_learned"]
        for mem_type in memory_types:
            entries = assistant.long_term.get_by_type(mem_type, limit=2)
            if entries:
                with st.expander(f"{mem_type.replace('_', ' ').title()} ({len(entries)})"):
                    for e in entries:
                        st.text(f"• {e.content[:150]}...")
                        st.caption(f"  importance: {e.importance} | tags: {', '.join(e.tags)}")
        
        # Тестовое сохранение
        st.divider()
        st.markdown("**Test Save to Long-Term Memory**")
        test_save = st.text_input("Content:", key="test_memory_content")
        test_type = st.selectbox("Type:", memory_types, key="test_memory_type")
        if st.button("Save Test Entry") and test_save:
            assistant.long_term.save_simple(test_save, test_type, importance=3)
            st.success(f"Saved: {test_save[:50]}...")
            st.rerun()
    
    # ===== ОТЛАДКА =====
    with st.expander("🐛 Debug Info", expanded=False):
        st.json({
            "session_id": st.session_state.current_session_id,
            "working_memory": assistant.working.to_dict(),
            "short_term_total": assistant.short_term.total_messages,
            "short_term_window": assistant.short_term.window_size,
            "has_summary": bool(assistant.short_term.summary),
            "active_profile": active_profile_id
        })
        
        if st.button("Force Rerun"):
            st.rerun()

# ===== ОСНОВНАЯ ОБЛАСТЬ =====
st.title("🤖 Code Assistant with Memory")
st.caption(f"Model: {st.session_state.assistant.main_model} | Session: {st.session_state.current_session_id[:8]}... | Profile: {active_profile_id}")

# Чат
for msg in st.session_state.messages:
    if msg is None:
        continue
    role = msg.get("role", "unknown")
    content = msg.get("content") or ""
    with st.chat_message(role):
        st.markdown(content)

if prompt := st.chat_input("Что нужно сделать в проекте?"):
    # Проверяем, первое ли это сообщение
    if len(st.session_state.messages) == 0:
        # Обновляем название сессии
        words = prompt.strip().split()[:5]
        title = " ".join(words)
        if len(title) > 50:
            title = title[:47] + "..."
        
        st.session_state.persistence.update_session_info(
            st.session_state.current_session_id,
            title=title,
            first_preview=prompt[:100]
        )
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        with st.spinner("Думаю..."):
            response = st.session_state.assistant.ask(prompt)
            st.markdown(response)
    
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()