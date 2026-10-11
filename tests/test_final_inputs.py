import datetime as dt
import hashlib
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from builder.inputs import expand_documents, source


def office_file(path, parts):
    with ZipFile(path, "w") as archive:
        for name, content in parts.items():
            archive.writestr(name, content)


def pdf_file(path, text=None):
    # A real one-page PDF with an embedded text stream; no rendering dependency.
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode() if text else b""
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
               b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"]
    raw, offsets = b"%PDF-1.4\n", [0]
    for index, item in enumerate(objects, 1):
        offsets.append(len(raw))
        raw += f"{index} 0 obj\n".encode() + item + b"\nendobj\n"
    start = len(raw)
    raw += b"xref\n0 6\n0000000000 65535 f \n"
    raw += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    raw += f"trailer\n<< /Root 1 0 R /Size 6 >>\nstartxref\n{start}\n%%EOF\n".encode()
    path.write_bytes(raw)


def spreadsheet(path, cells, *, date1904=False):
    office_file(path, {
        "xl/workbook.xml": f'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><workbookPr date1904="{int(date1904)}"/><sheets><sheet name="Kurallar" sheetId="1" r:id="rId1"/><sheet name="Ek" sheetId="2" r:id="rId2" state="hidden"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Target="/xl/worksheets/sheet2.xml"/></Relationships>',
        "xl/sharedStrings.xml": '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>Ödeme tarihi</t></si><si><r><t>İlk </t></r><r><t>kural</t></r></si></sst>',
        "xl/styles.xml": '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><cellXfs><xf numFmtId="0"/><xf numFmtId="14"/><xf numFmtId="20"/></cellXfs></styleSheet>',
        "xl/worksheets/sheet1.xml": f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1">{cells}</row></sheetData></worksheet>',
        "xl/worksheets/sheet2.xml": '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="2"><c r="C2" t="s"><v>1</v></c></row></sheetData></worksheet>',
    })


class FinalInputChecks(unittest.TestCase):
    def test_utf8_metadata_uses_original_bytes_and_legacy_line_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("brief.md", "api.yaml", "compiler.py", "worker.js", "wrangler.toml"):
                path = root / name
                raw = "1. Türkçe kural\r\n2. Onay gerekir\r\n".encode()
                path.write_bytes(raw)
                metadata, text = source(path, root)
                self.assertEqual(metadata, {"path": name, "sha256": hashlib.sha256(raw).hexdigest(), "lines": 2})
                self.assertEqual(text, raw.decode())

    def test_folder_is_recursive_sorted_and_deduplicated_without_silent_drops(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "nested").mkdir(); (root / ".hidden").mkdir()
            for name in ("Z.txt", "a.md", "nested/b.json", "~$busy.docx", ".hidden/secret.exe"):
                (root / name).write_text("source")
            expected = [(root / name).resolve() for name in ("a.md", "nested/b.json", "Z.txt")]
            self.assertEqual(expand_documents([root, root / "a.md"]), expected)
            (root / "not-readable.doc").write_text("binary")
            with self.assertRaisesRegex(ValueError, "Unsupported source format"):
                expand_documents([root])

    def test_docx_keeps_paragraph_order_tables_headers_and_notes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / "brief.docx"
            office_file(path, {
                "word/document.xml": '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Türkçe kural</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>Tarih</w:t></w:r></w:p><w:p><w:r><w:t>Bugün</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>11 Ekim</w:t></w:r></w:p></w:tc></w:tr></w:tbl><w:p><w:r><w:t>Son kural</w:t></w:r></w:p></w:body></w:document>',
                "word/header1.xml": '<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:r><w:t>Başlık</w:t></w:r></w:p></w:hdr>',
                "word/footnotes.xml": '<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:footnote><w:p><w:r><w:t>Dipnot kuralı</w:t></w:r></w:p></w:footnote></w:footnotes>',
            })
            metadata, text = source(path, root)
            self.assertIn("Türkçe kural\n[Table]\nTarih\nBugün | 11 Ekim\nSon kural", text)
            self.assertIn("Başlık", text); self.assertIn("Dipnot kuralı", text)
            self.assertEqual(metadata["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(metadata["extracted_sha256"], hashlib.sha256(text.encode("utf-8")).hexdigest())
            self.assertEqual(metadata["lines"], len(text.splitlines()))

    def test_xlsx_keeps_sheet_cell_dates_time_and_cached_formulas(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / "policy.xlsx"
            serial = (dt.datetime(2026, 10, 11) - dt.datetime(1899, 12, 30)).days
            spreadsheet(path, f'<c r="A1" t="s"><v>0</v></c><c r="B1" s="1"><v>{serial}</v></c><c r="C1" s="2"><v>0.5</v></c><c r="D1"><f>2+3</f><v>5</v></c><c r="E1" t="inlineStr"><is><t>Onay</t></is></c>')
            _, text = source(path, root)
            for expected in ("[Sheet Kurallar]", "A1=Ödeme tarihi", "B1=2026-10-11", "C1=12:00:00", "D1=5 [formula=2+3; cached value]", "E1=Onay", "[Sheet Ek]", "C2=İlk kural"):
                self.assertIn(expected, text)
            spreadsheet(path, '<c r="A1" s="1"><v>0</v></c>', date1904=True)
            self.assertIn("A1=1904-01-01", source(path, root)[1])

    def test_xlsx_missing_formula_cache_and_error_cells_fail_explicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / "policy.xlsx"
            for cell, error in (('<c r="A1"><f>2+3</f></c>', "no cached value"), ('<c r="A1" t="e"><v>#VALUE!</v></c>', "error value")):
                spreadsheet(path, cell)
                with self.assertRaisesRegex(ValueError, error):
                    source(path, root)

    def test_pdf_page_labels_and_scanned_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / "brief.pdf"
            pdf_file(path, "Only record after consent")
            self.assertIn("[Page 1]\nOnly record after consent", source(path, root)[1])
            pdf_file(path)
            with self.assertRaisesRegex(ValueError, "scanned pages need OCR"):
                source(path, root)

    def test_empty_invalid_or_xml_entity_sources_fail_with_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, raw, error in (("empty.txt", b" ", "no readable text"), ("bad.txt", b"\xff", "Cannot read source"), ("old.xls", b"binary", "Unsupported source")):
                path = root / name; path.write_bytes(raw)
                with self.assertRaisesRegex(ValueError, error):
                    source(path, root)
            path = root / "unsafe.docx"
            office_file(path, {"word/document.xml": '<!DOCTYPE document [<!ENTITY secret "hidden">]><document>&secret;</document>'})
            with self.assertRaisesRegex(ValueError, "XML declarations"):
                source(path, root)


if __name__ == "__main__":
    unittest.main()
