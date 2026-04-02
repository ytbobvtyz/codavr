# memory/task_state.py
from enum import Enum
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime


class TaskState(Enum):
    """Состояния задачи в конечном автомате"""
    PLANNING = "planning"      # Анализ, декомпозиция, уточнение требований
    EXECUTION = "execution"    # Написание кода, реализация
    VALIDATION = "validation"  # Тестирование, проверка, code review
    DONE = "done"              # Завершено, ожидание новой задачи


@dataclass
class TaskContext:
    """
    Контекст задачи — объединяет состояние и данные текущей задачи.
    Используется в Working Memory.
    """
    
    # Состояние автомата
    state: TaskState = TaskState.PLANNING
    
    # Основная информация о задаче
    goal: str = ""
    description: str = ""
    
    # Декомпозиция на подзадачи
    subtasks: List[Dict[str, str]] = field(default_factory=list)
    # Формат: [{"name": "...", "status": "pending|in_progress|done"}]
    
    # Текущий шаг
    current_step: str = ""
    next_step: str = ""
    
    # Что ожидается от пользователя (если нужно подтверждение)
    expected_from_user: str = ""
    
    # История переходов между состояниями
    transitions: List[Dict[str, str]] = field(default_factory=list)
    
    # Метаданные
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Допустимые переходы между состояниями
    TRANSITIONS = {
        TaskState.PLANNING: [TaskState.EXECUTION],
        TaskState.EXECUTION: [TaskState.PLANNING, TaskState.VALIDATION],
        TaskState.VALIDATION: [TaskState.DONE, TaskState.EXECUTION],
        TaskState.DONE: [TaskState.PLANNING],
    }
    
    def can_transition(self, new_state: TaskState) -> bool:
        """Проверяет, возможен ли переход в новое состояние"""
        return new_state in self.TRANSITIONS.get(self.state, [])
    
    def transition(self, new_state: TaskState, reason: str = "") -> bool:
        """
        Выполняет переход в новое состояние.
        Возвращает True если переход успешен.
        """
        if not self.can_transition(new_state):
            return False
        
        if self.state == new_state:
            return False
        
        # Логируем переход
        self.transitions.append({
            "from": self.state.value,
            "to": new_state.value,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })
        
        # Обновляем состояние
        self.state = new_state
        self.updated_at = datetime.now().isoformat()
        
        # Автоматические действия при переходах
        if new_state == TaskState.EXECUTION:
            self.expected_from_user = ""
        elif new_state == TaskState.VALIDATION:
            self.expected_from_user = "Проверьте результат и подтвердите"
        elif new_state == TaskState.DONE:
            self.current_step = "Задача завершена"
            self.next_step = ""
            self.expected_from_user = "Готов к следующей задаче"
        elif new_state == TaskState.PLANNING:
            self.expected_from_user = "Уточните требования или подтвердите план"
        
        return True
    
    def update_progress(self, current_step: str, next_step: str = ""):
        """Обновляет текущий и следующий шаг"""
        self.current_step = current_step
        if next_step:
            self.next_step = next_step
        self.updated_at = datetime.now().isoformat()
    
    def add_subtask(self, name: str, status: str = "pending"):
        """Добавляет подзадачу"""
        self.subtasks.append({"name": name, "status": status})
        self.updated_at = datetime.now().isoformat()
    
    def update_subtask(self, name: str, status: str) -> bool:
        """Обновляет статус подзадачи"""
        for task in self.subtasks:
            if task["name"] == name:
                task["status"] = status
                self.updated_at = datetime.now().isoformat()
                return True
        return False
    
    def set_expected_from_user(self, expected: str):
        """Устанавливает, что агент ожидает от пользователя"""
        self.expected_from_user = expected
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Превращает в словарь для JSON сериализации"""
        return {
            "state": self.state.value,
            "goal": self.goal,
            "description": self.description,
            "subtasks": self.subtasks,
            "current_step": self.current_step,
            "next_step": self.next_step,
            "expected_from_user": self.expected_from_user,
            "transitions": self.transitions,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskContext":
        """Восстанавливает из словаря"""
        context = cls()
        context.state = TaskState(data.get("state", "planning"))
        context.goal = data.get("goal", "")
        context.description = data.get("description", "")
        context.subtasks = data.get("subtasks", [])
        context.current_step = data.get("current_step", "")
        context.next_step = data.get("next_step", "")
        context.expected_from_user = data.get("expected_from_user", "")
        context.transitions = data.get("transitions", [])
        context.created_at = data.get("created_at", datetime.now().isoformat())
        context.updated_at = data.get("updated_at", datetime.now().isoformat())
        return context
    
    def to_prompt(self) -> str:
        """Форматирует для вставки в system prompt"""
        icons = {
            TaskState.PLANNING: "📋",
            TaskState.EXECUTION: "⚙️",
            TaskState.VALIDATION: "🔍",
            TaskState.DONE: "✅"
        }
        
        lines = [
            f"{icons.get(self.state, '📌')} **Task State: {self.state.value.upper()}**",
        ]
        
        if self.goal:
            lines.append(f"   Goal: {self.goal}")
        
        if self.current_step:
            lines.append(f"   Current step: {self.current_step}")
        
        if self.next_step:
            lines.append(f"   Next step: {self.next_step}")
        
        if self.expected_from_user:
            lines.append(f"   ⏳ Waiting from user: {self.expected_from_user}")
        
        if self.subtasks:
            done_count = sum(1 for t in self.subtasks if t.get("status") == "done")
            total_count = len(self.subtasks)
            lines.append(f"   Subtasks: {done_count}/{total_count} completed")
            # Показываем текущую подзадачу в работе
            in_progress = [t for t in self.subtasks if t.get("status") == "in_progress"]
            if in_progress:
                lines.append(f"   In progress: {in_progress[0]['name']}")
        
        if self.description:
            lines.append(f"   Description: {self.description[:100]}...")
        
        return "\n".join(lines)
    
    def reset(self):
        """Сбрасывает контекст для новой задачи"""
        self.state = TaskState.PLANNING
        self.goal = ""
        self.description = ""
        self.subtasks = []
        self.current_step = ""
        self.next_step = ""
        self.expected_from_user = ""
        self.transitions = []
        self.updated_at = datetime.now().isoformat()
    
    def is_empty(self) -> bool:
        """Проверяет, есть ли активная задача"""
        return not self.goal and not self.subtasks and self.state == TaskState.PLANNING