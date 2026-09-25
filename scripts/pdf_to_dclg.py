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

Large PDFs are converted in page-range chunks (see --chunk-pages) rather
than as one request: against this docling-serve instance, a single
~50-page request took ~5 minutes, and a 372-page request over the same
connection reliably failed partway through (empirically, somewhere past
the 3-5 minute mark) well before the server could have actually finished
-- consistent with an idle/keepalive timeout on the connection or a local
proxy in front of it, not a docling-serve processing limit.

Each chunk's DocLang output is cached to <output>.chunks/ as soon as it's
produced, keyed by its page range -- re-running the same command after a
failure (this host's docling-serve connection is itself intermittent;
see docs/kg-ingestion-pipeline.md) skips every chunk already converted
and only retries what's missing, and each chunk that does need a live
call gets its own retry-with-backoff before the whole run gives up. Once
every chunk has a cached .dclg, they're stitched into one final .dclg
with a single <doclang> root, byte-identical in content to what a single
(theoretically unbounded) request would have produced.
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
import pypdf
from docling.datamodel.service.options import ConvertDocumentsOptions
from docling.service_client import DoclingServiceClient, StatusWatcherKind
from tqdm import tqdm

DEFAULT_URL = "https://docling-serve.bim-guard.orb.local/"
DEFAULT_CHUNK_PAGES = 40
MAX_ATTEMPTS_PER_CHUNK = 3
RETRY_BACKOFF_SECONDS = 5.0

_DOCLANG_ROOT_RE = re.compile(r"^(\s*<doclang[^>]*>)(.*)(</doclang>\s*)$", re.DOTALL)


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

    fd, combined_path_str = tempfile.mkstemp(prefix="docling_orb_local_ca_", suffix=".pem")
    os.close(fd)
    combined_path = Path(combined_path_str)
    with open(certifi.where(), encoding="utf-8") as f:
        bundle = f.read()
    combined_path.write_text(bundle + "\n" + chain_pem, encoding="utf-8")

    os.environ["SSL_CERT_FILE"] = str(combined_path)


class ChunkPlan:
    """One page-range slice of the source PDF, and where its split PDF and
    converted .dclg live in the on-disk cache directory."""

    def __init__(self, cache_dir: Path, stem: str, start_page: int, end_page: int):
        self.start_page = start_page  # 1-indexed, inclusive
        self.end_page = end_page  # 1-indexed, inclusive
        label = f"{stem}_pages_{start_page:04d}-{end_page:04d}"
        self.pdf_path = cache_dir / f"{label}.pdf"
        self.dclg_path = cache_dir / f"{label}.dclg"

    @property
    def label(self) -> str:
        return f"pages {self.start_page}-{self.end_page}"

    @property
    def is_cached(self) -> bool:
        return self.dclg_path.is_file() and self.dclg_path.stat().st_size > 0


def _plan_chunks(pdf_path: Path, chunk_pages: int, cache_dir: Path) -> list[ChunkPlan]:
    reader = pypdf.PdfReader(pdf_path)
    total_pages = len(reader.pages)
    if chunk_pages <= 0:
        chunk_pages = total_pages
    plans = [
        ChunkPlan(cache_dir, pdf_path.stem, start + 1, min(start + chunk_pages, total_pages))
        for start in range(0, total_pages, chunk_pages)
    ]
    return plans


def _ensure_chunk_pdf(plan: ChunkPlan, source_reader: pypdf.PdfReader) -> None:
    if plan.pdf_path.is_file():
        return
    writer = pypdf.PdfWriter()
    for page in source_reader.pages[plan.start_page - 1 : plan.end_page]:
        writer.add_page(page)
    with open(plan.pdf_path, "wb") as f:
        writer.write(f)


def _convert_chunk(client: DoclingServiceClient, plan: ChunkPlan, options: ConvertDocumentsOptions) -> int | None:
    """Converts one chunk's PDF and writes its .dclg to the cache. Returns
    the page count on success, None on failure (caller decides whether to
    retry)."""
    for result in client.convert_all(source=[plan.pdf_path], options=options):
        if result.document:
            result.document.save_as_doclang(plan.dclg_path)
            return len(result.document.pages)
        return None
    return None


