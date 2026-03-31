import streamlit as st
from agent import CodeAssistant
from memory.persistence import PersistenceManager

st.set_page_config(page_title="Code Assistant with Memory", layout="wide")

# Инициализация менеджера сессий
if "persistence" not in st.session_state:
    st.session_state.persistence = PersistenceManager()

# Функция для переключения сессии
def switch_session(session_id: str):
    st.session_state.current_session_id = session_id
    st.session_state.assistant = CodeAssistant(session_id=session_id)
    st.session_state.messages = []
    
    # Загружаем историю
    saved_messages = st.session_state.assistant.persistence.load_conversation(
        session_id=session_id
    )
    for msg in saved_messages:
        st.session_state.messages.append({
            "role": msg["role"], 
            "content": msg["content"]
        })
    st.rerun()

def create_new_session():
    new_id = st.session_state.persistence.create_session("New conversation")
    switch_session(new_id)

def delete_session(session_id: str):
    if session_id == st.session_state.current_session_id:
        st.warning("Cannot delete current session. Switch to another first.")
        return
    st.session_state.persistence.delete_session(session_id)
    st.rerun()

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
        st.session_state.messages.append({
            "role": msg["role"], 
            "content": msg["content"]
        })

# ===== SIDEBAR =====
with st.sidebar:
    st.title("💬 Conversations")
    
    # Кнопка новой сессии
    if st.button("➕ New Conversation", use_container_width=True):
        create_new_session()
    
    st.divider()
    
    # Список всех сессий
    sessions = st.session_state.persistence.list_sessions(limit=20)
    
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
    
    # ===== ОТОБРАЖЕНИЕ ПАМЯТИ (как было) =====
    st.title("🧠 Memory Layers")
    
    # ===== КРАТКОСРОЧНАЯ ПАМЯТЬ =====
    with st.expander("📝 Short-Term Memory", expanded=True):
        assistant = st.session_state.assistant
        
        # Суммаризация предыдущего диалога
        summary = assistant.short_term.summary
        if summary:
            st.markdown("**📋 Summary of earlier conversation:**")
            st.info(summary[:300] + "..." if len(summary) > 300 else summary)
        else:
            st.caption("No summary yet (need more than 5 messages)")
        
        # Последние 5 сообщений
        st.markdown(f"**💬 Last {min(5, assistant.short_term.total_messages)} messages:**")
        recent = assistant.short_term.get_recent_window()
        if recent:
            for msg in recent[-5:]:
                role_icon = "👤" if msg["role"] == "user" else "🤖"
                st.caption(f"{role_icon} **{msg['role']}:** {msg['content'][:100]}...")
        else:
            st.caption("No messages yet")
        
        st.markdown(f"*Total messages in session: {assistant.short_term.total_messages}*")
    
    # ===== РАБОЧАЯ ПАМЯТЬ =====

    with st.expander("⚙️ Working Memory", expanded=True):
        working = assistant.working
        
        if working.goal:
            st.markdown(f"**🎯 Goal:** {working.goal}")
        else:
            st.caption("No active goal")
        
        st.markdown(f"**📊 Status:** `{working.status}`")
        
        if working.tasks:
            st.markdown("**✅ Tasks:**")
            for task in working.tasks:
                icon = "✅" if task["status"] == "done" else "🔄" if task["status"] == "in_progress" else "⏳"
                st.text(f"{icon} {task['name']} ({task['status']})")
        
        if working.next_steps:
            st.markdown("**➡️ Next Steps:**")
            for step in working.next_steps:
                st.text(f"• {step}")
        
        if working.files:
            st.markdown("**📁 Files:**")
            for f in working.files:
                st.code(f, language="python")
        
        if working.tech_stack:
            st.markdown(f"**🛠️ Tech Stack:** {', '.join(working.tech_stack)}")
        
        if working.decisions:
            st.markdown("**💡 Decisions:**")
            for key, value in working.decisions.items():
                st.text(f"{key}: {value}")
        
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
    
    # ===== ДОЛГОВРЕМЕННАЯ ПАМЯТЬ (МЕТА) =====
    with st.expander("📚 Long-Term Memory (Meta)", expanded=False):
        meta = assistant.meta_memory.load_all()
        
        # style.md
        st.markdown("**🎨 Style**")
        style_preview = meta.get("style.md", "")[:200]
        st.caption(style_preview + "..." if len(meta.get("style.md", "")) > 200 else style_preview)
        
        # constraint.md
        st.markdown("**🔒 Constraints**")
        constraint_preview = meta.get("constraint.md", "")[:200]
        st.caption(constraint_preview + "..." if len(meta.get("constraint.md", "")) > 200 else constraint_preview)
        
        # context.md
        st.markdown("**📖 Context**")
        context_preview = meta.get("context.md", "")[:200]
        st.caption(context_preview + "..." if len(meta.get("context.md", "")) > 200 else context_preview)
        
        st.divider()
        
        # Сохранённые воспоминания
        st.markdown("**💾 Saved Memories**")
        memory_types = ["user_preference", "code_pattern", "arch_decision", "lesson_learned"]
        for mem_type in memory_types:
            entries = assistant.long_term.get_by_type(mem_type, limit=2)
            if entries:
                with st.expander(f"{mem_type.replace('_', ' ').title()} ({len(entries)})"):
                    for e in entries:
                        st.text(f"• {e.content[:150]}...")
                        st.caption(f"  importance: {e.importance} | tags: {', '.join(e.tags)}")
        
        # Кнопка принудительного сохранения (для теста)
        test_save = st.text_input("Test save to long-term:", placeholder="content")
        test_type = st.selectbox("Type", memory_types)
        if st.button("Save Test Entry") and test_save:
            assistant.long_term.save_simple(test_save, test_type, importance=3)
            st.success(f"Saved: {test_save[:50]}...")
            st.rerun()
    
    # ===== ОТЛАДКА =====
    with st.expander("🐛 Debug Info", expanded=False):
        st.json({
            "working_memory": assistant.working.to_dict(),
            "short_term_total": assistant.short_term.total_messages,
            "short_term_window": assistant.short_term.window_size,
            "has_summary": bool(assistant.short_term.summary),
        })
        
        if st.button("Force Rerun"):
            st.rerun()

# Основная область — только чат
st.title("🤖 Code Assistant with Memory")
st.caption(f"Model: {st.session_state.assistant.main_model}")

# Чат
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Что нужно сделать в проекте?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        with st.spinner("Думаю..."):
            response = st.session_state.assistant.ask(prompt)
            st.markdown(response)
    
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()