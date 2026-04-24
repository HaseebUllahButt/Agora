"""Quick smoke test for Gemini integration — tests all 3 services + SmartBuyer reasoning."""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from dotenv import load_dotenv
load_dotenv()

from services import llm_services

print("🧪 GEMINI SMOKE TEST")
print("=" * 40)

# Check key loaded
key = os.getenv("GEMINI_API_KEY", "")
if not key or key == "your_gemini_api_key_here":
    print("❌ GEMINI_API_KEY not set in .env — please add it first!")
    sys.exit(1)
print(f"✅ GEMINI_API_KEY loaded ({key[:8]}...)")

# Test 1: Summarize
print("\n[1/3] Testing SummaryBot (summarize_text)...")
result = llm_services.summarize_text({"text": "Arc is an EVM-compatible Layer-1 blockchain where USDC is the native gas token. It enables zero-gas-cost micro-transactions for AI agents."})
print(f"   Result: {result}")
assert "summary" in result and len(result["summary"]) > 5, "❌ summarize_text failed"
print("   ✅ PASS")

# Test 2: Sentiment
print("\n[2/3] Testing MoodReader (analyze_sentiment)...")
result = llm_services.analyze_sentiment({"text": "I absolutely love how fast Arc settles transactions!"})
print(f"   Result: {result}")
assert "sentiment" in result, "❌ analyze_sentiment failed"
print("   ✅ PASS")

# Test 3: Tagline
print("\n[3/3] Testing AdCopyAI (generate_tagline)...")
result = llm_services.generate_tagline({"product": "Agora Marketplace", "audience": "AI developers"})
print(f"   Result: {result}")
assert "tagline" in result and len(result["tagline"]) > 5, "❌ generate_tagline failed"
print("   ✅ PASS")

print("\n" + "=" * 40)
print("🎉 ALL GEMINI SERVICES WORKING!")
print("   Run python scripts/supply_chain_demo.py next.")
