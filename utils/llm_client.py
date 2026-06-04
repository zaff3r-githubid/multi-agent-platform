# utils/llm_client.py
import os
from openai import AsyncOpenAI

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:1234/v1")
LLM_MODEL    = os.getenv("LLM_MODEL", "qwen/qwen3-14b")

# Points to localhost — no internet calls
_client = AsyncOpenAI(base_url=LLM_BASE_URL, api_key="lm-studio")

async def generate(prompt: str, system: str = "You are a helpful assistant.") -> str:
    """Send a prompt to local LM Studio, return the response text."""
    response = await _client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
        temperature=0.7,
        max_tokens=2048,
    )
    return response.choices[0].message.content.strip()