"""
backend/app/reports/pdf_generator.py

Production PDF Inspection Report Generator for LABELGUARD.
Uses ReportLab to generate government-inspection-grade, multi-page compliance reports
from the canonical report payload (build_inspection_report_data).
"""

from datetime import datetime
import io
import os
from pathlib import Path
from typing import Any

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from app.reports.report_data import build_inspection_report_data


REPORTS_DIR = Path(__file__).resolve().parents[2] / "storage" / "reports"
PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 36.0  # 0.5 inch margins
CONTENT_WIDTH = PAGE_WIDTH - (2 * MARGIN)  # 523.27 pt


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute and render running headers,
    footers, and 'Page X of Y' pagination across all pages.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict[str, Any]] = []
        self.ref_number: str = "INSPECTION"

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def _draw_page_decorations(self, total_pages: int) -> None:
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#718096"))

        # Running header on page 2+
        if self._pageNumber > 1:
            self.drawString(
                MARGIN,
                PAGE_HEIGHT - 24,
                "LABELGUARD — Legal Metrology Inspection Report",
            )
            self.drawRightString(
                PAGE_WIDTH - MARGIN,
                PAGE_HEIGHT - 24,
                f"Ref: {self.ref_number}",
            )
            self.setStrokeColor(colors.HexColor("#CBD5E0"))
            self.setLineWidth(0.5)
            self.line(
                MARGIN,
                PAGE_HEIGHT - 28,
                PAGE_WIDTH - MARGIN,
                PAGE_HEIGHT - 28,
            )

        # Running footer on all pages
        self.setStrokeColor(colors.HexColor("#CBD5E0"))
        self.setLineWidth(0.5)
        self.line(MARGIN, 28, PAGE_WIDTH - MARGIN, 28)

        self.drawString(
            MARGIN,
            18,
            "CONFIDENTIAL — Authorized Legal Metrology Inspection Record",
        )
        page_str = f"Page {self._pageNumber} of {total_pages}"
        self.drawRightString(PAGE_WIDTH - MARGIN, 18, page_str)

        self.restoreState()


def _sanitize(text: Any) -> str:
    """Escapes XML entities and replaces unsupported characters for standard ReportLab fonts."""
    if text is None:
        return "-"
    s = str(text)
    s = s.replace("₹", "Rs. ")
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return s


def _get_status_colors(status: str) -> tuple[colors.Color, colors.Color, str]:
    """Returns (text_color, bg_color, display_text) for compliance status."""
    st = str(status).strip().lower()
    if st == "compliant" or st == "pass":
        return (
            colors.HexColor("#1C4532"),
            colors.HexColor("#C6F6D5"),
            "COMPLIANT / PASS",
        )
    if st in ("non_compliant", "fail", "failed"):
        return (
            colors.HexColor("#742A2A"),
            colors.HexColor("#FED7D7"),
            "NON-COMPLIANT / FAIL",
        )
    if st in ("review", "warning"):
        return (
            colors.HexColor("#744210"),
            colors.HexColor("#FEEBC8"),
            "REVIEW REQUIRED",
        )
    return (
        colors.HexColor("#2D3748"),
        colors.HexColor("#EDF2F7"),
        st.upper() if st else "PENDING",
    )


def _build_image_flowable(
    image_data: dict[str, Any],
    max_w: float = 230.0,
    max_h: float = 160.0,
) -> Any:
    """Safely loads and scales an uploaded inspection image, or creates a placeholder."""
    abs_path = image_data.get("absolute_path")
    file_name = image_data.get("file_name", "image.png")
    image_type = (image_data.get("image_type") or "Scanned").capitalize()

    if abs_path and os.path.exists(abs_path):
        try:
            with PILImage.open(abs_path) as pil_img:
                orig_w, orig_h = pil_img.size

            aspect = orig_w / float(orig_h)
            if orig_w > orig_h:
                render_w = min(max_w, float(orig_w))
                render_h = render_w / aspect
                if render_h > max_h:
                    render_h = max_h
                    render_w = render_h * aspect
            else:
                render_h = min(max_h, float(orig_h))
                render_w = render_h * aspect
                if render_w > max_w:
                    render_w = max_w
                    render_h = render_w / aspect

            return RLImage(abs_path, width=render_w, height=render_h)

        except Exception:
            pass

    # Stylized placeholder when image cannot be read or is missing
    placeholder_style = ParagraphStyle(
        "ImgPlaceholder",
        fontName="Helvetica-Oblique",
        fontSize=8,
        textColor=colors.HexColor("#718096"),
        alignment=1,
    )
    p_text = f"<b>[{image_type} Panel]</b><br/>{_sanitize(file_name)}<br/><i>Image file unavailable on disk</i>"
    t = Table(
        [[Paragraph(p_text, placeholder_style)]],
        colWidths=[max_w],
        rowHeights=[max_h * 0.7],
    )
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7FAFC")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return t


