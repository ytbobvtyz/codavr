# agent.py
import os
from openai import OpenAI
from dotenv import load_dotenv
from memory import ShortTermMemory, WorkingMemory, LongTermMemory

# Загружаем .env при импорте
load_dotenv()

SYSTEM_PROMPT = """You are a code assistant for a Python/FastAPI/React developer.

Your capabilities:
- Read and analyze code files
- Suggest improvements and write code
- Help debug issues
- Explain code architecture

Rules:
- Always show code changes as diffs when possible
- Never suggest destructive operations without warning
- Prefer async SQLAlchemy patterns when working with databases
- Follow PEP 8 for Python code
- For React, use functional components with hooks

You have access to three memory layers:
- Short-term: current conversation flow
- Working: current task context (open files, task variables)
- Long-term: user preferences and project patterns

Always consider the working memory context when answering.
Use long-term memory to recall past solutions and user preferences."""

class CodeAssistant:
    def __init__(self):
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
        
        self.short_term = ShortTermMemory()
        self.working = WorkingMemory()
        self.long_term = LongTermMemory()
        
        self.model = "stepfun/step-3.5-flash:free"
    
    def _build_prompt(self, user_input: str) -> list:
        """Собирает messages с system prompt и всей памятью"""
        
        working_context = self.working.get_context()
        long_term_context = self.long_term.get_context(user_input)
        conversation = self.short_term.get_context()
        
        user_prompt = f"""
{long_term_context}

CURRENT TASK CONTEXT:
{working_context}

CONVERSATION HISTORY:
{self._format_conversation(conversation)}

USER: {user_input}

ASSISTANT:"""
        
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
    
    def _format_conversation(self, messages):
        formatted = []
        for msg in messages[-5:]:
            formatted.append(f"{msg['role'].upper()}: {msg['content']}")
        return "\n".join(formatted)
    
    def _decide_what_to_save(self, user_input: str, response: str):
        self.short_term.add("user", user_input)
        self.short_term.add("assistant", response)
        
        if "task:" in user_input.lower() or "задача:" in user_input:
            task = user_input.split(":", 1)[-1].strip()
            self.working.set_task(task)
            print(f"💾 Saved to working memory: new task '{task}'")
        
        if "file:" in user_input.lower():
            import re
            files = re.findall(r'file:\s*([^\s]+)', user_input)
            for file in files:
                self.working.add_open_file(file)
                print(f"💾 Saved to working memory: opened file {file}")
        
        important_keywords = ["learn", "запомни", "important", "важно", "preference", "предпочтение"]
        if any(keyword in user_input.lower() for keyword in important_keywords):
            self.long_term.save_user_preference(user_input)
            print(f"🧠 Saved to long-term memory: user preference")
        
        if "pattern:" in user_input.lower() or "шаблон:" in user_input:
            pattern = user_input.split(":", 1)[-1].strip()
            self.long_term.save_project_pattern(pattern)
            print(f"🧠 Saved to long-term memory: code pattern")
    
    def ask(self, user_input: str) -> str:
        try:
            messages = self._build_prompt(user_input)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
            )
            
            answer = response.choices[0].message.content
            self._decide_what_to_save(user_input, answer)
            return answer
            
        except Exception as e:
            error_msg = str(e)
            if "api_key" in error_msg.lower() or "unauthorized" in error_msg.lower() or "401" in error_msg:
                return "❌ API key is invalid or not set. Please check your OPENROUTER_API_KEY in .env file."
            return f"❌ Error: {error_msg}"
    
    def show_memory_state(self):
        print("\n" + "="*50)
        print("🧠 MEMORY STATE")
        print("="*50)
        
        print("\n📝 SHORT-TERM (last 5 messages):")
        for msg in self.short_term.messages[-5:]:
            print(f"  {msg['role']}: {msg['content'][:50]}...")
        
        print("\n⚙️ WORKING MEMORY:")
        print(f"  Current task: {self.working.current_task}")
        print(f"  Open files: {self.working.open_files}")
        print(f"  Variables: {self.working.task_variables}")
        
        print("\n💾 LONG-TERM (recent):")
        recent = self.long_term.get_context()
        print(f"  {recent[:200]}...")