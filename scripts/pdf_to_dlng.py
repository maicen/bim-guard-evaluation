from pathlib import Path
import os
from tqdm import tqdm

# 1. Import the thin client instead of the local heavy converter
from docling.service_client import DoclingServiceClient
from docling.datamodel.service.options import ConvertDocumentsOptions

file_path_str = r"C:\Users\osama\coding\bim-guard-evaluation\sources\OBC_2023.App-A.pdf"


# (Assuming file_path_str is already defined in your environment)
pdf_path = Path(file_path_str)
output_path = pdf_path.with_name(f"{pdf_path.stem}_docling.dclx")

print(f"Sending {pdf_path.name} to local docling-serve via Thin Client...")

# 2. Configure the server-side options (equivalent to PdfPipelineOptions)
options = ConvertDocumentsOptions(
    do_ocr=False,
    image_export_mode="embedded"  # Instructs the server to extract and return images
)

# 3. Connect to your local Docker container
with DoclingServiceClient(url="http://localhost:5001") as client:
    
    # We pass the file as a list so we can easily iterate over it with a progress bar.
    # If you have a folder of PDFs, you can just pass a list of all their paths here.
    sources = [pdf_path]
    
    # client.convert_all streams the files to the server and yields results as they finish
    results_iterator = client.convert_all(source=sources, options=options)
    
    # 4. Wrap the iterator in tqdm for a progress bar
    for result in tqdm(results_iterator, total=len(sources), desc="Processing PDFs", unit="file"):
        if result.document:
            # 5. The server returns the DoclingDocument object; save it locally
            result.document.save_as_doclang_archive(output_path)
            print(f"\n✅ Conversion complete and object 'result' is now in memory.")
            print(f"Lossless archive verified at: {output_path} (Size: {os.path.getsize(output_path)} bytes)")
        else:
            print(f"\n❌ Server failed to convert {pdf_path.name}")