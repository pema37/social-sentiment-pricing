"""
Retrospective Audit PDF Generator

Generates a professional PDF report from a RetrospectiveAuditResponse.
This is the "Free Pricing Audit" that gets emailed to prospects.

Uses fpdf2 (no system deps, Railway-safe).
"""

import io
from datetime import datetime
from decimal import Decimal
from typing import List

from fpdf import FPDF

from schemas.retrospective_audit import (
    RetrospectiveAuditResponse,
    AuditSummary,
    SKUAuditResult,
)


# ── Helpers ───────────────────────────────────────────────────

def _fmt_currency(value: Decimal | str) -> str:
    num = float(value) if isinstance(value, (Decimal, str)) else value
    return f"${num:,.0f}"


def _fmt_pct(value: Decimal | str | None) -> str:
    if value is None:
        return "—"
    num = float(value) if isinstance(value, (Decimal, str)) else value
    sign = "+" if num >= 0 else ""
    return f"{sign}{num:.1f}%"


def _fmt_date(iso_str: str | datetime) -> str:
    if isinstance(iso_str, datetime):
        return iso_str.strftime("%b %d, %Y")
    try:
        return datetime.fromisoformat(str(iso_str).replace("Z", "+00:00")).strftime("%b %d, %Y")
    except Exception:
        return str(iso_str)


# ── PDF Builder ───────────────────────────────────────────────

class AuditPDF(FPDF):
    """Custom PDF class with ActualPrice branding."""

    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=25)

    def header(self):
        # Brand bar
        self.set_fill_color(30, 64, 175)  # blue-700
        self.rect(0, 0, 210, 12, "F")
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(255, 255, 255)
        self.set_xy(10, 3)
        self.cell(0, 6, "ActualPrice  |  Pricing Intelligence Report", ln=True)
        self.set_text_color(0, 0, 0)
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Generated {datetime.utcnow().strftime('%B %d, %Y')}  |  Page {self.page_no()}/{{nb}}", align="C")

    def section_title(self, title: str):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(30, 64, 175)
        self.cell(0, 10, title, ln=True)
        self.set_draw_color(30, 64, 175)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)
        self.set_text_color(0, 0, 0)

    def metric_box(self, label: str, value: str, color_rgb: tuple = (220, 38, 38)):
        """Draw a highlighted metric."""
        x = self.get_x()
        y = self.get_y()
        self.set_font("Helvetica", "", 9)
        self.set_text_color(100, 100, 100)
        self.cell(60, 5, label, ln=True)
        self.set_font("Helvetica", "B", 20)
        self.set_text_color(*color_rgb)
        self.cell(60, 10, value, ln=True)
        self.set_text_color(0, 0, 0)
        self.ln(2)


