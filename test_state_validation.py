#!/usr/bin/env python3
"""
Unit tests for state transition validation in task_state.py
"""

import unittest
from memory.task_state import TaskContext, TaskState


class TestStateValidation(unittest.TestCase):
    """Test cases for state transition validation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.context = TaskContext()
    
    def test_valid_transitions(self):
        """Test that valid transitions work correctly"""
        # PLANNING -> EXECUTION
        self.assertTrue(self.context.transition(TaskState.EXECUTION, "plan confirmed"))
        self.assertEqual(self.context.state, TaskState.EXECUTION)
        self.assertIsNone(self.context.last_error)
        
        # EXECUTION -> VALIDATION
        self.assertTrue(self.context.transition(TaskState.VALIDATION, "code written"))
        self.assertEqual(self.context.state, TaskState.VALIDATION)
        self.assertIsNone(self.context.last_error)
        
        # VALIDATION -> DONE
        self.assertTrue(self.context.transition(TaskState.DONE, "tests passed"))
        self.assertEqual(self.context.state, TaskState.DONE)
        self.assertIsNone(self.context.last_error)
        
        # DONE -> PLANNING
        self.assertTrue(self.context.transition(TaskState.PLANNING, "new task"))
        self.assertEqual(self.context.state, TaskState.PLANNING)
        self.assertIsNone(self.context.last_error)
    
    def test_invalid_transitions(self):
        """Test that invalid transitions are blocked with proper error messages"""
        # Test PLANNING -> DONE (invalid)
        result = self.context.transition(TaskState.DONE, "invalid attempt")
        self.assertFalse(result)
        self.assertEqual(self.context.state, TaskState.PLANNING)  # State unchanged
        self.assertEqual(self.context.last_error, "Невозможно перейти из planning в done")
        
        # Test EXECUTION -> DONE (invalid)
        self.context.transition(TaskState.EXECUTION, "move to execution")
        result = self.context.transition(TaskState.DONE, "invalid attempt")
        self.assertFalse(result)
        self.assertEqual(self.context.state, TaskState.EXECUTION)  # State unchanged
        self.assertEqual(self.context.last_error, "Невозможно перейти из execution в done")
        
        # Test VALIDATION -> PLANNING (invalid)
        self.context.transition(TaskState.VALIDATION, "move to validation")
        result = self.context.transition(TaskState.PLANNING, "invalid attempt")
        self.assertFalse(result)
        self.assertEqual(self.context.state, TaskState.VALIDATION)  # State unchanged
        self.assertEqual(self.context.last_error, "Невозможно перейти из validation в planning")
    
    def test_same_state_transition(self):
        """Test that transitioning to the same state is blocked"""
        # Try to transition PLANNING to PLANNING
        result = self.context.transition(TaskState.PLANNING, "same state attempt")
        self.assertFalse(result)
        self.assertEqual(self.context.state, TaskState.PLANNING)  # State unchanged
        self.assertEqual(self.context.last_error, "Невозможно перейти из planning в planning")
    
    def test_can_transition_method(self):
        """Test the can_transition method directly"""
        # Test valid transitions from PLANNING
        self.assertTrue(self.context.can_transition(TaskState.EXECUTION))
        self.assertFalse(self.context.can_transition(TaskState.VALIDATION))
        self.assertFalse(self.context.can_transition(TaskState.DONE))
        
        # Move to EXECUTION and test from there
        self.context.transition(TaskState.EXECUTION, "test")
        self.assertTrue(self.context.can_transition(TaskState.PLANNING))
        self.assertTrue(self.context.can_transition(TaskState.VALIDATION))
        self.assertFalse(self.context.can_transition(TaskState.DONE))
    
    def test_error_clearing_on_success(self):
        """Test that last_error is cleared after successful transition"""
        # First attempt an invalid transition to set an error
        self.context.transition(TaskState.DONE, "invalid")
        self.assertIsNotNone(self.context.last_error)
        
        # Then perform a valid transition
        self.context.transition(TaskState.EXECUTION, "valid")
        self.assertIsNone(self.context.last_error)
    
    def test_transition_history_with_errors(self):
        """Test that transition history is only updated for successful transitions"""
        # Attempt invalid transition (should not be in history)
        self.context.transition(TaskState.DONE, "invalid attempt")
        self.assertEqual(len(self.context.transitions), 0)
        
        # Perform valid transition (should be in history)
        self.context.transition(TaskState.EXECUTION, "valid transition")
        self.assertEqual(len(self.context.transitions), 1)
        self.assertEqual(self.context.transitions[0]["from"], "planning")
        self.assertEqual(self.context.transitions[0]["to"], "execution")
    
    def test_all_possible_transitions(self):
        """Test all possible state transitions to ensure validation matrix is correct"""
        transitions_matrix = {
            TaskState.PLANNING: [TaskState.EXECUTION],
            TaskState.EXECUTION: [TaskState.PLANNING, TaskState.VALIDATION],
            TaskState.VALIDATION: [TaskState.DONE, TaskState.EXECUTION],
            TaskState.DONE: [TaskState.PLANNING],
        }
        
        for from_state, allowed_states in transitions_matrix.items():
            # Set context to from_state
            self.context.state = from_state
            
            for to_state in TaskState:
                if to_state in allowed_states:
                    # Should be valid
                    self.assertTrue(
                        self.context.can_transition(to_state),
                        f"Transition {from_state.value} -> {to_state.value} should be valid"
                    )
                else:
                    # Should be invalid
                    self.assertFalse(
                        self.context.can_transition(to_state),
                        f"Transition {from_state.value} -> {to_state.value} should be invalid"
                    )


if __name__ == "__main__":
    unittest.main()