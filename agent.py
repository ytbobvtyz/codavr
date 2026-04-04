# agent.py
import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from openai import OpenAI
from dotenv import load_dotenv

from memory import (
    ShortTermMemory,
    WorkingMemory,
    LongTermMemory,
    MemoryEntry,
    ProfileManager,
    PersistenceManager
)

from memory.persistence import PersistenceManager
from invariant_validator import InvariantValidator, validate_input, validate_output

load_dotenv()


class CodeAssistant:
    def __init__(self, session_id: str = None, profile_id: str = None):
        # Инициализация менеджера персистентности
        self.persistence = PersistenceManager()
        
        # Управление сессией
        if session_id is None:
            # Создаём новую сессию
            session_id = self.persistence.create_session("New conversation")
            print(f"✨ Created new session: {session_id}")
        
        self.session_id = session_id
        
        # Инициализация менеджера профилей
        self.profile_manager = ProfileManager()
        
        # Если указан profile_id — активируем его
        if profile_id:
            self.profile_manager.set_active_profile(profile_id)
        
        # Инициализация API
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY not found in .env file.\n"
                "Create .env with: OPENROUTER_API_KEY=your_key_here"
            )
        
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
        )
        
        # Модели
        self.main_model = "stepfun/step-3.5-flash:free" # stepfun/step-3.5-flash:free
        self.summarizer_model = "arcee-ai/trinity-large-preview:free" #nvidia/nemotron-3-nano-30b-a3b:free
        
        # Инициализация памяти
        self.short_term = ShortTermMemory(
            window_size=5,
            summarizer=self._summarize_messages
        )
        self.long_term = LongTermMemory("assistant_memory.db")
        self.working = WorkingMemory()
        
        # Восстанавливаем состояние из БД
        self._load_state()
        
        # Инструменты (tools), доступные агенту
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "update_working_memory",
                    "description": "Update the working memory with current task context. Call this when task goal changes, files are opened, or status updates.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "goal": {"type": "string", "description": "Current main goal"},
                            "status": {"type": "string", "enum": ["planning", "coding", "testing", "done"]},
                            "next_steps": {"type": "array", "items": {"type": "string"}},
                            "files": {"type": "array", "items": {"type": "string"}},
                            "tech_stack": {"type": "array", "items": {"type": "string"}},
                            "decisions": {"type": "object", "additionalProperties": {"type": "string"}},
                            "blockers": {"type": "array", "items": {"type": "string"}},
                        },
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "save_to_long_term_memory",
                    "description": "Save important information to long-term memory. Use for: user preferences, reusable code patterns, architectural decisions, lessons learned.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string", "description": "The content to save"},
                            "entry_type": {
                                "type": "string", 
                                "enum": ["user_preference", "code_pattern", "arch_decision", "lesson_learned"],
                                "description": "Type of memory"
                            },
                            "importance": {"type": "integer", "minimum": 1, "maximum": 5, "description": "Importance 1-5"},
                            "tags": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["content", "entry_type"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "add_task",
                    "description": "Add a subtask to working memory",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "status": {"type": "string", "enum": ["pending", "in_progress", "done"]},
                        },
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "update_task_status",
                    "description": "Update status of a subtask",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "status": {"type": "string", "enum": ["pending", "in_progress", "done"]},
                        },
                        "required": ["name", "status"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "add_blocker",
                    "description": "Report a blocker that prevents progress",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "blocker": {"type": "string"},
                        },
                        "required": ["blocker"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "transition_state",
                    "description": "Move task to next state. Use when: planning complete → execution, code written → validation, validation passed → done, or need redesign → back to planning",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target_state": {
                                "type": "string", 
                                "enum": ["planning", "execution", "validation", "done"],
                                "description": "Target state to transition to"
                            },
                            "reason": {
                                "type": "string",
                                "description": "Reason for transition (e.g., 'code written', 'needs redesign')"
                            }
                        },
                        "required": ["target_state"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "update_current_step",
                    "description": "Update current step and optionally next step",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "current_step": {"type": "string"},
                            "next_step": {"type": "string"}
                        },
                        "required": ["current_step"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "set_expected_from_user",
                    "description": "Tell user what you expect from them (e.g., confirmation, clarification)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "expected": {"type": "string"}
                        },
                        "required": ["expected"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "add_blocker",
                    "description": "Report a blocker that prevents progress",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "blocker": {"type": "string"}
                        },
                        "required": ["blocker"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "resolve_blocker",
                    "description": "Mark a blocker as resolved",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "blocker": {"type": "string"}
                        },
                        "required": ["blocker"]
                    }
                }
            }
        ]
        
        print(f"✅ Agent initialized: session={self.session_id}, profile={self.profile_manager.get_active_profile()}")


    
    def _summarize_messages(self, messages: List) -> str:
        """Суммаризирует старые сообщения для краткосрочной памяти"""
        conversation = "\n".join([f"{m.role}: {m.content}" for m in messages])
        
        prompt = f"""Суммаризируй следующий диалог кратко, но информативно (3-5 предложений). 
Сохрани: основную тему, ключевые вопросы, важные решения пользователя.

Диалог:
{conversation}

Суммаризация:"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.summarizer_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"⚠️ Summarization failed: {e}")
            return f"[Previous conversation: {len(messages)} messages]"
    
    def _recall_relevant_memories(self, user_input: str) -> List[MemoryEntry]:
        """Восстанавливает релевантные записи из долговременной памяти"""
        try:
            return self.long_term.recall(user_input, limit=3)
        except Exception as e:
            print(f"⚠️ Memory recall failed: {e}")
            return []
    
    def _build_system_prompt(self, relevant_memories: List[MemoryEntry]) -> str:
        """Собирает system prompt из профиля и других источников"""
        
        profile_content = self.profile_manager.get_profile_for_prompt()
        long_term_context = self.long_term.format_for_prompt(relevant_memories)
        working_context = self.working.to_system_text()
        
        # Упрощённая инструкция — без криков и противоречий
        unified_rules = """
    ## Task States & Transitions

    You have 4 states: PLANNING, EXECUTION, VALIDATION, DONE.

    **When to transition:**

    | Current State | Trigger | Next State |
    |---------------|---------|------------|
    | PLANNING | User confirms plan OR says "start" | EXECUTION |
    | EXECUTION | Code is written | VALIDATION |
    | EXECUTION | Architecture is wrong | PLANNING |
    | VALIDATION | Tests pass AND user says "done" or "accept" | DONE |
    | VALIDATION | Tests fail or user says "fix" | EXECUTION |
    | DONE | User asks new question | PLANNING |

    **CRITICAL RULES:**
    1. Do NOT ask clarifying questions unless impossible to proceed
    2. When user says "write code" — write code immediately, don't ask
    3. When tests pass and user confirms — transition to DONE
    4. Always call transition_state tool when changing states
    5. Be concise — don't over-explain

    **Tools:**
    - transition_state(target_state, reason)
    - update_current_step(current_step, next_step)
    - update_working_memory(goal, files, blockers)
    - save_to_long_term_memory(content, entry_type)

    ## How to complete a task
    When user says ANY of these, transition to DONE:
    - "задача завершена"
    - "всё готово"
    - "принимаю"
    - "done"
    - "закрывай"

    Example:
    User: "задача завершена" → You call transition_state(target_state="done", reason="user confirmed")
    """
        
        return f"""{profile_content}

    {long_term_context if long_term_context else ""}

    {working_context}

    {unified_rules}
    """

    
    def _build_user_prompt(self, user_input: str) -> str:
        """Собирает user prompt с краткосрочной памятью"""
        short_context = self.short_term.get_context()
        
        if short_context:
            return f"""{short_context}

