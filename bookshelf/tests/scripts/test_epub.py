"""Tests for scripts/book_pipeline/epub.py."""

import io
import zipfile

import pytest

from scripts.book_pipeline.epub import extract_epub_cover, extract_epub_metadata


CONTAINER_XML = b"""\
<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="content.opf"
              media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

FAKE_COVER_BYTES = b"\xff\xd8\xff\xe0"  # JPEG magic bytes


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


def make_epub_epub3_cover(cover_ext=".jpg") -> io.BytesIO:
    """Build an epub with an EPUB3 manifest cover-image entry."""
    opf = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Cover Book</dc:title>
  </metadata>
  <manifest>
    <item id="cover-img" href="images/cover{cover_ext}" media-type="image/jpeg" properties="cover-image"/>
  </manifest>
</package>
""".encode()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("META-INF/container.xml", CONTAINER_XML)
        zf.writestr("content.opf", opf)
        zf.writestr(f"images/cover{cover_ext}", FAKE_COVER_BYTES)
    buf.seek(0)
    return buf


def make_epub_epub2_cover() -> io.BytesIO:
    """Build an epub with an EPUB2 <meta name="cover"> entry."""
    opf = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>EPUB2 Book</dc:title>
    <meta name="cover" content="cover-img"/>
  </metadata>
  <manifest>
    <item id="cover-img" href="images/cover.jpg" media-type="image/jpeg"/>
  </manifest>
</package>
"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("META-INF/container.xml", CONTAINER_XML)
        zf.writestr("content.opf", opf)
        zf.writestr("images/cover.jpg", FAKE_COVER_BYTES)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# extract_epub_metadata
# ---------------------------------------------------------------------------

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

    def test_returns_unknown_when_no_author(self, tmp_path):
        opf = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"
            xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>No Author Book</dc:title>
    <dc:identifier opf:scheme="ISBN">9781234567890</dc:identifier>
  </metadata>
</package>
"""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("META-INF/container.xml", CONTAINER_XML)
            zf.writestr("content.opf", opf)
        epub_path = tmp_path / "noauthor.epub"
        epub_path.write_bytes(buf.getvalue())

        result = extract_epub_metadata(epub_path)

        assert result is not None
        assert result["author"] == "Unknown"

    def test_detects_isbn_by_978_text_prefix_without_scheme(self, tmp_path):
        opf = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>No Scheme Book</dc:title>
    <dc:identifier>9780123456789</dc:identifier>
  </metadata>
</package>
"""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("META-INF/container.xml", CONTAINER_XML)
            zf.writestr("content.opf", opf)
        epub_path = tmp_path / "noscheme.epub"
        epub_path.write_bytes(buf.getvalue())

        result = extract_epub_metadata(epub_path)

        assert result is not None
        assert result["isbn"] == "9780123456789"

    def test_returns_none_isbn_when_no_isbn_in_epub(self, tmp_path):
        opf = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>No ISBN Book</dc:title>
    <dc:creator>Some Author</dc:creator>
    <dc:identifier>uuid:some-random-uuid</dc:identifier>
  </metadata>
</package>
"""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("META-INF/container.xml", CONTAINER_XML)
            zf.writestr("content.opf", opf)
        epub_path = tmp_path / "noisbn.epub"
        epub_path.write_bytes(buf.getvalue())

        result = extract_epub_metadata(epub_path)

        assert result is not None
        assert result["isbn"] is None

    def test_returns_none_year_when_no_date(self, tmp_path):
        opf = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"
            xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>No Date Book</dc:title>
    <dc:identifier opf:scheme="ISBN">9781234567890</dc:identifier>
  </metadata>
</package>
"""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("META-INF/container.xml", CONTAINER_XML)
            zf.writestr("content.opf", opf)
        epub_path = tmp_path / "nodate.epub"
        epub_path.write_bytes(buf.getvalue())

        result = extract_epub_metadata(epub_path)

        assert result is not None
        assert result["year"] is None


# ---------------------------------------------------------------------------
# extract_epub_cover
# ---------------------------------------------------------------------------

class TestExtractEpubCover:
    def test_extracts_epub3_cover_image(self, tmp_path, monkeypatch):
        import scripts.book_pipeline.epub as epub_mod
        covers_dir = tmp_path / "covers"
        monkeypatch.setattr(epub_mod, "COVERS_DIR", covers_dir)

        epub_path = tmp_path / "test.epub"
        epub_path.write_bytes(make_epub_epub3_cover().read())

        result = extract_epub_cover(epub_path, "9781234567890")

        assert result == "/covers/9781234567890.jpg"
        assert (covers_dir / "9781234567890.jpg").read_bytes() == FAKE_COVER_BYTES

    def test_extracts_epub2_cover_image(self, tmp_path, monkeypatch):
        import scripts.book_pipeline.epub as epub_mod
        covers_dir = tmp_path / "covers"
        monkeypatch.setattr(epub_mod, "COVERS_DIR", covers_dir)

        epub_path = tmp_path / "test.epub"
        epub_path.write_bytes(make_epub_epub2_cover().read())

        result = extract_epub_cover(epub_path, "9780000000001")

        assert result == "/covers/9780000000001.jpg"
        assert (covers_dir / "9780000000001.jpg").read_bytes() == FAKE_COVER_BYTES

    def test_preserves_cover_extension(self, tmp_path, monkeypatch):
        import scripts.book_pipeline.epub as epub_mod
        monkeypatch.setattr(epub_mod, "COVERS_DIR", tmp_path / "covers")

        epub_path = tmp_path / "test.epub"
        epub_path.write_bytes(make_epub_epub3_cover(cover_ext=".png").read())

        result = extract_epub_cover(epub_path, "9781234567890")

        assert result == "/covers/9781234567890.png"

    def test_returns_none_when_no_cover_in_manifest(self, tmp_path, monkeypatch):
        import scripts.book_pipeline.epub as epub_mod
        monkeypatch.setattr(epub_mod, "COVERS_DIR", tmp_path / "covers")

        epub_path = tmp_path / "test.epub"
        epub_path.write_bytes(make_epub().read())  # no manifest section

        assert extract_epub_cover(epub_path, "9781234567890") is None

    def test_returns_none_for_corrupt_epub(self, tmp_path, monkeypatch):
        import scripts.book_pipeline.epub as epub_mod
        monkeypatch.setattr(epub_mod, "COVERS_DIR", tmp_path / "covers")

        epub_path = tmp_path / "corrupt.epub"
        epub_path.write_bytes(b"not a zip")

        assert extract_epub_cover(epub_path, "9781234567890") is None

    def test_creates_covers_dir_if_missing(self, tmp_path, monkeypatch):
        import scripts.book_pipeline.epub as epub_mod
        covers_dir = tmp_path / "new" / "covers"
        monkeypatch.setattr(epub_mod, "COVERS_DIR", covers_dir)

        epub_path = tmp_path / "test.epub"
        epub_path.write_bytes(make_epub_epub3_cover().read())

        extract_epub_cover(epub_path, "9781234567890")

        assert covers_dir.exists()
