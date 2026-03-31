# memory/profile_manager.py
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import shutil


class ProfileManager:
    """
    Управляет профилями пользователей.
    
    - Default профиль хранится в MD файлах (memory_profiles/default/)
    - Пользовательские профили хранятся в SQLite
    - При создании профиля копирует содержимое default с возможностью редактирования
    """
    
    def __init__(self, db_path: str = "agent_state.db", profiles_dir: str = "memory_profiles"):
        self.db_path = db_path
        self.profiles_dir = Path(profiles_dir)
        self.default_dir = self.profiles_dir / "default"
        
        # Создаём директории и default профиль если нужно
        self._init_directories()
        self._init_db()
    
    def _init_directories(self):
        """Создаёт структуру директорий и default профиль"""
        self.profiles_dir.mkdir(exist_ok=True)
        self.default_dir.mkdir(exist_ok=True)
        
        # Создаём default MD файлы если их нет
        self._ensure_default_md_files()
    
    def _ensure_default_md_files(self):
        """Создаёт MD файлы для default профиля если отсутствуют"""
        
        # style.md
        style_path = self.default_dir / "style.md"
        if not style_path.exists():
            style_path.write_text("""# Communication Style

- Я предпочитаю русский язык в общении, но код и технические термины на английском
- Нужны развёрнутые объяснения, не люблю "магию"
- Важна практическая применимость, а не теория
- Ценю, когда собеседник задаёт уточняющие вопросы перед решением
- Предпочитаю модульную архитектуру с чёткими интерфейсами

# Code Preferences

- Python 3.10+
- FastAPI для бэкенда
- SQLAlchemy 2.0 (async style)
- React + хуки для фронта
- Streamlit для быстрых прототипов
- Предпочитаю explicit над implicit
- Type hints обязательны

# Learning Style

- Учусь на практике через челленджи
- Нужна обратная связь по архитектурным решениям
- Хочу понимать "почему", а не только "как"
""", encoding="utf-8")
        
        # constraint.md
        constraint_path = self.default_dir / "constraint.md"
        if not constraint_path.exists():
            constraint_path.write_text("""# Technical Constraints

## Architecture
- Минимум внешних зависимостей
- Предпочтение стандартной библиотеке Python
- Модульность: каждый компонент можно заменить
- Чистая архитектура с разделением ответственности

## Stack (фиксированный)
- Python 3.10+
- FastAPI
- SQLAlchemy 2.0 (async)
- React + TypeScript

## API Policy
- Только бесплатные API
- OpenRouter с моделями: step-3.5-flash (основная), gpt-3.5-turbo (резерв)
- Никаких платных подписок без явного согласования

## Security
- API ключи только через .env
- Агент не может менять файлы за пределами проекта
- Нет автоматического выполнения destructive операций без подтверждения
""", encoding="utf-8")
        
        # context.md
        context_path = self.default_dir / "context.md"
        if not context_path.exists():
            context_path.write_text("""# Project Context

## Что делаем
Разрабатываем код-ассистента с трехуровневой памятью и персонализацией (челлендж Days 11-12)

## Роли
- Пользователь: middle-разработчик, работает один
- Агент: ассистент-программист, помогает писать и рефакторить код

## Текущий фокус
- Персонализация ассистента под разных пользователей
- Профили с предпочтениями (стиль, ограничения, контекст)
- Интеграция с OpenRouter

## Ближайшие цели
- Добавить инструменты для чтения/записи файлов
- Реализовать RAG для долговременной памяти
- Мульти-агентная архитектура (в планах)

## История проекта
- Day 11: модель памяти с тремя слоями
- Day 12: персонализация и управление профилями
""", encoding="utf-8")
    
    def _init_db(self):
        """Инициализирует таблицу профилей в SQLite"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                profile_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                style TEXT,
                constraints TEXT,
                context TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                parent TEXT DEFAULT 'default',
                version INTEGER DEFAULT 1
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _read_md_files(self, profile_dir: Path) -> Dict[str, str]:
        """Читает все MD файлы из директории"""
        content = {}
        for md_file in profile_dir.glob("*.md"):
            content[md_file.name] = md_file.read_text(encoding="utf-8")
        return content
    
    def _get_default_content(self) -> Dict[str, str]:
        """Возвращает содержимое default профиля"""
        return self._read_md_files(self.default_dir)
    
    def get_profile_content(self, profile_id: str) -> Dict[str, str]:
        """
        Возвращает содержимое профиля в формате {filename: content}
        Для default — из MD файлов
        Для пользовательских — из БД
        """
        if profile_id == "default":
            return self._get_default_content()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT style, constraints, context
            FROM user_profiles
            WHERE profile_id = ?
        """, (profile_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return self._get_default_content()
        
        return {
            "style.md": row[0] or "",
            "constraint.md": row[1] or "",
            "context.md": row[2] or ""
        }
    
    def list_profiles(self) -> List[Dict[str, Any]]:
        """Возвращает список всех профилей"""
        # Сначала default
        profiles = [{
            "id": "default",
            "name": "Default",
            "description": "Стандартный профиль (из MD файлов)",
            "created_at": None,
            "updated_at": None,
            "is_custom": False,
            "is_active": False
        }]
        
        # Пользовательские профили
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT profile_id, name, created_at, updated_at
            FROM user_profiles
            ORDER BY updated_at DESC
        """)
        
        for row in cursor.fetchall():
            profiles.append({
                "id": row[0],
                "name": row[1],
                "description": f"Создан {row[2][:10] if row[2] else 'unknown'}",
                "created_at": row[2],
                "updated_at": row[3],
                "is_custom": True,
                "is_active": False
            })
        
        conn.close()
        return profiles
    
    def get_active_profile(self) -> str:
        """Возвращает ID активного профиля"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        cursor.execute("""
            SELECT value FROM app_state WHERE key = 'active_profile'
        """)
        
        row = cursor.fetchone()
        conn.close()
        
        return row[0] if row else "default"
    
    def set_active_profile(self, profile_id: str) -> bool:
        """Устанавливает активный профиль"""
        # Проверяем существование профиля
        if profile_id != "default":
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM user_profiles WHERE profile_id = ?", (profile_id,))
            exists = cursor.fetchone() is not None
            conn.close()
            if not exists:
                return False
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        cursor.execute("""
            INSERT OR REPLACE INTO app_state (key, value)
            VALUES ('active_profile', ?)
        """, (profile_id,))
        
        conn.commit()
        conn.close()
        return True
    
    def create_profile(
        self, 
        profile_id: str, 
        name: str,
        style: str = None,
        constraints: str = None,
        context: str = None
    ) -> bool:
        """
        Создаёт новый пользовательский профиль.
        Если поля не указаны — копирует из default.
        """
        # Проверяем существование
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM user_profiles WHERE profile_id = ?", (profile_id,))
        if cursor.fetchone():
            conn.close()
            return False
        
        # Если поля не указаны — берём из default
        default_content = self._get_default_content()
        
        style = style or default_content.get("style.md", "")
        constraints = constraints or default_content.get("constraint.md", "")
        context = context or default_content.get("context.md", "")
        
        cursor.execute("""
            INSERT INTO user_profiles (profile_id, name, style, constraints, context)
            VALUES (?, ?, ?, ?, ?)
        """, (profile_id, name, style, constraints, context))
        
        conn.commit()
        conn.close()
        return True
    
    def update_profile(
        self,
        profile_id: str,
        style: str = None,
        constraints: str = None,
        context: str = None
    ) -> bool:
        """Обновляет поля профиля"""
        if profile_id == "default":
            return False
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if style is not None:
            updates.append("style = ?")
            params.append(style)
        
        if constraints is not None:
            updates.append("constraints = ?")
            params.append(constraints)
        
        if context is not None:
            updates.append("context = ?")
            params.append(context)
        
        if not updates:
            conn.close()
            return False
        
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(profile_id)
        
        cursor.execute(f"""
            UPDATE user_profiles 
            SET {', '.join(updates)}
            WHERE profile_id = ?
        """, params)
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    def delete_profile(self, profile_id: str) -> bool:
        """Удаляет профиль (нельзя удалить default и активный)"""
        if profile_id == "default":
            return False
        
        active = self.get_active_profile()
        if profile_id == active:
            return False
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_profiles WHERE profile_id = ?", (profile_id,))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    def reset_to_default(self, profile_id: str) -> bool:
        """Сбрасывает пользовательский профиль к значениям default"""
        if profile_id == "default":
            return False
        
        default_content = self._get_default_content()
        
        return self.update_profile(
            profile_id,
            style=default_content.get("style.md", ""),
            constraints=default_content.get("constraint.md", ""),
            context=default_content.get("context.md", "")
        )
    
    def get_profile_for_prompt(self, profile_id: str = None) -> str:
        """Возвращает содержимое профиля для вставки в system prompt"""
        if profile_id is None:
            profile_id = self.get_active_profile()
        
        content = self.get_profile_content(profile_id)
        
        prompt_parts = []
        for filename, file_content in content.items():
            if file_content.strip():
                prompt_parts.append(file_content)
        
        return "\n\n".join(prompt_parts)