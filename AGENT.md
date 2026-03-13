# Agent Architecture

## Overview

This agent is a CLI tool that calls an LLM API and returns a structured JSON answer. It is the foundation for the more advanced agent with tools and agentic loop that will be built in Tasks 2–3.

## LLM Provider

- **Provider:** Qwen Code API (self-hosted on VM)
- **Model:** `qwen3-coder-plus`
- **API Endpoint:** `http://10.93.24.178:42005/v1`
- **Authentication:** Bearer token

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
{"answer": "The answer from the LLM.", "tool_calls": []}
```

- `answer` — the LLM's response to the question
- `tool_calls` — empty array for Task 1 (will be populated in Task 2)

All debug/progress output goes to stderr.

## Architecture

### Components

1. **`load_config()`** — Reads `.env.agent.secret` and parses environment variables. Validates that all required keys are present.

2. **`call_llm()`** — Sends an HTTP POST request to the LLM API:
   - Endpoint: `{LLM_API_BASE}/chat/completions`
   - Headers: `Content-Type`, `Authorization: Bearer {LLM_API_KEY}`
   - Body: `{"model": LLM_MODEL, "messages": [{"role": "user", "content": question}]}`
   - Timeout: 60 seconds
   - Extracts answer from `choices[0].message.content`

3. **`main()`** — CLI entry point:
   - Parses command-line argument (question)
   - Calls `load_config()` and `call_llm()`
   - Outputs JSON to stdout
   - Exits with code 0 on success, 1 on error

### Data Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  CLI Input  │ ──> │ load_config │ ──> │  call_llm   │ ──> │  JSON Output│
│  (question) │     │   (config)  │     │  (HTTP API) │     │   (stdout)  │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                                              │
                                              ▼
                                       ┌─────────────┐
                                       │  LLM API    │
                                       │  (Qwen)     │
                                       └─────────────┘
```

## Error Handling

- **Missing argument:** Prints usage to stderr, exits with code 1
- **Missing config file:** Prints error to stderr, exits with code 1
- **Missing config keys:** Prints error to stderr, exits with code 1
- **HTTP request error:** Catches `httpx.RequestError`, prints to stderr, exits with code 1
- **HTTP status error:** Catches `httpx.HTTPStatusError`, prints to stderr, exits with code 1
- **Parse error:** Catches `KeyError`/`IndexError` if response format is unexpected

## Testing

Run the agent manually:

```bash
uv run agent.py "What is 2+2?"
```

Expected output (JSON to stdout):

```json
{"answer": "2 + 2 = 4.", "tool_calls": []}
```

## Files

- `agent.py` — main CLI script
- `.env.agent.secret` — configuration (gitignored)
- `plans/task-1.md` — implementation plan
- `AGENT.md` — this documentation
