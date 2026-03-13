"""Regression tests for agent.py CLI.

These tests run agent.py as a subprocess and verify the JSON output structure.
Run with: uv run pytest tests/test_agent.py -v
"""

import json
import subprocess
import sys
from pathlib import Path


class TestAgentOutput:
    """Test that agent.py outputs valid JSON with required fields."""

    def test_agent_returns_valid_json_with_required_fields(self):
        """Test that agent.py outputs JSON with 'answer' and 'tool_calls' fields."""
        project_root = Path(__file__).parent.parent
        agent_path = project_root / "agent.py"

        result = subprocess.run(
            ["uv", "run", str(agent_path), "What is 2+2?"],
            capture_output=True,
            text=True,
            timeout=60,
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


class TestDocumentationAgent:
    """Test that agent.py uses tools correctly for documentation questions."""

    def test_agent_uses_read_file_for_merge_conflict_question(self):
        """Test that agent uses read_file tool when asked about merge conflicts."""
        project_root = Path(__file__).parent.parent
        agent_path = project_root / "agent.py"

        result = subprocess.run(
            ["uv", "run", str(agent_path), "How do you resolve a merge conflict?"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=project_root,
        )

        if result.returncode != 0:
            print(f"stderr: {result.stderr}", file=sys.stderr)

        stdout = result.stdout.strip()
        assert stdout, f"stdout should not be empty. stderr: {result.stderr}"

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            raise AssertionError(f"stdout is not valid JSON: {e}\nstdout: {stdout}")

        # Check required fields
        assert "answer" in data, "JSON must contain 'answer' field"
        assert "tool_calls" in data, "JSON must contain 'tool_calls' field"
        assert "source" in data, "JSON must contain 'source' field"

        # Check that read_file was used
        tool_calls = data["tool_calls"]
        assert len(tool_calls) > 0, "Agent should have called at least one tool"
        
        tools_used = [tc.get("tool") for tc in tool_calls]
        assert "read_file" in tools_used, f"Agent should use read_file tool. Tools used: {tools_used}"

        # Check that source contains wiki/git-workflow.md
        source = data.get("source", "")
        assert "git-workflow.md" in source, f"Source should reference git-workflow.md, got: {source}"

    def test_agent_uses_list_files_for_wiki_question(self):
        """Test that agent uses list_files tool when asked about wiki files."""
        project_root = Path(__file__).parent.parent
        agent_path = project_root / "agent.py"

        result = subprocess.run(
            ["uv", "run", str(agent_path), "What files are in the wiki?"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=project_root,
        )

        if result.returncode != 0:
            print(f"stderr: {result.stderr}", file=sys.stderr)

        stdout = result.stdout.strip()
        assert stdout, f"stdout should not be empty. stderr: {result.stderr}"

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            raise AssertionError(f"stdout is not valid JSON: {e}\nstdout: {stdout}")

        # Check required fields
        assert "answer" in data, "JSON must contain 'answer' field"
        assert "tool_calls" in data, "JSON must contain 'tool_calls' field"

        # Check that list_files was used
        tool_calls = data["tool_calls"]
        assert len(tool_calls) > 0, "Agent should have called at least one tool"
        
        tools_used = [tc.get("tool") for tc in tool_calls]
        assert "list_files" in tools_used, f"Agent should use list_files tool. Tools used: {tools_used}"


class TestSystemAgent:
    """Test that agent.py uses query_api tool for system questions."""

    def test_agent_uses_read_file_for_framework_question(self):
        """Test that agent uses read_file to find the backend framework."""
        project_root = Path(__file__).parent.parent
        agent_path = project_root / "agent.py"

        result = subprocess.run(
            ["uv", "run", str(agent_path), "What Python web framework does the backend use?"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=project_root,
        )

        if result.returncode != 0:
            print(f"stderr: {result.stderr}", file=sys.stderr)

        stdout = result.stdout.strip()
        assert stdout, f"stdout should not be empty. stderr: {result.stderr}"

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            raise AssertionError(f"stdout is not valid JSON: {e}\nstdout: {stdout}")

        # Check required fields
        assert "answer" in data, "JSON must contain 'answer' field"
        assert "tool_calls" in data, "JSON must contain 'tool_calls' field"

        # Check that read_file was used
        tool_calls = data["tool_calls"]
        assert len(tool_calls) > 0, "Agent should have called at least one tool"
        
        tools_used = [tc.get("tool") for tc in tool_calls]
        assert "read_file" in tools_used, f"Agent should use read_file tool. Tools used: {tools_used}"

        # Check that answer mentions FastAPI
        answer = data.get("answer", "").lower()
        assert "fastapi" in answer, f"Answer should mention FastAPI. Got: {data.get('answer', '')}"

    def test_agent_uses_query_api_for_items_count(self):
        """Test that agent uses query_api to get item count from database."""
        project_root = Path(__file__).parent.parent
        agent_path = project_root / "agent.py"

        result = subprocess.run(
            ["uv", "run", str(agent_path), "How many items are in the database?"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=project_root,
        )

        if result.returncode != 0:
            print(f"stderr: {result.stderr}", file=sys.stderr)

        stdout = result.stdout.strip()
        assert stdout, f"stdout should not be empty. stderr: {result.stderr}"

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            raise AssertionError(f"stdout is not valid JSON: {e}\nstdout: {stdout}")

        # Check required fields
        assert "answer" in data, "JSON must contain 'answer' field"
        assert "tool_calls" in data, "JSON must contain 'tool_calls' field"

        # Check that query_api was used
        tool_calls = data["tool_calls"]
        assert len(tool_calls) > 0, "Agent should have called at least one tool"
        
        tools_used = [tc.get("tool") for tc in tool_calls]
        assert "query_api" in tools_used, f"Agent should use query_api tool. Tools used: {tools_used}"

        # Check that answer contains a number
        answer = data.get("answer", "")
        import re
        numbers = re.findall(r'\d+', answer)
        assert len(numbers) > 0, f"Answer should contain a number. Got: {answer}"
