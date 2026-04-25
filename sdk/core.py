import os
import secrets
from pathlib import Path
from typing import Optional

def bootstrap(
    circle_api_key: Optional[str] = None,
    circle_entity_secret: Optional[str] = None,
    circle_wallet_set_id: Optional[str] = None,
    groq_api_key: Optional[str] = None,
    gemini_api_key: Optional[str] = None,
    redis_host: str = "localhost",
    redis_port: int = 6379,
    redis_db: int = 0
):
    """
    Programmatically initialize the Agora ecosystem for a Colab/Jupyter environment.
    This replaces the need for .env files and CLI scripts.
    """
    from dotenv import load_dotenv
    load_dotenv()
    
    print("🚀 Initializing Agora SDK...")
    
    if not circle_api_key:
        circle_api_key = os.getenv("CIRCLE_API_KEY")
    if not circle_api_key:
        print("❌ Please provide a circle_api_key or set CIRCLE_API_KEY in .env")
        return
        
    # Set environment variables for in-memory use across the SDK
    os.environ["CIRCLE_API_KEY"] = circle_api_key
    if groq_api_key:
        os.environ["GROQ_API_KEY"] = groq_api_key
    if gemini_api_key:
        os.environ["GEMINI_API_KEY"] = gemini_api_key
        
    os.environ["REDIS_HOST"] = str(redis_host)
    os.environ["REDIS_PORT"] = str(redis_port)
    os.environ["REDIS_DB"] = str(redis_db)

    # 1. Circle SDK import (fail fast if missing)
    try:
        from circle.web3 import utils as circle_utils
    except ImportError:
        print("❌ Circle SDK not installed. Please run: !pip install circle-developer-controlled-wallets")
        return

    from shared.core import get_circle_client

    # 2. Entity Secret Generation & Registration
    if not circle_entity_secret:
        circle_entity_secret = os.getenv("CIRCLE_ENTITY_SECRET")
        
    if not circle_entity_secret:
        print("🔐 Generating new Entity Secret...")
        circle_entity_secret = secrets.token_hex(32)
        os.environ["CIRCLE_ENTITY_SECRET"] = circle_entity_secret
        
        print("📤 Registering Entity Secret with Circle Console...")
        import tempfile
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                circle_utils.register_entity_secret_ciphertext(
                    api_key=circle_api_key,
                    entity_secret=circle_entity_secret,
                    recoveryFileDownloadPath=tmpdir
                )
            print("✅ Successfully registered Entity Secret.")
        except Exception as e:
            print(f"❌ Failed to register Entity Secret: {e}")
            print("   Make sure your CIRCLE_API_KEY is valid.")
            return
    else:
        os.environ["CIRCLE_ENTITY_SECRET"] = circle_entity_secret
        print("✅ Using provided Entity Secret.")

    # 3. Wallet Set Creation
    if not circle_wallet_set_id:
        circle_wallet_set_id = os.getenv("CIRCLE_WALLET_SET_ID")
        
    if not circle_wallet_set_id:
        print("⛓️  Creating Circle Wallet Set on Arc Testnet...")
        try:
            client = get_circle_client(
                api_key=circle_api_key,
                entity_secret=circle_entity_secret
            )
            circle_wallet_set_id = client.create_wallet_set(name="Agora_Colab_Agents")
            os.environ["CIRCLE_WALLET_SET_ID"] = circle_wallet_set_id
            print(f"✅ Created Wallet Set: {circle_wallet_set_id}")
        except Exception as e:
            print(f"❌ Failed to create Wallet Set: {e}")
            return
    else:
        os.environ["CIRCLE_WALLET_SET_ID"] = circle_wallet_set_id
        print(f"✅ Using provided Wallet Set: {circle_wallet_set_id}")

    # 4. Master Wallet Creation
    master_wallet_id = os.environ.get("CIRCLE_MASTER_WALLET_ID")
    if not master_wallet_id:
        print("💰 Creating Master Funder Wallet...")
        try:
            client = get_circle_client(
                api_key=circle_api_key,
                entity_secret=circle_entity_secret,
                wallet_set_id=circle_wallet_set_id
            )
            wallet_info = client.create_wallet("Master_Funder")
            os.environ["CIRCLE_MASTER_WALLET_ID"] = wallet_info["wallet_id"]
            master_address = wallet_info["address"]
            
            print("="*60)
            print(f"✅ BOOTSTRAP COMPLETE!")
            print("="*60)
            print(f"⚠️  IMPORTANT: You must fund the Master Wallet before creating Buyers.")
            print(f"   Address: {master_address}")
            print(f"   Fund here: https://faucet.circle.com/")
            print("="*60)
            
        except Exception as e:
            print(f"❌ Failed to create Master Wallet: {e}")
            return
    else:
        print(f"✅ Using existing Master Wallet: {master_wallet_id}")

def wait_for_funding(amount_needed: float = 0.5):
    """
    Pause execution and poll the Circle API until the Master Wallet is funded.
    Useful for Colab where you want the cell to block until the user finishes the faucet.
    """
    master_wallet_id = os.environ.get("CIRCLE_MASTER_WALLET_ID")
    if not master_wallet_id:
        print("❌ System not bootstrapped. Run agora_sdk.bootstrap() first.")
        return

    from shared.core import get_circle_client
    import time
    
    client = get_circle_client()
    master_address = client.get_wallet(master_wallet_id).get("address")
    
    print(f"⏳ Waiting for {amount_needed} USDC on {master_address}...")
    print("   Go to https://faucet.circle.com/ to send funds.")
    
    while True:
        try:
            balance = client.get_balance(master_wallet_id)
            if balance >= amount_needed:
                print(f"✅ Funds detected! Current balance: {balance} USDC")
                break
        except Exception as e:
            pass
        
        time.sleep(5)