def generate_audit_pdf(audit: RetrospectiveAuditResponse) -> bytes:
    """
    Generate a PDF from a RetrospectiveAuditResponse.

    Returns raw PDF bytes ready for HTTP response or file save.
    """
    pdf = AuditPDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    summary = audit.summary

    # ── Title ─────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(17, 24, 39)
    pdf.cell(0, 12, "Retrospective Pricing Audit", ln=True)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(107, 114, 128)
    period = f"{_fmt_date(summary.analysis_period_start)} - {_fmt_date(summary.analysis_period_end)}"
    pdf.cell(0, 6, f"{summary.lookback_days}-day analysis  |  {summary.total_products_analyzed} products  |  {period}", ln=True)
    pdf.ln(8)

    # ── Headline: Total Impact ────────────────────────────
    pdf.section_title("Money Left on the Table")

    # Big red number
    pdf.set_font("Helvetica", "B", 36)
    pdf.set_text_color(220, 38, 38)
    pdf.cell(0, 18, _fmt_currency(summary.total_estimated_impact), ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(107, 114, 128)
    pdf.cell(0, 6, f"Estimated pricing gap over {summary.lookback_days} days", ln=True)
    pdf.ln(6)

    # Breakdown row
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(220, 38, 38)
    pdf.cell(63, 6, f"Lost Revenue: {_fmt_currency(summary.total_lost_revenue)}")
    pdf.set_text_color(234, 88, 12)
    pdf.cell(63, 6, f"Missed Margin: {_fmt_currency(summary.total_missed_margin)}")
    pdf.set_text_color(107, 114, 128)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(63, 6, f"Avg overpriced: {_fmt_pct(summary.avg_overpriced_gap_percent)}", ln=True)
    pdf.ln(4)

    # Projections box
    pdf.set_fill_color(254, 242, 242)  # red-50
    pdf.set_draw_color(252, 165, 165)  # red-300
    pdf.rect(10, pdf.get_y(), 190, 18, "DF")
    y_box = pdf.get_y() + 3
    pdf.set_xy(15, y_box)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(153, 27, 27)
    pdf.cell(90, 5, f"Monthly projection: {_fmt_currency(summary.monthly_projected_loss)}/mo")
    pdf.cell(90, 5, f"Annual projection: {_fmt_currency(summary.annual_projected_loss)}/yr", ln=True)
    pdf.set_xy(15, y_box + 8)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(107, 114, 128)
    pdf.cell(0, 5, "At current pricing patterns, this is what you stand to lose going forward.", ln=True)
    pdf.ln(12)

    # ── Per-SKU Table ─────────────────────────────────────
    pdf.section_title("Product-by-Product Breakdown")

    # Sort by impact
    skus: List[SKUAuditResult] = sorted(
        audit.sku_results,
        key=lambda s: float(s.total_estimated_impact),
        reverse=True,
    )

    # Table header
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(243, 244, 246)  # gray-100
    pdf.set_text_color(75, 85, 99)
    col_widths = [52, 22, 28, 20, 22, 22, 24]
    headers = ["Product", "Your Price", "Comp. Avg", "Gap", "Over/Under", "Aligned", "Est. Impact"]
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 7, h, border=1, fill=True, align="C" if i > 0 else "L")
    pdf.ln()

    # Table rows
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(31, 41, 55)
    for sku in skus:
        # Truncate long names
        name = sku.product_name[:28] + "..." if len(sku.product_name) > 30 else sku.product_name

        impact = float(sku.total_estimated_impact)
        if impact > 500:
            pdf.set_fill_color(254, 242, 242)  # red tint for high impact
            fill = True
        else:
            fill = False

        pdf.cell(col_widths[0], 6, name, border=1, fill=fill)
        pdf.cell(col_widths[1], 6, _fmt_currency(sku.current_price), border=1, align="R", fill=fill)
        pdf.cell(col_widths[2], 6, _fmt_currency(sku.current_competitor_avg) if sku.current_competitor_avg else "-", border=1, align="R", fill=fill)
        pdf.cell(col_widths[3], 6, _fmt_pct(sku.current_gap_percent), border=1, align="R", fill=fill)
        pdf.cell(col_widths[4], 6, f"{sku.days_overpriced}d / {sku.days_underpriced}d", border=1, align="C", fill=fill)
        pdf.cell(col_widths[5], 6, f"{sku.days_aligned}d", border=1, align="C", fill=fill)

        # Impact in red if significant
        pdf.set_text_color(220, 38, 38) if impact > 100 else pdf.set_text_color(31, 41, 55)
        pdf.cell(col_widths[6], 6, _fmt_currency(sku.total_estimated_impact), border=1, align="R", fill=fill)
        pdf.set_text_color(31, 41, 55)
        pdf.ln()

        # Page break safety
        if pdf.get_y() > 260:
            pdf.add_page()

    pdf.ln(8)

    # ── Top Offenders Callout ─────────────────────────────
    if summary.top_loss_products:
        pdf.set_fill_color(255, 251, 235)  # amber-50
        pdf.set_draw_color(251, 191, 36)  # amber-400
        box_h = 14 + len(summary.top_loss_products) * 5
        pdf.rect(10, pdf.get_y(), 190, box_h, "DF")
        pdf.set_xy(15, pdf.get_y() + 3)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(146, 64, 14)
        pdf.cell(0, 5, "Highest Impact Products:", ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(107, 114, 128)
        for i, name in enumerate(summary.top_loss_products[:5], 1):
            pdf.set_x(20)
            pdf.cell(0, 5, f"{i}. {name}", ln=True)
        pdf.ln(6)

    # ── CTA Section ───────────────────────────────────────
    if pdf.get_y() > 240:
        pdf.add_page()

    pdf.ln(8)
    pdf.set_fill_color(30, 64, 175)  # blue-700
    pdf.rect(10, pdf.get_y(), 190, 30, "F")
    y_cta = pdf.get_y() + 5
    pdf.set_xy(15, y_cta)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 8, "Stop leaving money on the table.", ln=True)
    pdf.set_x(15)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 5, "ActualPrice monitors your competitors 24/7 and shows you exactly when to adjust prices.", ln=True)
    pdf.set_x(15)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Book a demo: https://cal.com/actualprice/demo", ln=True)
    pdf.ln(10)

    # ── Methodology ───────────────────────────────────────
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(156, 163, 175)
    pdf.multi_cell(190, 4, audit.methodology)

    # Output
    return pdf.output()



    