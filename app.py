# app.py
import streamlit as st
from agent import CodeAssistant

st.set_page_config(page_title="Code Assistant with Memory", layout="wide")

# Инициализация
if "assistant" not in st.session_state:
    try:
        st.session_state.assistant = CodeAssistant()
        st.session_state.messages = []
    except ValueError as e:
        st.error(f"❌ {str(e)}")
        st.stop()

# Используем стандартный sidebar Streamlit — он фиксирован по умолчанию
with st.sidebar:
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