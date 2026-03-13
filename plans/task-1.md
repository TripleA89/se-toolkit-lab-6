# Plan for Task 1: Call an LLM from Code

## LLM Provider

- **Provider:** Qwen Code API (self-hosted on VM)
- **Model:** `qwen3-coder-plus`
- **API Endpoint:** `http://10.93.24.178:42005/v1/chat/completions`
- **Authentication:** Bearer token via `LLM_API_KEY` environment variable

## Architecture

### Components

1. **Configuration loader** — reads `.env.agent.secret` and extracts:
   - `LLM_API_KEY` — API key for authentication
   - `LLM_API_BASE` — base URL of the LLM API
   - `LLM_MODEL` — model name to use

2. **LLM client** — sends HTTP POST request to the LLM API:
   - Uses `httpx` library (already in project dependencies)
   - Sends request to `{LLM_API_BASE}/chat/completions`
   - Request body: `{"model": LLM_MODEL, "messages": [{"role": "user", "content": question}]}`
   - Parses response JSON to extract `choices[0].message.content`

3. **CLI interface** — `agent.py`:
   - Accepts question as first command-line argument
   - Calls LLM client
   - Outputs JSON to stdout: `{"answer": "...", "tool_calls": []}`
   - All debug/progress output goes to stderr

### Data Flow

```
Command line → agent.py → Read config → Build request → HTTP POST → LLM API
                                                              ↓
stdout JSON ← Format response ← Parse response ← HTTP response ←
```

## Error Handling

- **Missing argument:** Print usage message to stderr, exit with code 1
- **Missing config:** Print error to stderr if `.env.agent.secret` not found or incomplete
- **API connection error:** Catch `httpx.RequestError`, print to stderr, exit code 1
- **API error response:** Check HTTP status code, print error to stderr, exit code 1
- **Timeout:** Set 60-second timeout on HTTP request

## Testing

- Create 1 regression test in `backend/tests/unit/test_agent.py` (or similar)
- Test runs `agent.py` as subprocess with a test question
- Parses stdout JSON
- Asserts:
  - `answer` field exists and is non-empty string
  - `tool_calls` field exists and is empty array

## Deliverables

- [ ] `plans/task-1.md` — this plan
- [ ] `agent.py` — CLI agent
- [ ] `.env.agent.secret` — configuration (gitignored)
- [ ] `AGENT.md` — documentation
- [ ] 1 regression test
