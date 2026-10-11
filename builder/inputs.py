"""Read source documents as data; never run Office code or calculate formulas."""
import datetime as dt
import hashlib
import io
from pathlib import Path
import posixpath
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile


TEXT_EXTENSIONS = {".md", ".txt", ".json", ".yaml", ".yml", ".csv", ".js", ".toml"}
DOCUMENT_EXTENSIONS = TEXT_EXTENSIONS | {".pdf", ".docx", ".xlsx"}
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def expand_documents(paths):
    files = set()
    for item in paths:
        path = Path(item).resolve()
        if not path.exists():
            raise ValueError(f"Source does not exist: {path}")
        entries = path.rglob("*") if path.is_dir() else [path]
        for entry in entries:
            relative = entry.relative_to(path) if path.is_dir() else Path(entry.name)
            if any(part.startswith((".", "~$")) or part == "__MACOSX" for part in relative.parts):
                continue
            if entry.is_file():
                if entry.suffix.lower() not in DOCUMENT_EXTENSIONS:
                    raise ValueError(f"Unsupported source format: {entry}; use PDF, DOCX, XLSX or UTF-8 text.")
                files.add(entry.resolve())
    if not files:
        raise ValueError("No source documents found.")
    return sorted(files, key=lambda path: (str(path).casefold(), str(path)))


def _xml(archive, name):
    raw = archive.read(name)
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError(f"XML declarations are not supported: {name}")
    return ET.fromstring(raw)


def _word_text(node):
    if node.tag != W + "p":
        paragraphs = list(node.iter(W + "p"))
        if paragraphs:
            return "\n".join(_word_text(paragraph) for paragraph in paragraphs)
    return "".join("\t" if child.tag == W + "tab" else "\n" if child.tag in (W + "br", W + "cr")
                   else child.text or "" for child in node.iter()
                   if child.tag in (W + "t", W + "tab", W + "br", W + "cr"))


def _docx(raw):
    lines = []
    with ZipFile(io.BytesIO(raw)) as archive:
        parts = ["word/document.xml"] + sorted(name for name in archive.namelist()
                 if re.fullmatch(r"word/(?:header\d+|footer\d+|footnotes|endnotes|comments)\.xml", name))
        for name in parts:
            document = _xml(archive, name)
            lines.append(f"[Part {name}]")
            body = document.find(W + "body") if name == "word/document.xml" else document
            if body is None:
                raise ValueError("DOCX has no document body.")
            for child in body:
                if child.tag == W + "tbl":
                    lines.append("[Table]")
                    for row in child.findall(W + "tr"):
                        lines.append(" | ".join(_word_text(cell) for cell in row.findall(W + "tc")))
                else:
                    text = _word_text(child)
                    if text.strip():
                        lines.append(text)
    if not any(line.strip() and not line.startswith("[Part ") and line != "[Table]" for line in lines):
        raise ValueError("DOCX contains no readable text; image-only documents need OCR first.")
    return "\n".join(lines)


def _excel_number(value, style, styles, epoch):
    if styles is None:
        return value
    xfs = styles.find(S + "cellXfs")
    if xfs is None or style >= len(xfs):
        if style:
            raise ValueError(f"XLSX cell has invalid style index {style}.")
        return value
    number_format = int(xfs[style].get("numFmtId", "0"))
    custom = {int(item.get("numFmtId")): item.get("formatCode", "")
              for item in styles.findall(S + "numFmts/" + S + "numFmt")}
    code = re.sub(r'"[^"]*"|\\.|\[[^\]]*\]|_.|\*.', "", custom.get(number_format, "")).lower()
    time_format = number_format in {18, 19, 20, 21, 22, 45, 46, 47} or bool(re.search(r"[hs]", code))
    date_format = number_format in {14, 15, 16, 17, 22} | set(range(27, 37)) | set(range(50, 59)) or bool(re.search(r"[yd]", code)) or ("m" in code and not time_format)
    if not date_format and not time_format:
        return value
    serial = float(value)
    if number_format == 46 or re.search(r"\[(?:h+|m+|s+)\]", custom.get(number_format, ""), re.I):
        return str(dt.timedelta(days=serial))
    result = epoch + dt.timedelta(days=serial + (1 if epoch.year == 1899 and 0 < serial < 60 else 0))
    if time_format and not date_format:
        return result.time().isoformat()
    return result.isoformat() if serial % 1 else result.date().isoformat()


