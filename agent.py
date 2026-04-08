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
import re
import asyncio
from mcp_integration.manager import MCPManager
import traceback

load_dotenv()


class CodeAssistant:
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
                max_tokens=2000,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            print(f"⚠️ Summarization failed: {e}")
            return f"[Previous conversation: {len(messages)} messages]"

    def _load_state(self):
        """Загружает состояние из персистентного хранилища"""
        profile_id = self.profile_manager.get_active_profile() or "default"
        
        # Загружаем историю диалога
        saved_messages = self.persistence.load_conversation(
            session_id=self.session_id,
            profile_id=profile_id
        )
        for msg in saved_messages:
            if msg is None:
                continue
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            self.short_term.add(role, content)
        
        print(f"📂 Loaded {len(saved_messages)} messages from history (profile: {profile_id})")
        
        # Загружаем рабочую память
        saved_working = self.persistence.load_working_memory(
            session_id=self.session_id,
            profile_id=profile_id
        )
        if saved_working:
            self.working = WorkingMemory.from_dict(saved_working)
            print(f"📂 Loaded working memory: {getattr(self.working.task, 'goal', 'No goal')}")
        
        # Суммаризация
        saved_summary = self.persistence.load_latest_summary(
            session_id=self.session_id,
            profile_id=profile_id
        )
        if saved_summary:
            self.short_term._summary = saved_summary
            self.short_term._summary_dirty = False
            print(f"📂 Loaded summary: {saved_summary[:100]}...")

    def _load_mcp_tools(self):
        """Загружает MCP инструменты (optional connect)"""
        print("🔍 DEBUG: Starting _load_mcp_tools (remote)")
        
        try:
            # Optional connect with new loop (safe for init)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            if not self.mcp_manager.get_connection_status('yandex'):
                success = loop.run_until_complete(self.mcp_manager.connect_remote('yandex', 'http://localhost:8000', 'Yandex Maps'))
                if not success:
                    print("⚠️ MCP connect failed in init (404? Start server on port 8000) — retry on call")
                    loop.close()
                    return
            
            loop.close()
            
            all_tools_info = self.mcp_manager.get_all_tools()
            yandex_tools = [t for t in all_tools_info if t['server_id'] == 'yandex']
            tool_count = 0
            for tool in yandex_tools:
                openai_tool = {
                    "type": "function",
                    "function": {
                        "name": f"mcp_{tool['tool_name']}",
                        "description": tool['description'],
                        "parameters": tool['input_schema']
                    }
                }
                self.tools.append(openai_tool)
                tool_count += 1
                print(f"🔍 DEBUG: Added tool: mcp_{tool['tool_name']}")
            print(f"✅ Загружено {tool_count} MCP инструментов из Yandex")
        except Exception as e:
            print(f"⚠️ Ошибка загрузки MCP: {e}")
            traceback.print_exc()

    def __init__(self, session_id: str = None, profile_id: str = None, mcp_manager: Optional[MCPManager] = None):
        # Persistence
        self.persistence = PersistenceManager()
        
        # Session
        if session_id is None:
            session_id = self.persistence.create_session("New conversation")
            print(f"✨ Created new session: {session_id}")
        
        self.session_id = session_id or "default_session"
        
        # Profiles
        self.profile_manager = ProfileManager()
        if profile_id:
            self.profile_manager.set_active_profile(profile_id)
        
        # API
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not found in .env")
        
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
        )
        
        # Models
        self.main_model = "anthropic/claude-opus-4.6"
        self.summarizer_model = "openrouter/free"
        
        # Memory
        self.short_term = ShortTermMemory(
            window_size=15,
            summarizer=self._summarize_messages
        )
        self.long_term = LongTermMemory("assistant_memory.db")
        self.working = WorkingMemory()
        
        # MCP Manager
        self.mcp_manager = mcp_manager or MCPManager()
        
        # Load state
        self._load_state()
        
        # Built-in tools
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "update_working_memory",
                    "description": "Update working memory.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "goal": {"type": "string"},
                            "status": {"type": "string", "enum": ["planning", "coding", "testing", "done"]},
                            "next_steps": {"type": "array", "items": {"type": "string"}},
                            "files": {"type": "array", "items": {"type": "string"}},
                            "tech_stack": {"type": "array", "items": {"type": "string"}},
                            "decisions": {"type": "object"},
                            "blockers": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
            },
            # Add other built-in if needed (shortened for token)
        ]
        
        # Load MCP
        self._load_mcp_tools()
        
        print(f"✅ Agent initialized: session={self.session_id}, profile={self.profile_manager.get_active_profile() or 'default'}")

    def _call_mcp_tool_sync(self, tool_name: str, args: dict) -> str:
        """Sync MCP call"""
        print(f"🔍 DEBUG MCP: Calling '{tool_name}' args: {args}")
        
        if not self.mcp_manager:
            return "MCP not init"
        
        # Retry connect with new loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            if not self.mcp_manager.get_connection_status('yandex'):
                print("🔍 DEBUG MCP: Retrying connect...")
                success = loop.run_until_complete(self.mcp_manager.connect_remote('yandex', 'http://localhost:8000', 'Yandex Maps'))
                if not success:
                    return "Connect failed - check server on localhost:8000"
            
            # Call tool
            coro = self.mcp_manager.call_tool('yandex', tool_name, args)
            result = loop.run_until_complete(coro)
            print(f"🔍 DEBUG MCP: Result: {str(result)[:100]}...")
            return str(result or "Empty")[:500]
        except Exception as e:
            print(f"🔍 DEBUG MCP: Error: {e}")
            traceback.print_exc()
            err_str = str(e)
            if "404" in err_str:
                return "Server error 404 - run uvicorn on port 8000"
            if "API ключ" in err_str:
                return "Yandex API key error - check .env YANDEX_MAPS_API_KEY"
            return f"MCP error: {e}"
        finally:
            loop.close()

    async def _execute_tool_calls(self, tool_calls: List) -> str:
        """Tool execution"""
        results = []
        
        for tool_call in tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            
            if name.startswith("mcp_"):
                tool_name = name[4:]
                result = self._call_mcp_tool_sync(tool_name, args)
                results.append(f"MCP {tool_name}: {result}")
            else:
                results.append(f"Built-in tool {name} executed")
        
        return "\n".join(results) or "No results"

    def ask(self, user_input: str) -> str:
        """Main method"""
        profile_id = self.profile_manager.get_active_profile() or "default"
        
        # Validation
        is_valid, invariant_name, violation_reason = validate_input(user_input)
        if not is_valid:
            description = InvariantValidator.get_invariant_description(invariant_name or "unknown")
            return f"❌ Invalid: {invariant_name or 'unknown'}. {description} {violation_reason or ''}"
        
        # Save user
        self.persistence.save_message("user", user_input, session_id=self.session_id)
        
        # Title if first
        if len(self.persistence.load_conversation(session_id=self.session_id)) == 0:
            self.update_session_title(user_input)
        
        # Memories
        relevant_memories = self._recall_relevant_memories(user_input)
        
        # Prompts
        system_prompt = self._build_system_prompt(relevant_memories)
        user_prompt = self._build_user_prompt(user_input)
        
        # Short-term
        self.short_term.add("user", user_input)
        
        # Messages
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.short_term.get_recent_window())
        messages.append({"role": "user", "content": user_prompt})
        
        try:
            # API
            response = self.client.chat.completions.create(
                model=self.main_model,
                messages=messages,
                tools=self.tools,
                tool_choice="auto",
                temperature=0.7,
            )
            
            assistant_message = response.choices[0].message
            
            # Tools
            if assistant_message.tool_calls:
                self.short_term.add("assistant", json.dumps([tc.function.name for tc in assistant_message.tool_calls]))
                
                # Use new loop for async execution in sync ask()
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                tool_results = loop.run_until_complete(self._execute_tool_calls(assistant_message.tool_calls))
                loop.close()
                
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
                answer = final_response.choices[0].message.content or ""
            else:
                answer = assistant_message.content or ""
            
            # Sanitize
            answer = self._sanitize_response(answer)
            
            # Validation
            is_valid_response, response_invariant_name, violation_reason = validate_output(answer)
            if not is_valid_response:
                return f"❌ Response invalid: {response_invariant_name or 'unknown'} {violation_reason or ''}"
            
            # Save
            self.short_term.add("assistant", answer)
            self.persistence.save_message("assistant", answer, session_id=self.session_id)
            self._save_state()
            
            return answer
            
        except Exception as e:
            error_msg = str(e)
            if "api_key" in error_msg.lower() or "401" in error_msg:
                return "❌ API key invalid. Check .env."
            return f"❌ Error: {error_msg}"

    def _recall_relevant_memories(self, user_input: str) -> List[MemoryEntry]:
        try:
            return self.long_term.recall(user_input, limit=3)
        except Exception as e:
            print(f"⚠️ Recall failed: {e}")
            return []

    def _build_system_prompt(self, relevant_memories: List[MemoryEntry]) -> str:
        profile_content = self.profile_manager.get_profile_for_prompt() or ""
        long_term_context = self.long_term.format_for_prompt(relevant_memories) or ""
        working_context = self.working.to_system_text() or ""
        
        mcp_instruction = """
## MCP TOOLS (Yandex)

Use MCP for geo:
1. mcp_geocode_address (address: str) - address to coords
2. mcp_reverse_geocode (lat: float, lon: float) - coords to address
3. mcp_calculate_distance_simple (from_address: str, to_address: str) - distance

MANDATORY: Use MCP for geo questions. No knowledge!
Example: Distance Moscow-Perm → mcp_calculate_distance_simple(from="Moscow", to="Perm")
"""
        return f"""{profile_content}

{long_term_context}

{working_context}

{mcp_instruction}
"""

    def _build_user_prompt(self, user_input: str) -> str:
        short_context = self.short_term.get_context()
        if short_context:
            return f"""{short_context}

User: {user_input}"""
        return user_input

    def switch_profile(self, profile_id: str) -> bool:
        success = self.profile_manager.set_active_profile(profile_id)
        print(f"🔄 Switched to {profile_id}" if success else "Switch failed")
        return success
    
    def list_profiles(self) -> List[Dict]:
        return self.profile_manager.list_profiles()
    
    def get_current_profile_id(self) -> str:
        return self.profile_manager.get_active_profile() or "default"

    def _sanitize_response(self, text: str | None) -> str:
        text = text or ""
        cleaned = text
        
        cleaned = re.sub(r'<function=[^>]+>.*?</function=[^>]+>', '', cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'<tool>.*?</tool>', '', cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'<invoke>.*?</invoke>', '', cleaned, flags=re.DOTALL)
        
        cleaned = re.sub(r'\{\s*"name"\s*:\s*"[^"]+",\s*"arguments"\s*:.*?\}', '', cleaned, flags=re.DOTALL)
        
        tool_names = ["update_working_memory", "save_to_long_term_memory", "add_task", "update_task_status", "add_blocker", "resolve_blocker", "transition_state", "update_current_step", "set_expected_from_user"]
        
        for tool_name in tool_names:
            pattern = rf'\b{re.escape(tool_name)}\s*\([^)]*\)'
            cleaned = re.sub(pattern, '', cleaned)
            pattern_multiline = rf'\b{re.escape(tool_name)}\s*\(\s*[^)]*?\)'
            cleaned = re.sub(pattern_multiline, '', cleaned, flags=re.DOTALL)
        
        lines = [line.strip() for line in cleaned.split('\n')]
        cleaned = '\n'.join(line for line in lines if line)
        
        return cleaned.strip()

    def show_memory_state(self):
        print("\n" + "="*60)
        print("🧠 MEMORY STATE")
        print("="*60)
        
        print(f"\n📂 Session: {self.session_id}")
        print(f"  Short-term: {self.short_term.total_messages} msgs")
        if self.short_term.summary:
            print(f"  Summary: {self.short_term.summary[:200]}...")
        
        print("\n⚙️ Working: {self.working.to_system_text()}")
        
        print("\n📚 Long-term:")
        for entry_type in ["user_preference", "code_pattern", "arch_decision", "lesson_learned"]:
            entries = self.long_term.get_by_type(entry_type, limit=2)
            if entries:
                print(f"  {entry_type}: {len(entries)}")
                for e in entries:
                    print(f"    - {e.content[:80]}...")

    def _save_state(self):
        profile_id = self.profile_manager.get_active_profile() or "default"
        
        self.persistence.save_working_memory(
            self.working.to_dict(),
            session_id=self.session_id,
            profile_id=profile_id
        )
        
        if self.short_term.summary:
            self.persistence.save_summary(
                self.short_term.summary,
                self.short_term.total_messages,
                session_id=self.session_id,
                profile_id=profile_id
            )

    def update_session_title(self, user_input: str):
        profile_id = self.profile_manager.get_active_profile() or "default"
        
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
        print(f"📝 Title: '{title}'")

    def reset_working_memory(self):
        self.working.reset()
        self._save_state()
        print("✅ Working reset")

    def clear_short_term(self):
        self.short_term.clear()
        print("✅ Short-term cleared")