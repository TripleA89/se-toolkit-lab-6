#!/usr/bin/env python3
"""Agent CLI - calls an LLM with tools and returns a structured JSON answer."""

import json
import os
import sys
from pathlib import Path

import httpx


def load_config() -> dict:
    """Load configuration from .env.agent.secret file."""
    env_file = Path(__file__).parent / ".env.agent.secret"

    if not env_file.exists():
        print(f"Error: {env_file} not found", file=sys.stderr)
        sys.exit(1)

    config = {}
    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()

    # Validate required keys
    required_keys = ["LLM_API_KEY", "LLM_API_BASE", "LLM_MODEL"]
    for key in required_keys:
        if key not in config:
            print(f"Error: Missing {key} in {env_file}", file=sys.stderr)
            sys.exit(1)

    return config


def is_safe_path(requested_path: str) -> bool:
    """Check if the requested path is within the project directory."""
    project_root = Path(__file__).parent.resolve()
    try:
        full_path = (project_root / requested_path).resolve()
        return str(full_path).startswith(str(project_root))
    except (ValueError, OSError):
        return False


def read_file(path: str) -> str:
    """Read a file from the project repository.
    
    Args:
        path: Relative path from project root.
    
    Returns:
        File contents as string, or error message.
    """
    if not path:
        return "Error: path is required"
    
    if not is_safe_path(path):
        return f"Error: access denied - path '{path}' is outside project directory"
    
    project_root = Path(__file__).parent.resolve()
    full_path = project_root / path
    
    if not full_path.exists():
        return f"Error: file '{path}' does not exist"
    
    if not full_path.is_file():
        return f"Error: '{path}' is not a file"
    
    try:
        return full_path.read_text()
    except (IOError, OSError) as e:
        return f"Error: cannot read file '{path}': {e}"


def list_files(path: str) -> str:
    """List files and directories at a given path.
    
    Args:
        path: Relative directory path from project root.
    
    Returns:
        Newline-separated listing of entries, or error message.
    """
    if not path:
        return "Error: path is required"
    
    if not is_safe_path(path):
        return f"Error: access denied - path '{path}' is outside project directory"
    
    project_root = Path(__file__).parent.resolve()
    full_path = project_root / path
    
    if not full_path.exists():
        return f"Error: directory '{path}' does not exist"
    
    if not full_path.is_dir():
        return f"Error: '{path}' is not a directory"
    
    try:
        entries = sorted(full_path.iterdir())
        return "\n".join(entry.name for entry in entries)
    except (IOError, OSError) as e:
        return f"Error: cannot list directory '{path}': {e}"


def get_tool_schemas() -> list:
    """Return the tool schemas for the LLM."""
    return [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file from the project repository",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')"
                        }
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files and directories at a given path",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative directory path from project root (e.g., 'wiki')"
                        }
                    },
                    "required": ["path"]
                }
            }
        }
    ]


def execute_tool(tool_name: str, args: dict) -> str:
    """Execute a tool and return the result."""
    if tool_name == "read_file":
        return read_file(args.get("path", ""))
    elif tool_name == "list_files":
        return list_files(args.get("path", ""))
    else:
        return f"Error: unknown tool '{tool_name}'"


