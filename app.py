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

    # Инициализация MCP менеджера в session_state
    if "mcp_manager" not in st.session_state:
        st.session_state.mcp_manager = MCPManager()
        st.session_state.mcp_connections_initialized = False

    # Функция для инициализации подключений
    async def init_mcp_connections():
        if not st.session_state.mcp_connections_initialized:
            # Подключаем локальный echo сервер (исправленный путь)
            echo_server_path = "mcp_integration/servers/echo_server.py"
            if os.path.exists(echo_server_path):
                await st.session_state.mcp_manager.connect_local(
                    server_id="echo_server",
                    script_path=echo_server_path,
                    name="Echo Test Server"
                )
            st.session_state.mcp_connections_initialized = True

    # Запускаем инициализацию (в фоне)
    if not st.session_state.mcp_connections_initialized:
        try:
            asyncio.run(init_mcp_connections())
        except RuntimeError:
            # Если event loop уже запущен (например в Streamlit)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(init_mcp_connections())

    # Отображаем текущие подключения
    connections = st.session_state.mcp_manager.get_connections_info()

    if connections:
        for conn in connections:
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.markdown(f"**{conn['name']}**")
                st.caption(f"{conn['tools_count']} tools | {conn['type']}")
            with col2:
                if conn['status'] == "connected":
                    st.success("✅")
                else:
                    st.warning("⚪")
            with col3:
                if st.button("Disconnect", key=f"disconnect_{conn['id']}"):
                    try:
                        asyncio.run(st.session_state.mcp_manager.disconnect(conn['id']))
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(st.session_state.mcp_manager.disconnect(conn['id']))
                    st.rerun()
    else:
        st.info("No MCP connections. Local server will auto-connect.")

    # Кнопка ручного подключения
    with st.expander("➕ Add MCP Server", expanded=False):
        server_type = st.selectbox("Server Type", ["Local (stdio)", "Remote (HTTP) - coming soon"])
        
        if server_type == "Local (stdio)":
            server_path = st.text_input("Script Path", value="mcp_integration/servers/echo_server.py")
            server_name = st.text_input("Display Name", value="Custom Server")
            
            if st.button("Connect"):
                async def connect():
                    await st.session_state.mcp_manager.connect_local(
                        server_id="custom_" + str(hash(server_path)),
                        script_path=server_path,
                        name=server_name
                    )
                try:
                    asyncio.run(connect())
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(connect())
                st.rerun()

    # Показываем активные инструменты
    all_tools = st.session_state.mcp_manager.get_all_tools()
    if all_tools:
        with st.expander("🔧 Active Tools", expanded=False):
            for tool in all_tools[:10]:
                st.caption(f"• {tool['server_name']} :: {tool['tool_name']}")
            if len(all_tools) > 10:
                st.caption(f"... and {len(all_tools) - 10} more")
                
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