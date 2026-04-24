import os
import sys
import json
from pathlib import Path

# Ensure we can import from sdk
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sdk.agent import Agent, CONFIG_FILE

def list_agents():
    local_agents = []
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            local_agents = list(data.keys())
    
    # Also fetch from the Marketplace API to find "Ghost" agents
    remote_agents = []
    try:
        import requests
        api_url = os.getenv("AGORA_API_URL", "http://localhost:8000")
        resp = requests.get(f"{api_url}/agents", timeout=5)
        if resp.status_code == 200:
            remote_agents = [a["agent_id"] for a in resp.json()]
    except:
        pass # API might be offline

    # Combine and remove duplicates
    return list(set(local_agents + remote_agents))

def main():
    print("🛠️  AGORA AGENT MANAGER")
    print("----------------------")
    
    agents = list_agents()
    if not agents:
        return

    print("Current Local Agents:")
    for i, agent_id in enumerate(agents, 1):
        print(f"[{i}] {agent_id}")
    print(f"[{len(agents) + 1}] DELETE ALL AGENTS")
    print("[0] Cancel")

    choice = input("\nSelect an agent to delete (or 0 to cancel): ").strip()

    if not choice or choice == "0":
        print("Cancelled.")
        return

    try:
        idx = int(choice)
        if idx == len(agents) + 1:
            print(f"⚠️  DELETING ALL {len(agents)} AGENTS...")
            for aid in agents:
                Agent(aid).delete()
            print("✅ All agents wiped.")
        elif 1 <= idx <= len(agents):
            target = agents[idx-1]
            print(f"⚠️  Deleting {target}...")
            Agent(target).delete()
            print(f"✅ {target} removed.")
        else:
            print("Invalid choice.")
    except Exception as e:
        print(f"❌ Error during deletion: {e}")

if __name__ == "__main__":
    main()
