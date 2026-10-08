# DFG-PDF-Umbenenner

Kopiert DFG-PDFs (Voten, Entscheidungsvorlagen, …) aus einem Ordner in einen
anderen und stellt dabei das **Geschäftszeichen** aus der ersten PDF-Seite vor
den Dateinamen:

| vorher | nachher |
|---|---|
| `2026_07_30_Votum_Bitzek_Duesseldorf.pdf` | `AB1234-5-1_2026_07_30_Votum_Bitzek_Duesseldorf.pdf` |
| `Entscheidungsvorlage (39).pdf` | `CD5678-12-2_Entscheidungsvorlage.pdf` |

Alle Geschäftszeichen in dieser Anleitung, im Quellcode und in den Tests
sind **frei erfunden** und gehören zu keinem echten DFG-Projekt.

Das Programm braucht **keine Internetverbindung** und keine Installation.
Die Originaldateien werden nie verändert.

---

## Anleitung für Anwenderinnen und Anwender

### 1. Herunterladen

Auf der [Releases-Seite](../../releases/latest) die passende Datei laden:

| Rechner | Datei |
|---|---|
| Windows | `DFG-PDF-Umbenenner-Windows.exe` |
| Mac mit Apple-Chip (M1, M2, M3, …) | `DFG-PDF-Umbenenner-macOS-AppleSilicon.zip` |
| Mac mit Intel-Chip (vor 2021) | `DFG-PDF-Umbenenner-macOS-Intel.zip` |

Welchen Chip der Mac hat, steht unter Apple-Menü → „Über diesen Mac“.

### 2. Beim ersten Start: Sicherheitswarnung wegklicken

Das Programm ist nicht bei Apple oder Microsoft registriert (das kostet
jährlich Geld). Deshalb warnen beide Systeme beim **ersten** Start. Das ist
normal und ungefährlich; danach kommt die Warnung nicht mehr.

**Windows** zeigt „Der Computer wurde durch Windows geschützt“:
„Weitere Informationen“ anklicken, dann „Trotzdem ausführen“.
Falls Windows Defender die Datei als verdächtig meldet, ist das ein
bekannter Fehlalarm bei Programmen dieser Bauart; die IT kann die Datei
freigeben.

**Mac** zeigt „… kann nicht geöffnet werden, da es von einem nicht
verifizierten Entwickler stammt“:

1. ZIP-Datei doppelklicken, es entsteht `DFG-PDF-Umbenenner.app`.
2. Die App **einmal** doppelklicken; die Warnung mit „Fertig“ schließen.
3. Systemeinstellungen → „Datenschutz & Sicherheit“ → ganz unten erscheint
   „DFG-PDF-Umbenenner wurde blockiert“ → **„Dennoch öffnen“** klicken und
   mit Passwort bestätigen.
4. Ab jetzt startet die App normal per Doppelklick.

(Auf älteren macOS-Versionen reicht Rechtsklick auf die App → „Öffnen“.)

### 3. Benutzen

1. **Quellordner** wählen: der Ordner, in dem die PDFs liegen.
2. **Zielordner** wählen: dorthin kommen die umbenannten Kopien
   (darf nicht derselbe Ordner sein).
3. **Vorschau** klicken. Die Tabelle zeigt für jede PDF-Datei den alten
   Namen, das gefundene Geschäftszeichen, den neuen Namen und den Status.
4. Wenn alles stimmt: **Kopieren & Umbenennen** klicken.

Im Zielordner liegt danach zusätzlich eine Textdatei
`Protokoll_Umbenennung_<Datum>.txt`, in der steht, was mit jeder Datei
passiert ist.

### Regeln

- Es wird nur die **erste Seite** jeder PDF-Datei gelesen.
- Eine PDF-Datei wird nur umbenannt, wenn auf Seite 1 das Wort **„DFG“**
  oder **„Antragstyp“** steht. Alle anderen PDFs werden übersprungen.
- Das Geschäftszeichen hat die Form `XX NNNN/NN-N` (z. B. `AB 1234/5-1`,
  `CD 5678/12-2`, `SFB 999/1-3`). Stehen mehrere auf Seite 1, wird das
  **erste** genommen.
- Im Dateinamen entfällt das Leerzeichen, aus `/` wird `-`:
  `AB 1234/5-1` → `AB1234-5-1`.
- Eine Browser-Nummer wie ` (39)` am Ende des alten Namens wird entfernt.
- Gäbe es zweimal denselben neuen Namen, wird `_2`, `_3`, … angehängt.
- Übersprungene Dateien werden **nicht** kopiert; sie stehen mit Begründung
  in der Vorschau und im Protokoll.

---

## For developers

Single-file Python program: [dfg_pdf_renamer.py](dfg_pdf_renamer.py).
The core logic is at the top (no GUI code), the tkinter GUI below, a small
command-line interface at the bottom. Only dependency: `pypdf` (pure Python).

### Run from source

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python dfg_pdf_renamer.py                       # GUI
.venv/bin/python dfg_pdf_renamer.py --cli QUELLE ZIEL --dry-run   # no window
```

On a Homebrew Mac, tkinter is a separate package: `brew install python-tk@3.14`
(matching your Python version).

### Tests

```bash
.venv/bin/python -m unittest discover tests
```

The tests generate small synthetic PDFs on the fly
([tests/make_test_pdfs.py](tests/make_test_pdfs.py)). To get a folder of
example PDFs for trying the GUI:

```bash
.venv/bin/python tests/make_test_pdfs.py tests/beispiel-pdfs
```

### Adjusting the rules

Everything configurable sits at the top of `dfg_pdf_renamer.py`:

- `REQUIRED_KEYWORDS` — words that mark a PDF as a DFG document.
- `ID_PATTERN` — the Geschäftszeichen regular expression (letters, number,
  slash, sub-number, hyphen, period, optional trailing letter).
- `DUPLICATE_SUFFIX` — what counts as a browser duplicate suffix.

Add a test case in `tests/test_renamer.py` when you change one of them.

### Making a release

Binaries are built by GitHub Actions
([.github/workflows/release.yml](.github/workflows/release.yml)) on free
Windows and macOS runners, so no local build machine is needed:

```bash
# 1. bump VERSION in dfg_pdf_renamer.py, commit
# 2. tag and push the tag
git tag v1.0.1
git push origin v1.0.1
```

A few minutes later the release appears under "Releases" with the Windows
`.exe` and two macOS `.zip` files attached. Users download from there.

The repository should be **public** so that users can download releases
without a GitHub account. (A private repo works too, but then every user
needs to be logged in to GitHub and have access.)

### Building locally (optional)

```bash
.venv/bin/pip install pyinstaller
.venv/bin/pyinstaller --windowed --name DFG-PDF-Umbenenner dfg_pdf_renamer.py          # macOS -> dist/DFG-PDF-Umbenenner.app
pyinstaller --onefile --windowed --name DFG-PDF-Umbenenner dfg_pdf_renamer.py          # Windows -> dist\DFG-PDF-Umbenenner.exe
```

### Why the security warnings, and how to get rid of them

The binaries are not code-signed. macOS Gatekeeper and Windows SmartScreen
therefore warn on first launch (see the user section above). Removing the
warnings requires an Apple Developer ID (about 99 €/year, plus notarization)
and a Windows code-signing certificate (a few hundred €/year). Both can be
added to the workflow later without changing the program.

## Lizenz

MIT, siehe [LICENSE](LICENSE).
