"""
MoodReader — sentiment analysis agent.

Run::

    agora-agent run agents/moodreader/agent.py --port 9002
"""

from agora_x402 import pay_for
from pathlib import Path

from agora_x402 import AgentServer, Wallet
from dotenv import load_dotenv

# Auto-load .env so this works from any shell or test runner
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


POSITIVE_HINTS = {"good", "great", "love", "amazing",
                  "wonderful", "fantastic", "excellent", "happy"}
NEGATIVE_HINTS = {"bad", "terrible", "hate",
                  "awful", "worst", "sad", "angry", "broken"}


@pay_for(
    price="0.0008",
    category="llm",
    description="Classify text sentiment as positive/negative/neutral.",
    path="/analyze-sentiment",
)
def analyze_sentiment(text: str) -> dict:
    text = (text or "").lower()
    pos = sum(1 for w in POSITIVE_HINTS if w in text)
    neg = sum(1 for w in NEGATIVE_HINTS if w in text)
    if pos > neg:
        label = "positive"
    elif neg > pos:
        label = "negative"
    else:
        label = "neutral"
    score = (pos - neg) / max(pos + neg, 1)
    return {"label": label, "score": round(score, 3), "positive_hits": pos, "negative_hits": neg}


server = AgentServer(
    agent_id="moodreader",
    name="MoodReader",
    description="Cheap, fast sentiment classifier.",
    wallet=Wallet.from_env("MOODREADER_PRIVATE_KEY"),
)
