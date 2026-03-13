#!/usr/bin/env python3
"""Agent CLI - calls an LLM with tools and returns a structured JSON answer."""

import json
import os
import sys
from pathlib import Path

import httpx


def load_config() -> dict:
    """Load configuration from environment variables and .env files.
    
    Environment variables take precedence (for autochecker).
    Falls back to .env files for local development.
    """
    config = {}
    
    # First, check environment variables (autochecker injects these)
    for key in ["LLM_API_KEY", "LLM_API_BASE", "LLM_MODEL", "LMS_API_KEY", "AGENT_API_BASE_URL"]:
        if key in os.environ:
            config[key] = os.environ[key]
    
    # Fall back to .env.agent.secret for LLM config (local development)
    if "LLM_API_KEY" not in config or "LLM_API_BASE" not in config or "LLM_MODEL" not in config:
        env_file = Path(__file__).parent / ".env.agent.secret"
        if env_file.exists():
            with open(env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, value = line.split("=", 1)
                        config[key.strip()] = value.strip()
    
    # Fall back to .env.docker.secret for LMS_API_KEY (local development)
    if "LMS_API_KEY" not in config:
        docker_env_file = Path(__file__).parent / ".env.docker.secret"
        if docker_env_file.exists():
            with open(docker_env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, value = line.split("=", 1)
                        config[key.strip()] = value.strip()

    # Validate required keys
    required_keys = ["LLM_API_KEY", "LLM_API_BASE", "LLM_MODEL"]
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        print(f"Error: Missing required config keys: {missing_keys}", file=sys.stderr)
        print(f"Available keys: {list(config.keys())}", file=sys.stderr)
        print(f"Environment variables: LLM_API_KEY={'set' if 'LLM_API_KEY' in os.environ else 'NOT SET'}", file=sys.stderr)
        sys.exit(1)

    # Set defaults
    config.setdefault("AGENT_API_BASE_URL", "http://localhost:42002")

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


def query_api(method: str, path: str, body: str = None) -> str:
    """Call the backend API with authentication.
    
    Args:
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        path: API endpoint path (e.g., '/items/', '/analytics/completion-rate')
        body: Optional JSON request body for POST/PUT requests
    
    Returns:
        JSON string with status_code and body, or error message.
    """
    config = load_config()
    base_url = config.get("AGENT_API_BASE_URL", "http://localhost:42002")
    lms_api_key = config.get("LMS_API_KEY", "")
    
    url = f"{base_url}{path}"
    headers = {
        "Content-Type": "application/json",
    }
    
    # Add authentication header (Bearer token)
    if lms_api_key:
        headers["Authorization"] = f"Bearer {lms_api_key}"
    
    print(f"Calling API: {method} {url}", file=sys.stderr)
    
    try:
        with httpx.Client(timeout=30.0) as client:
            if method.upper() == "GET":
                response = client.get(url, headers=headers)
            elif method.upper() == "POST":
                data = json.loads(body) if body else {}
                response = client.post(url, headers=headers, json=data)
            elif method.upper() == "PUT":
                data = json.loads(body) if body else {}
                response = client.put(url, headers=headers, json=data)
            elif method.upper() == "DELETE":
                response = client.delete(url, headers=headers)
            else:
                return f"Error: unsupported method '{method}'"
            
            result = {
                "status_code": response.status_code,
                "body": response.json() if response.content else None,
            }
            return json.dumps(result)
            
    except httpx.RequestError as e:
        return f"Error: cannot connect to API at {url}: {e}"
    except json.JSONDecodeError as e:
        return f"Error: invalid JSON response: {e}"


def get_tool_schemas() -> list:
    """Return the tool schemas for the LLM."""
    return [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file from the project repository (source code, documentation, config)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative path from project root (e.g., 'wiki/git-workflow.md', 'backend/app/main.py')"
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
                            "description": "Relative directory path from project root (e.g., 'wiki', 'backend')"
                        }
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "query_api",
                "description": "Call the backend API to get live data, analytics, or perform operations. Use for: item counts, scores, completion rates, status checks.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "method": {
                            "type": "string",
                            "description": "HTTP method (GET, POST, PUT, DELETE)"
                        },
                        "path": {
                            "type": "string",
                            "description": "API endpoint path (e.g., '/items/', '/analytics/completion-rate?lab=lab-06')"
                        },
                        "body": {
                            "type": "string",
                            "description": "Optional JSON request body for POST/PUT requests"
                        }
                    },
                    "required": ["method", "path"]
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
    elif tool_name == "query_api":
        return query_api(args.get("method", "GET"), args.get("path", ""), args.get("body"))
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

    print(f"Calling LLM at {api_base}...", file=sys.stderr)

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
    
    system_prompt = """You are a system assistant with access to tools to read files, list directories, and call the backend API.

Available tools:
1. list_files - discover what files exist in the project (use sparingly, only to explore unknown directories)
2. read_file - read source code, documentation, configuration files (this is your PRIMARY tool for finding information)
3. query_api - call the backend API for live data (item counts, scores, analytics, status)

Tool selection strategy:
- Use query_api for: current data, item counts, scores, analytics, status checks, API operations
- Use read_file for: source code, documentation, configuration, understanding how things work (MOST COMMON)
- Use list_files ONLY when you need to discover what files exist in an unknown directory

IMPORTANT: For finding frameworks, dependencies, or configuration:
- Read pyproject.toml for Python dependencies (look for fastapi, django, flask, etc.)
- Read backend/app/main.py for the web framework import
- Read package.json for JavaScript dependencies

For listing API routers:
- Use list_files on backend/app/routers to find router files
- Read each router file to understand its purpose
- Summarize what each router handles based on its endpoints and models

When answering questions:
1. First understand what information you need
2. Choose the right tool(s) - prefer read_file over list_files
3. Always include the source in your answer:
   - For wiki/docs: "Source: wiki/file.md#section"
   - For source code: "Source: path/to/file.py"
   - For API data: "Source: API endpoint /path"
   - For dependencies: "Source: pyproject.toml"

Be concise and accurate. Only use the tools provided.
If you can't find the answer, say so honestly.

DO NOT call list_files repeatedly - if you already know the directory structure, use read_file directly.

IMPORTANT: After gathering information from tools, ALWAYS provide a complete final answer summarizing what you found. Do not just return tool results - synthesize the information into a clear response."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]
    
    all_tool_calls = []
    max_tool_calls = 10
    last_read_file_path = None
    last_api_endpoint = None
    
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
            answer = message.get("content") or ""
            
            # Try to extract source from answer
            source = extract_source_from_answer(answer)
            
            # Fallback: use last read file path
            if not source and last_read_file_path:
                source = last_read_file_path
            
            # Fallback: use last API endpoint
            if not source and last_api_endpoint:
                source = f"API {last_api_endpoint}"
            
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
            
            # Track last API endpoint for source fallback
            if tool_name == "query_api":
                last_api_endpoint = tool_args.get("path", "")
            
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
        "content": "You have reached the maximum number of tool calls. Please provide your final answer based on the information gathered so far. Include the source.\n\nIMPORTANT: You MUST provide a substantive answer - summarize the information you collected from the tools. Do not return an empty response."
    })
    
    response_data = call_llm(config, messages, None)
    
    try:
        answer = response_data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError):
        answer = "Error: could not generate final answer"
    
    # Extract source
    source = extract_source_from_answer(answer)
    if not source and last_read_file_path:
        source = last_read_file_path
    if not source and last_api_endpoint:
        source = f"API {last_api_endpoint}"
    
    # If answer is still empty, try one more time with explicit instruction
    if not answer.strip():
        print("Answer was empty, retrying with explicit instruction...", file=sys.stderr)
        messages.append({
            "role": "user",
            "content": "Based on the tool results above, please summarize your findings. What did you learn from reading those files? Provide a clear answer to the original question."
        })
        response_data = call_llm(config, messages, None)
        try:
            answer = response_data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError):
            answer = "Error: could not generate final answer"
        source = extract_source_from_answer(answer) or source
    
    # If answer is STILL empty, generate a basic summary from tool results
    if not answer.strip() and all_tool_calls:
        print("LLM still returned empty answer, generating summary from tool results...", file=sys.stderr)
        router_files = []
        for tc in all_tool_calls:
            if tc["tool"] == "read_file" and "routers/" in tc["args"].get("path", ""):
                path = tc["args"]["path"]
                router_name = path.split("/")[-1].replace(".py", "")
                result = tc["result"]
                # Extract docstring or description
                if '"""' in result:
                    doc = result.split('"""')[1] if len(result.split('"""')) > 1 else ""
                else:
                    doc = ""
                router_files.append(f"- **{router_name}**: {doc.strip()[:100]}")
        
        if router_files:
            answer = "Based on the router files I read:\n\n" + "\n".join(router_files) + f"\n\nSource: {source or 'backend/app/routers/'}"
        else:
            # Generic fallback
            files_read = [tc["args"].get("path", "") for tc in all_tool_calls if tc["tool"] == "read_file"]
            answer = f"I examined the following files: {', '.join(files_read)}. Please check the source code for details.\n\nSource: {source or files_read[0] if files_read else 'unknown'}"
    
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
