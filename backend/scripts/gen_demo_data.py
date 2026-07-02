"""
Generate REAL-FORMAT synthetic medical files for the demo — the formats a doctor
actually uploads: formatted PDF reports (text-layer, so pypdf extracts + cites
pages), a scanned/photographed prescription IMAGE (read by Gemini vision), plain
clinic notes, and a CSV lab series. NOT developer JSON.

One coherent patient story (Rahul Sharma, 52M) that exercises every feature:
  intake note      → diabetes + metformin + smoking + LDL + family history + lisinopril
  discharge PDF    → penicillin allergy (page 2 = the citation target)
  lab PDF          → HbA1c 8.6 (rising) + creatinine 1.6 (high, no follow-up)
  hba1c CSV        → HbA1c 7.8 (trend start)
  med-change note  → lisinopril → amlodipine (supersession / self-heal)
  prescription IMG → amoxicillin (IMAGE → vision) → the penicillin-allergy STOP
  son intake note  → names father Rahul (MRN) → automatic family linkage

Run:  cd backend && .venv/Scripts/python.exe scripts/gen_demo_data.py
Output: data/demo_uploads/
"""
from __future__ import annotations

import os
import random
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT = Path(__file__).resolve().parents[2] / "data" / "demo_uploads"
OUT.mkdir(parents=True, exist_ok=True)

DISCLAIMER = "Demo only — synthetic data, not medical advice. No real PHI."
PATIENT = "Rahul Sharma"
MRN = "RH-4471"
DOB = "1974-02-03"

