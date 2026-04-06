#!/usr/bin/env python3
"""
Test script for invariant validation
"""

from invariant_validator import validate_input, validate_output, InvariantValidator

def test_user_input_validation():
    """Test user input validation"""
    print("=" * 60)
    print("Testing User Input Validation")
    print("=" * 60)
    
    # Test cases: (input, should_be_valid, expected_invariant)
    test_cases = [
        ("How to use free API?", True, None),
        ("I need a paid API key", False, "free_api_only"),
        ("Use PostgreSQL for database", False, "sqlite_over_postgres"),
        ("Install TensorFlow", False, "minimal_dependencies"),
        ("Write Python 3.12 code", False, "python_310_plus"),
        ("Create a simple SQLite database", True, None),
        ("Use requests library", True, None),
        ("How to use free OpenAI API?", True, None),
    ]
    
    for user_input, expected_valid, expected_invariant in test_cases:
        is_valid, invariant_name, reason = validate_input(user_input)
        status = "✓ PASS" if is_valid == expected_valid and invariant_name == expected_invariant else "✗ FAIL"
        print(f"{status}: '{user_input[:50]}...'")
        print(f"  Expected valid: {expected_valid}, Got: {is_valid}")
        print(f"  Expected invariant: {expected_invariant}, Got: {invariant_name}")
        if reason:
            print(f"  Reason: {reason}")
        print()

def test_agent_response_validation():
    """Test agent response validation"""
    print("=" * 60)
    print("Testing Agent Response Validation")
    print("=" * 60)
    
    # Test cases: (response, should_be_valid, expected_invariant)
    test_cases = [
        ("Here's code using SQLite database", True, None),
        ("You should use PostgreSQL for better performance", False, "sqlite_over_postgres"),
        ("I recommend using paid API service", False, "free_api_only"),
        ("Install TensorFlow: pip install tensorflow", False, "minimal_dependencies"),
        ("import torch", False, "minimal_dependencies"),
        ("Here's code using match-case (Python 3.10+)", True, None),
        ("Use the free API from OpenRouter", True, None),
        # Tool call leak tests
        ("I'll call update_working_memory(goal='test')", False, "no_tool_call_leak"),
        ("<function=transition_state>...</function=transition_state>", False, "no_tool_call_leak"),
        ("<tool>update_current_step(...)</tool>", False, "no_tool_call_leak"),
        ("{\"name\": \"add_task\", \"arguments\": {\"name\": \"test\"}}", False, "no_tool_call_leak"),
        ("Normal response without tool calls", True, None),
    ]
    
    for response, expected_valid, expected_invariant in test_cases:
        is_valid, invariant_name, reason = validate_output(response)
        status = "✓ PASS" if is_valid == expected_valid and invariant_name == expected_invariant else "✗ FAIL"
        print(f"{status}: '{response[:50]}...'")
        print(f"  Expected valid: {expected_valid}, Got: {is_valid}")
        print(f"  Expected invariant: {expected_invariant}, Got: {invariant_name}")
        if reason:
            print(f"  Reason: {reason}")
        print()

def test_invariant_descriptions():
    """Test invariant descriptions are available"""
    print("=" * 60)
    print("Testing Invariant Descriptions")
    print("=" * 60)
    
    for invariant_name in InvariantValidator.INVARIANTS.keys():
        desc = InvariantValidator.get_invariant_description(invariant_name)
        print(f"✓ {invariant_name}: {desc[:80]}...")
    print()

if __name__ == "__main__":
    test_user_input_validation()
    test_agent_response_validation()
    test_invariant_descriptions()
    print("All tests completed!")
