"""Plain-text extraction from uploaded course material (PDF, TXT, DOCX, PPTX)."""
import html
import io
import re
import zipfile


class ExtractionError(Exception):
    pass


def _xml_text(data, member_prefix):
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = sorted(
            (n for n in zf.namelist() if n.startswith(member_prefix) and n.endswith('.xml')),
            key=lambda n: [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', n)],
        )
        parts = []
        for name in names:
            xml = zf.read(name).decode('utf-8', errors='ignore')
            # Paragraph ends become line breaks; then keep only the text runs.
            xml = re.sub(r'</(?:w|a):p>', '<w:t>\n</w:t>', xml)
            runs = re.findall(r'<(?:w|a):t(?:\s[^>]*)?>([^<]*)</(?:w|a):t>', xml)
            parts.append(html.unescape(''.join(runs)))
        return '\n'.join(parts)


def extract_text(file_field):
    """Return the text content of a CourseMaterial file, or raise ExtractionError."""
    name = file_field.name.lower()
    with file_field.open('rb') as handle:
        data = handle.read()

    if name.endswith('.txt'):
        return data.decode('utf-8', errors='ignore')
    if name.endswith('.pdf'):
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ExtractionError('PDF support needs the "pypdf" package.') from exc
        reader = PdfReader(io.BytesIO(data))
        return '\n'.join(page.extract_text() or '' for page in reader.pages)
    if name.endswith('.docx'):
        return _xml_text(data, 'word/document')
    if name.endswith('.pptx'):
        return _xml_text(data, 'ppt/slides/slide')
    raise ExtractionError('Text can only be read from PDF, TXT, DOCX or PPTX material.')
