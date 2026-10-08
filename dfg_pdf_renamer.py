#!/usr/bin/env python3
"""
DFG-PDF-Umbenenner  –  DFG PDF renamer
======================================

Copies PDF files from a source folder to a target folder and puts the DFG
"Geschäftszeichen" (file reference, e.g. "AB 1234/5-1") in front of the
file name:

    2026_07_30_Votum_Bitzek_Duesseldorf.pdf
        ->  AB1234-5-1_2026_07_30_Votum_Bitzek_Duesseldorf.pdf

    Entscheidungsvorlage (39).pdf
        ->  CD5678-12-2_Entscheidungsvorlage.pdf

Rules
-----
* Only the FIRST page of each PDF is read.
* A PDF is treated as a DFG document only if page 1 contains one of the
  words in REQUIRED_KEYWORDS ("DFG" or "Antragstyp").  Other PDFs are skipped.
* The Geschäftszeichen is found with the regular expression ID_PATTERN.
  If page 1 contains several, the FIRST one is used.
* In the new name the space is removed and the slash becomes a hyphen:
  "AB 1234/5-1" -> "AB1234-5-1".
* A browser duplicate suffix like " (39)" at the end of the old name is dropped.
* Original files are never modified, moved or deleted – they are copied.
* If two files would get the same new name, "_2", "_3", ... is appended.
* A log file ("Protokoll") listing every file and what happened to it is
  written into the target folder.

The program has a small graphical interface (tkinter, part of Python) and
can also be used from the command line:

    python dfg_pdf_renamer.py --cli QUELLORDNER ZIELORDNER [--dry-run]

Only the pure-Python package "pypdf" is required (pip install pypdf).
No network connection is used at any point.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    sys.exit("Das Paket 'pypdf' fehlt. Installieren mit:  pip install pypdf")

APP_NAME = "DFG-PDF-Umbenenner"
VERSION = "1.0.0"

# A PDF is only renamed if its first page contains at least one of these words.
REQUIRED_KEYWORDS = ("DFG", "Antragstyp")

# The DFG Geschäftszeichen, e.g. "AB 1234/5-1", "CD 5678/12-2", "SFB 999/1-3".
# Letters, project number, slash, sub number, hyphen, funding period,
# optionally followed by a single letter.  Adjust here if the format changes.
ID_PATTERN = re.compile(
    r"""
    (?<![A-Za-z])      # not glued to a preceding letter
    ([A-Z]{1,4})       # 1-4 capital letters:  KL, BO, SFB, TRR, ...
    \s{0,2}            # optional space (PDF text may contain odd spacing)
    (\d{1,6})          # project number:        2961
    /                  # slash
    (\d{1,4})          # sub number:            20
    -                  # hyphen
    (\d{1,3})          # funding period:        1
    ([A-Z]?)           # optional trailing letter
    (?![A-Za-z0-9])    # not glued to a following letter or digit
    """,
    re.VERBOSE,
)

# Browser download duplicates look like "Entscheidungsvorlage (39)".
DUPLICATE_SUFFIX = re.compile(r"\s*\(\d+\)\s*$")


# --------------------------------------------------------------------------
# Core logic (no GUI code here – this part is tested by tests/test_renamer.py)
# --------------------------------------------------------------------------

@dataclass
class Entry:
    """What should happen to one PDF file."""
    source: Path
    new_name: str = ""          # empty if the file is skipped
    reference: str = ""         # the Geschäftszeichen as found in the PDF
    ok: bool = False            # True = will be copied
    message: str = ""           # human readable explanation (German)


@dataclass
class Plan:
    source_dir: Path
    target_dir: Path
    entries: list[Entry] = field(default_factory=list)

    @property
    def to_copy(self) -> list[Entry]:
        return [e for e in self.entries if e.ok]

    @property
    def skipped(self) -> list[Entry]:
        return [e for e in self.entries if not e.ok]


def first_page_text(pdf_path: Path) -> str:
    """Return the text of the first page of a PDF ("" if there is none)."""
    reader = PdfReader(str(pdf_path))
    if len(reader.pages) == 0:
        return ""
    return reader.pages[0].extract_text() or ""


def is_dfg_document(text: str) -> bool:
    """True if the page text contains one of the required keywords."""
    return any(keyword in text for keyword in REQUIRED_KEYWORDS)


def find_reference(text: str) -> str | None:
    """Return the first Geschäftszeichen in the text, e.g. 'AB 1234/5-1'."""
    match = ID_PATTERN.search(text)
    if not match:
        return None
    letters, project, sub, period, suffix = match.groups()
    return f"{letters} {project}/{sub}-{period}{suffix}"


def reference_for_filename(reference: str) -> str:
    """'AB 1234/5-1' -> 'AB1234-5-1' (no space, slash becomes hyphen)."""
    return reference.replace(" ", "").replace("/", "-")


def clean_stem(stem: str) -> str:
    """'Entscheidungsvorlage (39)' -> 'Entscheidungsvorlage'."""
    return DUPLICATE_SUFFIX.sub("", stem).strip()


def analyse_pdf(pdf_path: Path) -> Entry:
    """Decide what to do with one PDF.  Never raises – errors go into the Entry."""
    entry = Entry(source=pdf_path)
    try:
        text = first_page_text(pdf_path)
    except Exception as exc:  # broken / encrypted PDF etc.
        entry.message = f"Fehler beim Lesen: {exc}"
        return entry

    if not text.strip():
        entry.message = "Übersprungen: Seite 1 enthält keinen Text"
        return entry
    if not is_dfg_document(text):
        entry.message = "Übersprungen: kein DFG-Dokument (weder 'DFG' noch 'Antragstyp' auf Seite 1)"
        return entry

    reference = find_reference(text)
    if reference is None:
        entry.message = "Übersprungen: kein Geschäftszeichen auf Seite 1 gefunden"
        return entry

    entry.reference = reference
    entry.new_name = f"{reference_for_filename(reference)}_{clean_stem(pdf_path.stem)}.pdf"
    entry.ok = True
    entry.message = "OK"
    return entry


def make_plan(source_dir: Path, target_dir: Path) -> Plan:
    """Analyse every PDF in source_dir and resolve name collisions."""
    source_dir, target_dir = Path(source_dir), Path(target_dir)
    plan = Plan(source_dir=source_dir, target_dir=target_dir)

    pdf_files = sorted(
        p for p in source_dir.iterdir()
        if p.is_file() and p.suffix.lower() == ".pdf"
    )
    for pdf in pdf_files:
        plan.entries.append(analyse_pdf(pdf))

    # Resolve collisions: names already used in this plan or existing in target.
    taken = {p.name.lower() for p in target_dir.iterdir()} if target_dir.is_dir() else set()
    for entry in plan.to_copy:
        base = entry.new_name[:-4]  # without ".pdf"
        candidate, counter = entry.new_name, 1
        while candidate.lower() in taken:
            counter += 1
            candidate = f"{base}_{counter}.pdf"
        if candidate != entry.new_name:
            entry.message = f"OK (Name war schon vergeben, _{counter} angehängt)"
            entry.new_name = candidate
        taken.add(candidate.lower())
    return plan


def execute_plan(plan: Plan) -> Path:
    """Copy the files and write the log.  Returns the path of the log file."""
    plan.target_dir.mkdir(parents=True, exist_ok=True)
    for entry in plan.to_copy:
        try:
            shutil.copy2(entry.source, plan.target_dir / entry.new_name)
        except Exception as exc:
            entry.ok = False
            entry.message = f"Fehler beim Kopieren: {exc}"
    return write_log(plan)


def write_log(plan: Plan) -> Path:
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = plan.target_dir / f"Protokoll_Umbenennung_{stamp}.txt"
    lines = [
        f"{APP_NAME} {VERSION} – Protokoll vom {dt.datetime.now():%d.%m.%Y %H:%M}",
        f"Quellordner: {plan.source_dir}",
        f"Zielordner:  {plan.target_dir}",
        f"Kopiert: {len(plan.to_copy)}   Übersprungen/Fehler: {len(plan.skipped)}",
        "",
    ]
    for entry in plan.entries:
        if entry.ok:
            lines.append(f"[OK]    {entry.source.name}  ->  {entry.new_name}   ({entry.reference})")
        else:
            lines.append(f"[---]   {entry.source.name}  :  {entry.message}")
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log_path


# --------------------------------------------------------------------------
# Graphical interface (tkinter)
# --------------------------------------------------------------------------

def run_gui() -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title(f"{APP_NAME} {VERSION}")
    root.geometry("1000x600")
    root.minsize(700, 400)

    source_var = tk.StringVar()
    target_var = tk.StringVar()
    status_var = tk.StringVar(value="Bitte Quell- und Zielordner wählen, dann 'Vorschau' klicken.")
    current_plan: list[Plan] = []  # holds at most one Plan (list so closures can replace it)

    # --- folder pickers ---------------------------------------------------
    frame = ttk.Frame(root, padding=10)
    frame.pack(fill="x")

    def pick(var: tk.StringVar, title: str) -> None:
        chosen = filedialog.askdirectory(title=title, initialdir=var.get() or str(Path.home()))
        if chosen:
            var.set(chosen)
            copy_button.config(state="disabled")

    ttk.Label(frame, text="Quellordner (PDFs liegen hier):").grid(row=0, column=0, sticky="w")
    ttk.Entry(frame, textvariable=source_var, width=80).grid(row=0, column=1, sticky="ew", padx=5)
    ttk.Button(frame, text="Ordner wählen…",
               command=lambda: pick(source_var, "Quellordner wählen")).grid(row=0, column=2)

    ttk.Label(frame, text="Zielordner (umbenannte Kopien):").grid(row=1, column=0, sticky="w", pady=(5, 0))
    ttk.Entry(frame, textvariable=target_var, width=80).grid(row=1, column=1, sticky="ew", padx=5, pady=(5, 0))
    ttk.Button(frame, text="Ordner wählen…",
               command=lambda: pick(target_var, "Zielordner wählen")).grid(row=1, column=2, pady=(5, 0))
    frame.columnconfigure(1, weight=1)

    # --- action buttons ---------------------------------------------------
    buttons = ttk.Frame(root, padding=(10, 0, 10, 5))
    buttons.pack(fill="x")

    def do_preview() -> None:
        source, target = Path(source_var.get()), Path(target_var.get())
        if not source.is_dir():
            messagebox.showerror(APP_NAME, "Bitte einen gültigen Quellordner wählen.")
            return
        if not target_var.get():
            messagebox.showerror(APP_NAME, "Bitte einen Zielordner wählen.")
            return
        if source.resolve() == target.resolve():
            messagebox.showerror(APP_NAME, "Quell- und Zielordner müssen verschieden sein.")
            return

        status_var.set("Lese PDFs …")
        root.update_idletasks()
        plan = make_plan(source, target)
        current_plan[:] = [plan]
        show_plan(plan)
        n_ok, n_skip = len(plan.to_copy), len(plan.skipped)
        if not plan.entries:
            status_var.set("Keine PDF-Dateien im Quellordner gefunden.")
        else:
            status_var.set(f"Vorschau: {n_ok} Datei(en) werden kopiert, {n_skip} übersprungen. "
                           f"Zum Ausführen 'Kopieren & Umbenennen' klicken.")
        copy_button.config(state="normal" if n_ok else "disabled")

    def do_copy() -> None:
        if not current_plan:
            return
        plan = current_plan[0]
        if not messagebox.askyesno(
            APP_NAME,
            f"{len(plan.to_copy)} Datei(en) werden umbenannt nach\n{plan.target_dir}\nkopiert.\n\n"
            "Die Originale bleiben unverändert. Fortfahren?",
        ):
            return
        log_path = execute_plan(plan)
        show_plan(plan)
        copy_button.config(state="disabled")
        status_var.set(f"Fertig: {len(plan.to_copy)} kopiert, {len(plan.skipped)} übersprungen. "
                       f"Protokoll: {log_path.name}")
        messagebox.showinfo(
            APP_NAME,
            f"Fertig.\n\nKopiert: {len(plan.to_copy)}\nÜbersprungen/Fehler: {len(plan.skipped)}\n\n"
            f"Ein Protokoll liegt im Zielordner:\n{log_path.name}",
        )

    ttk.Button(buttons, text="Vorschau", command=do_preview).pack(side="left")
    copy_button = ttk.Button(buttons, text="Kopieren & Umbenennen", command=do_copy, state="disabled")
    copy_button.pack(side="left", padx=10)

    # --- result table -----------------------------------------------------
    table_frame = ttk.Frame(root, padding=(10, 0, 10, 0))
    table_frame.pack(fill="both", expand=True)
    columns = ("old", "ref", "new", "status")
    table = ttk.Treeview(table_frame, columns=columns, show="headings")
    table.heading("old", text="Alter Name")
    table.heading("ref", text="Geschäftszeichen")
    table.heading("new", text="Neuer Name")
    table.heading("status", text="Status")
    table.column("old", width=280)
    table.column("ref", width=120)
    table.column("new", width=320)
    table.column("status", width=260)
    scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=table.yview)
    table.configure(yscrollcommand=scrollbar.set)
    table.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    table.tag_configure("skip", foreground="#888888")
    table.tag_configure("error", foreground="#b00020")

    def show_plan(plan: Plan) -> None:
        table.delete(*table.get_children())
        for entry in plan.entries:
            tag = "ok" if entry.ok else ("error" if entry.message.startswith("Fehler") else "skip")
            table.insert("", "end", tags=(tag,),
                         values=(entry.source.name, entry.reference, entry.new_name, entry.message))

    # --- status bar -------------------------------------------------------
    ttk.Label(root, textvariable=status_var, padding=(10, 5), anchor="w").pack(fill="x")

    root.mainloop()


# --------------------------------------------------------------------------
# Command line interface
# --------------------------------------------------------------------------

def run_cli(source: str, target: str, dry_run: bool) -> int:
    plan = make_plan(Path(source), Path(target))
    for entry in plan.entries:
        arrow = f"->  {entry.new_name}" if entry.ok else f":   {entry.message}"
        print(f"{'OK ' if entry.ok else '---'}  {entry.source.name}  {arrow}")
    print(f"\n{len(plan.to_copy)} zu kopieren, {len(plan.skipped)} übersprungen.")
    if dry_run:
        print("(Testlauf – nichts kopiert)")
        return 0
    log_path = execute_plan(plan)
    print(f"Protokoll: {log_path}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cli", nargs=2, metavar=("QUELLORDNER", "ZIELORDNER"),
                        help="ohne Fenster: PDFs aus QUELLORDNER nach ZIELORDNER kopieren")
    parser.add_argument("--dry-run", action="store_true", help="nur anzeigen, nichts kopieren (mit --cli)")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {VERSION}")
    args = parser.parse_args()

    if args.cli:
        sys.exit(run_cli(args.cli[0], args.cli[1], args.dry_run))
    run_gui()


if __name__ == "__main__":
    main()
