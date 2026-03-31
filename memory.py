# memory.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
import json
import sqlite3
from pathlib import Path

class MemoryType(Enum):
    SHORT_TERM = "short_term"
    WORKING = "working"
    LONG_TERM = "long_term"

@dataclass
class MemoryEntry:
    """Отдельная запись в памяти"""
    content: str
    type: MemoryType
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self):
        return {
            "content": self.content,
            "type": self.type.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }

class ShortTermMemory:
    """Краткосрочная память - текущий диалог"""
    def __init__(self, max_messages: int = 20):
        self.messages: List[Dict] = []
        self.max_messages = max_messages
    
    def add(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        if len(self.messages) > self.max_messages:
            self.messages.pop(0)
    
    def get_context(self) -> List[Dict]:
        return self.messages
    
    def clear(self):
        self.messages = []

class WorkingMemory:
    """Рабочая память - данные текущей задачи"""
    def __init__(self):
        self.current_task: Optional[str] = None
        self.open_files: List[str] = []
        self.last_search_results: List[str] = []
        self.pending_actions: List[Dict] = []
        self.task_variables: Dict[str, Any] = {}
        
    def set_task(self, task: str):
        self.current_task = task
        self.task_variables = {}
        self.pending_actions = []
        
    def add_open_file(self, filepath: str):
        if filepath not in self.open_files:
            self.open_files.append(filepath)
    
    def add_search_result(self, result: str):
        self.last_search_results.append(result)
        # храним только последние 5 результатов
        if len(self.last_search_results) > 5:
            self.last_search_results.pop(0)
    
    def get_context(self) -> str:
        context = f"Current task: {self.current_task}\n"
        context += f"Open files: {', '.join(self.open_files)}\n"
        if self.task_variables:
            context += f"Variables: {json.dumps(self.task_variables, indent=2)}\n"
        return context
    
    def clear(self):
        self.current_task = None
        self.open_files = []
        self.last_search_results = []
        self.pending_actions = []
        self.task_variables = {}

class LongTermMemory:
    """Долговременная память - профиль, изученные решения, знания о проекте"""
    def __init__(self, db_path: str = "assistant_memory.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS long_term_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_type TEXT,
                content TEXT,
                tags TEXT,
                importance INTEGER DEFAULT 1,
                created_at TIMESTAMP,
                last_accessed TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    
    def save(self, content: str, memory_type: str, tags: List[str] = None, importance: int = 1):
        """Сохраняет информацию в долговременную память"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO long_term_memory (memory_type, content, tags, importance, created_at, last_accessed)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (memory_type, content, json.dumps(tags or []), importance, datetime.now(), datetime.now()))
        conn.commit()
        conn.close()
    
    def recall(self, query: str, memory_type: str = None, limit: int = 5) -> List[str]:
        """Восстанавливает релевантную информацию из памяти"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Простой поиск по ключевым словам
        # В реальном проекте стоит добавить векторный поиск
        words = query.lower().split()
        
        query_parts = []
        params = []
        for word in words:
            query_parts.append("content LIKE ?")
            params.append(f"%{word}%")
        
        where_clause = " OR ".join(query_parts)
        if memory_type:
            where_clause += " AND memory_type = ?"
            params.append(memory_type)
        
        cursor.execute(f"""
            SELECT content FROM long_term_memory 
            WHERE {where_clause}
            ORDER BY importance DESC, last_accessed DESC
            LIMIT ?
        """, params + [limit])
        
        results = [row[0] for row in cursor.fetchall()]
        conn.close()
        return results
    
    def save_project_pattern(self, pattern: str):
        """Сохраняет паттерн кода или решение из проекта"""
        self.save(pattern, "code_pattern", ["project", "pattern"], importance=3)
    
    def save_user_preference(self, preference: str):
        """Сохраняет предпочтения пользователя"""
        self.save(preference, "user_preference", ["user"], importance=5)
    
    def get_context(self, query: str = "") -> str:
        """Возвращает релевантный контекст из долговременной памяти"""
        if not query:
            # Возвращаем последние важные воспоминания
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT content FROM long_term_memory 
                ORDER BY importance DESC, last_accessed DESC 
                LIMIT 5
            """)
            results = [row[0] for row in cursor.fetchall()]
            conn.close()
        else:
            results = self.recall(query)
        
        if not results:
            return ""
        return "Relevant past knowledge:\n" + "\n".join(f"- {r}" for r in results)