def _xlsx(raw):
    lines = []
    with ZipFile(io.BytesIO(raw)) as archive:
        workbook = _xml(archive, "xl/workbook.xml")
        rels = {item.get("Id"): item.get("Target") for item in _xml(archive, "xl/_rels/workbook.xml.rels")
                if item.get("TargetMode") != "External"}
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared = ["".join(text.text or "" for text in item.findall(S + "t") + item.findall(S + "r/" + S + "t"))
                      for item in _xml(archive, "xl/sharedStrings.xml")]
        styles = _xml(archive, "xl/styles.xml") if "xl/styles.xml" in archive.namelist() else None
        properties = workbook.find(S + "workbookPr")
        epoch = dt.datetime(1904, 1, 1) if properties is not None and properties.get("date1904") in ("1", "true") else dt.datetime(1899, 12, 30)
        sheets = workbook.find(S + "sheets")
        if sheets is None:
            raise ValueError("XLSX contains no worksheets.")
        count = 0
        for sheet in sheets:
            name = sheet.get("name", "")
            target = rels.get(sheet.get(R + "id"))
            if not target:
                raise ValueError(f"XLSX worksheet has no local content: {name}")
            part = posixpath.normpath(target.lstrip("/") if target.startswith("/") else posixpath.join("xl", target))
            lines.append(f"[Sheet {name}]")
            for row in _xml(archive, part).findall(".//" + S + "sheetData/" + S + "row"):
                cells = []
                for cell in row.findall(S + "c"):
                    coordinate = cell.get("r", "?")
                    kind, value, formula = cell.get("t"), cell.find(S + "v"), cell.find(S + "f")
                    if formula is not None and (value is None or value.text is None):
                        raise ValueError(f"XLSX formula has no cached value: {name}!{coordinate}; recalculate and save it in Excel first.")
                    text = value.text if value is not None and value.text is not None else ""
                    if kind == "inlineStr":
                        text = "".join(item.text or "" for item in cell.iter(S + "t"))
                    elif kind == "s":
                        text = shared[int(text)]
                    elif kind == "b":
                        text = "TRUE" if text == "1" else "FALSE"
                    elif kind == "e":
                        raise ValueError(f"XLSX contains an error value: {name}!{coordinate}={text}")
                    elif kind in (None, "n") and text:
                        text = _excel_number(text, int(cell.get("s", "0")), styles, epoch)
                    if formula is not None:
                        text += f" [formula={formula.text or ''}; cached value]"
                    if text:
                        cells.append(f"{coordinate}={text}")
                        count += 1
                if cells:
                    lines.append(" | ".join(cells))
        if not count:
            raise ValueError("XLSX contains no readable cells.")
    return "\n".join(lines)


def _pdf(raw):
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise ValueError("PDF reading needs pypdf; install requirements.txt first.") from error
    reader = PdfReader(io.BytesIO(raw))
    if reader.is_encrypted:
        raise ValueError("Encrypted PDF is not supported; provide a decrypted copy.")
    lines = []
    for index, page in enumerate(reader.pages, 1):
        text = page.extract_text(extraction_mode="layout") or ""
        if not text.strip():
            raise ValueError(f"PDF page {index} has no readable text; scanned pages need OCR first.")
        lines.extend((f"[Page {index}]", text))
    return "\n".join(lines)


def source(path, root):
    path, root = Path(path).resolve(), Path(root).resolve()
    raw = path.read_bytes()
    extension = path.suffix.lower()
    try:
        if extension in TEXT_EXTENSIONS or extension == ".py":
            content = raw.decode("utf-8")
        elif extension == ".docx":
            content = _docx(raw)
        elif extension == ".xlsx":
            content = _xlsx(raw)
        elif extension == ".pdf":
            content = _pdf(raw)
        else:
            raise ValueError(f"Unsupported source format: {extension}")
        if not content.strip():
            raise ValueError("Source contains no readable text.")
    except Exception as error:
        raise ValueError(f"Cannot read source {path}: {error}") from error
    label = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
    metadata = {"path": label, "sha256": hashlib.sha256(raw).hexdigest(), "lines": len(content.splitlines())}
    if extension in {".pdf", ".docx", ".xlsx"}:
        metadata["extracted_sha256"] = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return metadata, content
