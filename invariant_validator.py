# invariant_validator.py
"""
Validation module for tech invariants.
Ensures user input and agent responses comply with defined constraints.
"""

import re
from typing import Tuple, List, Optional


class InvariantViolationError(Exception):
    """Raised when an invariant is violated"""
    pass


class InvariantValidator:
    """Validates content against tech invariants"""
    
    # Invariant definitions with violation keywords/patterns
    INVARIANTS = {
        "no_tool_call_leak": {
            "description": "Ответ не должен содержать синтаксис вызова инструментов в текстовом виде",
            "violation_patterns": [
                r'<function=[^>]+>.*?</function=[^>]+>',
                r'<tool>.*?</tool>',
                r'<invoke>.*?</invoke>',
                r'\{\s*"name"\s*:\s*"[^"]+",\s*"arguments"\s*:.*?\}',
                r'\bupdate_working_memory\s*\(',
                r'\bsave_to_long_term_memory\s*\(',
                r'\badd_task\s*\(',
                r'\bupdate_task_status\s*\(',
                r'\badd_blocker\s*\(',
                r'\bresolve_blocker\s*\(',
                r'\btransition_state\s*\(',
                r'\bupdate_current_step\s*\(',
                r'\bset_expected_from_user\s*\('
            ]
        },
        "free_api_only": {
            "description": "Только бесплатные API. Никаких платных подписок.",
            "violation_keywords": [
                "paid api", "платный api", "subscription", "подписка",
                "pay for", "оплатить", "купить", "purchase", "buy",
                "premium", "pro plan", "enterprise plan", "billing",
                "credit card", "карта", "цена", "стоимость", "price",
                "trial", "триал", "free trial", "пробный период"
            ],
            "allowed_patterns": [
                r"free\s*api", r"бесплатный\s*api", r"open\s*source",
                r"no\s*cost", r"без\s*платы", r"public\s*api"
            ]
        },
        "python_310_plus": {
            "description": "Код должен работать на Python 3.10+",
            "violation_patterns": [
                # Python 3.11+ features that wouldn't work on 3.10
                r"except\s+\w+\s+as\s+\w+:",  # except Exception as e: is fine, but grouped except is 3.11+
                r"match\s+\w+:",  # match-case is 3.10+ but we're checking for 3.12+ features
                r"type\s+dict\[",  # PEP 585 is 3.9+, but some 3.12+ type syntax
                r"\.__\w+__\s*=",  # Some dunder methods in 3.12+
            ],
            "allowed_patterns": [
                r"def\s+\w+\s*\(.*\)\s*->",  # Type hints are fine
                r"match\s+\w+:",  # match-case is 3.10+ so allowed
                r"except\s*\w+\s*:",  # Basic except is fine
            ]
        },
        "minimal_dependencies": {
            "description": "Минимум внешних зависимостей",
            "violation_keywords": [
                "install tensorflow", "установить tensorflow",
                "install torch", "установить torch",
                "install django", "установить django",
                "heavy library", "тяжёлая библиотека",
                "large dependency", "большая зависимость",
                "add dependency", "добавить зависимость",
                "pip install", "пип инсталл",
                "conda install", "конда инсталл"
            ],
            "allowed_libs": [
                "requests", "httpx", "aiohttp",  # HTTP clients
                "pydantic", "pandas", "numpy",  # Data handling
                "fastapi", "flask", "starlette",  # Web frameworks
                "sqlalchemy", "aiosqlite",  # Database
                "python-dotenv", "click", "rich",  # Utilities
                "openai", "anthropic",  # AI clients
                "pytest", "hypothesis",  # Testing
            ]
        },
        "sqlite_over_postgres": {
            "description": "Для хранения данных используем SQLite, не PostgreSQL",
            "violation_keywords": [
                "postgresql", "postgres", "postgresql database",
                "миграция на postgresql", "migrate to postgresql",
                "use postgres", "использовать postgres",
                "postgres instead", "postgresql instead",
                "switch to postgres", "перейти на postgres"
            ],
            "allowed_patterns": [
                r"sqlite", r"sqlite3", r"\.db", r"database.*sqlite",
                r"local.*database", "локальная база"
            ]
        }
    }
    
    @classmethod
    def validate_user_input(cls, user_input: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate user input against invariants.
        Returns: (is_valid, invariant_name, violation_reason)
        """
        if not user_input:
            return True, None, None
            
        user_input_lower = user_input.lower()
        
        # Check free_api_only invariant - look for paid service keywords
        paid_keywords = [
            "paid api", "платный api", "subscription", "подписка",
            "pay for", "оплатить", "купить", "purchase", "buy",
            "premium", "pro plan", "enterprise plan", "billing",
            "credit card", "карта", "цена", "стоимость", "price",
            "paid service", "платный сервис", "paid subscription"
        ]
        for keyword in paid_keywords:
            if keyword in user_input_lower:
                return False, "free_api_only", "Предложено использовать платный сервис"
        
        # Check python_310_plus - user asking for Python 3.12+ specific features
        python_312_keywords = ["python 3.12", "python 3.13", "python 3.14", "3.12+", "3.13+"]
        for keyword in python_312_keywords:
            if keyword in user_input_lower:
                return False, "python_310_plus", "Запрос о Python 3.12+ без проверки совместимости"
        
        # Check minimal_dependencies - user requesting heavy libraries
        heavy_libs = ["tensorflow", "torch", "django", "pytorch"]
        for lib in heavy_libs:
            if lib in user_input_lower:
                return False, "minimal_dependencies", f"Запрошена тяжёлая библиотека: {lib}"
        
        # Check sqlite_over_postgres - user requesting PostgreSQL
        for keyword in cls.INVARIANTS["sqlite_over_postgres"]["violation_keywords"]:
            if keyword in user_input_lower:
                return False, "sqlite_over_postgres", f"Запрошена миграция на PostgreSQL"
        
        return True, None, None
    
    @classmethod
    def validate_agent_response(cls, response: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate agent's response against invariants.
        Returns: (is_valid, invariant_name, violation_reason)
        """
        if not response:
            return True, None, None
            
        # Check for tool call syntax leakage FIRST (highest priority)
        tool_leak_invariant = cls.INVARIANTS.get("no_tool_call_leak")
        if tool_leak_invariant:
            for pattern in tool_leak_invariant["violation_patterns"]:
                if re.search(pattern, response, flags=re.DOTALL | re.IGNORECASE):
                    return False, "no_tool_call_leak", f"Обнаружен синтаксис вызова инструментов в тексте ответа"
        
        response_lower = response.lower()
        
        # Check free_api_only - agent suggesting paid services
        paid_phrases = [
            "paid api", "платный api", "subscription", "подписка",
            "you need to pay", "нужно оплатить", "купить api",
            "premium version", "pro version", "enterprise",
            "billing", "цена", "стоимость", "price"
        ]
        for phrase in paid_phrases:
            if phrase in response_lower:
                return False, "free_api_only", f"Агент предложил платный сервис: '{phrase}'"
        
        # Check python_310_plus - agent using Python 3.12+ syntax
        # Look for match-case with guards (3.10+ is ok, but some 3.12+ features)
        if re.search(r"except\s+\w+\s+as\s+\w+\s*:", response):
            # This is actually 3.10+ syntax, but could be 3.11+ grouped except
            if re.search(r"except\s+\w+\s+as\s+\w+\s*:\s*except\s+\w+\s+as\s+\w+:", response):
                return False, "python_310_plus", "Использован синтаксис группового except (Python 3.11+)"
        
        # Check minimal_dependencies - agent suggesting heavy libraries
        heavy_libs = {
            "tensorflow": "TensorFlow",
            "torch": "PyTorch", 
            "django": "Django",
            "tensorflow": "TensorFlow",
            "pytorch": "PyTorch"
        }
        for lib_key, lib_name in heavy_libs.items():
            if f"import {lib_key}" in response_lower or f"from {lib_key}" in response_lower:
                return False, "minimal_dependencies", f"Агент использовал тяжёлую библиотеку: {lib_name}"
        
        # Check if agent suggests installing heavy dependencies
        install_patterns = [
            r"pip\s+install\s+(tensorflow|torch|django)",
            r"установите\s+(tensorflow|torch|django)",
            r"install\s+(tensorflow|torch|django)"
        ]
        for pattern in install_patterns:
            if re.search(pattern, response_lower):
                return False, "minimal_dependencies", "Агент предложил установить тяжёлую библиотеку"
        
        # Check sqlite_over_postgres - agent suggesting PostgreSQL
        postgres_terms = ["postgresql", "postgres", "postgres db"]
        for term in postgres_terms:
            if term in response_lower:
                return False, "sqlite_over_postgres", f"Агент предложил использовать PostgreSQL"
        
        return True, None, None
    
    @classmethod
    def get_invariant_description(cls, invariant_name: str) -> str:
        """Get description of an invariant"""
        return cls.INVARIANTS.get(invariant_name, {}).get("description", "Unknown invariant")


def validate_input(user_input: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """Convenience function for validating user input"""
    return InvariantValidator.validate_user_input(user_input)


def validate_output(response: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """Convenience function for validating agent response"""
    return InvariantValidator.validate_agent_response(response)
