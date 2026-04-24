import os
import json
import requests

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

def _call_groq(prompt: str) -> str:
    if not GROQ_API_KEY:
        return "Error: GROQ_API_KEY not configured. Please add it to .env"
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5,
        "max_tokens": 1024
    }
    
    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Groq Error: {str(e)}"

def summarize_text(params: dict) -> dict:
    text = params.get("text", "")
    if not text:
        return {"error": "Missing 'text' parameter"}
    
    prompt = f"Please provide a concise summary of the following text:\n\n{text}"
    summary = _call_groq(prompt)
    return {"summary": summary}

def analyze_sentiment(params: dict) -> dict:
    text = params.get("text", "")
    if not text:
        return {"error": "Missing 'text' parameter"}
    
    prompt = f"Analyze the sentiment of the following text. Respond with only a JSON object containing 'sentiment' (positive, negative, or neutral) and 'confidence' (0.0 to 1.0).\n\nText: {text}"
    result = _call_groq(prompt)
    
    try:
        import re
        json_match = re.search(r'\{.*\}', result, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        return json.loads(result)
    except:
        return {"sentiment": "unknown", "raw_response": result}

def generate_tagline(params: dict) -> dict:
    product = params.get("product", "")
    audience = params.get("audience", "general")
    if not product:
        return {"error": "Missing 'product' parameter"}
        
    prompt = f"Create a catchy, single-sentence marketing tagline for a product called '{product}' targeting {audience}. Respond ONLY with the tagline."
    tagline = _call_groq(prompt)
    return {"tagline": tagline.strip('\"\'')}
