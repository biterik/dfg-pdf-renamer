"""
Create small synthetic PDFs for testing – without any extra library.

A PDF is written by hand (one page, Helvetica, WinAnsi encoding so that
German umlauts work).  Run directly to fill a folder with example files:

    python tests/make_test_pdfs.py  tests/beispiel-pdfs
"""

from __future__ import annotations

import sys
from pathlib import Path


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_simple_pdf(path: Path, lines: list[str], *, empty: bool = False) -> None:
    """Write a one-page PDF containing the given lines of text."""
    if empty:
        content = b""
    else:
        ops = ["BT", "/F1 12 Tf", "72 720 Td", "14 TL"]
        for line in lines:
            ops.append(f"({_escape(line)}) Tj T*")
        ops.append("ET")
        content = "\n".join(ops).encode("cp1252")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))


# The example files used by the tests and by `python tests/make_test_pdfs.py`.
EXAMPLES: dict[str, list[str]] = {
    "2026_07_30_Votum_Bitzek_Duesseldorf.pdf": [
        "Deutsche Forschungsgemeinschaft (DFG)",
        "Votum zu AB 1234/5-1",
        "Gutachter: Prof. Dr. Erik Bitzek",
    ],
    "Entscheidungsvorlage (39).pdf": [
        "Antragstyp: Sachbeihilfe",
        "Geschäftszeichen: CD 5678/12-2",
        "Siehe auch das verwandte Projekt MU 1234/5-2.",
    ],
    "Entscheidungsvorlage (40).pdf": [
        "Antragstyp: Sachbeihilfe",
        "Geschäftszeichen: SFB 999/1-3",
    ],
    "Rechnung_Hotel.pdf": [
        "Rechnung Nr. 4711",
        "Zimmer 2 Nächte",
    ],
    "DFG_ohne_Zeichen.pdf": [
        "DFG Allgemeine Hinweise",
        "Dieses Dokument hat kein Geschäftszeichen.",
    ],
}


def write_examples(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name, lines in EXAMPLES.items():
        write_simple_pdf(folder / name, lines)
    write_simple_pdf(folder / "leer.pdf", [], empty=True)
    (folder / "notiz.txt").write_text("keine PDF-Datei", encoding="utf-8")


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "beispiel-pdfs")
    write_examples(target)
    print(f"Beispiel-PDFs geschrieben nach: {target.resolve()}")
