# memory/working.py
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from memory.task_state import TaskContext, TaskState


@dataclass
class WorkingMemory:
    """
    Рабочая память — текущий контекст задачи.
    Использует TaskContext для управления состоянием.
    """
    
    # Контекст задачи (состояние, цель, подзадачи)
    task: TaskContext = field(default_factory=TaskContext)
    
    # Файлы, с которыми работаем
    files: List[str] = field(default_factory=list)
    
    # Блокеры (что мешает завершить)
    blockers: List[str] = field(default_factory=list)
    
    # Произвольные переменные задачи
    variables: Dict[str, Any] = field(default_factory=dict)
    
    def update_task_goal(self, goal: str, description: str = ""):
        """Обновляет цель задачи"""
        self.task.goal = goal
        if description:
            self.task.description = description
        self.task.updated_at = self._now()
    
    def transition_state(self, new_state: str, reason: str = "") -> bool:
        """Переводит задачу в новое состояние"""
        try:
            new_state_enum = TaskState(new_state)
            return self.task.transition(new_state_enum, reason)
        except ValueError:
            return False
    
    def add_subtask(self, name: str, status: str = "pending"):
        """Добавляет подзадачу"""
        self.task.add_subtask(name, status)
    
    def update_subtask(self, name: str, status: str) -> bool:
        """Обновляет статус подзадачи"""
        return self.task.update_subtask(name, status)
    
    def add_file(self, filepath: str):
        """Добавляет файл в рабочую область"""
        if filepath not in self.files:
            self.files.append(filepath)
    
    def remove_file(self, filepath: str):
        """Удаляет файл из рабочей области"""
        if filepath in self.files:
            self.files.remove(filepath)
    
    def add_blocker(self, blocker: str):
        """Добавляет блокер"""
        if blocker not in self.blockers:
            self.blockers.append(blocker)
    
    def resolve_blocker(self, blocker: str) -> bool:
        """Убирает блокер"""
        if blocker in self.blockers:
            self.blockers.remove(blocker)
            return True
        return False
    
    def set_expected_from_user(self, expected: str):
        """Устанавливает ожидание от пользователя"""
        self.task.set_expected_from_user(expected)
    
    def to_dict(self) -> Dict:
        """Превращает в словарь для JSON сериализации"""
        return {
            "task": self.task.to_dict(),
            "files": self.files,
            "blockers": self.blockers,
            "variables": self.variables,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "WorkingMemory":
        """Восстанавливает из словаря"""
        memory = cls()
        memory.task = TaskContext.from_dict(data.get("task", {}))
        memory.files = data.get("files", [])
        memory.blockers = data.get("blockers", [])
        memory.variables = data.get("variables", {})
        return memory
    
    def to_system_text(self) -> str:
        """Форматирует для вставки в system prompt"""
        parts = ["## CURRENT WORKING MEMORY"]
        
        # Контекст задачи
        parts.append(self.task.to_prompt())
        
        # Дополнительная информация
        if self.files:
            parts.append(f"\n**Files in context:**")
            for f in self.files:
                parts.append(f"  📄 {f}")
        
        if self.blockers:
            parts.append(f"\n**Blockers:**")
            for blocker in self.blockers:
                parts.append(f"  ⚠️ {blocker}")
        
        if self.variables:
            parts.append(f"\n**Variables:**")
            for key, value in self.variables.items():
                parts.append(f"  • {key}: {value}")
        
        return "\n".join(parts)
    
    def is_empty(self) -> bool:
        """Проверяет, пустая ли рабочая память"""
        return self.task.is_empty() and not self.files and not self.blockers
    
    def reset(self):
        """Сбрасывает рабочую память для новой задачи"""
        self.task.reset()
        self.files = []
        self.blockers = []
        self.variables = {}
    
    def _now(self) -> str:
        """Возвращает текущее время в ISO формате"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def update(self, **kwargs) -> List[str]:
        """
        Обновляет поля рабочей памяти.
        Используется для обратной совместимости со старыми tool calls.
        """
        changed = []
        
        if "goal" in kwargs:
            self.task.goal = kwargs["goal"]
            changed.append("goal")
        
        if "status" in kwargs:
            if self.transition_state(kwargs["status"]):
                changed.append("status")
        
        if "next_steps" in kwargs and kwargs["next_steps"]:
            self.task.next_step = kwargs["next_steps"][0]
            changed.append("next_steps")
        
        if "files" in kwargs:
            for f in kwargs["files"]:
                self.add_file(f)
            changed.append("files")
        
        if "tech_stack" in kwargs:
            self.variables["tech_stack"] = kwargs["tech_stack"]
            changed.append("tech_stack")
        
        if "decisions" in kwargs:
            for key, value in kwargs["decisions"].items():
                self.variables[f"decision_{key}"] = value
            changed.append("decisions")
        
        if "blockers" in kwargs:
            for b in kwargs["blockers"]:
                self.add_blocker(b)
            changed.append("blockers")
        
        return changed