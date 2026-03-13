#!/usr/bin/env python3
"""Agent CLI - calls an LLM and returns a structured JSON answer."""

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


def call_lllm(config: dict, question: str) -> str:
    """Call the LLM API and return the answer."""
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
        "messages": [{"role": "user", "content": question}],
    }
    
    print(f"Calling LLM at {url}...", file=sys.stderr)
    
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            # Extract answer from response
            answer = data["choices"][0]["message"]["content"]
            return answer
            
    except httpx.RequestError as e:
        print(f"Error connecting to LLM API: {e}", file=sys.stderr)
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(f"LLM API returned error: {e}", file=sys.stderr)
        sys.exit(1)
    except (KeyError, IndexError) as e:
        print(f"Error parsing LLM response: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point."""
    # Check command-line arguments
    if len(sys.argv) < 2:
        print("Usage: agent.py <question>", file=sys.stderr)
        sys.exit(1)
    
    question = sys.argv[1]
    
    # Load configuration
    config = load_config()
    
    # Call LLM
    answer = call_lllm(config, question)
    
    # Output JSON to stdout
    result = {
        "answer": answer,
        "tool_calls": [],
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
