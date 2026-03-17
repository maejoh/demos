"""Tests for scripts/book_pipeline/epub.py."""

import io
import zipfile

from scripts.book_pipeline.epub import extract_epub_metadata


CONTAINER_XML = b"""\
<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="content.opf"
              media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""


def make_epub(title="Test Book", author="Test Author", isbn="9781234567890", date="2020-01-01") -> io.BytesIO:
    """Build a minimal valid epub (zip) in memory."""
    opf = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"
            xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>{title}</dc:title>
    <dc:creator>{author}</dc:creator>
    <dc:identifier opf:scheme="ISBN">{isbn}</dc:identifier>
    <dc:date>{date}</dc:date>
  </metadata>
</package>
""".encode()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("META-INF/container.xml", CONTAINER_XML)
        zf.writestr("content.opf", opf)
    buf.seek(0)
    return buf


class TestExtractEpubMetadata:
    def test_extracts_title_author_isbn_and_year(self, tmp_path):
        epub_path = tmp_path / "test.epub"
        epub_path.write_bytes(make_epub().read())

        result = extract_epub_metadata(epub_path)

        assert result is not None
        assert result["title"] == "Test Book"
        assert result["author"] == "Test Author"
        assert result["isbn"] == "9781234567890"
        assert result["year"] == 2020

    def test_returns_none_for_epub_with_no_title(self, tmp_path):
        epub_path = tmp_path / "notitle.epub"
        epub_path.write_bytes(make_epub(title="").read())

        result = extract_epub_metadata(epub_path)

        assert result is None

    def test_returns_none_for_corrupt_epub(self, tmp_path):
        epub_path = tmp_path / "corrupt.epub"
        epub_path.write_bytes(b"not a zip file")

        result = extract_epub_metadata(epub_path)

        assert result is None
