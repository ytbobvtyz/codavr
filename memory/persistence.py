# memory/persistence.py
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path


class PersistenceManager:
    """Сохраняет состояние агента между перезагрузками"""
    
    def __init__(self, db_path: str = "agent_state.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица для истории диалога
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                session_id TEXT DEFAULT 'default'
            )
        """)
        
        # Таблица для рабочей памяти
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS working_memory_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state_json TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                session_id TEXT DEFAULT 'default'
            )
        """)
        
        # Таблица для суммаризации
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary TEXT NOT NULL,
                message_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                session_id TEXT DEFAULT 'default'
            )
        """)
        
        conn.commit()
        conn.close()
    
    def save_message(self, role: str, content: str, session_id: str = "default"):
        """Сохраняет одно сообщение в историю"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO conversation_history (role, content, session_id)
            VALUES (?, ?, ?)
        """, (role, content, session_id))
        conn.commit()
        conn.close()
    
    def load_conversation(self, limit: int = None, session_id: str = "default") -> List[Dict]:
        """Загружает историю диалога"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = """
            SELECT role, content, timestamp 
            FROM conversation_history 
            WHERE session_id = ?
            ORDER BY id ASC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query, (session_id,))
        rows = cursor.fetchall()
        conn.close()
        
        return [{"role": row[0], "content": row[1], "timestamp": row[2]} for row in rows]
    
    def save_working_memory(self, working_memory_dict: Dict, session_id: str = "default"):
        """Сохраняет состояние рабочей памяти"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Удаляем старую запись для этой сессии
        cursor.execute("DELETE FROM working_memory_state WHERE session_id = ?", (session_id,))
        
        # Сохраняем новую
        cursor.execute("""
            INSERT INTO working_memory_state (state_json, session_id)
            VALUES (?, ?)
        """, (json.dumps(working_memory_dict, ensure_ascii=False), session_id))
        
        conn.commit()
        conn.close()
    
    def load_working_memory(self, session_id: str = "default") -> Optional[Dict]:
        """Загружает состояние рабочей памяти"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT state_json 
            FROM working_memory_state 
            WHERE session_id = ?
            ORDER BY updated_at DESC 
            LIMIT 1
        """, (session_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        return json.loads(row[0]) if row else None
    
    def save_summary(self, summary: str, message_count: int, session_id: str = "default"):
        """Сохраняет суммаризацию диалога"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO conversation_summary (summary, message_count, session_id)
            VALUES (?, ?, ?)
        """, (summary, message_count, session_id))
        conn.commit()
        conn.close()
    
    def load_latest_summary(self, session_id: str = "default") -> Optional[str]:
        """Загружает последнюю суммаризацию"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT summary 
            FROM conversation_summary 
            WHERE session_id = ?
            ORDER BY created_at DESC 
            LIMIT 1
        """, (session_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        return row[0] if row else None
    
    def clear_session(self, session_id: str = "default"):
        """Очищает все данные сессии"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM conversation_history WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM working_memory_state WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM conversation_summary WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()

# memory/persistence.py — добавляем методы для работы с сессиями

    def create_session(self, first_message_preview: str = "New conversation") -> str:
        """Создаёт новую сессию и возвращает её ID"""
        import uuid
        session_id = str(uuid.uuid4())
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Создаём таблицу sessions если её нет
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                title TEXT,
                first_preview TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                message_count INTEGER DEFAULT 0
            )
        """)
        
        cursor.execute("""
            INSERT INTO sessions (session_id, title, first_preview)
            VALUES (?, ?, ?)
        """, (session_id, first_message_preview[:50], first_message_preview[:100]))
        
        conn.commit()
        conn.close()
        
        return session_id
    
    def list_sessions(self, limit: int = 20) -> List[Dict]:
        """Возвращает список всех сессий для бокового меню"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Убеждаемся что таблица существует
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                title TEXT,
                first_preview TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                message_count INTEGER DEFAULT 0
            )
        """)
        
        cursor.execute("""
            SELECT session_id, title, first_preview, created_at, updated_at, message_count
            FROM sessions
            ORDER BY updated_at DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "session_id": row[0],
                "title": row[1] or "Untitled",
                "first_preview": row[2],
                "created_at": row[3],
                "updated_at": row[4],
                "message_count": row[5] or 0
            }
            for row in rows
        ]
    
    def update_session_info(self, session_id: str, title: str = None, first_preview: str = None, message_count: int = None):
        """Обновляет метаинформацию сессии"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if title:
            updates.append("title = ?")
            params.append(title)
        
        if first_preview:
            updates.append("first_preview = ?")
            params.append(first_preview)
        
        if message_count is not None:
            updates.append("message_count = ?")
            params.append(message_count)
        
        updates.append("updated_at = CURRENT_TIMESTAMP")
        
        if updates:
            params.append(session_id)
            cursor.execute(f"""
                UPDATE sessions 
                SET {', '.join(updates)}
                WHERE session_id = ?
            """, params)
        
        conn.commit()
        conn.close()
        
    def delete_session(self, session_id: str):
        """Удаляет сессию и все связанные данные"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM conversation_history WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM working_memory_state WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM conversation_summary WHERE session_id = ?", (session_id,))
        
        conn.commit()
        conn.close()