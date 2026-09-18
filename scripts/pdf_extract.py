from pypdf import PdfReader, PdfWriter

def extract_pages(input_pdf, output_pdf, pages_to_extract):
    """
    Extracts specified pages from a PDF and saves them to a new PDF.
    :param input_pdf: Path to the source PDF file
    :param output_pdf: Path where the extracted PDF should be saved
    :param pages_to_extract: List of 0-indexed page numbers to extract (e.g., [0, 2] for pages 1 and 3)
    """
    reader = PdfReader(input_pdf)
    writer = PdfWriter()
    
    # Loop through and add only the requested pages
    for page_num in pages_to_extract:
        if page_num < len(reader.pages):
            writer.add_page(reader.pages[page_num])
        else:
            print(f"Warning: Page index {page_num} is out of range for this PDF.")

    # Save the new subset PDF
    with open(output_pdf, "wb") as out_file:
        writer.write(out_file)
    print(f"Successfully extracted pages to {output_pdf}")

# Example usage: Extracting the 1st, 3rd, and 5th pages (0, 2, and 4 in 0-indexed count)
extract_pages("sources\\OBC_2023.Volume_1_P_9.pdf", "sources\\OBC_2023.Volume_1_P_9_extracted_subset.pdf", list(range(0, 4)))
