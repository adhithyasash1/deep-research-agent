"""Baseline Deep Agent: question → Deep Agent → search tool → answer."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Literal

from deepagents import create_deep_agent
from tavily import TavilyClient

from src.helpers.config import ENV_PATH, DEFAULT_MODEL, get_model, load_env, missing_keys

SYSTEM_PROMPT = """You are a research assistant.

Use the internet_search tool to gather evidence before answering.
Prefer primary sources and recent material when available.
Synthesize a clear, structured answer with key points and citations (URLs).
"""


def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
) -> dict:
    """Run a web search and return results."""
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY is not set")

    client = TavilyClient(api_key=api_key)
    return client.search(
        query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic,
    )


def build_agent(model: str | None = None):
    """Create the baseline Deep Agent with a search tool."""
    return create_deep_agent(
        model=get_model(model),
        tools=[internet_search],
        system_prompt=SYSTEM_PROMPT,
    )


def _message_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            else:
                text = getattr(block, "text", None)
                if text:
                    parts.append(str(text))
        return "\n".join(p for p in parts if p)
    return str(content)


def run(question: str, model: str | None = None) -> str:
    """Run question → Deep Agent → tools → answer."""
    agent = build_agent(model=model)
    result = agent.invoke(
        {"messages": [{"role": "user", "content": question}]},
    )
    final = result["messages"][-1]
    return _message_text(final.content)


def main(argv: list[str] | None = None) -> int:
    load_env()

    parser = argparse.ArgumentParser(
        description="Baseline Deep Agent research CLI",
    )
    parser.add_argument(
        "question",
        help="Research question to ask the agent",
    )
    parser.add_argument(
        "--model",
        default=None,
        help=f"Model string (default from .env MODEL, else {DEFAULT_MODEL})",
    )
    args = parser.parse_args(argv)

    model = get_model(args.model)
    missing = missing_keys(model)
    if missing:
        print(
            f"error: missing {', '.join(missing)} in {ENV_PATH}",
            file=sys.stderr,
        )
        print("Paste keys into .env (see .env.example).", file=sys.stderr)
        return 1

    answer = run(args.question, model=model)
    print(answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
