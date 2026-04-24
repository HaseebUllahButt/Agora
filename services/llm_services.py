import os
import json
import time
import requests
import re

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# gemini-2.5-flash: stable GA model, best free-tier limits
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _call_gemini(prompt: str, json_output: bool = False) -> str:
    """Call Gemini 2.0 Flash with exponential backoff for 429 rate limiting.
    
    Free tier: 15 RPM, 1,500 RPD, 1M TPM.
    The frenzy demo is well within limits (~0.5 RPM) due to Circle polling delays.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "Error: GEMINI_API_KEY not configured. Please add it to .env"

    headers = {"Content-Type": "application/json"}
    config = {
        "temperature": 0.5,
        "maxOutputTokens": 1024,
    }
    if json_output:
        config["responseMimeType"] = "application/json"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": config
    }

    url = f"{GEMINI_API_BASE}/{GEMINI_MODEL}:generateContent?key={api_key}"

    for attempt in range(4):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)

            if response.status_code == 429:
                wait = 2 ** attempt  # 1s, 2s, 4s, 8s
                print(f"   ⏳ Gemini rate limit (429), retrying in {wait}s...")
                time.sleep(wait)
                continue

            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()

        except requests.exceptions.Timeout:
            print(f"   ⚠️ Gemini timeout (attempt {attempt + 1}/4)")
            time.sleep(2 ** attempt)
        except Exception as e:
            return f"Gemini Error: {str(e)}"

    return "Error: Gemini request failed after retries."


def summarize_text(params: dict) -> dict:
    text = params.get("text", "")
    if not text:
        return {"error": "Missing 'text' parameter"}

    prompt = f"Please provide a concise one-sentence summary of the following text:\n\n{text}"
    summary = _call_gemini(prompt)
    return {"summary": summary}


def analyze_sentiment(params: dict) -> dict:
    text = params.get("text", "")
    if not text:
        return {"error": "Missing 'text' parameter"}

    prompt = (
        f"Analyze the sentiment of the following text. "
        f"Respond with only a JSON object containing 'sentiment' (positive, negative, or neutral) "
        f"and 'confidence' (0.0 to 1.0).\n\nText: {text}"
    )
    result = _call_gemini(prompt, json_output=True)

    try:
        json_match = re.search(r'\{.*\}', result, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        return json.loads(result)
    except Exception:
        return {"sentiment": "unknown", "raw_response": result}


def generate_tagline(params: dict) -> dict:
    product = params.get("product", "")
    audience = params.get("audience", "general")
    if not product:
        return {"error": "Missing 'product' parameter"}

    prompt = (
        f"Create a catchy, single-sentence marketing tagline for a product called '{product}' "
        f"targeting {audience}. Respond ONLY with the tagline, no quotes, no explanation."
    )
    tagline = _call_gemini(prompt)
    return {"tagline": tagline.strip('"\'').strip()}
