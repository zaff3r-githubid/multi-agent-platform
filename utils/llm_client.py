# utils/llm_client.py
import os
import time
from openai import AsyncOpenAI
from dataclasses import dataclass

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:1234/v1")
LLM_MODEL    = os.getenv("LLM_MODEL", "qwen/qwen3-14b")

# Points to localhost — no internet calls
_client = AsyncOpenAI(base_url=LLM_BASE_URL, api_key="lm-studio")


@dataclass
class LLMResponse:
    """
    Wraps the LLM response text alongside token usage metadata.
    This lets the LLM queue capture observability data without
    changing how agents use the generate() function.
    """
    text:              str
    prompt_tokens:     int
    completion_tokens: int
    total_tokens:      int
    response_time_ms:  int
    tokens_per_sec:    float


async def generate(prompt: str, system: str = "You are a helpful assistant.") -> str:
    """
    Send a prompt to local LM Studio, return the response text.
    Internally captures token usage but returns just the string
    so existing agent code doesn't need to change.
    """
    result = await generate_with_usage(prompt, system)
    return result.text


async def generate_with_usage(
    prompt: str,
    system: str = "You are a helpful assistant."
) -> LLMResponse:
    """
    Full version — returns text AND token usage metadata.
    Called by the LLM queue to capture observability data.
    """
    start_ms = int(time.time() * 1000)

    response = await _client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
        temperature=0.7,
        max_tokens=2048,
    )

    elapsed_ms = int(time.time() * 1000) - start_ms
    text       = response.choices[0].message.content.strip()

    # Extract token counts — LM Studio returns these in the usage object
    usage             = response.usage
    prompt_tokens     = usage.prompt_tokens     if usage else 0
    completion_tokens = usage.completion_tokens if usage else 0
    total_tokens      = usage.total_tokens      if usage else 0

    # Tokens per second — how fast the model generated the response
    elapsed_sec    = elapsed_ms / 1000 if elapsed_ms > 0 else 1
    tokens_per_sec = round(completion_tokens / elapsed_sec, 1) if completion_tokens > 0 else 0.0

    return LLMResponse(
        text              = text,
        prompt_tokens     = prompt_tokens,
        completion_tokens = completion_tokens,
        total_tokens      = total_tokens,
        response_time_ms  = elapsed_ms,
        tokens_per_sec    = tokens_per_sec,
    )