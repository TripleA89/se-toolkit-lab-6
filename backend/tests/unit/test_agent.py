"""Regression tests for agent.py CLI.

These tests run agent.py as a subprocess and verify the JSON output structure.
Run with: uv run pytest backend/tests/unit/test_agent.py -v
"""

import json
import subprocess
import sys
from pathlib import Path


class TestAgentOutput:
    """Test that agent.py outputs valid JSON with required fields."""

    def test_agent_returns_valid_json_with_required_fields(self):
        """Test that agent.py outputs JSON with 'answer' and 'tool_calls' fields."""
        # Get the path to agent.py (project root)
        project_root = Path(__file__).parent.parent.parent.parent
        agent_path = project_root / "agent.py"
        
        # Run agent.py with a test question
        # Use uv run via shell to ensure proper environment
        result = subprocess.run(
            f"uv run {agent_path} 'What is 2+2?'",
            capture_output=True,
            text=True,
            timeout=60,
            shell=True,
            cwd=project_root,
        )
        
        # Debug: print stderr if test fails
        if result.returncode != 0:
            print(f"stderr: {result.stderr}", file=sys.stderr)
        
        # stdout should contain valid JSON
        stdout = result.stdout.strip()
        assert stdout, f"stdout should not be empty. stderr: {result.stderr}"
        
        # Parse JSON
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            raise AssertionError(f"stdout is not valid JSON: {e}\nstdout: {stdout}")
        
        # Check required fields
        assert "answer" in data, "JSON must contain 'answer' field"
        assert "tool_calls" in data, "JSON must contain 'tool_calls' field"
        
        # Check field types
        assert isinstance(data["answer"], str), "'answer' must be a string"
        assert isinstance(data["tool_calls"], list), "'tool_calls' must be an array"
        
        # Check that answer is non-empty
        assert len(data["answer"]) > 0, "'answer' must not be empty"
