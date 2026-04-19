"""
shared/llm.py

Lightweight Gemini API wrapper.
We use httpx directly to avoid the heavy google-generativeai SDK and grpcio dependencies,
which can take 20+ minutes to compile from source on unsupported/bleeding-edge Python versions.
"""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()


async def generate_gemini_content(prompt: str, system_instruction: str = None) -> str:
    """
    Call Gemini 2.0 Flash REST API directly.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        raise ValueError("GEMINI_API_KEY not set in .env")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }

    if system_instruction:
        payload["system_instruction"] = {
            "parts": [{"text": system_instruction}]
        }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, json=payload)
        
        if response.status_code != 200:
            raise Exception(f"Gemini API error ({response.status_code}): {response.text}")
            
        data = response.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            raise Exception(f"Unexpected Gemini response format: {data}")

