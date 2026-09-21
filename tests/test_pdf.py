from rag.document_loader import load_pdf_file
from pypdf import PdfReader

pdf_path = "documents/pdf/AI_Data_Analyst_Chatbot_Roadmap.pdf"

print("=== DIRECT PDF TEST ===")

reader = PdfReader(pdf_path)

print("PDF pages:", len(reader.pages))

first_page_text = reader.pages[0].extract_text() or ""

print("First page characters:", len(first_page_text))
print("First page preview:")
print(repr(first_page_text[:500]))

print()
print("=== OUR LOADER TEST ===")

docs = load_pdf_file(pdf_path)

print("Documents loaded:", len(docs))

for doc in docs:
    print(
        "Page:",
        doc.metadata["page"],
        "| Characters:",
        len(doc.page_content)
    )