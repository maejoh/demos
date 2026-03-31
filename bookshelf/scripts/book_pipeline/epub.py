import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath

from .utils import COVERS_DIR

NS = {
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def extract_epub_metadata(epub_path: Path) -> dict | None:
    """Extract title, author, ISBN, and year from an epub file."""
    try:
        with zipfile.ZipFile(epub_path, "r") as zf:
            container = ET.fromstring(zf.read("META-INF/container.xml"))
            opf_path = container.find(".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile").get("full-path")

            opf = ET.fromstring(zf.read(opf_path))
            metadata = opf.find("opf:metadata", NS)

            title = getattr(metadata.find("dc:title", NS), "text", None)
            author = getattr(metadata.find("dc:creator", NS), "text", None)

            isbn = None
            for identifier in metadata.findall("dc:identifier", NS):
                scheme = identifier.get("{http://www.idpf.org/2007/opf}scheme", "").upper()
                text = identifier.text or ""
                if "ISBN" in scheme or text.startswith("978") or text.startswith("979"):
                    isbn = text.replace("-", "").strip()
                    break

            date_text = getattr(metadata.find("dc:date", NS), "text", None) or ""
            year_match = re.search(r'\d{4}', date_text)
            year = int(year_match.group()) if year_match else None

            if not title:
                print(f"  [skip] No title found in {epub_path.name}")
                return None

            return {
                "title": title.strip(),
                "author": author.strip() if author else "Unknown",
                "isbn": isbn,
                "year": year,
                "epub_path": epub_path,
            }

    except Exception as e:
        print(f"  [error] {epub_path.name}: {e}")
        return None


def extract_epub_cover(epub_path: Path, key: str) -> str | None:
    """
    Extract the cover image from an epub and save it to public/covers/.
    Returns the relative URL (e.g. '/covers/9781234567890.jpg') or None.

    Tries two methods:
      1. EPUB3: manifest item with properties="cover-image"
      2. EPUB2: <meta name="cover"> pointing to a manifest item id
    """
    try:
        with zipfile.ZipFile(epub_path, "r") as zf:
            container = ET.fromstring(zf.read("META-INF/container.xml"))
            opf_path = container.find(".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile").get("full-path")
            opf_dir = PurePosixPath(opf_path).parent

            opf = ET.fromstring(zf.read(opf_path))
            manifest = opf.find("opf:manifest", NS)

            cover_href = None

            # Method 1: EPUB3 — manifest item with properties="cover-image"
            if manifest is not None:
                for item in manifest.findall("opf:item", NS):
                    if "cover-image" in item.get("properties", ""):
                        cover_href = item.get("href")
                        break

            # Method 2: EPUB2 — <meta name="cover" content="item-id">
            if not cover_href:
                metadata_el = opf.find("opf:metadata", NS)
                if metadata_el is not None:
                    for meta in metadata_el.findall("opf:meta", NS):
                        if meta.get("name") == "cover":
                            cover_id = meta.get("content")
                            if cover_id and manifest is not None:
                                for item in manifest.findall("opf:item", NS):
                                    if item.get("id") == cover_id:
                                        cover_href = item.get("href")
                                        break
                            break

            if not cover_href:
                return None

            # Resolve path relative to OPF location (zip paths always use forward slashes)
            cover_zip_path = str(opf_dir / cover_href) if str(opf_dir) != "." else cover_href

            ext = PurePosixPath(cover_href).suffix.lower() or ".jpg"
            COVERS_DIR.mkdir(parents=True, exist_ok=True)
            out_path = COVERS_DIR / f"{key}{ext}"
            out_path.write_bytes(zf.read(cover_zip_path))

            return f"/covers/{key}{ext}"

    except Exception as e:
        print(f"  [warn] cover extraction failed for {epub_path.name}: {e}")
        return None


def extract_epub_toc(epub_path: Path) -> list[dict] | None:
    """
    Extract table of contents from an epub file.

    Returns a nested list of {"title": str, "children": [...]} dicts.
    Tries EPUB3 nav.xhtml first, then falls back to EPUB2 toc.ncx.
    Returns None on failure.
    """
    try:
        with zipfile.ZipFile(epub_path, "r") as zf:
            container = ET.fromstring(zf.read("META-INF/container.xml"))
            opf_path = container.find(".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile").get("full-path")
            opf_dir = PurePosixPath(opf_path).parent

            opf = ET.fromstring(zf.read(opf_path))
            manifest = opf.find("opf:manifest", NS)

            nav_href = None
            ncx_href = None
            if manifest is not None:
                for item in manifest.findall("opf:item", NS):
                    if "nav" in item.get("properties", "").split():
                        nav_href = item.get("href")
                    if item.get("media-type") == "application/x-dtbncx+xml":
                        ncx_href = item.get("href")

            # EPUB3: parse nav.xhtml
            if nav_href:
                nav_zip_path = str(opf_dir / nav_href) if str(opf_dir) != "." else nav_href
                if nav_zip_path in zf.namelist():
                    nav_root = ET.fromstring(zf.read(nav_zip_path))
                    toc = _parse_nav_xhtml(nav_root)
                    if toc:
                        return toc

            # EPUB2: parse toc.ncx
            if ncx_href:
                ncx_zip_path = str(opf_dir / ncx_href) if str(opf_dir) != "." else ncx_href
                if ncx_zip_path in zf.namelist():
                    ncx_root = ET.fromstring(zf.read(ncx_zip_path))
                    return _parse_ncx(ncx_root)

        return None

    except Exception as e:
        print(f"  [warn] TOC extraction failed for {epub_path.name}: {e}")
        return None


def _parse_nav_xhtml(root: ET.Element) -> list[dict]:
    XHTML_NS = "http://www.w3.org/1999/xhtml"
    EPUB_NS = "http://www.idpf.org/2007/ops"

    toc_nav = None
    for nav in root.iter(f"{{{XHTML_NS}}}nav"):
        if nav.get(f"{{{EPUB_NS}}}type") == "toc":
            toc_nav = nav
            break

    if toc_nav is None:
        return []

    ol = toc_nav.find(f"{{{XHTML_NS}}}ol")
    return _parse_nav_ol(ol, XHTML_NS) if ol is not None else []


def _parse_nav_ol(ol: ET.Element, ns: str) -> list[dict]:
    entries = []
    for li in ol.findall(f"{{{ns}}}li"):
        a = li.find(f"{{{ns}}}a")
        span = li.find(f"{{{ns}}}span")
        label = a if a is not None else span
        title = "".join(label.itertext()).strip() if label is not None else ""

        children_ol = li.find(f"{{{ns}}}ol")
        children = _parse_nav_ol(children_ol, ns) if children_ol is not None else []

        if title:
            entries.append({"title": title, "children": children})
    return entries


def _parse_ncx(root: ET.Element) -> list[dict]:
    NCX_NS = "http://www.daisy.org/z3986/2005/ncx/"
    nav_map = root.find(f"{{{NCX_NS}}}navMap")
    return _parse_nav_points(nav_map, NCX_NS) if nav_map is not None else []


def _parse_nav_points(parent: ET.Element, ns: str) -> list[dict]:
    entries = []
    for nav_point in parent.findall(f"{{{ns}}}navPoint"):
        label = nav_point.find(f"{{{ns}}}navLabel/{{{ns}}}text")
        title = label.text.strip() if label is not None and label.text else ""
        children = _parse_nav_points(nav_point, ns)
        if title:
            entries.append({"title": title, "children": children})
    return entries
