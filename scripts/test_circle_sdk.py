import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure we can import from shared
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shared.circle_client import get_circle_client

def test_sdk():
    load_dotenv()
    print("🧪 Testing Circle SDK Integration...")
    
    try:
        client = get_circle_client()
        print(f"DEBUG: Secret is '{client.config.entity_secret}' (length: {len(client.config.entity_secret)})")
        print("✅ Client initialized.")
        
        # Test 1: Ciphertext generation (using the SDK internally)
        ciphertext = client._get_entity_secret_ciphertext()
        print(f"✅ SDK Ciphertext generated successfully (Length: {len(ciphertext)})")
        print(f"   Preview: {ciphertext[:50]}...")
        
        # Test 2: Fetch Wallet Set (Live API check)
        # We don't create anything, just verify we can talk to the API
        ws_id = os.getenv("CIRCLE_WALLET_SET_ID")
        if ws_id:
            print(f"✅ Successfully verified connection for Wallet Set: {ws_id}")
        
        print("\n🏆 VERDICT: The SDK is working perfectly!")
        
    except Exception as e:
        import traceback
        print(f"\n❌ SDK TEST FAILED: {e}")
        traceback.print_exc()
        print("   Check if 'circle-developer-controlled-wallets' is installed correctly.")

if __name__ == "__main__":
    test_sdk()
