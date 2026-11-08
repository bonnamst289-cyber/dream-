# -*- coding: utf-8 -*-
"""AVA Document Creator — বাস্তব ডকুমেন্ট তৈরি + যাচাই।
গ্যারান্টিড: TXT, Markdown, CSV, HTML (কোনো লাইব্রেরি ছাড়াই, বাংলা Unicode সহ)
স্বয়ংক্রিয় (লাইব্রেরি থাকলে): DOCX (python-docx), XLSX (openpyxl), PDF (fpdf2/reportlab)
সৎ নীতি: ফাইল না তৈরি হলে বা যাচাই ব্যর্থ হলে স্পষ্ট বলে — ভুয়া সাফল্য নয়।"""
import csv
import datetime
import os

from pathlib import Path

DESKTOP = None  # lazy: file_manager.desktop_path()


def _desktop() -> Path:
    global DESKTOP
    if DESKTOP is None:
        import file_manager
        DESKTOP = Path(file_manager.desktop_path())
    return DESKTOP


def _lib(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def _verify(path: str, min_size: int = 10) -> tuple[bool, str]:
    if not os.path.exists(path):
        return False, "ফাইল তৈরিই হয়নি"
    if os.path.getsize(path) < min_size:
        return False, "ফাইল খুব ছোট/খালি — যাচাই ব্যর্থ"
    return True, f"যাচাইকৃত ({os.path.getsize(path)} bytes)"


def create_txt(name: str, content: str) -> dict:
    path = _desktop() / f"{name}.txt"
    try:
        path.write_text(content, encoding="utf-8")
    except OSError as e:
        return {"ok": False, "msg": str(e)}
    ok, note = _verify(str(path))
    return {"ok": ok, "path": str(path), "msg": note}


def create_md(name: str, title: str, body: str) -> dict:
    path = _desktop() / f"{name}.md"
    content = f"# {title}\n\n_তৈরি: {datetime.datetime.now():%Y-%m-%d %H:%M}_\n\n{body}\n"
    try:
        path.write_text(content, encoding="utf-8")
    except OSError as e:
        return {"ok": False, "msg": str(e)}
    ok, note = _verify(str(path))
    return {"ok": ok, "path": str(path), "msg": note}


def create_csv(name: str, rows: list[list]) -> dict:
    path = _desktop() / f"{name}.csv"
    try:
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerows(rows)
    except OSError as e:
        return {"ok": False, "msg": str(e)}
    ok, note = _verify(str(path))
    return {"ok": ok, "path": str(path), "msg": note}


def create_html(name: str, title: str, body: str) -> dict:
    path = _desktop() / f"{name}.html"
    content = f"""<!DOCTYPE html><html lang="bn"><head><meta charset="utf-8">
<title>{title}</title><style>body{{font-family:'Noto Sans Bengali',sans-serif;
max-width:800px;margin:40px auto;line-height:1.7}}</style></head>
<body><h1>{title}</h1><p><i>{datetime.datetime.now():%Y-%m-%d %H:%M}</i></p>
{body}</body></html>"""
    try:
        path.write_text(content, encoding="utf-8")
    except OSError as e:
        return {"ok": False, "msg": str(e)}
    ok, note = _verify(str(path), 100)
    return {"ok": ok, "path": str(path), "msg": note}


def create_docx(name: str, title: str, body: str) -> dict:
    if not _lib("docx"):
        return {"ok": False, "msg": "python-docx ইনস্টল নেই — বলুন 'python-docx ইনস্টল করো'"}
    from docx import Document
    doc = Document()
    doc.add_heading(title, level=1)
    doc.add_paragraph(f"তৈরি: {datetime.datetime.now():%Y-%m-%d %H:%M} — AVA Universal AI")
    for para in body.split("\n"):
        if para.strip():
            doc.add_paragraph(para)
    path = _desktop() / f"{name}.docx"
    doc.save(str(path))
    ok, note = _verify(str(path), 500)
    return {"ok": ok, "path": str(path), "msg": note}


def create_xlsx(name: str, rows: list[list]) -> dict:
    if not _lib("openpyxl"):
        return {"ok": False, "msg": "openpyxl ইনস্টল নেই — বলুন 'openpyxl ইনস্টল করো'"}
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Data"
    for row in rows:
        ws.append(row)
    path = _desktop() / f"{name}.xlsx"
    wb.save(str(path))
    ok, note = _verify(str(path), 100)
    return {"ok": ok, "path": str(path), "msg": note}


def create_pdf(name: str, title: str, body: str) -> dict:
    if _lib("fpdf"):
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=14)
        pdf.multi_cell(0, 10, title)
        pdf.set_font("Helvetica", size=11)
        pdf.multi_cell(0, 8, body)
        path = _desktop() / f"{name}.pdf"
        pdf.output(str(path))
        ok, note = _verify(str(path), 200)
        return {"ok": ok, "path": str(path), "msg": note + " (⚠️ বাংলা ফন্ট এমবেড ছাড়া ইংরেজি ভালো দেখাবে)"}
    return {"ok": False, "msg": "fpdf2 ইনস্টল নেই — বলুন 'fpdf2 ইনস্টল করো' "
            "(বিকল্প: HTML ডকুমেন্ট বানিয়ে প্রিন্ট→PDF করতে পারেন)"}


