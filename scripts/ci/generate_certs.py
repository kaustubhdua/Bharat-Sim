#!/usr/bin/env python3
"""Generate self-contained local CA and TLS certificates for the CI HTTPS probe."""
from __future__ import annotations

import ipaddress
from datetime import datetime, timedelta, timezone
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import NameOID


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent.parent
    cert_dir = repo_root / "scripts" / "ci" / "certs"
    cert_dir.mkdir(parents=True, exist_ok=True)
    res_raw = repo_root / "smoke-android" / "app" / "src" / "debug" / "res" / "raw"
    res_raw.mkdir(parents=True, exist_ok=True)

    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "BharatSim"),
        x509.NameAttribute(NameOID.COMMON_NAME, "BharatSim CI Root CA"),
    ])
    now = datetime.now(timezone.utc)
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None), critical=True
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )

    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    server_name = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "BharatSim"),
        x509.NameAttribute(NameOID.COMMON_NAME, "probe.bharatsim.local"),
    ])
    san = x509.SubjectAlternativeName([
        x509.DNSName("probe.bharatsim.local"),
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.IPv4Address("198.18.77.2")),
        x509.IPAddress(ipaddress.IPv4Address("198.18.77.1")),
        x509.IPAddress(ipaddress.IPv4Address("10.0.2.2")),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
    ])
    server_cert = (
        x509.CertificateBuilder()
        .subject_name(server_name)
        .issuer_name(ca_name)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([x509.ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(server_key.public_key()),
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
            critical=False,
        )
        .add_extension(san, critical=False)
        .sign(ca_key, hashes.SHA256())
    )

    ca_pem = ca_cert.public_bytes(serialization.Encoding.PEM)
    server_cert_pem = server_cert.public_bytes(serialization.Encoding.PEM)
    server_key_pem = server_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )

    (cert_dir / "ca.crt").write_bytes(ca_pem)
    (cert_dir / "server.crt").write_bytes(server_cert_pem)
    (cert_dir / "server.key").write_bytes(server_key_pem)
    (res_raw / "ci_ca.crt").write_bytes(ca_pem)

    print("Generated certificates:")
    print(f"  CA cert: {cert_dir / 'ca.crt'} ({len(ca_pem)} bytes)")
    print(f"  Server cert: {cert_dir / 'server.crt'} ({len(server_cert_pem)} bytes)")
    print(f"  Server key: {cert_dir / 'server.key'} ({len(server_key_pem)} bytes)")
    print(f"  Android raw cert: {res_raw / 'ci_ca.crt'} ({len(ca_pem)} bytes)")


if __name__ == "__main__":
    main()