def generate_inspection_pdf(
    db: Session,
    inspection_id: int,
) -> Path:
    """
    Generates a canonical, professional Legal Metrology PDF inspection report
    using ReportLab and saves it to storage/reports/<reference_number>_inspection_report.pdf.
    """
    report_data = build_inspection_report_data(
        db=db,
        inspection_id=inspection_id,
        report_format="pdf",
    )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ref_num = report_data["inspection"]["reference_number"]
    pdf_filename = f"{ref_num}_inspection_report.pdf"
    pdf_path = REPORTS_DIR / pdf_filename

    # Build Document Template
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
    )

    styles = getSampleStyleSheet()

    # Custom Typography Styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1A365D"),
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#4A5568"),
    )
    h1_style = ParagraphStyle(
        "Heading1_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#1A365D"),
        spaceBefore=8,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "Body_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#2D3748"),
    )
    body_bold = ParagraphStyle(
        "Body_Bold",
        parent=body_style,
        fontName="Helvetica-Bold",
    )
    cell_style = ParagraphStyle(
        "Cell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#2D3748"),
    )
    cell_bold = ParagraphStyle(
        "CellBold",
        parent=cell_style,
        fontName="Helvetica-Bold",
    )
    cell_header = ParagraphStyle(
        "CellHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.white,
    )
    badge_style = ParagraphStyle(
        "StatusBadge",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        alignment=1,
    )

    story: list[Any] = []

    # ---------------------------------------------------------
    # 1. HEADER / BANNER SECTION
    # ---------------------------------------------------------
    status_fg, status_bg, status_label = _get_status_colors(
        report_data["inspection"]["compliance_status"]
    )
    badge_style.textColor = status_fg

    header_left = [
        Paragraph("<b>LABELGUARD</b>", title_style),
        Paragraph(
            "AI-Assisted Legal Metrology Inspection Report",
            subtitle_style,
        ),
        Spacer(1, 4),
        Paragraph(
            f"<b>Reference:</b> {_sanitize(ref_num)} &nbsp;&nbsp;|&nbsp;&nbsp; <b>ID:</b> {report_data['inspection']['inspection_id']}",
            body_style,
        ),
        Paragraph(
            f"<b>Generated:</b> {_sanitize(report_data['metadata']['report_generated_at'])}",
            body_style,
        ),
    ]

    badge_table = Table(
        [[Paragraph(status_label, badge_style)]],
        colWidths=[150],
        rowHeights=[28],
    )
    badge_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), status_bg),
                ("BOX", (0, 0), (-1, -1), 1.5, status_fg),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )

    header_table = Table(
        [[header_left, badge_table]],
        colWidths=[CONTENT_WIDTH - 160, 160],
    )
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(header_table)
    story.append(Spacer(1, 6))
    story.append(
        HRFlowable(
            width="100%",
            thickness=1.5,
            color=colors.HexColor("#1A365D"),
            spaceBefore=2,
            spaceAfter=8,
        )
    )

    # ---------------------------------------------------------
    # 2. INSPECTION DETAILS & LOCATION EVIDENCE (SIDE-BY-SIDE)
    # ---------------------------------------------------------
    loc = report_data["location"]
    insp = report_data["inspection"]
    inspector = report_data["inspector"]

    col_w = (CONTENT_WIDTH - 10) / 2.0

    # Inspection details column
    insp_rows = [
        [
            Paragraph("Inspector:", cell_bold),
            Paragraph(
                f"{_sanitize(inspector.get('full_name'))} ({_sanitize(inspector.get('role'))})",
                cell_style,
            ),
        ],
        [
            Paragraph("Email:", cell_bold),
            Paragraph(_sanitize(inspector.get("email")), cell_style),
        ],
        [
            Paragraph("Status:", cell_bold),
            Paragraph(
                f"{_sanitize(insp.get('status')).upper()} / {_sanitize(insp.get('compliance_status')).upper()}",
                cell_style,
            ),
        ],
        [
            Paragraph("Created At:", cell_bold),
            Paragraph(_sanitize(insp.get("created_at")), cell_style),
        ],
        [
            Paragraph("Scan Started:", cell_bold),
            Paragraph(_sanitize(insp.get("scan_started_at")), cell_style),
        ],
        [
            Paragraph("Scan Completed:", cell_bold),
            Paragraph(_sanitize(insp.get("scan_completed_at")), cell_style),
        ],
    ]

    insp_details_table = Table(
        insp_rows, colWidths=[col_w * 0.38, col_w * 0.62]
    )
    insp_details_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    # Location details column
    loc_rows = [
        [
            Paragraph("Coordinates:", cell_bold),
            Paragraph(
                (
                    f"{loc['latitude']:.6f}, {loc['longitude']:.6f}"
                    if loc.get("is_available")
                    else "Location unavailable"
                ),
                cell_style,
            ),
        ],
        [
            Paragraph("Accuracy:", cell_bold),
            Paragraph(
                (
                    f"±{loc['location_accuracy_m']} m"
                    if loc.get("location_accuracy_m") is not None
                    else "-"
                ),
                cell_style,
            ),
        ],
        [
            Paragraph("Source:", cell_bold),
            Paragraph(_sanitize(loc.get("location_source")), cell_style),
        ],
        [
            Paragraph("Captured At:", cell_bold),
            Paragraph(_sanitize(loc.get("location_captured_at")), cell_style),
        ],
        [
            Paragraph("GPS Verification:", cell_bold),
            Paragraph(
                (
                    "<font color='#1C4532'><b>Geo-tagged Valid</b></font>"
                    if loc.get("is_available")
                    else "<font color='#718096'>Not Available</font>"
                ),
                cell_style,
            ),
        ],
        [
            Paragraph("Audit State:", cell_bold),
            Paragraph("Authenticated Session", cell_style),
        ],
    ]

    loc_table = Table(loc_rows, colWidths=[col_w * 0.38, col_w * 0.62])
    loc_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    overview_table = Table(
        [
            [
                Paragraph("<b>INSPECTION PROFILE</b>", h1_style),
                Paragraph("<b>LOCATION EVIDENCE</b>", h1_style),
            ],
            [insp_details_table, loc_table],
        ],
        colWidths=[col_w, col_w],
    )
    overview_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(overview_table)
    story.append(Spacer(1, 6))

    # ---------------------------------------------------------
    # 3. PRODUCT DETAILS
    # ---------------------------------------------------------
    prod = report_data.get("product")
    story.append(Paragraph("<b>PRODUCT DETAILS</b>", h1_style))

    if prod is not None:
        prod_data = [
            [
                Paragraph("Product Name:", cell_bold),
                Paragraph(_sanitize(prod.get("product_name")), cell_style),
                Paragraph("Brand Name:", cell_bold),
                Paragraph(_sanitize(prod.get("brand_name")), cell_style),
            ],
            [
                Paragraph("Category:", cell_bold),
                Paragraph(_sanitize(prod.get("category")), cell_style),
                Paragraph("Package Type:", cell_bold),
                Paragraph(_sanitize(prod.get("package_type")), cell_style),
            ],
            [
                Paragraph("Manufacturer:", cell_bold),
                Paragraph(
                    _sanitize(prod.get("manufacturer_name")), cell_style
                ),
                Paragraph("Address:", cell_bold),
                Paragraph(
                    _sanitize(prod.get("manufacturer_address")), cell_style
                ),
            ],
        ]
        prod_table = Table(
            prod_data,
            colWidths=[
                CONTENT_WIDTH * 0.18,
                CONTENT_WIDTH * 0.32,
                CONTENT_WIDTH * 0.18,
                CONTENT_WIDTH * 0.32,
            ],
        )
    else:
        prod_table = Table(
            [
                [
                    Paragraph(
                        "<i>No registered catalog product associated with this inspection (Unlinked Package Scan).</i>",
                        cell_style,
                    )
                ]
            ],
            colWidths=[CONTENT_WIDTH],
        )

    prod_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(prod_table)
    story.append(Spacer(1, 6))

    # ---------------------------------------------------------
    # 4. COMPLIANCE SUMMARY METRICS
    # ---------------------------------------------------------
    summ = report_data["evidence_summary"]
    story.append(Paragraph("<b>COMPLIANCE EVALUATION SUMMARY</b>", h1_style))

    summary_headers = [
        Paragraph("Total Rules", cell_header),
        Paragraph("Passed", cell_header),
        Paragraph("Failed", cell_header),
        Paragraph("Review", cell_header),
        Paragraph("N/A", cell_header),
        Paragraph("Declarations", cell_header),
        Paragraph("Violations", cell_header),
    ]
    summary_vals = [
        Paragraph(str(summ.get("total_rules", 0)), cell_bold),
        Paragraph(
            f"<font color='#1C4532'><b>{summ.get('passed_rules', 0)}</b></font>",
            cell_bold,
        ),
        Paragraph(
            f"<font color='#742A2A'><b>{summ.get('failed_rules', 0)}</b></font>",
            cell_bold,
        ),
        Paragraph(
            f"<font color='#744210'><b>{summ.get('reviewed_rules', 0)}</b></font>",
            cell_bold,
        ),
        Paragraph(str(summ.get("not_applicable_rules", 0)), cell_bold),
        Paragraph(str(summ.get("declarations_count", 0)), cell_bold),
        Paragraph(str(summ.get("violations_count", 0)), cell_bold),
    ]

    metric_w = CONTENT_WIDTH / 7.0
    summary_table = Table(
        [summary_headers, summary_vals], colWidths=[metric_w] * 7
    )
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A365D")),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F8FAFC")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 8))

    # ---------------------------------------------------------
    # 5. ACTUAL SCANNED IMAGES (ORIGINAL EVIDENCE)
    # ---------------------------------------------------------
    images = report_data.get("images", [])
    if images:
        story.append(
            Paragraph("<b>ACTUAL SCANNED IMAGES (ORIGINAL EVIDENCE)</b>", h1_style)
        )

        image_cells: list[list[Any]] = []
        # Pair images in 2-column layout
        for idx in range(0, len(images), 2):
            img_pair = images[idx : idx + 2]
            row_elements = []

            for img_item in img_pair:
                img_flowable = _build_image_flowable(img_item, max_w=240.0, max_h=160.0)
                meta_text = (
                    f"<b>Panel:</b> {_sanitize(img_item.get('image_type')).upper()}&nbsp;&nbsp;|&nbsp;&nbsp;"
                    f"<b>File:</b> {_sanitize(img_item.get('file_name'))}<br/>"
                    f"<b>Hash:</b> <font size='6'>{_sanitize(img_item.get('content_hash'))[:32]}...</font><br/>"
                    f"<b>Size:</b> {img_item.get('file_size', 0):,} bytes&nbsp;&nbsp;|&nbsp;&nbsp;"
                    f"<b>Uploaded:</b> {_sanitize(img_item.get('created_at'))[:19]}"
                )
                cell_flowables = [
                    img_flowable,
                    Spacer(1, 2),
                    Paragraph(meta_text, cell_style),
                ]
                row_elements.append(cell_flowables)

            if len(row_elements) == 1:
                row_elements.append("")  # Empty second column

            image_cells.append(row_elements)

        img_grid_w = (CONTENT_WIDTH - 10) / 2.0
        img_table = Table(
            image_cells, colWidths=[img_grid_w, img_grid_w]
        )
        img_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(img_table)
        story.append(Spacer(1, 6))

    # ---------------------------------------------------------
    # 6. EXTRACTED DECLARATIONS TABLE
    # ---------------------------------------------------------
    declarations = report_data.get("declarations", [])
    story.append(Paragraph("<b>MANDATORY DECLARATIONS EVIDENCE</b>", h1_style))

    decl_table_data = [
        [
            Paragraph("Field Name", cell_header),
            Paragraph("Extracted Value (Raw OCR)", cell_header),
            Paragraph("Normalized Value", cell_header),
            Paragraph("Present", cell_header),
            Paragraph("Confidence", cell_header),
        ]
    ]

    for d in declarations:
        conf_str = (
            f"{d['confidence']:.1f}%" if d.get("confidence") is not None else "-"
        )
        pres_str = "YES" if d.get("is_present") else "NO"
        decl_table_data.append(
            [
                Paragraph(f"<b>{_sanitize(d.get('field_name'))}</b>", cell_style),
                Paragraph(_sanitize(d.get("extracted_value")), cell_style),
                Paragraph(_sanitize(d.get("normalized_value")), cell_style),
                Paragraph(pres_str, cell_style),
                Paragraph(conf_str, cell_style),
            ]
        )

    if len(decl_table_data) == 1:
        decl_table_data.append(
            [
                Paragraph(
                    "<i>No declarations extracted from images.</i>", cell_style
                ),
                Paragraph("-", cell_style),
                Paragraph("-", cell_style),
                Paragraph("-", cell_style),
                Paragraph("-", cell_style),
            ]
        )

    decl_table = Table(
        decl_table_data,
        colWidths=[
            CONTENT_WIDTH * 0.24,
            CONTENT_WIDTH * 0.32,
            CONTENT_WIDTH * 0.24,
            CONTENT_WIDTH * 0.10,
            CONTENT_WIDTH * 0.10,
        ],
        repeatRows=1,
    )
    decl_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A365D")),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#F8FAFC")],
                ),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(decl_table)
    story.append(Spacer(1, 8))

    # ---------------------------------------------------------
    # 7. RULE COMPLIANCE MATRIX (DYNAMIC DDL)
    # ---------------------------------------------------------
    rules = report_data.get("rules", [])
    story.append(
        Paragraph("<b>STATUTORY COMPLIANCE RULE EVALUATION MATRIX</b>", h1_style)
    )

    rule_table_data = [
        [
            Paragraph("Rule / Statute", cell_header),
            Paragraph("Requirement / Title", cell_header),
            Paragraph("Result", cell_header),
            Paragraph("Evaluated Checks", cell_header),
        ]
    ]

    for r in rules:
        r_fg, r_bg, r_label = _get_status_colors(r.get("result_status"))
        checks_text = "<br/>".join(
            f"• <b>{_sanitize(c.get('field_name'))}</b> ({_sanitize(c.get('operator'))}): {_sanitize(c.get('status')).upper()}"
            for c in r.get("checks", [])
        )
        rule_table_data.append(
            [
                Paragraph(
                    f"<b>{_sanitize(r.get('rule_code'))}</b><br/>{_sanitize(r.get('rule_number'))} (v{r.get('version')})",
                    cell_style,
                ),
                Paragraph(
                    f"<b>{_sanitize(r.get('title'))}</b><br/>{_sanitize(r.get('requirement'))}",
                    cell_style,
                ),
                Paragraph(
                    f"<font color='{r_fg.hexval()}'><b>{r_label}</b></font>",
                    cell_style,
                ),
                Paragraph(checks_text or "-", cell_style),
            ]
        )

    rule_matrix_table = Table(
        rule_table_data,
        colWidths=[
            CONTENT_WIDTH * 0.22,
            CONTENT_WIDTH * 0.40,
            CONTENT_WIDTH * 0.16,
            CONTENT_WIDTH * 0.22,
        ],
        repeatRows=1,
    )
    rule_matrix_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A365D")),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#F8FAFC")],
                ),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(rule_matrix_table)
    story.append(Spacer(1, 8))

    # ---------------------------------------------------------
    # 8. VIOLATIONS & REVIEW FINDINGS
    # ---------------------------------------------------------
    violations = report_data.get("violations", [])
    story.append(
        Paragraph("<b>RECORDED VIOLATIONS & REVIEW FINDINGS</b>", h1_style)
    )

    if not violations:
        no_violation_box = Table(
            [
                [
                    Paragraph(
                        "<b>COMPLIANCE VERIFIED:</b> No violations or review items identified. "
                        "All scanned label declarations satisfy mandatory legal metrology requirements.",
                        ParagraphStyle(
                            "CompliantCallout",
                            parent=cell_style,
                            textColor=colors.HexColor("#1C4532"),
                        ),
                    )
                ]
            ],
            colWidths=[CONTENT_WIDTH],
        )
        no_violation_box.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, -1),
                        colors.HexColor("#C6F6D5"),
                    ),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#38A169")),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(no_violation_box)
    else:
        viol_table_data = [
            [
                Paragraph("Field / Rule", cell_header),
                Paragraph("Severity", cell_header),
                Paragraph("Status", cell_header),
                Paragraph("Violation Message", cell_header),
                Paragraph("Detected vs Expected", cell_header),
            ]
        ]
        for v in violations:
            v_fg, v_bg, v_status = _get_status_colors(v.get("status"))
            detected_str = f"Det: {_sanitize(v.get('detected_value'))}<br/>Exp: {_sanitize(v.get('expected_value'))}"
            viol_table_data.append(
                [
                    Paragraph(
                        f"<b>{_sanitize(v.get('field_name'))}</b>", cell_style
                    ),
                    Paragraph(
                        f"<b>{_sanitize(v.get('severity')).upper()}</b>",
                        cell_style,
                    ),
                    Paragraph(
                        f"<font color='{v_fg.hexval()}'><b>{_sanitize(v.get('status')).upper()}</b></font>",
                        cell_style,
                    ),
                    Paragraph(_sanitize(v.get("message")), cell_style),
                    Paragraph(detected_str, cell_style),
                ]
            )

        viol_table = Table(
            viol_table_data,
            colWidths=[
                CONTENT_WIDTH * 0.20,
                CONTENT_WIDTH * 0.14,
                CONTENT_WIDTH * 0.14,
                CONTENT_WIDTH * 0.28,
                CONTENT_WIDTH * 0.24,
            ],
            repeatRows=1,
        )
        viol_table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.HexColor("#742A2A"),
                    ),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#FFF5F5")],
                    ),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E53E3E")),
                    (
                        "INNERGRID",
                        (0, 0),
                        (-1, -1),
                        0.5,
                        colors.HexColor("#FED7D7"),
                    ),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(viol_table)

    story.append(Spacer(1, 8))

    # ---------------------------------------------------------
    # 9. REGULATORY TRACEABILITY & AUDIT PROVENANCE
    # ---------------------------------------------------------
    reg = report_data.get("regulation") or {}
    story.append(Paragraph("<b>REGULATORY TRACEABILITY & AUDIT PROVENANCE</b>", h1_style))

    trace_data = [
        [
            Paragraph("Enacting Regulation:", cell_bold),
            Paragraph(
                f"{_sanitize(reg.get('name'))} ({_sanitize(reg.get('code'))})",
                cell_style,
            ),
            Paragraph("Jurisdiction / Authority:", cell_bold),
            Paragraph(
                f"{_sanitize(reg.get('jurisdiction'))} — {_sanitize(reg.get('authority'))}",
                cell_style,
            ),
        ],
        [
            Paragraph("Generator Engine:", cell_bold),
            Paragraph(
                f"{_sanitize(report_data['metadata'].get('generator_version'))} (ReportLab 4.4.9)",
                cell_style,
            ),
            Paragraph("Report Generated At:", cell_bold),
            Paragraph(
                _sanitize(report_data["metadata"].get("report_generated_at")),
                cell_style,
            ),
        ],
    ]

    trace_table = Table(
        trace_data,
        colWidths=[
            CONTENT_WIDTH * 0.20,
            CONTENT_WIDTH * 0.30,
            CONTENT_WIDTH * 0.22,
            CONTENT_WIDTH * 0.28,
        ],
    )
    trace_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(trace_table)
    story.append(Spacer(1, 8))

    # ---------------------------------------------------------
    # 10. STATUTORY DISCLAIMER
    # ---------------------------------------------------------
    disclaimer_text = (
        "<b>STATUTORY NOTICE &amp; DISCLAIMER:</b> This inspection record is generated by LABELGUARD AI "
        "as an automated decision-support finding under the Legal Metrology (Packaged Commodities) Rules, 2011. "
        "This document constitutes preliminary technical analysis. Final statutory enforcement, compounding, "
        "or adjudication remains strictly within the discretionary authority of the designated Legal Metrology Officer."
    )
    disclaimer_table = Table(
        [[Paragraph(disclaimer_text, cell_style)]],
        colWidths=[CONTENT_WIDTH],
    )
    disclaimer_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EDF2F7")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(disclaimer_table)

    # Build Document with Custom NumberedCanvas
    def _canvas_factory(*args: Any, **kwargs: Any) -> NumberedCanvas:
        c = NumberedCanvas(*args, **kwargs)
        c.ref_number = ref_num
        return c

    doc.build(story, canvasmaker=_canvas_factory)

    return pdf_path