def _concat_doclang(bodies: list[str]) -> str:
    """Concatenates multiple single-root <doclang>...</doclang> documents'
    inner content into one combined document with a single root."""
    if len(bodies) == 1:
        return bodies[0]
    open_tag = close_tag = None
    inner_parts = []
    for text in bodies:
        m = _DOCLANG_ROOT_RE.match(text)
        if not m:
            raise ValueError("chunk output is not a well-formed single-root <doclang> document")
        open_tag = open_tag or m.group(1)
        close_tag = close_tag or m.group(3)
        inner_parts.append(m.group(2))
    return open_tag + "".join(inner_parts) + close_tag


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, type=Path, help="Source code PDF, e.g. sources/SBC-201-2007.pdf")
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Output .dclg path (default: <input stem>_docling.dclg next to the input)",
    )
    parser.add_argument("--url", default=DEFAULT_URL, help="docling-serve base URL")
    parser.add_argument("--ocr", action="store_true", help="Enable OCR (default: off, for text-native PDFs)")
    parser.add_argument(
        "--chunk-pages", type=int, default=DEFAULT_CHUNK_PAGES,
        help=f"Split into page-range chunks of this size before converting (default: {DEFAULT_CHUNK_PAGES}). "
             "0 disables chunking and sends the whole PDF in one request.",
    )
    parser.add_argument(
        "--keep-chunk-cache", action="store_true",
        help="Don't delete <output>.chunks/ after a successful run (default: deleted once the stitched "
             ".dclg is written; kept automatically on any failure so a re-run can resume).",
    )
    args = parser.parse_args(argv)

    pdf_path = args.input
    if not pdf_path.exists():
        parser.error(f"input PDF not found: {pdf_path}")
    output_path = args.output or pdf_path.with_name(f"{pdf_path.stem}_docling.dclg")
    cache_dir = output_path.with_name(output_path.stem + ".chunks")
    cache_dir.mkdir(parents=True, exist_ok=True)

    _trust_orb_local_cert(args.url)

    file_size_mb = pdf_path.stat().st_size / (1024 * 1024)
    print(f"Sending {pdf_path.name} ({file_size_mb:.2f} MB) to docling-serve ({args.url}) via Thin Client...")

    options = ConvertDocumentsOptions(
        do_ocr=args.ocr,
        image_export_mode="placeholder",  # extract images, but keep the .dclg text-only
    )

    plans = _plan_chunks(pdf_path, args.chunk_pages, cache_dir)
    already_cached = sum(p.is_cached for p in plans)
    print(f"{len(plans)} chunk(s) of up to {max(args.chunk_pages, 1)} pages each -> cache: {cache_dir}")
    if already_cached:
        print(f"{already_cached}/{len(plans)} already converted from a previous run -- resuming")

    source_reader = pypdf.PdfReader(pdf_path)
    failed_plan: ChunkPlan | None = None
    total_pages = 0
    start_time = time.time()

    # Polling instead of the default websocket status watcher: on this
    # OrbStack setup the server redirects the websocket reconnect to a raw
    # internal container IP that isn't routable from outside the VM, so it
    # hangs retrying forever. Polling re-uses the same base URL every time.
    with tqdm(total=len(plans), desc=f"Converting {pdf_path.name}", unit="chunk") as pbar:
        for plan in plans:
            if plan.is_cached:
                pbar.update(1)
                continue

            _ensure_chunk_pdf(plan, source_reader)

            num_pages = None
            for attempt in range(1, MAX_ATTEMPTS_PER_CHUNK + 1):
                try:
                    with DoclingServiceClient(url=args.url, status_watcher=StatusWatcherKind.POLLING) as client:
                        num_pages = _convert_chunk(client, plan, options)
                except Exception as exc:  # noqa: BLE001 -- any transport/service error is retryable here
                    tqdm.write(f"  [{plan.label}] attempt {attempt}/{MAX_ATTEMPTS_PER_CHUNK} raised {exc!r}")
                    num_pages = None

                if num_pages is not None:
                    break
                if attempt < MAX_ATTEMPTS_PER_CHUNK:
                    tqdm.write(
                        f"  [{plan.label}] attempt {attempt}/{MAX_ATTEMPTS_PER_CHUNK} failed, "
                        f"retrying in {RETRY_BACKOFF_SECONDS:.0f}s..."
                    )
                    time.sleep(RETRY_BACKOFF_SECONDS)

            if num_pages is None:
                tqdm.write(f"\n❌ Giving up on {plan.label} after {MAX_ATTEMPTS_PER_CHUNK} attempts")
                failed_plan = plan
                break

            total_pages += num_pages
            pbar.update(1)
            pbar.set_postfix_str(f"{total_pages} pages ({time.time() - start_time:.1f}s)")

    if failed_plan is not None:
        print(
            f"\nStopped at {failed_plan.label} -- {sum(p.is_cached for p in plans)}/{len(plans)} chunks "
            f"cached in {cache_dir}. Re-run the same command to resume; already-converted chunks are skipped."
        )
        return 1

    bodies = [p.dclg_path.read_text(encoding="utf-8") for p in plans]
    combined = _concat_doclang(bodies)
    output_path.write_text(combined, encoding="utf-8")

    if not args.keep_chunk_cache:
        for p in plans:
            p.pdf_path.unlink(missing_ok=True)
            p.dclg_path.unlink(missing_ok=True)
        cache_dir.rmdir()

    total_pages = sum(p.end_page - p.start_page + 1 for p in plans)
    elapsed = time.time() - start_time
    print(f"\n✅ Conversion complete: {total_pages} pages processed in {elapsed:.1f}s.")
    print(f"DocLang file saved at: {output_path} (Size: {os.path.getsize(output_path):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
