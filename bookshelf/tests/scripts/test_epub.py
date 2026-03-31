"""Tests for scripts/book_pipeline/epub.py."""

import io
import zipfile

import pytest

from scripts.book_pipeline.epub import extract_epub_cover, extract_epub_metadata, extract_epub_toc


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


# ---------------------------------------------------------------------------
# TOC builder helpers
# ---------------------------------------------------------------------------

def make_epub_epub3_toc(nested: bool = False, toc_nav_type: str = "toc") -> io.BytesIO:
    """Build an epub with an EPUB3 nav.xhtml TOC."""
    if nested:
        items = """\
        <li><a href="ch1.xhtml">Chapter 1</a></li>
        <li><a href="ch2.xhtml">Chapter 2</a>
          <ol>
            <li><a href="ch2.xhtml#s1">Section 2.1</a></li>
          </ol>
        </li>"""
    else:
        items = """\
        <li><a href="ch1.xhtml">Chapter 1</a></li>
        <li><a href="ch2.xhtml">Chapter 2</a></li>"""

    nav = f"""\
<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
  <body>
    <nav epub:type="{toc_nav_type}">
      <ol>
{items}
      </ol>
    </nav>
  </body>
</html>""".encode()

    opf = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>TOC Book</dc:title>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
  </manifest>
</package>
"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("META-INF/container.xml", CONTAINER_XML)
        zf.writestr("content.opf", opf)
        zf.writestr("nav.xhtml", nav)
    buf.seek(0)
    return buf


def make_epub_epub2_toc(nested: bool = False) -> io.BytesIO:
    """Build an epub with an EPUB2 toc.ncx TOC."""
    if nested:
        points = """\
    <navPoint id="ch1">
      <navLabel><text>Chapter 1</text></navLabel>
      <content src="ch1.xhtml"/>
    </navPoint>
    <navPoint id="ch2">
      <navLabel><text>Chapter 2</text></navLabel>
      <content src="ch2.xhtml"/>
      <navPoint id="ch2s1">
        <navLabel><text>Section 2.1</text></navLabel>
        <content src="ch2.xhtml#s1"/>
      </navPoint>
    </navPoint>"""
    else:
        points = """\
    <navPoint id="ch1">
      <navLabel><text>Chapter 1</text></navLabel>
      <content src="ch1.xhtml"/>
    </navPoint>
    <navPoint id="ch2">
      <navLabel><text>Chapter 2</text></navLabel>
      <content src="ch2.xhtml"/>
    </navPoint>"""

    ncx = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <navMap>
{points}
  </navMap>
</ncx>""".encode()

    opf = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>NCX Book</dc:title>
  </metadata>
  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
  </manifest>
</package>
"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("META-INF/container.xml", CONTAINER_XML)
        zf.writestr("content.opf", opf)
        zf.writestr("toc.ncx", ncx)
    buf.seek(0)
    return buf


def make_epub_both_toc(nav_title: str = "Nav Chapter", ncx_title: str = "NCX Chapter") -> io.BytesIO:
    """Build an epub with both EPUB3 nav.xhtml and EPUB2 toc.ncx."""
    nav = f"""\
<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
  <body>
    <nav epub:type="toc">
      <ol><li><a href="ch1.xhtml">{nav_title}</a></li></ol>
    </nav>
  </body>
</html>""".encode()

    ncx = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/">
  <navMap>
    <navPoint id="ch1">
      <navLabel><text>{ncx_title}</text></navLabel>
      <content src="ch1.xhtml"/>
    </navPoint>
  </navMap>
</ncx>""".encode()

    opf = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Both Book</dc:title>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
  </manifest>
</package>
"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("META-INF/container.xml", CONTAINER_XML)
        zf.writestr("content.opf", opf)
        zf.writestr("nav.xhtml", nav)
        zf.writestr("toc.ncx", ncx)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# extract_epub_toc
# ---------------------------------------------------------------------------

