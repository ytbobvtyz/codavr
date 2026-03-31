# app.py
import streamlit as st
from agent import CodeAssistant

st.set_page_config(page_title="Code Assistant with Memory", layout="wide")

# Инициализация агента (ключ уже в .env)
if "assistant" not in st.session_state:
    try:
        st.session_state.assistant = CodeAssistant()
    except ValueError as e:
        st.error(f"❌ {str(e)}")
        st.stop()

# Боковая панель с отображением памяти
with st.sidebar:
    st.title("🧠 Memory Layers")
    
    if st.button("Show Memory State"):
        with st.expander("Memory State"):
            st.code("Check console for detailed memory output")
        st.session_state.assistant.show_memory_state()
    
    st.subheader("Working Memory")
    working = st.session_state.assistant.working
    st.write(f"**Task:** {working.current_task or 'None'}")
    st.write(f"**Files:** {', '.join(working.open_files) or 'None'}")
    
    st.subheader("Quick Actions")
    if st.button("Clear Short-term"):
        st.session_state.assistant.short_term.clear()
        st.success("Short-term memory cleared")
    
    if st.button("Clear Working"):
        st.session_state.assistant.working.clear()
        st.success("Working memory cleared")

# Основной интерфейс
st.title("🤖 Code Assistant with Explicit Memory")

# Информация о статусе API
st.caption(f"✅ API ready | Model: {st.session_state.assistant.model}")

# Примеры команд
with st.expander("📚 Примеры команд для тестирования памяти"):
    st.markdown("""
    **Рабочая память:**
    - `task: Рефакторинг модуля auth`
    - `file: src/auth.py`
    
    **Долговременная память:**
    - `Запомни: я предпочитаю SQLAlchemy 2.0 style`
    - `pattern: Используй repository pattern для работы с БД`
    
    **Запросы:**
    - `Как организовать JWT авторизацию?`
    - `Напиши функцию для валидации email`
    """)

# Чат
if "messages" not in st.session_state:
    st.session_state.messages = []

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