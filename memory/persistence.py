# memory/persistence.py
import sqlite3
import json
from typing import List, Dict, Optional
from datetime import datetime


class PersistenceManager:
    """Сохраняет состояние агента между перезагрузками"""
    
    def __init__(self, db_path: str = "agent_state.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Инициализирует базу данных с миграцией"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # === SESSIONS TABLE ===
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'")
        if cursor.fetchone():
            # Проверяем и добавляем недостающие колонки
            cursor.execute("PRAGMA table_info(sessions)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'profile_id' not in columns:
                cursor.execute("ALTER TABLE sessions ADD COLUMN profile_id TEXT DEFAULT 'default'")
            if 'message_count' not in columns:
                cursor.execute("ALTER TABLE sessions ADD COLUMN message_count INTEGER DEFAULT 0")
        else:
            cursor.execute("""
                CREATE TABLE sessions (
                    session_id TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL DEFAULT 'default',
                    title TEXT,
                    first_preview TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    message_count INTEGER DEFAULT 0
                )
            """)
        
        # === CONVERSATION HISTORY ===
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                session_id TEXT DEFAULT 'default',
                profile_id TEXT DEFAULT 'default'
            )
        """)
        
        cursor.execute("PRAGMA table_info(conversation_history)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'profile_id' not in columns:
            cursor.execute("ALTER TABLE conversation_history ADD COLUMN profile_id TEXT DEFAULT 'default'")
        
        # === WORKING MEMORY ===
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS working_memory_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state_json TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                session_id TEXT DEFAULT 'default',
                profile_id TEXT DEFAULT 'default'
            )
        """)
        
        cursor.execute("PRAGMA table_info(working_memory_state)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'profile_id' not in columns:
            cursor.execute("ALTER TABLE working_memory_state ADD COLUMN profile_id TEXT DEFAULT 'default'")
        
        # === CONVERSATION SUMMARY ===
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary TEXT NOT NULL,
                message_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                session_id TEXT DEFAULT 'default',
                profile_id TEXT DEFAULT 'default'
            )
        """)
        
        cursor.execute("PRAGMA table_info(conversation_summary)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'profile_id' not in columns:
            cursor.execute("ALTER TABLE conversation_summary ADD COLUMN profile_id TEXT DEFAULT 'default'")
        
        # Индексы (с проверкой существования)
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_profile ON sessions(profile_id)")
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_session ON conversation_history(session_id)")
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_profile ON conversation_history(profile_id)")
        except sqlite3.OperationalError:
            pass
        
        conn.commit()
        conn.close()
    
    def create_session(self, first_message_preview: str = "New conversation", profile_id: str = "default") -> str:
        """Создаёт новую сессию для конкретного профиля"""
        import uuid
        session_id = str(uuid.uuid4())
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO sessions (session_id, profile_id, title, first_preview, message_count)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, profile_id, first_message_preview[:50], first_message_preview[:100], 0))
        
        conn.commit()
        conn.close()
        
        return session_id
    
    def list_sessions(self, profile_id: str = None, limit: int = 20) -> List[Dict]:
        """Возвращает список сессий для конкретного профиля"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if profile_id:
            cursor.execute("""
                SELECT session_id, title, first_preview, created_at, updated_at, message_count
                FROM sessions
                WHERE profile_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
            """, (profile_id, limit))
        else:
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
    
    def save_message(self, role: str, content: str, session_id: str = "default", profile_id: str = "default"):
        """Сохраняет сообщение"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO conversation_history (role, content, session_id, profile_id)
            VALUES (?, ?, ?, ?)
        """, (role, content, session_id, profile_id))
        conn.commit()
        conn.close()
    
    def load_conversation(self, session_id: str = None, profile_id: str = None, limit: int = None) -> List[Dict]:
        """Загружает историю диалога"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = "SELECT role, content, timestamp FROM conversation_history WHERE 1=1"
        params = []
        
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        
        if profile_id:
            query += " AND profile_id = ?"
            params.append(profile_id)
        
        query += " ORDER BY id ASC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [{"role": row[0], "content": row[1], "timestamp": row[2]} for row in rows]
    
    def save_working_memory(self, working_memory_dict: Dict, session_id: str = "default", profile_id: str = "default"):
        """Сохраняет рабочую память"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM working_memory_state WHERE session_id = ? AND profile_id = ?", 
                      (session_id, profile_id))
        
        cursor.execute("""
            INSERT INTO working_memory_state (state_json, session_id, profile_id)
            VALUES (?, ?, ?)
        """, (json.dumps(working_memory_dict, ensure_ascii=False), session_id, profile_id))
        
        conn.commit()
        conn.close()
    
    def load_working_memory(self, session_id: str = "default", profile_id: str = "default") -> Optional[Dict]:
        """Загружает рабочую память"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT state_json 
            FROM working_memory_state 
            WHERE session_id = ? AND profile_id = ?
            ORDER BY updated_at DESC 
            LIMIT 1
        """, (session_id, profile_id))
        
        row = cursor.fetchone()
        conn.close()
        
        return json.loads(row[0]) if row else None
    
    def save_summary(self, summary: str, message_count: int, session_id: str = "default", profile_id: str = "default"):
        """Сохраняет суммаризацию"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO conversation_summary (summary, message_count, session_id, profile_id)
            VALUES (?, ?, ?, ?)
        """, (summary, message_count, session_id, profile_id))
        conn.commit()
        conn.close()
    
    def load_latest_summary(self, session_id: str = "default", profile_id: str = "default") -> Optional[str]:
        """Загружает последнюю суммаризацию"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT summary 
            FROM conversation_summary 
            WHERE session_id = ? AND profile_id = ?
            ORDER BY created_at DESC 
            LIMIT 1
        """, (session_id, profile_id))
        
        row = cursor.fetchone()
        conn.close()
        
        return row[0] if row else None
    
    def delete_session(self, session_id: str, profile_id: str = None):
        """Удаляет сессию"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if profile_id:
            cursor.execute("DELETE FROM sessions WHERE session_id = ? AND profile_id = ?", 
                          (session_id, profile_id))
            cursor.execute("DELETE FROM conversation_history WHERE session_id = ? AND profile_id = ?", 
                          (session_id, profile_id))
            cursor.execute("DELETE FROM working_memory_state WHERE session_id = ? AND profile_id = ?", 
                          (session_id, profile_id))
            cursor.execute("DELETE FROM conversation_summary WHERE session_id = ? AND profile_id = ?", 
                          (session_id, profile_id))
        else:
            cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM conversation_history WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM working_memory_state WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM conversation_summary WHERE session_id = ?", (session_id,))
        
        conn.commit()
        conn.close()
    
    def update_session_info(self, session_id: str, profile_id: str = None, title: str = None, 
                           first_preview: str = None, message_count: int = None):
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
            if profile_id:
                params.append(profile_id)
                cursor.execute(f"""
                    UPDATE sessions 
                    SET {', '.join(updates)}
                    WHERE session_id = ? AND profile_id = ?
                """, params)
            else:
                cursor.execute(f"""
                    UPDATE sessions 
                    SET {', '.join(updates)}
                    WHERE session_id = ?
                """, params)
        
        conn.commit()
        conn.close()