## Current User Input

{user_input}"""
        else:
            return user_input

    def switch_profile(self, profile_id: str) -> bool:
        """Переключает профиль пользователя"""
        success = self.profile_manager.set_active_profile(profile_id)
        if success:
            print(f"🔄 Switched to profile: {profile_id}")
        return success
    
    def list_profiles(self) -> List[Dict]:
        """Возвращает список доступных профилей"""
        return self.profile_manager.list_profiles()
    
    def get_current_profile_id(self) -> str:
        """Возвращает ID текущего профиля"""
        return self.profile_manager.get_active_profile()
    
    def _execute_tool_calls(self, tool_calls: List) -> str:
        """Выполняет вызовы инструментов и возвращает результат"""
        results = []
        
        for tool_call in tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            
            if name == "update_working_memory":
                # Теперь метод update есть в WorkingMemory
                changed = self.working.update(**args)
                results.append(f"Working memory updated: {', '.join(changed)}")
            
            elif name == "save_to_long_term_memory":
                entry = MemoryEntry(
                    content=args["content"],
                    entry_type=args["entry_type"],
                    importance=args.get("importance", 3),
                    tags=args.get("tags", [])
                )
                entry_id = self.long_term.save(entry)
                results.append(f"Saved to long-term memory (ID: {entry_id})")
            
            elif name == "add_task":
                self.working.add_subtask(args["name"], args.get("status", "pending"))
                results.append(f"Subtask added: {args['name']}")
            
            elif name == "update_task_status":
                success = self.working.update_subtask(args["name"], args["status"])
                results.append(f"Subtask {args['name']} → {args['status']}: {'done' if success else 'not found'}")
            
            elif name == "add_blocker":
                self.working.add_blocker(args["blocker"])
                results.append(f"Blocker added: {args['blocker']}")
            
            elif name == "resolve_blocker":
                success = self.working.resolve_blocker(args["blocker"])
                results.append(f"Blocker {args['blocker']}: {'resolved' if success else 'not found'}")
            
            elif name == "transition_state":
                success = self.working.transition_state(args["target_state"], args.get("reason", ""))
                results.append(f"State transition: {success}")
                if success:
                    results.append(f"Now in state: {self.working.task.state.value}")
            
            elif name == "update_current_step":
                self.working.task.update_progress(args["current_step"], args.get("next_step", ""))
                results.append(f"Current step updated: {args['current_step']}")
            
            elif name == "set_expected_from_user":
                self.working.set_expected_from_user(args["expected"])
                results.append(f"Expected from user: {args['expected']}")
        
        return "\n".join(results) if results else "No tools executed"



    def ask(self, user_input: str) -> str:
        """Основной метод для общения с ассистентом"""
        profile_id = self.profile_manager.get_active_profile()

        # 0. ВАЛИДАЦИЯ ВВОДА ПОЛЬЗОВАТЕЛЯ
        is_valid, invariant_name, violation_reason = validate_input(user_input)
        if not is_valid:
            description = InvariantValidator.get_invariant_description(invariant_name)
            return (f"❌ **Запрос отклонён**\n\n"
                   f"Нарушение инварианта: **{invariant_name}**\n"
                   f"Описание: {description}\n"
                   f"Причина: {violation_reason}\n\n"
                   f"Пожалуйста, переформулируйте запрос в соответствии с ограничениями.")

        # Проверяем, первое ли это сообщение в сессии
        existing_messages = self.persistence.load_conversation(
            session_id=self.session_id,
            profile_id=profile_id
        )
        is_first_message = len(existing_messages) == 0

        # Если первое сообщение — обновляем название сессии
        if is_first_message:
            self.update_session_title(user_input)

        # Сохраняем сообщение пользователя
        self.persistence.save_message(
            "user", user_input,
            session_id=self.session_id,
            profile_id=profile_id
        )

        # Обновляем заголовок сессии при первом сообщении
        total_messages = len(self.persistence.load_conversation(session_id=self.session_id))
        if total_messages == 0:
            self.update_session_title(user_input)

        # Сохраняем сообщение пользователя в БД
        self.persistence.save_message("user", user_input, session_id=self.session_id)

        # 1. Восстанавливаем релевантные воспоминания
        relevant_memories = self._recall_relevant_memories(user_input)

        # 2. Строим промпты
        system_prompt = self._build_system_prompt(relevant_memories)
        user_prompt = self._build_user_prompt(user_input)

        # 3. Добавляем текущее сообщение в краткосрочную память
        self.short_term.add("user", user_input)

        # 4. Формируем messages для API
        messages = [
            {"role": "system", "content": system_prompt},
        ]

        messages.extend(self.short_term.get_recent_window())
        messages.append({"role": "user", "content": user_prompt})

        # 5. Retry mechanism for response validation
        max_retries = 2
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                # 6. API вызов
                response = self.client.chat.completions.create(
                    model=self.main_model,
                    messages=messages,
                    tools=self.tools,
                    tool_choice="auto",
                    temperature=0.7,
                )
                
                assistant_message = response.choices[0].message
                
                # 7. Обрабатываем tool calls
                if assistant_message.tool_calls:
                    self.short_term.add("assistant", json.dumps([tc.function.name for tc in assistant_message.tool_calls]))
                    tool_results = self._execute_tool_calls(assistant_message.tool_calls)
                    
                    messages.append(assistant_message)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": assistant_message.tool_calls[0].id,
                        "content": tool_results
                    })
                    
                    final_response = self.client.chat.completions.create(
                        model=self.main_model,
                        messages=messages,
                        temperature=0.7,
                    )
                    answer = final_response.choices[0].message.content
                else:
                    answer = assistant_message.content
                
                # 8. ВАЛИДАЦИЯ ОТВЕТА АГЕНТА
                is_valid_response, response_invariant_name, violation_reason = validate_output(answer)
                
                if not is_valid_response:
                    retry_count += 1
                    if retry_count <= max_retries:
                        # Add violation info to system prompt for retry
                        description = InvariantValidator.get_invariant_description(response_invariant_name)
                        violation_msg = (f"\n\n⚠️ **CRITICAL: Your previous response violated tech invariant '{response_invariant_name}'**\n"
                                       f"Invariant: {description}\n"
                                       f"Violation: {violation_reason}\n\n"
                                       f"**You MUST comply with all tech invariants in your next response.**\n"
                                       f"Do NOT suggest paid APIs, heavy dependencies, PostgreSQL, or Python 3.12+ features without compatibility checks.")
                        
                        # Modify system prompt to reinforce constraints
                        messages[0]["content"] += violation_msg
                        continue  # Retry
                    else:
                        # Max retries exceeded - return error
                        description = InvariantValidator.get_invariant_description(response_invariant_name)
                        return (f"❌ **Ошибка валидации ответа**\n\n"
                               f"Агент несколько раз нарушил инвариант: **{response_invariant_name}**\n"
                               f"Описание: {description}\n"
                               f"Причина: {violation_reason}\n\n"
                               f"Попробуйте переформулировать запрос или изменить требования.")
                
                # 9. Сохраняем ответ
                self.short_term.add("assistant", answer)
                self.persistence.save_message(
                    "assistant", answer,
                    session_id=self.session_id,
                    profile_id=profile_id
                )
                self._save_state()
                
                return answer
                
            except Exception as e:
                error_msg = str(e)
                if "api_key" in error_msg.lower() or "unauthorized" in error_msg.lower() or "401" in error_msg:
                    return "❌ API key is invalid. Please check your OPENROUTER_API_KEY in .env file."
                return f"❌ Error: {error_msg}"
    
    def show_memory_state(self):
        """Отладка: показывает состояние всей памяти"""
        print("\n" + "="*60)
        print("🧠 MEMORY STATE")
        print("="*60)
        
        print(f"\n📂 Session ID: {self.session_id}")
        
        print("\n📁 META MEMORY (from MD files):")
        meta = self.meta_memory.load_all()
        for name, content in meta.items():
            print(f"  {name}: {content[:100]}..." if len(content) > 100 else f"  {name}: {content}")
        
        print("\n💾 SHORT-TERM MEMORY:")
        print(f"  Total messages: {self.short_term.total_messages}")
        print(f"  Window size: {self.short_term.window_size}")
        summary = self.short_term.summary
        if summary:
            print(f"  Summary: {summary[:200]}...")
        
        print("\n⚙️ WORKING MEMORY:")
        print(self.working.to_system_text())
        
        print("\n📚 LONG-TERM MEMORY (recent by type):")
        for entry_type in ["user_preference", "code_pattern", "arch_decision", "lesson_learned"]:
            entries = self.long_term.get_by_type(entry_type, limit=2)
            if entries:
                print(f"  {entry_type}: {len(entries)} entries")
                for e in entries:
                    print(f"    - {e.content[:80]}...")
    
# agent.py — все методы, работающие с persistence

    def _load_state(self):
        """Загружает состояние из персистентного хранилища"""
        profile_id = self.profile_manager.get_active_profile()
        
        # Загружаем историю диалога в краткосрочную память
        saved_messages = self.persistence.load_conversation(
            session_id=self.session_id,
            profile_id=profile_id
        )
        for msg in saved_messages:
            self.short_term.add(msg["role"], msg["content"])
        
        print(f"📂 Loaded {len(saved_messages)} messages from history (profile: {profile_id})")
        
        # Загружаем рабочую память
        saved_working = self.persistence.load_working_memory(
            session_id=self.session_id,
            profile_id=profile_id
        )
        if saved_working:
            self.working = WorkingMemory.from_dict(saved_working)
            # Исправлено: goal теперь в task.goal
            print(f"📂 Loaded working memory: {self.working.task.goal}")
        
        # Загружаем суммаризацию (если есть)
        saved_summary = self.persistence.load_latest_summary(
            session_id=self.session_id,
            profile_id=profile_id
        )
        if saved_summary:
            # Восстанавливаем суммаризацию в краткосрочную память
            self.short_term._summary = saved_summary
            self.short_term._summary_dirty = False
            print(f"📂 Loaded summary: {saved_summary[:100]}...")
    
    def _save_state(self):
        """Сохраняет текущее состояние в персистентное хранилище"""
        profile_id = self.profile_manager.get_active_profile()
        
        # Сохраняем рабочую память
        self.persistence.save_working_memory(
            self.working.to_dict(),
            session_id=self.session_id,
            profile_id=profile_id
        )
        
        # Сохраняем суммаризацию
        if self.short_term.summary:
            self.persistence.save_summary(
                self.short_term.summary,
                self.short_term.total_messages,
                session_id=self.session_id,
                profile_id=profile_id
            )
    
    def update_session_title(self, user_input: str):
        """Обновляет заголовок сессии на основе первого сообщения"""
        profile_id = self.profile_manager.get_active_profile()
        
        words = user_input.strip().split()[:5]
        title = " ".join(words)
        if len(title) > 50:
            title = title[:47] + "..."
        
        preview = user_input[:100] if len(user_input) > 100 else user_input
        
        self.persistence.update_session_info(
            self.session_id,
            profile_id=profile_id,
            title=title,
            first_preview=preview
        )
        print(f"📝 Session title updated: '{title}'")
    
    def reset_working_memory(self):
        """Сбрасывает рабочую память для новой задачи"""
        self.working.reset()  # Теперь reset есть в WorkingMemory
        self._save_state()
        print("✅ Working memory reset")
    
    def clear_short_term(self):
        """Очищает краткосрочную память"""
        self.short_term.clear()
        print("✅ Short-term memory cleared")