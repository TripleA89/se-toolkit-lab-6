# Agent Architecture

## Overview

This agent is a CLI tool with an **agentic loop** that calls an LLM and uses tools (`read_file`, `list_files`) to answer questions based on the project wiki. The agent returns a structured JSON answer with `answer`, `source`, and `tool_calls` fields.

## LLM Provider

- **Provider:** Qwen Code API (self-hosted on VM)
- **Model:** `qwen3-coder-plus`
- **API Endpoint:** `http://10.93.24.178:42005/v1`
- **Authentication:** Bearer token
- **Tool calling:** Native function calling support

## How to Run

### Setup

1. Create `.env.agent.secret` from `.env.agent.example`:
   ```bash
   cp .env.agent.example .env.agent.secret
   ```

2. Fill in the configuration:
   - `LLM_API_KEY` — your API key
   - `LLM_API_BASE` — base URL of the LLM API
   - `LLM_MODEL` — model name (e.g., `qwen3-coder-plus`)

### Usage

```bash
uv run agent.py "Your question here"
```

### Output

The agent outputs a single JSON line to stdout:

```json
{
  "answer": "The answer from the LLM.",
  "source": "wiki/git-workflow.md#section-anchor",
  "tool_calls": [
    {"tool": "list_files", "args": {"path": "wiki"}, "result": "..."},
    {"tool": "read_file", "args": {"path": "wiki/git-workflow.md"}, "result": "..."}
  ]
}
```

- `answer` — the LLM's response to the question
- `source` — the wiki file path (and optional anchor) that the answer came from
- `tool_calls` — array of all tool calls made, each with `tool`, `args`, and `result`

All debug/progress output goes to stderr.

## Architecture

### Components

1. **`load_config()`** — Reads `.env.agent.secret` and parses environment variables. Validates that all required keys are present.

2. **`is_safe_path()`** — Security check to prevent directory traversal attacks. Ensures requested paths stay within the project directory.

3. **`read_file()`** — Tool function that reads a file from the project repository. Returns file contents or an error message.

4. **`list_files()`** — Tool function that lists files and directories at a given path. Returns newline-separated listing or an error message.

5. **`get_tool_schemas()`** — Returns the tool schemas for the LLM in OpenAI-compatible format.

6. **`execute_tool()`** — Dispatcher that calls the appropriate tool function based on the tool name.

7. **`extract_source_from_answer()`** — Parses the LLM answer to extract the source file reference.

8. **`call_llm()`** — Sends an HTTP POST request to the LLM API with messages and optional tool schemas.

9. **`run_agentic_loop()`** — Main agentic loop:
   - Sends user question + tool schemas to LLM
   - If LLM returns tool calls → executes them, appends results, repeats
   - If LLM returns final answer → extracts answer and source, returns
   - Limits: maximum 10 tool calls total

10. **`main()`** — CLI entry point that orchestrates the flow.

### Tool Schemas

Tools are defined as OpenAI-compatible function schemas:

```json
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
          "description": "Relative path from project root"
        }
      },
      "required": ["path"]
    }
  }
}
```

### Agentic Loop

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  CLI Input  │ ──> │  call_llm   │ ──> │  LLM API    │
│  (question) │     │ (with tools)│     │  (Qwen)     │
└─────────────┘     └─────────────┘     └─────────────┘
                           ▲                    │
                           │                    ▼
                           │            ┌─────────────┐
                           │            │ tool_calls? │
                           │            └─────────────┘
                           │                  │
                    ┌──────┴──────┐           │
                    │             │ no        │ yes
                    ▼             │           │
            ┌─────────────┐       │           ▼
            │ JSON Output │       │    ┌─────────────┐
            │   (answer)  │       │    │execute_tool │
            └─────────────┘       │    │  (read_file,│
                                  │    │  list_files)│
                                  │    └─────────────┘
                                  │           │
                                  │           ▼
                                  │    ┌─────────────┐
                                  └────│  append to  │
                                       │   messages  │
                                       └─────────────┘
```

### System Prompt

The system prompt instructs the LLM to:

1. Use `list_files` to discover what files exist
2. Use `read_file` to find relevant information
3. Always include the source file path in the answer
4. Include section anchors when applicable

### Path Security

To prevent directory traversal attacks:

```python
def is_safe_path(requested_path: str) -> bool:
    project_root = Path(__file__).parent.resolve()
    full_path = (project_root / requested_path).resolve()
    return str(full_path).startswith(str(project_root))
```

This ensures that even if the LLM tries to read `../../../etc/passwd`, the request will be denied.

### Source Extraction Strategy

Three-layer approach for reliability:

1. **Parse LLM response:** Look for `Source: wiki/file.md` pattern in the answer
2. **Fallback to last read file:** If no source in answer, use the path from the last `read_file` call
3. **Regex fallback:** Search for any `wiki/*.md` pattern in the answer

## Error Handling

- **Missing argument:** Prints usage to stderr, exits with code 1
- **Missing config file:** Prints error to stderr, exits with code 1
- **Missing config keys:** Prints error to stderr, exits with code 1
- **HTTP request error:** Catches `httpx.RequestError`, prints to stderr, exits with code 1
- **HTTP status error:** Catches `httpx.HTTPStatusError`, prints to stderr, exits with code 1
- **Parse error:** Catches `KeyError`/`IndexError` if response format is unexpected
- **Tool error:** Returns error message as tool result (doesn't crash)

## Testing

Run tests with:

```bash
uv run pytest tests/test_agent.py -v
```

Tests cover:

1. Basic JSON output with required fields (`answer`, `tool_calls`)
2. Tool usage for documentation questions (`read_file` for merge conflict)
3. Tool usage for wiki listing (`list_files` for wiki files)

### Manual Testing

```bash
# Basic question (no tools needed)
uv run agent.py "What is 2+2?"

# Documentation question (uses tools)
uv run agent.py "How do you resolve a merge conflict?"

# Wiki listing question
uv run agent.py "What files are in the wiki?"
```

## Files

- `agent.py` — main CLI script with agentic loop and tools
- `.env.agent.secret` — configuration (gitignored)
- `plans/task-1.md` — implementation plan for Task 1
- `plans/task-2.md` — implementation plan for Task 2
- `AGENT.md` — this documentation
- `tests/test_agent.py` — regression tests
