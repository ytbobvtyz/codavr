# memory/working.py
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class TaskStatus(Enum):
    PLANNING = "planning"
    CODING = "coding"
    TESTING = "testing"
    DONE = "done"


@dataclass
class WorkingMemory:
    """
    Рабочая память — текущий контекст задачи.
    Хранится в system prompt, обновляется через tool calls.
    """
    
    # Основная цель текущей задачи
    goal: str = ""
    
    # Список подзадач с их статусами
    tasks: List[Dict[str, str]] = field(default_factory=list)
    # Каждая задача: {"name": "...", "status": "pending|in_progress|done"}
    
    # Текущий статус всего воркфлоу
    status: TaskStatus = TaskStatus.PLANNING
    
    # Следующие шаги
    next_steps: List[str] = field(default_factory=list)
    
    # Файлы, с которыми работаем
    files: List[str] = field(default_factory=list)
    
    # Технологии в текущей задаче
    tech_stack: List[str] = field(default_factory=list)
    
    # Важные архитектурные решения
    decisions: Dict[str, str] = field(default_factory=dict)
    
    # Блокеры (что мешает завершить)
    blockers: List[str] = field(default_factory=list)
    
    # Произвольные переменные задачи
    variables: Dict[str, Any] = field(default_factory=dict)
    
    def update(self, **kwargs) -> List[str]:
        """
        Обновляет поля рабочей памяти.
        Возвращает список изменённых полей.
        """
        changed = []
        
        for key, value in kwargs.items():
            if hasattr(self, key) and getattr(self, key) != value:
                setattr(self, key, value)
                changed.append(key)
        
        return changed
    
    def add_task(self, name: str, status: str = "pending") -> None:
        """Добавляет подзадачу"""
        self.tasks.append({"name": name, "status": status})
    
    def update_task(self, name: str, status: str) -> bool:
        """Обновляет статус подзадачи. Возвращает True если найдено."""
        for task in self.tasks:
            if task["name"] == name:
                task["status"] = status
                return True
        return False
    
    def add_file(self, filepath: str) -> None:
        """Добавляет файл в рабочую область"""
        if filepath not in self.files:
            self.files.append(filepath)
    
    def add_blocker(self, blocker: str) -> None:
        """Добавляет блокер"""
        if blocker not in self.blockers:
            self.blockers.append(blocker)
    
    def resolve_blocker(self, blocker: str) -> bool:
        """Убирает блокер. Возвращает True если найден."""
        if blocker in self.blockers:
            self.blockers.remove(blocker)
            return True
        return False
    
    def to_dict(self) -> Dict:
        """Превращает в словарь для JSON сериализации"""
        return {
            "goal": self.goal,
            "tasks": self.tasks,
            "status": self.status.value,
            "next_steps": self.next_steps,
            "files": self.files,
            "tech_stack": self.tech_stack,
            "decisions": self.decisions,
            "blockers": self.blockers,
            "variables": self.variables,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "WorkingMemory":
        """Восстанавливает из словаря"""
        memory = cls()
        memory.goal = data.get("goal", "")
        memory.tasks = data.get("tasks", [])
        memory.status = TaskStatus(data.get("status", "planning"))
        memory.next_steps = data.get("next_steps", [])
        memory.files = data.get("files", [])
        memory.tech_stack = data.get("tech_stack", [])
        memory.decisions = data.get("decisions", {})
        memory.blockers = data.get("blockers", [])
        memory.variables = data.get("variables", {})
        return memory
    
    def to_system_text(self) -> str:
        """Форматирует для вставки в system prompt"""
        if not self.goal and not self.tasks and not self.files:
            return "## CURRENT WORKING MEMORY\n(No active task)"
        
        lines = [
            "## CURRENT WORKING MEMORY",
            f"**Goal:** {self.goal}" if self.goal else "",
            f"**Status:** {self.status.value}",
            "",
            "**Tasks:**" if self.tasks else "",
        ]
        
        for task in self.tasks:
            status_icon = "✅" if task["status"] == "done" else "🔄" if task["status"] == "in_progress" else "⏳"
            lines.append(f"  {status_icon} {task['name']} ({task['status']})")
        
        if self.next_steps:
            lines.append("\n**Next Steps:**")
            for step in self.next_steps:
                lines.append(f"  → {step}")
        
        if self.files:
            lines.append("\n**Files in context:**")
            for f in self.files:
                lines.append(f"  📄 {f}")
        
        if self.tech_stack:
            lines.append(f"\n**Tech Stack:** {', '.join(self.tech_stack)}")
        
        if self.decisions:
            lines.append("\n**Decisions:**")
            for key, value in self.decisions.items():
                lines.append(f"  • {key}: {value}")
        
        if self.blockers:
            lines.append("\n**Blockers:**")
            for blocker in self.blockers:
                lines.append(f"  ⚠️ {blocker}")
        
        return "\n".join(filter(None, lines))
    
    def is_empty(self) -> bool:
        """Проверяет, пустая ли рабочая память"""
        return not (self.goal or self.tasks or self.files)
    
    def reset(self) -> None:
        """Сбрасывает рабочую память для новой задачи"""
        self.goal = ""
        self.tasks = []
        self.status = TaskStatus.PLANNING
        self.next_steps = []
        self.files = []
        self.tech_stack = []
        self.decisions = {}
        self.blockers = []
        self.variables = {}