# Plan for Task 2: The Documentation Agent

## Overview

This plan describes how to extend the Task 1 agent with tools (`read_file`, `list_files`) and an agentic loop to answer questions using the project wiki.

## LLM Provider

- **Provider:** Qwen Code API (self-hosted on VM)
- **Model:** `qwen3-coder-plus`
- **API Endpoint:** `http://10.93.24.178:42005/v1`
- **Tool calling:** Native function calling support

## Tool Schemas

### `read_file`

```json
{
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
```

### `list_files`

```json
{
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
```

## Agentic Loop

1. Send user question + tool schemas to LLM
2. Parse response:
   - If `tool_calls` present → execute each tool, append results as `tool` role messages, repeat from step 1
   - If no `tool_calls` → extract final answer and source, output JSON
3. **Limit:** Maximum 10 tool calls total (not iterations)
4. **Timeout:** 60 seconds total

## Path Security

To prevent directory traversal attacks (`../`):

1. Resolve the requested path against project root using `Path.resolve()`
2. Check that the resolved path starts with project root
3. Reject any path that escapes the project boundary

```python
def is_safe_path(requested_path: str) -> bool:
    project_root = Path(__file__).parent
    full_path = (project_root / requested_path).resolve()
    return str(full_path).startswith(str(project_root))
```

## Source Extraction Strategy

Three-layer approach for reliability:

1. **System prompt:** Instruct LLM to include source file path in response
2. **Parse response:** Look for `Source:` pattern in the answer text
3. **Fallback:** Use the path from the last `read_file` tool call

## System Prompt

```
You are a documentation assistant. You have access to tools to read files and list directories.

When answering questions:
1. Use list_files to discover what files exist
2. Use read_file to find the relevant information
3. Always include the source file path in your answer (e.g., "Source: wiki/git-workflow.md")
4. If the answer comes from a specific section, include the anchor (e.g., "wiki/git-workflow.md#resolving-merge-conflicts")

Be concise and accurate. Only use the tools provided.
```

## Tests

Two regression tests:

1. **Merge conflict question:**
   - Question: `"How do you resolve a merge conflict?"`
   - Expected: `read_file` in tool_calls, `wiki/git-workflow.md` in source

2. **Wiki listing question:**
   - Question: `"What files are in the wiki?"`
   - Expected: `list_files` in tool_calls

## Implementation Steps

1. Create this plan file
2. Define tool schemas in `agent.py`
3. Implement `read_file` and `list_files` functions with path security
4. Implement agentic loop (max 10 tool calls)
5. Update JSON output to include `source` field
6. Update `AGENT.md` documentation
7. Add 2 regression tests in `tests/`
8. Test manually, then run pytest