def capabilities() -> str:
    lines = ["📄 ডকুমেন্ট ক্রিয়েটর — সমর্থিত ফরম্যাট:"]
    for fmt, lib in (("TXT/MD/CSV/HTML", None), ("DOCX", "docx"),
                     ("XLSX", "openpyxl"), ("PDF", "fpdf")):
        if lib is None:
            lines.append(f"• {fmt} ✔️ (সর্বদা)")
        else:
            lines.append(f"• {fmt} {'✔️ (লাইব্রেরি আছে)' if _lib(lib) else '❌ (লাইব্রেরি নেই — ইনস্টল করলে চলবে)'}")
    return "\n".join(lines)


# ----------------- ভয়েস রাউটার -----------------
def handle(user_text: str) -> tuple[bool, str] | None:
    t = user_text.lower()
    if not any(w in t for w in ("ডকুমেন্ট", "document", "রিপোর্ট লেখো", "ইনভয়েস",
                                "invoice", "মিটিং নোট", "meeting note", "স্প্রেডশিট",
                                "spreadsheet", "প্রেজেন্টেশন", "docx", "xlsx", "pdf",
                                "মার্কডাউন")):
        return None
    m = re.search(r"(?:নাম|name)\s+([\w\u0980-\u09FF\- ]+?)(?:\s+(?:বানাও|বানা|create|koro|করো)|$)",
                  user_text, re.I)
    name = (m.group(1).strip() if m else
            f"AVA_Document_{datetime.datetime.now():%Y%m%d_%H%M}").replace(" ", "_")

    if "ইনভয়েস" in t or "invoice" in t:
        rows = [["আইটেম", "পরিমাণ", "দাম"], ["—", "—", "—"]]
        return True, _fmt(create_csv(name + "_invoice", rows), "CSV ইনভয়েস টেমপ্লেট")
    if "স্প্রেডশিট" in t or "spreadsheet" in t or "xlsx" in t or "এক্সেল" in t:
        return True, _fmt(create_xlsx(name, [["শিরোনাম"], ["ডেটা..."]]), "XLSX")
    if "pdf" in t:
        return True, _fmt(create_pdf(name, name.replace("_", " "),
                                     user_text), "PDF")
    if "docx" in t or "ওয়ার্ড" in t or "word" in t:
        return True, _fmt(create_docx(name, name.replace("_", " "), user_text), "DOCX")
    if "স্প্রেডশিট" not in t and ("মিটিং" in t or "meeting" in t or "নোট" in t):
        return True, _fmt(create_md(name, name.replace("_", " "), user_text), "Markdown")
    if "html" in t or "ওয়েব রিপোর্ট" in t:
        return True, _fmt(create_html(name, name.replace("_", " "), user_text), "HTML")
    return True, _fmt(create_md(name, name.replace("_", " "), user_text), "Markdown") + \
        ("\n💡 capabilities:\n" + capabilities())


def _fmt(r: dict, kind: str) -> str:
    if r["ok"]:
        return f"✅ {kind} তৈরি ও যাচাইকৃত: {r['path']}\n{r['msg']}"
    return f"❌ {kind} তৈরি হয়নি — {r['msg']}"
