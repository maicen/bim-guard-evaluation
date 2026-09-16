import time
from pathlib import Path
import os
from tqdm import tqdm

# 1. Import the thin client instead of the local heavy converter
from docling.service_client import DoclingServiceClient
from docling.datamodel.service.options import ConvertDocumentsOptions

file_path_str = r"C:\Users\osama\coding\bim-guard-evaluation\sources\OBC_2023.App-A.pdf"

pdf_path = Path(file_path_str)
output_path = pdf_path.with_name(f"{pdf_path.stem}_docling.dclx")

file_size_mb = pdf_path.stat().st_size / (1024 * 1024)
print(f"Sending {pdf_path.name} ({file_size_mb:.2f} MB) to local docling-serve via Thin Client...")

# 2. Configure the server-side options (equivalent to PdfPipelineOptions)
options = ConvertDocumentsOptions(
    do_ocr=False,
    image_export_mode="embedded"  # Instructs the server to extract and return images
)

# 3. Connect to your local Docker container
with DoclingServiceClient(url="http://localhost:5001") as client:
    sources = [pdf_path]
    results_iterator = client.convert_all(source=sources, options=options)
    
    # 4. Wrap the iterator in tqdm with clean logging and elapsed timing
    with tqdm(total=len(sources), desc=f"Converting {pdf_path.name}", unit="doc") as pbar:
        start_time = time.time()
        for result in results_iterator:
            elapsed = time.time() - start_time
            if result.document:
                num_pages = len(result.document.pages)
                # 5. Save DoclingDocument archive locally
                result.document.save_as_doclang_archive(output_path)
                pbar.set_postfix_str(f"{num_pages} pages ({elapsed:.1f}s)")
                pbar.update(1)
                tqdm.write(f"\n✅ Conversion complete: {num_pages} pages processed in {elapsed:.1f}s.")
                tqdm.write(f"Lossless archive verified at: {output_path} (Size: {os.path.getsize(output_path):,} bytes)")
            else:
                pbar.update(1)
                tqdm.write(f"\n❌ Server failed to convert {pdf_path.name}")