styles = getSampleStyleSheet()
H = ParagraphStyle("H", parent=styles["Heading1"], fontSize=16, spaceAfter=6, textColor=colors.HexColor("#0c1521"))
SUB = ParagraphStyle("SUB", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#8a99a8"))
SEC = ParagraphStyle("SEC", parent=styles["Heading2"], fontSize=11, spaceBefore=10, spaceAfter=3, textColor=colors.HexColor("#0e8c84"))
BODY = ParagraphStyle("BODY", parent=styles["Normal"], fontSize=9.5, leading=14, textColor=colors.HexColor("#0c1521"))


def _header(story, org, kind):
    story.append(Paragraph(org, H))
    story.append(Paragraph(f"{kind}  ·  {DISCLAIMER}", SUB))
    story.append(Spacer(1, 6))
    t = Table([[f"Patient: {PATIENT}", f"MRN: {MRN}", f"DOB: {DOB}"]], colWidths=[2.6*inch, 1.8*inch, 1.8*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f4f7f9")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0c1521")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e6ebf0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e6ebf0")),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))


def discharge_summary_2021():
    path = OUT / "discharge_summary_2021.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=LETTER, topMargin=0.7*inch)
    s = []
    _header(s, "City General Hospital — Internal Medicine", "Discharge Summary")
    s.append(Paragraph("Admission", SEC))
    s.append(Paragraph(
        "Admission date: 2021-08-05. Discharge date: 2021-08-09. Mr. Sharma, a 47-year-old "
        "man (at time of admission), was treated for community-acquired pneumonia and has "
        "recovered. Diabetes remained stable during the stay.", BODY))
    s.append(Paragraph("Hospital Course", SEC))
    s.append(Paragraph(
        "Empiric antibiotics were started. On day 2 the patient developed an adverse drug "
        "reaction (see Allergy Review, page 2). Antibiotics were changed and the reaction "
        "resolved. He was discharged in stable condition with primary-care follow-up.", BODY))
    s.append(Paragraph("Discharge Medications", SEC))
    s.append(Paragraph("Metformin 500 mg twice daily (continued). Follow up with primary care.", BODY))
    # page 2 — the canonical allergy citation target
    s.append(PageBreak())
    s.append(Paragraph("Allergy Review", H))
    s.append(Paragraph("Page 2 · Allergy documentation  ·  " + DISCLAIMER, SUB))
    s.append(Spacer(1, 10))
    s.append(Paragraph("Documented Drug Allergy", SEC))
    s.append(Paragraph(
        "<b>Allergy: Penicillin.</b> During this admission the patient developed a "
        "reaction to a penicillin-class antibiotic: <b>rash and breathing difficulty</b>. "
        "Severity: <b>severe</b>. Date recorded: 2021-08-06. Recorded by: Dr. A. Adams.", BODY))
    s.append(Spacer(1, 6))
    s.append(Paragraph(
        "Clinical instruction: AVOID penicillin-class antibiotics (including amoxicillin, "
        "ampicillin) and review beta-lactam alternatives before prescribing.", BODY))
    doc.build(s)
    return path


def lab_report_2025():
    path = OUT / "lab_report_2025.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=LETTER, topMargin=0.7*inch)
    s = []
    _header(s, "Metro Diagnostics Laboratory", "Laboratory Report")
    s.append(Paragraph("Specimen collected: 2025-12-04. Reported: 2025-12-05. Ordering: Dr. R. Mehta.", BODY))
    s.append(Spacer(1, 8))
    rows = [
        ["Test", "Result", "Units", "Reference range", "Flag"],
        ["HbA1c", "8.6", "%", "< 7.0", "HIGH"],
        ["Creatinine", "1.6", "mg/dL", "0.7 – 1.3", "HIGH"],
        ["eGFR", "52", "mL/min/1.73m2", "> 60", "LOW"],
        ["LDL cholesterol", "165", "mg/dL", "< 100", "HIGH"],
    ]
    t = Table(rows, colWidths=[1.9*inch, 0.9*inch, 1.3*inch, 1.6*inch, 0.7*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0e8c84")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e6ebf0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("TEXTCOLOR", (4, 1), (4, -1), colors.HexColor("#d7263d")),
        ("FONTNAME", (4, 1), (4, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    s.append(t)
    s.append(Spacer(1, 10))
    s.append(Paragraph("Interpretation", SEC))
    s.append(Paragraph(
        "HbA1c remains elevated and has risen versus prior results. Creatinine is elevated "
        "with reduced eGFR — recommend nephrology review and repeat renal function.", BODY))
    doc.build(s)
    return path


def scanned_prescription_image():
    """A photographed/scanned prescription — off-white, slight rotation + blur, so it
    reads like a real phone photo of a paper Rx. Gemini vision extracts amoxicillin."""
    W, Hh = 1000, 680
    img = Image.new("RGB", (W, Hh), (250, 248, 242))
    d = ImageDraw.Draw(img)

    def font(sz, bold=False):
        for name in (("arialbd.ttf" if bold else "arial.ttf"), "DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(name, sz)
            except Exception:
                continue
        return ImageFont.load_default()

    # letterhead
    d.rectangle([0, 0, W, 70], fill=(235, 232, 224))
    d.text((30, 20), "Sunrise Family Clinic", font=font(30, True), fill=(40, 40, 40))
    d.text((30, 84), "Rx  —  Prescription", font=font(22, True), fill=(30, 30, 30))
    d.line([30, 120, W-30, 120], fill=(120, 120, 120), width=2)
    y = 150
    for line in [
        f"Patient: {PATIENT}      MRN: {MRN}",
        f"DOB: {DOB}                 Date: 2026-06-14",
        "",
        "Rx:  Amoxicillin 500 mg",
        "     Take one capsule three times daily x 7 days",
        "     Dx: dental infection",
        "",
        "Prescriber: Dr. S. Kapoor        Signature: __________",
    ]:
        d.text((40, y), line, font=font(24, line.startswith("Rx:")), fill=(25, 25, 25))
        y += 44
    d.text((30, Hh-34), DISCLAIMER, font=font(15), fill=(150, 150, 150))

    # make it look scanned/photographed: slight rotation, blur, sensor noise
    img = img.rotate(-1.6, expand=True, fillcolor=(250, 248, 242))
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    px = img.load()
    random.seed(7)
    for _ in range(9000):
        x, yy = random.randint(0, img.width-1), random.randint(0, img.height-1)
        n = random.randint(-18, 18)
        r, g, b = px[x, yy]
        px[x, yy] = (max(0, min(255, r+n)), max(0, min(255, g+n)), max(0, min(255, b+n)))
    path = OUT / "prescription_scan.png"
    img.save(path)
    return path


def text_files():
    made = []
    intake = OUT / "clinic_note_intake.txt"
    intake.write_text(
        f"SUNRISE FAMILY CLINIC — New Patient Intake Note\n{DISCLAIMER}\n\n"
        f"Patient: {PATIENT}   MRN: {MRN}   DOB: {DOB}\n"
        "Date: 2024-06-12\n\n"
        "History: Type 2 diabetes mellitus diagnosed in 2019, currently on metformin 500 mg "
        "twice daily. Hypertension — started on lisinopril 10 mg daily in 2024-02.\n"
        "Lifestyle: Current smoker (about 1 pack/day), sedentary, limited exercise.\n"
        "Labs today: LDL cholesterol 165 mg/dL (high).\n"
        "Family history: Father had a heart attack (myocardial infarction) at age 49. "
        "Mother — no significant history.\n",
        encoding="utf-8")
    made.append(intake)

    medchange = OUT / "med_change_note.txt"
    medchange.write_text(
        f"SUNRISE FAMILY CLINIC — Progress Note\n{DISCLAIMER}\n\n"
        f"Patient: {PATIENT}   MRN: {MRN}\nDate: 2026-04-20\n\n"
        "Blood pressure inadequately controlled on lisinopril. Stopped lisinopril; "
        "switched to amlodipine 5 mg daily. Patient tolerating well. — Dr. R. Mehta\n",
        encoding="utf-8")
    made.append(medchange)

    son = OUT / "son_intake_note.txt"
    son.write_text(
        f"SUNRISE FAMILY CLINIC — New Patient Intake Note\n{DISCLAIMER}\n\n"
        "Patient: Arjun Sharma   MRN: AS-7788   DOB: 1999-06-01\n"
        "Date: 2026-06-20\n\n"
        "Reason for visit: routine check, family history review.\n"
        "Lifestyle: non-smoker, exercises regularly.\n"
        f"Family history: Father — {PATIENT}, MRN {MRN} — has type 2 diabetes and had a "
        "myocardial infarction at age 49. Mother — no significant history.\n",
        encoding="utf-8")
    made.append(son)
    return made


def hba1c_csv():
    path = OUT / "hba1c_series_2024.csv"
    path.write_text(
        "patient,mrn,date,test,value,unit,reference_range,flag,source\n"
        f"{PATIENT},{MRN},2024-06-12,HbA1c,7.8,%,<7.0,high,hba1c_series_2024.csv\n",
        encoding="utf-8")
    return path


def main():
    made = []
    made.append(discharge_summary_2021())
    made.append(lab_report_2025())
    made.append(scanned_prescription_image())
    made += text_files()
    made.append(hba1c_csv())
    print(f"Generated {len(made)} real-format files in {OUT}:")
    for p in made:
        print("  ", p.name, f"({p.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
