from pypdf import PdfReader

def load_pdf(path: str) -> str:
    try:
        reader = PdfReader(path)
        text = ""

        for page in reader.pages:
            text += page.extract_text() or ""

        return text

    except Exception as e:
        print("PDF error:", e)
        return ""