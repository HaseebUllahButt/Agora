"""
shared/llm.py

Lightweight Groq API wrapper.
Uses OpenAI-compatible chat completions endpoint over HTTP.
"""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()


async def generate_llm_content(prompt: str, system_instruction: str = None) -> str:
    """
    Call Groq chat completions API directly.
    """
    api_key = os.getenv("GROQ_API_KEY")
    model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    if not api_key or api_key == "your_groq_api_key_here":
        raise ValueError("GROQ_API_KEY not set in .env")

    url = "https://api.groq.com/openai/v1/chat/completions"

    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        
        if response.status_code != 200:
            raise Exception(f"Groq API error ({response.status_code}): {response.text}")
            
        data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            raise Exception(f"Unexpected Groq response format: {data}")


async def generate_gemini_content(prompt: str, system_instruction: str = None) -> str:
    """Backward-compatible alias for existing imports across the codebase."""
    return await generate_llm_content(prompt, system_instruction)

