"""產生 e2e 的測試 CA 與三個公開 RSS 站的憑證（M3 票 21），寫進 `tests/fixtures/e2e/tls/`。

Berth 對 Mikan 番組頁與單一字幕組 feed 的網址是自己組的、寫死 `https://mikanani.me/`
（`adapters/rss/mikan.py`），所以替身（`tests/e2e/sites.py`）一定要講 TLS、Berth 一定要信它。
e2e 的 compose 把這三個主機名指到替身，再以 `SSL_CERT_FILE` 讓 Berth 的 httpx 多信這一張 CA
（`sites.py` 把它接在系統的 CA 清單後面，真的 TMDB 照樣驗得過）。

**私鑰進版控是刻意的**：它只簽得出這三個主機名、只有 e2e 的容器信它。一次產生、放三十年，
CI 不必裝 `cryptography`；要換（例如加一個站）就重跑：

    uv run --with cryptography python tests/e2e/make_tls.py

Python 3.13 起 `ssl.create_default_context()` 開著 `VERIFY_X509_STRICT`：CA 要有關鍵的
BasicConstraints 與 KeyUsage，葉憑證要有 AKI / SKI 與 SAN，缺一個就驗不過。
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

# `cryptography` 不是專案依賴（只有重產憑證時用得到，見上面的 `uv run --with`），
# 所以專案環境的 mypy 找不到它。
from cryptography import x509  # type: ignore[import-not-found]
from cryptography.hazmat.primitives import hashes, serialization  # type: ignore[import-not-found]
from cryptography.hazmat.primitives.asymmetric import ec  # type: ignore[import-not-found]
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID  # type: ignore[import-not-found]

OUT = Path(__file__).resolve().parents[1] / "fixtures" / "e2e" / "tls"
#: 替身冒充的主機名（`tests/e2e/compose.yml` 的 network aliases，`services/rss.py` 的 `_HOSTS`）。
HOSTS = ("mikanani.me", "nyaa.si", "acg.rip")
NOT_BEFORE = datetime(2026, 1, 1, tzinfo=UTC)
NOT_AFTER = datetime(2056, 1, 1, tzinfo=UTC)


def _name(common: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common)])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_ski = x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key())
    ca = (
        x509.CertificateBuilder()
        .subject_name(_name("Berth e2e test CA"))
        .issuer_name(_name("Berth e2e test CA"))
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(NOT_BEFORE)
        .not_valid_after(NOT_AFTER)
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=False,
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
        .add_extension(ca_ski, critical=False)
        .sign(ca_key, hashes.SHA256())
    )

    site_key = ec.generate_private_key(ec.SECP256R1())
    site = (
        x509.CertificateBuilder()
        .subject_name(_name(HOSTS[0]))
        .issuer_name(ca.subject)
        .public_key(site_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(NOT_BEFORE)
        .not_valid_after(NOT_AFTER)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(host) for host in HOSTS]), critical=False
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(site_key.public_key()), critical=False
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(ca_ski), critical=False
        )
        .sign(ca_key, hashes.SHA256())
    )

    pem = serialization.Encoding.PEM
    (OUT / "ca.pem").write_bytes(ca.public_bytes(pem))
    (OUT / "site.pem").write_bytes(site.public_bytes(pem))
    (OUT / "site.key").write_bytes(
        site_key.private_bytes(pem, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )


if __name__ == "__main__":
    main()
