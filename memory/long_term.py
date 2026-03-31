# memory/long_term.py
import os
import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class MemoryEntry:
    """Запись в долговременной памяти"""
    content: str
    entry_type: str  # code_pattern, user_preference, arch_decision, lesson_learned
    importance: int = 1  # 1-5, где 5 — очень важно
    tags: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class LongTermMemory:
    """
    Долговременная память — сохраняет важные паттерны, решения, предпочтения.
    Использует SQLite для хранения, в будущем добавим векторный поиск.
    """
    
    def __init__(self, db_path: str = "assistant_memory.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Инициализирует базу данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_type TEXT NOT NULL,
                content TEXT NOT NULL,
                importance INTEGER DEFAULT 1,
                tags TEXT,
                timestamp TIMESTAMP,
                metadata TEXT,
                last_accessed TIMESTAMP
            )
        """)
        
        # Создаём индекс для быстрого поиска по типу
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_type ON memories(entry_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_importance ON memories(importance)")
        
        conn.commit()
        conn.close()
    
    def save(self, entry: MemoryEntry) -> int:
        """Сохраняет запись в память. Возвращает ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO memories (entry_type, content, importance, tags, timestamp, metadata, last_accessed)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.entry_type,
            entry.content,
            entry.importance,
            json.dumps(entry.tags),
            entry.timestamp.isoformat(),
            json.dumps(entry.metadata),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        entry_id = cursor.lastrowid
        conn.close()
        return entry_id
    
    def save_simple(self, content: str, entry_type: str, importance: int = 1, tags: List[str] = None) -> int:
        """Упрощённое сохранение"""
        entry = MemoryEntry(
            content=content,
            entry_type=entry_type,
            importance=importance,
            tags=tags or []
        )
        return self.save(entry)
    
    def recall(self, query: str, entry_type: str = None, limit: int = 5) -> List[MemoryEntry]:
        """
        Восстанавливает записи по ключевым словам.
        В текущей версии — простой поиск по LIKE.
        В будущем — заменим на векторный поиск.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Простой поиск по ключевым словам
        words = query.lower().split()
        conditions = []
        params = []
        
        for word in words:
            conditions.append("content LIKE ?")
            params.append(f"%{word}%")
        
        where_clause = " OR ".join(conditions)
        
        if entry_type:
            where_clause += " AND entry_type = ?"
            params.append(entry_type)
        
        cursor.execute(f"""
            SELECT entry_type, content, importance, tags, timestamp, metadata
            FROM memories
            WHERE {where_clause}
            ORDER BY importance DESC, last_accessed DESC
            LIMIT ?
        """, params + [limit])
        
        results = []
        for row in cursor.fetchall():
            entry = MemoryEntry(
                entry_type=row[0],
                content=row[1],
                importance=row[2],
                tags=json.loads(row[3]),
                timestamp=datetime.fromisoformat(row[4]),
                metadata=json.loads(row[5])
            )
            results.append(entry)
        
        conn.close()
        
        # Обновляем last_accessed
        if results:
            self._update_access_time([r.id for r in results])
        
        return results
    
    def _update_access_time(self, ids: List[int]):
        """Обновляет время последнего доступа"""
        if not ids:
            return
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        placeholders = ",".join("?" * len(ids))
        cursor.execute(f"""
            UPDATE memories SET last_accessed = ?
            WHERE id IN ({placeholders})
        """, [datetime.now().isoformat()] + ids)
        conn.commit()
        conn.close()
    
    def get_by_type(self, entry_type: str, limit: int = 10) -> List[MemoryEntry]:
        """Получает записи по типу"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT entry_type, content, importance, tags, timestamp, metadata, id
            FROM memories
            WHERE entry_type = ?
            ORDER BY importance DESC, last_accessed DESC
            LIMIT ?
        """, (entry_type, limit))
        
        results = []
        for row in cursor.fetchall():
            entry = MemoryEntry(
                entry_type=row[0],
                content=row[1],
                importance=row[2],
                tags=json.loads(row[3]),
                timestamp=datetime.fromisoformat(row[4]),
                metadata=json.loads(row[5])
            )
            results.append(entry)
        
        conn.close()
        return results
    
    def format_for_prompt(self, entries: List[MemoryEntry]) -> str:
        """Форматирует записи для вставки в system prompt"""
        if not entries:
            return ""
        
        lines = ["## LONG-TERM MEMORY (relevant past knowledge)"]
        
        for entry in entries:
            type_icon = {
                "user_preference": "👤",
                "code_pattern": "📐",
                "arch_decision": "🏗️",
                "lesson_learned": "📝"
            }.get(entry.entry_type, "📌")
            
            lines.append(f"\n{type_icon} **{entry.entry_type.replace('_', ' ').title()}** (importance: {entry.importance})")
            lines.append(f"   {entry.content}")
            if entry.tags:
                lines.append(f"   Tags: {', '.join(entry.tags)}")
        
        return "\n".join(lines)
    
    def delete_old(self, days: int = 30, importance_threshold: int = 3):
        """Удаляет старые неважные записи"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM memories
            WHERE importance < ? 
            AND julianday('now') - julianday(timestamp) > ?
        """, (importance_threshold, days))
        
        conn.commit()
        deleted = cursor.rowcount
        conn.close()
        return deleted


class MetaMemory:
    """
    Загружает MD файлы из папки memory_meta/
    Это неизменяемая долговременная память (style, constraints, context)
    """
    
    def __init__(self, meta_dir: str = "memory_meta"):
        self.meta_dir = Path(meta_dir)
        self._ensure_dir()
    
    def _ensure_dir(self):
        """Создаёт директорию если её нет"""
        self.meta_dir.mkdir(exist_ok=True)
    
    def load_file(self, filename: str) -> str:
        """Загружает MD файл, возвращает содержимое"""
        filepath = self.meta_dir / filename
        if filepath.exists():
            return filepath.read_text(encoding="utf-8")
        return f"# {filename}\n\n(File not found. Create {filepath})"
    
    def load_all(self) -> Dict[str, str]:
        """Загружает все MD файлы"""
        files = ["style.md", "constraint.md", "context.md"]
        return {f: self.load_file(f) for f in files}
    
    def get_system_prompt(self) -> str:
        """Собирает system prompt из всех MD файлов"""
        contents = self.load_all()
        
        prompt = f"""
{contents.get('style.md', '')}

{contents.get('constraint.md', '')}

{contents.get('context.md', '')}
"""
        return prompt.strip()