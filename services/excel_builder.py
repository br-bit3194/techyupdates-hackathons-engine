"""In-memory Excel workbook generator using openpyxl with 4 styled tabs, 12 formatted columns, and direct clickable links."""

import io
import re
from typing import List, Dict
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from services.ai_extractor import HackathonRecord

CATEGORY_CONFIG = [
    {
        "category_name": "AI & GenAI Hackathons",
        "sheet_name": "🤖 AI & GenAI",
        "color_hex": "4338CA",  # Electric Indigo
        "zebra_hex": "EEF2FF",
    },
    {
        "category_name": "Web3 & Open Source Hackathons",
        "sheet_name": "🌐 Web3 & Open Source",
        "color_hex": "0F766E",  # Deep Teal
        "zebra_hex": "F0FDFA",
    },
    {
        "category_name": "Student & University Hackathons",
        "sheet_name": "🎓 Student & University",
        "color_hex": "065F46",  # Emerald Forest
        "zebra_hex": "F0FDF4",
    },
    {
        "category_name": "Open Innovation & Hiring Challenges",
        "sheet_name": "🏆 Open & Hiring Sprints",
        "color_hex": "991B1B",  # Deep Wine Red
        "zebra_hex": "FEF2F2",
    },
]

HEADERS = [
    "Organizer / Platform",
    "Hackathon Title",
    "Theme / Track",
    "Mode",
    "Location",
    "Prize Pool / Rewards",
    "Date Posted",
    "Registration Deadline",
    "Event Dates",
    "Eligibility",
    "Why Participate?",
    "Direct Apply Link",
]

COLUMN_WIDTHS = [22, 32, 26, 14, 20, 22, 16, 20, 18, 22, 46, 22]


def _extract_numeric_prize(prize_str: str) -> float:
    """Extract a numeric heuristic from prize string for descending value sorting."""
    if not prize_str or "unspecified" in prize_str.lower() or "swag" in prize_str.lower():
        return 0.0
    numbers = re.findall(r"(\d+(?:,\d+)*(?:\.\d+)?)", prize_str.replace(",", ""))
    if not numbers:
        return 0.0
    val = float(numbers[-1])
    if "₹" in prize_str or "rs" in prize_str.lower() or "inr" in prize_str.lower() or "lakh" in prize_str.lower() or "lpa" in prize_str.lower():
        return val * 1200
    if "k" in prize_str.lower():
        return val * 1000
    if "$" in prize_str:
        return val
    return val


def _sort_records(records: List[HackathonRecord]) -> List[HackathonRecord]:
    """Sort hackathons prioritizing largest prize pool and recognizable events."""
    return sorted(records, key=lambda r: _extract_numeric_prize(r.prize_pool), reverse=True)


def build_excel_workbook(hackathons: List[HackathonRecord]) -> io.BytesIO:
    """Generate a 4-tab styled Excel workbook in memory with 12 structured columns."""
    wb = openpyxl.Workbook()
    default_sheet = wb.active
    if default_sheet is not None:
        wb.remove(default_sheet)

    thin_border = Border(
        left=Side(style="thin", color="E2E8F0"),
        right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"),
        bottom=Side(style="thin", color="E2E8F0"),
    )

    for cfg in CATEGORY_CONFIG:
        cat_name = cfg["category_name"]
        sheet_title = cfg["sheet_name"]
        header_color = cfg["color_hex"]
        zebra_color = cfg["zebra_hex"]

        ws = wb.create_sheet(title=sheet_title)
        ws.views.sheetView[0].showGridLines = True
        ws.freeze_panes = "A2"

        # 1. Header Styling
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color=header_color, end_color=header_color, fill_type="solid")
        header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

        for col_idx, (header_text, width) in enumerate(zip(HEADERS, COLUMN_WIDTHS), start=1):
            cell = ws.cell(row=1, column=col_idx, value=header_text)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            cell.border = thin_border
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = width

        ws.row_dimensions[1].height = 28

        # 2. Filter records for this category
        cat_records = [h for h in hackathons if h.category == cat_name]
        sorted_records = _sort_records(cat_records)

        # 3. Populate Data Rows
        body_font = Font(name="Calibri", size=10, color="1E293B")
        link_font = Font(name="Calibri", size=10, color="2563EB", underline="single", bold=True)
        zebra_fill = PatternFill(start_color=zebra_color, end_color=zebra_color, fill_type="solid")
        white_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

        align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)
        align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)

        for r_idx, h in enumerate(sorted_records, start=2):
            fill = zebra_fill if (r_idx % 2 == 0) else white_fill

            row_data = [
                (h.platform, align_left, body_font),
                (h.title, align_left, body_font),
                (h.theme, align_center, body_font),
                (h.mode, align_center, body_font),
                (h.location, align_center, body_font),
                (h.prize_pool, align_center, body_font),
                (h.posted_date, align_center, body_font),
                (h.registration_deadline, align_center, body_font),
                (h.event_dates, align_center, body_font),
                (h.eligibility, align_center, body_font),
                (h.why_participate, align_left, body_font),
            ]

            for c_idx, (val, alignment, font) in enumerate(row_data, start=1):
                cell = ws.cell(row=r_idx, column=c_idx, value=val)
                cell.font = font
                cell.fill = fill
                cell.alignment = alignment
                cell.border = thin_border

            # Column 12: Clickable HYPERLINK formula
            link_cell = ws.cell(row=r_idx, column=12)
            clean_url = (h.apply_url or "").strip()
            if clean_url.startswith("http"):
                escaped_url = clean_url.replace('"', '""')
                link_cell.value = f'=HYPERLINK("{escaped_url}", "Register Direct ↗")'
            else:
                link_cell.value = "Registration Closed"
            link_cell.font = link_font
            link_cell.fill = fill
            link_cell.alignment = align_center
            link_cell.border = thin_border

            ws.row_dimensions[r_idx].height = 24

        # Auto-filter over all populated rows
        last_row = max(len(sorted_records) + 1, 2)
        ws.auto_filter.ref = f"A1:L{last_row}"

    output_stream = io.BytesIO()
    wb.save(output_stream)
    output_stream.seek(0)
    return output_stream
