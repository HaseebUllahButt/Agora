import base64
import binascii
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA256

# ==========================================
# CONFIGURATION
# ==========================================
# 1. Your 32-byte hex secret (64 characters total)
# Example: "9b9e20b9feb25c367d6e05adf1fd38fa71d7fe80b68ecdca08b813b29cdec9c3"
ENTITY_SECRET_HEX = "d48f9a221e91ca671d3b7cd16757a05de6987ab80828b4b931aeec65977cf953"

# 2. Your Public Key from the NEW account
PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEAxfjz9QXkFm6pbyXYYK/y
YzGIqn/0duly5s5uIdQSoIyRoV/VC6tySYGiQ90lqyxZbEdwjK6EtyZCK2TDF+xA
jPlCq3L3gVHFni39OaZYWAHuwe+zF3Pxoc2YW3RCFf+/CMybHRbE6mooz4TBdFKW
eYiuHtJfu7k4MsA6YC8rr6BraeC83BFguWmzvHpglIXI40tUGaNLemNn1cA3DTGd
i8l158Py9Z8wtCHhailWdabGPTzJbX1DmHJuE4uvZhuWalwBQrwu9wd1dSV4g4ve
Z/FOkQKxfT6EjmqO9irwrR1SJkkbJvNA61lelr19uQh+BJwqRrXDFu+HYxcWSDy2
UbKTLcC2d0OQ6/q0wbLTY1rbtkZP8C3ClbHRYiS8hbr+qmYra6RA2GHKJgYr76IM
lo7qWwcppYWtl99WUT77ieiIP5d6xZ5zf18ANYvK61GqZxm4wis5O147beeQhebp
z17J12WjcPssg9deG6uTHAJZfe9m6myqgnQ60C9jQ1J2F59reny3mxsZz8hGIwYz
qOj+opIvr2cUUHaeSk4EzFzTOSXypxHsX1xGHlaZanDbfDXvkNV3t1sIcu4hXS4V
X8TaCdYFpFLEKZjgi7fNI+SxjNIj54RpJRLBd/AVcx4CL7ORNY4MqTAaPq/W4rPg
JoCLaIPqZlGZkws+CoJR9c0CAwEAAQ==
-----END PUBLIC KEY-----"""

def run_encryption():
    try:
        # Validate hex secret length
        if len(ENTITY_SECRET_HEX) != 64:
            print(f"❌ Error: Your secret is {len(ENTITY_SECRET_HEX)} chars. It MUST be 64.")
            return

        # Load RSA Key
        rsa_key = RSA.importKey(PUBLIC_KEY_PEM)
        
        # Initialize Cipher with Circle's required specs (OAEP + SHA256)
        cipher = PKCS1_OAEP.new(
            key=rsa_key,
            hashAlgo=SHA256,
            mgfunc=lambda x, y: PKCS1_OAEP.MGF1(x, y, SHA256)
        )
        
        # Convert hex string to raw bytes and encrypt
        secret_bytes = binascii.unhexlify(ENTITY_SECRET_HEX)
        ciphertext = cipher.encrypt(secret_bytes)
        
        # Convert to Base64 for the web console
        final_string = base64.b64encode(ciphertext).decode()
        
        print("\n" + "="*70)
        print("PASTE THIS INTO THE CIRCLE CONSOLE:")
        print("="*70)
        print(final_string)
        print("="*70)
        print(f"Length: {len(final_string)} characters")

    except Exception as e:
        print(f"❌ Encryption failed: {e}")

if __name__ == "__main__":
    run_encryption()