def extract_source_from_answer(answer: str) -> str | None:
    """Try to extract source from the LLM answer text."""
    import re
    # Look for patterns like "Source: wiki/file.md" or "wiki/file.md#anchor"
    patterns = [
        r"[Ss]ource:\s*([^\s\n]+)",
        r"([a-zA-Z0-9_/.-]+\.md(?:#[a-zA-Z0-9_-]+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, answer)
        if match:
            source = match.group(1)
            # Validate it looks like a wiki path
            if source.startswith("wiki/") and ".md" in source:
                return source
    return None


def call_llm(config: dict, messages: list, tools: list = None) -> dict:
    """Call the LLM API and return the parsed response."""
    api_base = config["LLM_API_BASE"]
    api_key = config["LLM_API_KEY"]
    model = config["LLM_MODEL"]

    url = f"{api_base}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    
    payload = {
        "model": model,
        "messages": messages,
    }
    
    if tools:
        payload["tools"] = tools

    print(f"Calling LLM at {url}...", file=sys.stderr)

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

            return data

    except httpx.RequestError as e:
        print(f"Error connecting to LLM API: {e}", file=sys.stderr)
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(f"LLM API returned error: {e}", file=sys.stderr)
        sys.exit(1)


def run_agentic_loop(config: dict, question: str) -> tuple[str, str, list]:
    """Run the agentic loop and return (answer, source, tool_calls)."""
    tools = get_tool_schemas()
    
    system_prompt = """You are a documentation assistant. You have access to tools to read files and list directories.

When answering questions:
1. Use list_files to discover what files exist
2. Use read_file to find the relevant information
3. Always include the source file path in your answer (e.g., "Source: wiki/git-workflow.md")
4. If the answer comes from a specific section, include the anchor (e.g., "wiki/git-workflow.md#resolving-merge-conflicts")

Be concise and accurate. Only use the tools provided."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]
    
    all_tool_calls = []
    max_tool_calls = 10
    last_read_file_path = None
    
    while len(all_tool_calls) < max_tool_calls:
        print(f"\n--- Iteration {len(all_tool_calls) + 1} ---", file=sys.stderr)
        
        response_data = call_llm(config, messages, tools)
        
        # Extract message from response
        try:
            choice = response_data["choices"][0]
            message = choice["message"]
        except (KeyError, IndexError) as e:
            print(f"Error parsing LLM response: {e}", file=sys.stderr)
            sys.exit(1)
        
        # Check for tool calls
        tool_calls = message.get("tool_calls") or message.get("function_call")
        
        if not tool_calls:
            # No tool calls - this is the final answer
            answer = message.get("content", "")
            
            # Try to extract source from answer
            source = extract_source_from_answer(answer)
            
            # Fallback: use last read file path
            if not source and last_read_file_path:
                source = last_read_file_path
            
            # If still no source, try to find any wiki reference
            if not source:
                import re
                match = re.search(r'wiki/[a-zA-Z0-9_/.-]+\.md', answer)
                if match:
                    source = match.group(0)
            
            return answer, source, all_tool_calls
        
        # Handle tool calls - normalize to list
        if isinstance(tool_calls, dict):
            tool_calls = [tool_calls]
        
        # Execute each tool call
        for tc in tool_calls:
            # Handle different response formats
            if "function" in tc:
                tool_name = tc["function"]["name"]
                tool_args = json.loads(tc["function"]["arguments"])
            else:
                tool_name = tc.get("name", tc.get("tool", ""))
                tool_args = tc.get("arguments", tc.get("args", {}))
                if isinstance(tool_args, str):
                    tool_args = json.loads(tool_args)
            
            print(f"Executing tool: {tool_name}({tool_args})", file=sys.stderr)
            
            result = execute_tool(tool_name, tool_args)
            
            # Track last read file for source fallback
            if tool_name == "read_file":
                last_read_file_path = tool_args.get("path", "")
            
            # Store tool call with result
            tool_call_record = {
                "tool": tool_name,
                "args": tool_args,
                "result": result
            }
            all_tool_calls.append(tool_call_record)
            
            # Add tool result to messages
            messages.append({
                "role": "assistant",
                "content": "",
                "tool_calls": [tc] if isinstance(tc, dict) else tc
            })
            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", f"{tool_name}_call"),
                "content": result
            })
    
    # Max tool calls reached - try to get final answer
    print("\nMax tool calls reached, generating final answer...", file=sys.stderr)
    
    messages.append({
        "role": "system",
        "content": "You have reached the maximum number of tool calls. Please provide your final answer based on the information gathered so far. Include the source file path."
    })
    
    response_data = call_llm(config, messages, None)
    
    try:
        answer = response_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        answer = "Error: could not generate final answer"
    
    # Extract source
    source = extract_source_from_answer(answer)
    if not source and last_read_file_path:
        source = last_read_file_path
    
    return answer, source, all_tool_calls


def main():
    """Main entry point."""
    # Check command-line arguments
    if len(sys.argv) < 2:
        print("Usage: agent.py <question>", file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]

    # Load configuration
    config = load_config()

    # Run agentic loop
    answer, source, tool_calls = run_agentic_loop(config, question)

    # Output JSON to stdout
    result = {
        "answer": answer,
        "source": source or "",
        "tool_calls": tool_calls,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
