from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

# Убираем Enum, используем простые строки
VALID_STATUSES = ["planning", "coding", "testing", "done"]


@dataclass
class WorkingMemory:
    """Рабочая память — текущий контекст задачи."""
    
    goal: str = ""
    tasks: List[Dict[str, str]] = field(default_factory=list)
    status: str = "planning"  # строка, не Enum
    next_steps: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    tech_stack: List[str] = field(default_factory=list)
    decisions: Dict[str, str] = field(default_factory=dict)
    blockers: List[str] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    
    def update(self, **kwargs) -> List[str]:
        changed = []
        for key, value in kwargs.items():
            if key == "status" and value not in VALID_STATUSES:
                print(f"⚠️ Invalid status '{value}', keeping '{self.status}'")
                continue
            if hasattr(self, key) and getattr(self, key) != value:
                setattr(self, key, value)
                changed.append(key)
        return changed
    
    def add_task(self, name: str, status: str = "pending") -> None:
        self.tasks.append({"name": name, "status": status})
    
    def update_task(self, name: str, status: str) -> bool:
        for task in self.tasks:
            if task["name"] == name:
                task["status"] = status
                return True
        return False
    
    def add_file(self, filepath: str) -> None:
        if filepath not in self.files:
            self.files.append(filepath)
    
    def add_blocker(self, blocker: str) -> None:
        if blocker not in self.blockers:
            self.blockers.append(blocker)
    
    def resolve_blocker(self, blocker: str) -> bool:
        if blocker in self.blockers:
            self.blockers.remove(blocker)
            return True
        return False
    
    def to_dict(self) -> Dict:
        return {
            "goal": self.goal,
            "tasks": self.tasks,
            "status": self.status,  # теперь просто строка
            "next_steps": self.next_steps,
            "files": self.files,
            "tech_stack": self.tech_stack,
            "decisions": self.decisions,
            "blockers": self.blockers,
            "variables": self.variables,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "WorkingMemory":
        memory = cls()
        memory.goal = data.get("goal", "")
        memory.tasks = data.get("tasks", [])
        memory.status = data.get("status", "planning")
        memory.next_steps = data.get("next_steps", [])
        memory.files = data.get("files", [])
        memory.tech_stack = data.get("tech_stack", [])
        memory.decisions = data.get("decisions", {})
        memory.blockers = data.get("blockers", [])
        memory.variables = data.get("variables", {})
        return memory
    
    def to_system_text(self) -> str:
        if not self.goal and not self.tasks and not self.files:
            return "## CURRENT WORKING MEMORY\n(No active task)"
        
        lines = [
            "## CURRENT WORKING MEMORY",
            f"**Goal:** {self.goal}" if self.goal else "",
            f"**Status:** {self.status}",
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
        return not (self.goal or self.tasks or self.files)
    
    def reset(self) -> None:
        self.goal = ""
        self.tasks = []
        self.status = "planning"
        self.next_steps = []
        self.files = []
        self.tech_stack = []
        self.decisions = {}
        self.blockers = []
        self.variables = {}