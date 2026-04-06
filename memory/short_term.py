# memory/short_term.py
import json
from typing import List, Dict, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class Message:
    """Отдельное сообщение в диалоге"""
    role: str  # 'user' или 'assistant'
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {"role": self.role, "content": self.content}
    
    def to_tuple(self) -> tuple:
        """Для хранения в списке сообщений API"""
        return (self.role, self.content)


class ShortTermMemory:
    """
    Краткосрочная память с двумя уровнями:
    1. Скользящее окно из последних N сообщений (хранятся полностью)
    2. Суммаризация всех сообщений, которые выпали из окна
    
    При добавлении каждого нового сообщения проверяется:
    - Если общее количество сообщений превышает window_size + 1
    - Самое старое сообщение (из тех, что ещё не в окне) отправляется в суммаризацию
    """
    
    def __init__(
        self, 
        window_size: int = 5,
        summarizer: Optional[Callable[[List[Message]], str]] = None
    ):
        """
        Args:
            window_size: Размер скользящего окна (храним N последних сообщений)
            summarizer: Функция для суммаризации сообщений.
                        Если None, суммаризация не выполняется (только окно)
        """
        self.window_size = window_size
        self.summarizer = summarizer
        
        # Все сообщения (история)
        self._all_messages: List[Message] = []
        
        # Суммаризация старых сообщений
        self._summary: str = ""
        
        # Флаг, что суммаризация устарела (нужно перегенерировать)
        self._summary_dirty: bool = False
    
    def add(self, role: str, content: str) -> None:
        """Добавляет новое сообщение в память"""
        message = Message(role=role, content=content)
        self._all_messages.append(message)
        
        # Проверяем, нужно ли пересчитать суммаризацию
        # Если общее количество сообщений превышает window_size
        if len(self._all_messages) > self.window_size:
            self._summary_dirty = True
    
    def _regenerate_summary(self) -> None:
        """
        Перегенерирует суммаризацию для всех сообщений вне окна.
        Вызывается только при необходимости (лениво).
        """
        if not self._summary_dirty:
            return
        
        # Сообщения вне окна (старые)
        old_messages = self._all_messages[:-self.window_size]
        
        if not old_messages:
            self._summary = ""
            self._summary_dirty = False
            return
        
        # Если нет суммаризатора — просто перечисляем сообщения
        if self.summarizer is None:
            self._summary = self._format_messages(old_messages)
        else:
            # Используем переданную функцию суммаризации
            self._summary = self.summarizer(old_messages)
        
        self._summary_dirty = False
    
    def _format_messages(self, messages: List[Message]) -> str:
        """Форматирует сообщения в текст (без суммаризации)"""
        lines = []
        for msg in messages:
            if msg is None:
                continue
            role = msg.role if msg.role else "unknown"
            content = msg.content if msg.content else ""
            lines.append(f"{role.upper()}: {content}")
        return "\n".join(lines)
    
    def get_recent_window(self) -> List[Dict]:
        """
        Возвращает последние N сообщений в формате для API
        (готовый массив для messages)
        """
        recent = self._all_messages[-self.window_size:]
        result = []
        for msg in recent:
            if msg is None:
                continue
            result.append(msg.to_dict())
        return result
    
    def get_context(self) -> str:
        """
        Возвращает полный контекст для вставки в user prompt:
        - Суммаризация старых сообщений (если есть)
        - Последние N сообщений (полностью)
        """
        self._regenerate_summary()
        
        parts = []
        
        # Добавляем суммаризацию
        if self._summary:
            parts.append(f"[Предыдущая часть диалога]\n{self._summary}")
        
        # Добавляем последние сообщения
        recent = self._all_messages[-self.window_size:]
        if recent:
            recent_text = self._format_messages(recent)
            parts.append(f"[Последние {len(recent)} сообщений]\n{recent_text}")
        
        return "\n\n".join(parts) if parts else ""
    
    def get_full_history(self) -> List[Dict]:
        """Возвращает ВСЮ историю (для отладки)"""
        result = []
        for msg in self._all_messages:
            if msg is None:
                continue
            result.append(msg.to_dict())
        return result
    
    def clear(self) -> None:
        """Очищает всю память"""
        self._all_messages = []
        self._summary = ""
        self._summary_dirty = False
    
    @property
    def total_messages(self) -> int:
        """Общее количество сообщений в памяти"""
        return len(self._all_messages)
    
    @property
    def summary(self) -> str:
        """Текущая суммаризация (только для чтения)"""
        self._regenerate_summary()
        return self._summary