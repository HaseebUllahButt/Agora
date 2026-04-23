import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure we can import from shared
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shared.circle_client import get_circle_client

def bootstrap():
    """
    One-stop Setup Tool for Circle Integration.
    Handles .env creation, interactive key input, and Wallet Set bootstrapping.
    """
    env_path = Path(".env")
    
    # 1. Ensure .env exists
    if not env_path.exists():
        print("No .env file found. Creating a new one...")
        with open(env_path, "w") as f:
            f.write("# Agora Marketplace Configuration\n")
    
    load_dotenv(override=True)
    
    # 2. Check Core Keys
    api_key = os.getenv("CIRCLE_API_KEY")
    entity_secret = os.getenv("CIRCLE_ENTITY_SECRET")
    
    if not api_key:
        api_key = input("Enter your Circle API Key: ").strip()
        with open(env_path, "a") as f:
            f.write(f"CIRCLE_API_KEY={api_key}\n")

    if not entity_secret:
        entity_secret = input("Enter your Circle Entity Secret: ").strip()
        with open(env_path, "a") as f:
            f.write(f"CIRCLE_ENTITY_SECRET={entity_secret}\n")

    # Reload again to ensure os.environ is updated
    load_dotenv(override=True)

    print("\n--- Agora Circle Health Check ---")
    
    # 3. Handle Wallet Set
    existing_set_id = os.getenv("CIRCLE_WALLET_SET_ID")
    if existing_set_id:
        print(f"✅ CIRCLE_WALLET_SET_ID is already configured: {existing_set_id}")
    else:
        print("🔄 No CIRCLE_WALLET_SET_ID found. Bootstrapping...")
        try:
            client = get_circle_client()
            new_set_id = client.create_wallet_set(name="Agora_Marketplace_Agents")
            with open(env_path, "a") as f:
                f.write(f"\nCIRCLE_WALLET_SET_ID={new_set_id}\n")
            print(f"✅ Successfully created and saved Wallet Set ID: {new_set_id}")
        except Exception as e:
            print(f"❌ Failed to create Wallet Set: {e}")
            sys.exit(1)

    print("\n🚀 All systems operational. Your environment is ready for Agora.")

if __name__ == "__main__":
    bootstrap()
