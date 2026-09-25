"""
scripts/pdf_to_dclg.py
------------------------------------------------
CLI: converts a source code PDF into plain DocLang markup (.dclg) via a
local docling-serve instance. First step of the repeatable code-ingestion
pipeline documented in docs/kg-ingestion-pipeline.md.

Usage:
    uv run python scripts/pdf_to_dclg.py --input sources/SBC-201-2007.pdf
    uv run python scripts/pdf_to_dclg.py --input sources/SBC-201-2007.pdf \\
        --output sources/SBC-201-2007_docling.dclg \\
        --url https://docling-serve.bim-guard.orb.local/
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

import certifi
from docling.datamodel.service.options import ConvertDocumentsOptions
from docling.service_client import DoclingServiceClient, StatusWatcherKind
from tqdm import tqdm

DEFAULT_URL = "https://docling-serve.bim-guard.orb.local/"


def _trust_orb_local_cert(url: str) -> None:
    """OrbStack's *.orb.local domains serve a self-signed, OrbStack-issued
    cert that macOS/curl trust via the system keychain but Python's certifi
    bundle does not know about, so httpx (used internally by
    DoclingServiceClient) fails TLS verification with
    CERTIFICATE_VERIFY_FAILED. Rather than disabling verification, fetch
    that host's own cert chain over TLS and append it to a copy of
    certifi's bundle, then point httpx at that combined bundle via
    SSL_CERT_FILE for the rest of this process -- verification stays on,
    it just also trusts this one local, OrbStack-controlled host.

    httpx (see httpx._config.create_ssl_context) checks the SSL_CERT_FILE
    env var *before* falling back to certifi.where(), so that env var is
    the hook that actually reaches the httpx.Client DoclingServiceClient
    builds internally -- monkeypatching certifi.where() directly does not,
    since that env-var check short-circuits before certifi is ever
    consulted."""
    parts = urlsplit(url)
    if not parts.hostname or not parts.hostname.endswith(".orb.local"):
        return

    port = parts.port or 443
    # ssl.get_server_certificate() only returns the leaf cert, not the
    # intermediate/root that actually signed it -- that's not enough for
    # verification to succeed, so shell out to openssl for the full chain.
    proc = subprocess.run(
        ["openssl", "s_client", "-connect", f"{parts.hostname}:{port}", "-servername", parts.hostname, "-showcerts"],
        input="", capture_output=True, text=True, timeout=15,
    )
    cert_blocks = re.findall(
        r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", proc.stdout, re.DOTALL
    )
    if not cert_blocks:
        raise RuntimeError(f"could not fetch TLS cert chain for {parts.hostname}:{port} via openssl s_client")
    chain_pem = "\n".join(cert_blocks)

    combined = tempfile.NamedTemporaryFile(
        mode="w", suffix=".pem", prefix="docling_orb_local_ca_", delete=False
    )
    with open(certifi.where(), encoding="utf-8") as f:
        combined.write(f.read())
    combined.write("\n")
    combined.write(chain_pem)
    combined.close()

    os.environ["SSL_CERT_FILE"] = combined.name


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, type=Path, help="Source code PDF, e.g. sources/SBC-201-2007.pdf")
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Output .dclg path (default: <input stem>_docling.dclg next to the input)",
    )
    parser.add_argument("--url", default=DEFAULT_URL, help="docling-serve base URL")
    parser.add_argument("--ocr", action="store_true", help="Enable OCR (default: off, for text-native PDFs)")
    args = parser.parse_args(argv)

    pdf_path = args.input
    if not pdf_path.exists():
        parser.error(f"input PDF not found: {pdf_path}")
    output_path = args.output or pdf_path.with_name(f"{pdf_path.stem}_docling.dclg")

    _trust_orb_local_cert(args.url)

    file_size_mb = pdf_path.stat().st_size / (1024 * 1024)
    print(f"Sending {pdf_path.name} ({file_size_mb:.2f} MB) to docling-serve ({args.url}) via Thin Client...")

    # Server-side conversion options (equivalent to PdfPipelineOptions).
    options = ConvertDocumentsOptions(
        do_ocr=args.ocr,
        image_export_mode="placeholder",  # extract images, but keep the .dclg text-only
    )

    # Polling instead of the default websocket status watcher: on this
    # OrbStack setup the server redirects the websocket reconnect to a
    # raw internal container IP that isn't routable from outside the VM,
    # so it hangs retrying forever. Polling re-uses the same base URL for
    # every request instead.
    with DoclingServiceClient(url=args.url, status_watcher=StatusWatcherKind.POLLING) as client:
        sources = [pdf_path]
        results_iterator = client.convert_all(source=sources, options=options)

        with tqdm(total=len(sources), desc=f"Converting {pdf_path.name}", unit="doc") as pbar:
            start_time = time.time()
            failed = False
            for result in results_iterator:
                elapsed = time.time() - start_time
                if result.document:
                    num_pages = len(result.document.pages)
                    # Save DoclingDocument as plain DocLang markup (not an OPC archive).
                    result.document.save_as_doclang(output_path)
                    pbar.set_postfix_str(f"{num_pages} pages ({elapsed:.1f}s)")
                    pbar.update(1)
                    tqdm.write(f"\n✅ Conversion complete: {num_pages} pages processed in {elapsed:.1f}s.")
                    tqdm.write(f"DocLang file saved at: {output_path} (Size: {os.path.getsize(output_path):,} bytes)")
                else:
                    pbar.update(1)
                    tqdm.write(f"\n❌ Server failed to convert {pdf_path.name}")
                    failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
