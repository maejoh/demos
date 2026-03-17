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
