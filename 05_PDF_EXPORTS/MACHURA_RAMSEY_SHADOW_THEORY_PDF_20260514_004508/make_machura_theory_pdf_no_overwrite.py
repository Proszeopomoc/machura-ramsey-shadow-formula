#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import hashlib
import os
import textwrap
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

INCLUDE_DIRS = [
    "00_FORMULA",
    "01_ARITHMETIC_CORE",
    "02_TEST_PROTOCOL",
    "03_EVIDENCE",
    "04_PUBLIC_TEXT",
]

EXTS = {".txt", ".md"}

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def to_ascii(s: str) -> str:
    s = s.replace("\u2013", "-").replace("\u2014", "-").replace("\u2212", "-")
    s = s.replace("\u2192", "->").replace("\u21d2", "=>").replace("\u2208", " in ")
    s = s.replace("\u2205", "empty").replace("\u03a6", "Phi").replace("\u03c6", "phi")
    s = s.replace("\u0394", "Delta").replace("\u03c7", "chi").replace("\u03c9", "omega")
    s = s.replace("\u03b1", "alpha")
    s = unicodedata.normalize("NFKD", s)
    return s.encode("ascii", "ignore").decode("ascii")

def collect_sources(root: Path):
    files = []
    for d in INCLUDE_DIRS:
        base = root / d
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file() and p.suffix.lower() in EXTS:
                files.append(p)
    return sorted(files, key=lambda p: str(p).lower())

def pdf_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

def make_pdf_from_text(text: str, pdf_path: Path):
    text = to_ascii(text)
    raw_lines = []
    for line in text.splitlines():
        line = line.rstrip()
        if len(line) <= 92:
            raw_lines.append(line)
        else:
            raw_lines.extend(textwrap.wrap(line, width=92, replace_whitespace=False, drop_whitespace=False))

    lines_per_page = 58
    pages = [raw_lines[i:i+lines_per_page] for i in range(0, len(raw_lines), lines_per_page)]
    if not pages:
        pages = [[""]]

    objects = []

    def add_obj(data: bytes) -> int:
        objects.append(data)
        return len(objects)

    # Reserve fixed objects.
    add_obj(b"<< /Type /Catalog /Pages 2 0 R >>")
    add_obj(b"")
    add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")

    page_obj_nums = []

    for page_lines in pages:
        cmds = []
        cmds.append("BT")
        cmds.append("/F1 8.5 Tf")
        cmds.append("45 800 Td")
        cmds.append("11.5 TL")
        for line in page_lines:
            cmds.append(f"({pdf_escape(line)}) Tj")
            cmds.append("T*")
        cmds.append("ET")
        stream = "\n".join(cmds).encode("latin-1", errors="replace")

        page_num = len(objects) + 1
        stream_num = len(objects) + 2
        page_obj_nums.append(page_num)

        page_obj = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 3 0 R >> >> "
            f"/Contents {stream_num} 0 R >>"
        ).encode("ascii")

        stream_obj = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"\nendstream"
        )

        add_obj(page_obj)
        add_obj(stream_obj)

    kids = " ".join(f"{n} 0 R" for n in page_obj_nums)
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_obj_nums)} >>".encode("ascii")

    out = bytearray()
    out.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]

    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode("ascii"))
        out.extend(obj)
        out.extend(b"\nendobj\n")

    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects)+1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))

    out.extend(
        f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n".encode("ascii")
    )

    pdf_path.write_bytes(out)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--master", required=True)
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--sources-list", required=True)
    args = ap.parse_args()

    root = Path(args.root)
    master = Path(args.master)
    pdf = Path(args.pdf)
    sources_list = Path(args.sources_list)

    sources = collect_sources(root)

    lines = []
    lines.append("MACHURA RAMSEY SHADOW THEORY - UNIFIED SIGNED VIEW")
    lines.append("==================================================")
    lines.append("")
    lines.append("Author: Michal Machura")
    lines.append("Generated UTC: " + datetime.now(timezone.utc).isoformat())
    lines.append("Project root: " + str(root))
    lines.append("")
    lines.append("Scope:")
    lines.append("This document collects the current theory layer of the Machura Ramsey Shadow Formula.")
    lines.append("It uses standard Ramsey terminology and separates theory from numerical audit evidence.")
    lines.append("")
    lines.append("Included source files:")
    lines.append("----------------------")

    source_lines = []
    for p in sources:
        rel = p.relative_to(root)
        h = sha256_file(p)
        source_lines.append(f"{h}  {rel}")
        lines.append(f"{h}  {rel}")

    lines.append("")
    lines.append("DOCUMENT BODY")
    lines.append("=============")

    for p in sources:
        rel = p.relative_to(root)
        lines.append("")
        lines.append("")
        lines.append("======================================================================")
        lines.append("SOURCE FILE: " + str(rel))
        lines.append("SHA256: " + sha256_file(p))
        lines.append("======================================================================")
        lines.append("")
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            content = f"[READ ERROR: {e}]"
        lines.append(content)

    master_text = "\n".join(lines) + "\n"

    if master.exists():
        raise SystemExit(f"STOP: master exists: {master}")
    if pdf.exists():
        raise SystemExit(f"STOP: pdf exists: {pdf}")
    if sources_list.exists():
        raise SystemExit(f"STOP: sources list exists: {sources_list}")

    master.write_text(master_text, encoding="utf-8")
    sources_list.write_text("\n".join(source_lines) + "\n", encoding="utf-8")
    make_pdf_from_text(master_text, pdf)

    print("DONE")
    print("MASTER:", master)
    print("PDF:", pdf)
    print("SOURCES:", sources_list)
    print("PDF_SHA256:", sha256_file(pdf))

if __name__ == "__main__":
    main()
