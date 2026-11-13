"""Private-key conversion without deprecated PyOpenSSL crypto APIs."""

from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def load_rsa_private_key(key_path):
    """Convert Certbot's PKCS#8 (or PKCS#1) PEM to the CAS RSA PEM format."""
    private_key = serialization.load_pem_private_key(
        Path(key_path).read_bytes(), password=None
    )
    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise ValueError("CAS upload requires an RSA private key; use --key-type rsa")
    return private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode("ascii")


if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Convert an RSA private key to PKCS#1 PEM")
    parser.add_argument("source")
    parser.add_argument("destination")
    args = parser.parse_args()
    key = load_rsa_private_key(args.source)
    fd = os.open(args.destination, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as output:
        os.fchmod(output.fileno(), 0o600)
        output.write(key)
