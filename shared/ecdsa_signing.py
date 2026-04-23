"""
shared/ecdsa_signing.py

ECDSA signing and verification for x402 payment headers.
Uses secp256k1 (Ethereum standard) via eth_keys.
"""

import os
from eth_keys import keys
from eth_utils import keccak
import json
import hashlib
import secrets


def generate_keypair():
    """Generate a new secure random ECDSA keypair (secp256k1)."""
    # Use secrets module for cryptographically secure random private key
    private_key_bytes = secrets.token_bytes(32)
    private_key = keys.PrivateKey(private_key_bytes)
    return {
        "private_key_hex": private_key.to_hex(),
        "public_key_hex": private_key.public_key.to_hex(),
        "address": private_key.public_key.to_checksum_address()
    }


def create_payload_hash(amount_usdc: float, sender: str, recipient: str, 
                        nonce: str, expiry_timestamp: int) -> str:
    """Create SHA256 hash of payment payload."""
    payload = {
        "amount_usdc": amount_usdc,
        "sender": sender.lower(),
        "recipient": recipient.lower(),
        "nonce": nonce,
        "expiry": expiry_timestamp
    }
    payload_json = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(payload_json.encode()).hexdigest()


def sign_x402_header(private_key_hex: str, amount_usdc: float, sender: str, 
                     recipient: str, nonce: str, expiry_timestamp: int) -> dict:
    """
    Generate a signed x402 payment header.
    
    Returns:
        {
            "amount": float,
            "sender": str,
            "recipient": str,
            "nonce": str,
            "expiry": int,
            "signature": str (hex)
        }
    """
    private_key = keys.PrivateKey(bytes.fromhex(private_key_hex.replace("0x", "")))
    
    # Create payload hash
    payload_hash = create_payload_hash(amount_usdc, sender, recipient, nonce, expiry_timestamp)
    
    # Sign with private key (ECDSA secp256k1)
    message_bytes = bytes.fromhex(payload_hash)
    signature = private_key.sign_msg(message_bytes)
    
    return {
        "amount": amount_usdc,
        "sender": sender,
        "recipient": recipient,
        "nonce": nonce,
        "expiry": expiry_timestamp,
        "signature": signature.to_hex(),
        "public_key": private_key.public_key.to_hex()
    }


def verify_x402_signature(header: dict) -> bool:
    """
    Verify an x402 payment header signature.
    
    Args:
        header: {
            "amount": float,
            "sender": str,
            "recipient": str,
            "nonce": str,
            "expiry": int,
            "signature": str,
            "public_key": str
        }
    
    Returns:
        True if signature is valid, False otherwise
    """
    try:
        # Recreate payload hash
        payload_hash = create_payload_hash(
            header["amount"],
            header["sender"],
            header["recipient"],
            header["nonce"],
            header["expiry"]
        )
        
        # Recover public key from signature
        message_bytes = bytes.fromhex(payload_hash)
        sig_bytes = bytes.fromhex(header["signature"].replace("0x", ""))
        sig = keys.Signature(sig_bytes)
        
        recovered_pubkey = sig.recover_public_key(message_bytes)
        recovered_address = recovered_pubkey.to_checksum_address()
        
        # Check if recovered address matches sender
        return recovered_address.lower() == header["sender"].lower()
    
    except Exception as e:
        print(f"Signature verification failed: {e}")
        return False


def validate_x402_header(header: dict, expected_recipient: str) -> tuple[bool, str]:
    """
    Full validation of x402 header:
    1. Signature is valid
    2. Recipient matches expected recipient
    3. Expiry is in the future
    
    Returns:
        (valid: bool, reason: str)
    """
    import time
    
    # Check expiry
    if header["expiry"] < int(time.time()):
        return False, "Header expired"
    
    # Check recipient
    if header["recipient"].lower() != expected_recipient.lower():
        return False, "Recipient mismatch"
    
    # Check signature
    if not verify_x402_signature(header):
        return False, "Invalid signature"
    
    return True, "OK"


if __name__ == "__main__":
    # Quick test
    keypair = generate_keypair()
    print(f"Private key: {keypair['private_key_hex']}")
    print(f"Address: {keypair['address']}")
    
    # Create a signed header
    import time
    now = int(time.time())
    header = sign_x402_header(
        keypair["private_key_hex"],
        0.001,  # $0.001 USDC
        keypair["address"],
        "0x1234567890123456789012345678901234567890",  # recipient
        "nonce-12345",
        now + 60
    )
    
    print(f"\nSigned header: {header}")
    
    # Verify it
    valid, reason = validate_x402_header(header, header["recipient"])
    print(f"Verification: {valid} ({reason})")
