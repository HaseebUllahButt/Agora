"""
DataWizard — pure data utilities (no external dependencies).

Run::

    agora-agent run agents/datawizard/agent.py --port 9003
"""

from agora_x402 import pay_for
import csv
import io
import json
from pathlib import Path

from agora_x402 import AgentServer, Wallet
from dotenv import load_dotenv

# Auto-load .env so this works from any shell or test runner
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


@pay_for(
    price="0.0005",
    category="data",
    description="Convert a JSON list of objects into a CSV string.",
    path="/json-to-csv",
)
def json_to_csv(records: list) -> dict:
    if not isinstance(records, list) or not records:
        return {"csv": "", "rows": 0}
    if not all(isinstance(r, dict) for r in records):
        raise ValueError("`records` must be a list of dict")

    keys: list[str] = []
    for r in records:
        for k in r.keys():
            if k not in keys:
                keys.append(k)

    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=keys)
    writer.writeheader()
    for r in records:
        writer.writerow(r)
    return {"csv": out.getvalue(), "rows": len(records), "columns": keys}


@pay_for(
    price="0.0003",
    category="data",
    description="Pretty-print arbitrary JSON.",
    path="/pretty-json",
)
def pretty_json(payload) -> dict:
    return {"pretty": json.dumps(payload, indent=2, sort_keys=True)}


server = AgentServer(
    agent_id="datawizard",
    name="DataWizard",
    description="Tiny bag of pure data-shaping utilities.",
    wallet=Wallet.from_env("DATAWIZARD_PRIVATE_KEY"),
)