class TestExtractEpubToc:
    def test_extracts_flat_epub3_toc(self, tmp_path):
        epub_path = tmp_path / "test.epub"
        epub_path.write_bytes(make_epub_epub3_toc().read())

        result = extract_epub_toc(epub_path)

        assert result is not None
        assert len(result) == 2
        assert result[0] == {"title": "Chapter 1", "children": []}
        assert result[1] == {"title": "Chapter 2", "children": []}

    def test_extracts_nested_epub3_toc(self, tmp_path):
        epub_path = tmp_path / "test.epub"
        epub_path.write_bytes(make_epub_epub3_toc(nested=True).read())

        result = extract_epub_toc(epub_path)

        assert result is not None
        assert result[1]["title"] == "Chapter 2"
        assert len(result[1]["children"]) == 1
        assert result[1]["children"][0]["title"] == "Section 2.1"

    def test_extracts_flat_epub2_ncx_toc(self, tmp_path):
        epub_path = tmp_path / "test.epub"
        epub_path.write_bytes(make_epub_epub2_toc().read())

        result = extract_epub_toc(epub_path)

        assert result is not None
        assert len(result) == 2
        assert result[0]["title"] == "Chapter 1"
        assert result[1]["title"] == "Chapter 2"

    def test_extracts_nested_epub2_ncx_toc(self, tmp_path):
        epub_path = tmp_path / "test.epub"
        epub_path.write_bytes(make_epub_epub2_toc(nested=True).read())

        result = extract_epub_toc(epub_path)

        assert result is not None
        assert result[1]["children"][0] == {"title": "Section 2.1", "children": []}

    def test_prefers_epub3_nav_over_ncx(self, tmp_path):
        epub_path = tmp_path / "test.epub"
        epub_path.write_bytes(make_epub_both_toc(nav_title="Nav Chapter", ncx_title="NCX Chapter").read())

        result = extract_epub_toc(epub_path)

        assert result is not None
        assert result[0]["title"] == "Nav Chapter"

    def test_falls_back_to_ncx_when_nav_has_no_toc_type(self, tmp_path):
        """nav.xhtml exists but epub:type is 'landmarks', not 'toc' — should fall back to NCX."""
        epub_path = tmp_path / "test.epub"
        # make_epub_epub3_toc with toc_nav_type="landmarks" produces a nav with no toc entries
        buf = io.BytesIO()
        nav = b"""\
<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
  <body>
    <nav epub:type="landmarks">
      <ol><li><a href="ch1.xhtml">Start</a></li></ol>
    </nav>
  </body>
</html>"""
        ncx = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/">
  <navMap>
    <navPoint id="ch1">
      <navLabel><text>NCX Fallback</text></navLabel>
      <content src="ch1.xhtml"/>
    </navPoint>
  </navMap>
</ncx>"""
        opf = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Fallback</dc:title></metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
  </manifest>
</package>"""
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("META-INF/container.xml", CONTAINER_XML)
            zf.writestr("content.opf", opf)
            zf.writestr("nav.xhtml", nav)
            zf.writestr("toc.ncx", ncx)
        epub_path.write_bytes(buf.getvalue())

        result = extract_epub_toc(epub_path)

        assert result is not None
        assert result[0]["title"] == "NCX Fallback"

    def test_returns_none_when_no_toc_source(self, tmp_path):
        """epub with no nav.xhtml or toc.ncx in manifest returns None."""
        epub_path = tmp_path / "notoc.epub"
        epub_path.write_bytes(make_epub().read())

        assert extract_epub_toc(epub_path) is None

    def test_returns_none_for_corrupt_epub(self, tmp_path):
        epub_path = tmp_path / "corrupt.epub"
        epub_path.write_bytes(b"not a zip")

        assert extract_epub_toc(epub_path) is None

    def test_nav_item_with_span_instead_of_anchor(self, tmp_path):
        """<span> is used for section headers that aren't links — title should still be captured."""
        nav = b"""\
<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
  <body>
    <nav epub:type="toc">
      <ol>
        <li><span>Part One</span>
          <ol>
            <li><a href="ch1.xhtml">Chapter 1</a></li>
          </ol>
        </li>
      </ol>
    </nav>
  </body>
</html>"""
        opf = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Span Book</dc:title></metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
  </manifest>
</package>"""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("META-INF/container.xml", CONTAINER_XML)
            zf.writestr("content.opf", opf)
            zf.writestr("nav.xhtml", nav)
        epub_path = tmp_path / "span.epub"
        epub_path.write_bytes(buf.getvalue())

        result = extract_epub_toc(epub_path)

        assert result is not None
        assert result[0]["title"] == "Part One"
        assert result[0]["children"][0]["title"] == "Chapter 1"
