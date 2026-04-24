import hashlib
import re

def generate_hash(params: dict) -> dict:
    input_text = params.get("input", "")
    algorithm = params.get("algorithm", "sha256").lower()
    
    if not input_text:
        return {"error": "Missing 'input' parameter"}
        
    try:
        hasher = getattr(hashlib, algorithm)()
        hasher.update(str(input_text).encode('utf-8'))
        return {
            "algorithm": algorithm,
            "hash": hasher.hexdigest()
        }
    except AttributeError:
        return {"error": f"Unsupported algorithm: {algorithm}"}

def word_frequency(params: dict) -> dict:
    text = params.get("text", "")
    limit = params.get("limit", 10)
    
    if not text:
        return {"error": "Missing 'text' parameter"}
        
    # Simple tokenization
    words = re.findall(r'\b\w+\b', text.lower())
    
    freq = {}
    for word in words:
        if len(word) > 3:  # Skip very short words usually
            freq[word] = freq.get(word, 0) + 1
            
    # Sort by frequency
    sorted_freq = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    
    return {
        "total_words": len(words),
        "unique_words": len(freq),
        "top_words": dict(sorted_freq[:limit])
    }

def estimate_read_time(params: dict) -> dict:
    text = params.get("text", "")
    wpm = params.get("wpm", 200) # Words per minute
    
    if not text:
        return {"error": "Missing 'text' parameter"}
        
    words = len(re.findall(r'\b\w+\b', text))
    minutes = words / wpm
    
    return {
        "word_count": words,
        "read_time_minutes": round(minutes, 2),
        "read_time_seconds": round(minutes * 60)
    }
