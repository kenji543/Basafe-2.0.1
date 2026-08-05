"""Dependency-free PDF report generation for saved assessments."""

from __future__ import annotations

from io import BytesIO
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


def _safe_text(value: Any) -> str:
    if value is None:
        return "Unavailable"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return (
        str(value)
        .replace("\r", " ")
        .replace("\n", " ")
        .replace("\u2011", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2192", "->")
    )


def _provenance_line(label: str, record: Mapping[str, Any] | None) -> str:
    record = record or {}
    metadata = record.get("source_metadata") or record.get("metadata") or {}
    if not isinstance(metadata, Mapping):
        metadata = {}
    status = record.get("data_status")
    if not status:
        status = (
            "official"
            if record.get("is_official")
            else "demonstration"
            if record.get("is_demo")
            else "not reported"
        )
    name = (
        record.get("source_name")
        or record.get("dataset_name")
        or metadata.get("source_name")
        or metadata.get("name")
    )
    date = (
        record.get("source_date")
        or metadata.get("source_date")
        or metadata.get("date")
    )
    quality = record.get("quality_status") or metadata.get("quality_status")
    source_url = (
        record.get("source_url")
        or metadata.get("source_url")
        or metadata.get("sourceUrl")
    )
    retrieved_at = (
        record.get("retrieved_at")
        or metadata.get("retrieved_at")
        or metadata.get("retrievedAt")
    )
    attribution = record.get("attribution") or metadata.get("attribution")
    return (
        f"{label}: source={_safe_text(name)}; date={_safe_text(date)}; "
        f"status={_safe_text(status)}; quality={_safe_text(quality)}; "
        f"retrieved={_safe_text(retrieved_at)}; URL={_safe_text(source_url)}; "
        f"attribution={_safe_text(attribution)}"
    )


def assessment_report_lines(
    assessment: Mapping[str, Any], disclaimer: str
) -> list[str]:
    """Build the complete human-readable content used by the PDF."""
    location = assessment.get("location", {})
    result = assessment.get("result", {})
    hazards = assessment.get("hazards", [])
    lines = [
        "GeoSafe-FIS Assessment Report",
        "Planning-oriented multi-hazard screening prototype",
        "",
        f"Assessment ID: {_safe_text(assessment.get('id'))}",
        f"Assessment created: {_safe_text(assessment.get('created_at'))}",
        f"Report generated: {datetime.now(timezone.utc).isoformat()}",
        f"Status: {_safe_text(assessment.get('status', result.get('status'))).upper()}",
        f"Model version: {_safe_text(result.get('model_version'))}",
        f"Model checksum (SHA-256): {_safe_text(result.get('model_checksum'))}",
        "",
        "SELECTED LOCATION",
        f"Selection label: {_safe_text(location.get('label'))}",
        f"Selection method: {_safe_text(location.get('selection_method'))}",
        f"Coordinates: {_safe_text(location.get('latitude'))}, {_safe_text(location.get('longitude'))}",
        f"Inside Basey municipal boundary: {_safe_text(location.get('inside_basey'))}",
        f"Barangay: {_safe_text((location.get('barangay') or {}).get('name'))}",
        "",
        "HAZARD INPUTS",
    ]
    for hazard in hazards:
        transformation = hazard.get("model_transformation") or {}
        cache = hazard.get("cache") or {}
        lines.extend(
            [
                (
                    f"{_safe_text(hazard.get('name', hazard.get('hazard_type')))} "
                    f"[{_safe_text(hazard.get('availability_status'))}]"
                ),
                (
                    "  Official source value: field="
                    f"{_safe_text(hazard.get('classification_field'))}; "
                    f"code={_safe_text(hazard.get('raw_code'))}; "
                    f"label={_safe_text(hazard.get('official_label', hazard.get('classification')))}"
                ),
                (
                    "  GeoSafe-FIS model transformation: normalized index="
                    f"{_safe_text(hazard.get('normalized_value'))} / 100; "
                    f"{_safe_text(transformation.get('notice'))}"
                ),
                (
                    f"  Source: {_safe_text(hazard.get('source_name'))}; "
                    f"date: {_safe_text(hazard.get('source_date'))}; "
                    f"retrieved: {_safe_text(hazard.get('retrieved_at'))}; "
                    f"spatial reference: {_safe_text(hazard.get('spatial_reference'))}; "
                    f"quality: {_safe_text(hazard.get('quality_status'))}; "
                    f"official: {_safe_text(hazard.get('is_official'))}; "
                    f"demonstration: {_safe_text(hazard.get('is_demo'))}"
                ),
                (
                    f"  Layer URL: {_safe_text(hazard.get('source_url'))}; "
                    f"attribution: {_safe_text(hazard.get('attribution'))}"
                ),
                (
                    f"  Cache: from cache={_safe_text(cache.get('from_cache'))}; "
                    f"stale={_safe_text(cache.get('stale'))}; "
                    f"expires={_safe_text(cache.get('expires_at'))}"
                ),
            ]
        )
        for warning in hazard.get("warnings", []):
            lines.append(f"  Data-quality warning: {_safe_text(warning)}")
    lines.extend(["", "FUZZY RESULT"])
    if result.get("status") == "complete":
        lines.extend(
            [
                f"Normalized screening score: {_safe_text(result.get('score'))} / 100",
                f"Descriptive category: {_safe_text(result.get('category'))}",
                f"Centroid before rounding: {_safe_text(result.get('centroid'))}",
            ]
        )
    else:
        lines.extend(
            [
                "Assessment incomplete - no score or vulnerability category was assigned.",
                f"Missing required inputs: {', '.join(result.get('missing_inputs', [])) or 'Unavailable'}",
                "Missing information was not interpreted as low vulnerability.",
            ]
        )

    weight_record = result.get("indicator_weights") or {}
    weight_values = weight_record.get("values") or {}
    lines.extend(["", "APPLIED INDICATOR WEIGHTS"])
    lines.append(
        f"Method: {_safe_text(weight_record.get('method'))}; "
        f"configured method: {_safe_text(weight_record.get('configured_method'))}; "
        f"status: {_safe_text(weight_record.get('status'))}"
    )
    if weight_values:
        lines.append(
            ", ".join(
                f"{indicator}={float(weight):.3f}"
                for indicator, weight in weight_values.items()
            )
        )
    else:
        lines.append("No indicator weights were applied because the required input set is incomplete or unconfigured.")

    lines.extend(["", "MEMBERSHIP VALUES"])
    for variable, memberships in result.get("memberships", {}).items():
        values = ", ".join(
            f"{term}={float(degree):.3f}" for term, degree in memberships.items()
        )
        lines.append(f"{variable}: {values}")

    lines.extend(["", "ACTIVATED FUZZY RULES"])
    if not result.get("activated_rules"):
        lines.append("No rules evaluated because the required input set is incomplete.")
    for rule in result.get("activated_rules", []):
        lines.extend(
            [
                f"{rule['id']} activation={float(rule['activation']):.3f}, weight={float(rule['weight']):.2f}",
                f"  {rule['statement']}",
                f"  Rationale: {_safe_text(rule.get('rationale'))}",
            ]
        )

    lines.extend(["", "HISTORICAL INCIDENT CONTEXT"])
    incidents = assessment.get("historical_incidents", [])
    if not incidents:
        lines.append("No matching incident record is available in the loaded dataset.")
    for incident in incidents:
        lines.append(
            f"{_safe_text(incident.get('incident_date'))} - "
            f"{_safe_text(incident.get('title', incident.get('incident_type')))} "
            f"[{_safe_text(incident.get('incident_type'))}; "
            f"severity {_safe_text(incident.get('severity'))}; "
            f"relationship {_safe_text(incident.get('match_reason'))}; "
            f"distance km {_safe_text(incident.get('distance_km'))}]: "
            f"{_safe_text(incident.get('description'))}"
        )

    lines.extend(["", "CLUP REFERENCE CONTEXT"])
    references = assessment.get("clup_references", [])
    if not references:
        lines.append("No matching CLUP reference is available in the loaded dataset.")
    for reference in references:
        lines.append(
            f"{_safe_text(reference.get('title'))} "
            f"[{_safe_text(reference.get('reference_type'))}; "
            f"section {_safe_text(reference.get('document_section'))}; "
            f"relationship {_safe_text(reference.get('match_reason'))}]: "
            f"{_safe_text(reference.get('description'))}"
        )
        if reference.get("planning_note"):
            lines.append(
                f"  Planning note: {_safe_text(reference.get('planning_note'))}"
            )

    lines.extend(["", "SOURCE INFORMATION"])
    sources = assessment.get("source_information", {})
    lines.append(
        _provenance_line(
            "Municipal boundary", sources.get("municipal_boundary")
        )
    )
    lines.append(
        _provenance_line("Barangay boundary", sources.get("barangay_boundary"))
    )
    lines.append(
        "Hazard source names, dates, retrieval states, URLs, attributions, and "
        "cache status are listed with each hazard input above."
    )
    fuzzy_source = sources.get("fuzzy_model", {})
    lines.append(
        "Fuzzy model: version="
        f"{_safe_text(fuzzy_source.get('version', result.get('model_version')))}; "
        f"checksum={_safe_text(fuzzy_source.get('checksum', result.get('model_checksum')))}; "
        f"status={_safe_text(fuzzy_source.get('status'))}"
    )

    lines.extend(["", "DATA-QUALITY AND AVAILABILITY NOTICES"])
    notices = assessment.get("data_quality_notices", [])
    if not notices:
        lines.append("No additional notice was recorded.")
    lines.extend(f"- {_safe_text(notice)}" for notice in notices)

    lines.extend(["", "PLANNING-ORIENTED RECOMMENDATIONS"])
    lines.extend(
        f"- {_safe_text(item)}" for item in assessment.get("recommendations", [])
    )
    lines.extend(["", "DISCLAIMER", disclaimer])
    return lines


def generate_pdf(
    lines: Iterable[str],
    title: str = "GeoSafe-FIS Assessment",
    assessment: Mapping[str, Any] | None = None,
) -> bytes:
    """Generate a branded, readable multi-page assessment report."""
    report_lines = list(lines)
    output = BytesIO()
    page_width, page_height = letter
    pdf = canvas.Canvas(
        output,
        pagesize=letter,
        pageCompression=0,
        pdfVersion=(1, 4),
    )
    pdf.setTitle(title)
    pdf.setAuthor("GeoSafe-FIS research project")
    pdf.setSubject("Preliminary multi-hazard screening report")

    navy = HexColor("#073B4C")
    teal = HexColor("#147D72")
    amber = HexColor("#D28A1E")
    ink = HexColor("#1C2D32")
    muted = HexColor("#60747A")
    border = HexColor("#D8E2DF")
    pale = HexColor("#F2F7F5")
    page_number = 0
    y = 0.0
    locator_drawn = False

    section_names = {
        "SELECTED LOCATION",
        "HAZARD INPUTS",
        "FUZZY RESULT",
        "APPLIED INDICATOR WEIGHTS",
        "MEMBERSHIP VALUES",
        "ACTIVATED FUZZY RULES",
        "HISTORICAL INCIDENT CONTEXT",
        "CLUP REFERENCE CONTEXT",
        "SOURCE INFORMATION",
        "DATA-QUALITY AND AVAILABILITY NOTICES",
        "PLANNING-ORIENTED RECOMMENDATIONS",
        "DISCLAIMER",
    }

    def draw_page_frame() -> None:
        nonlocal page_number, y
        page_number += 1
        pdf.setFillColor(navy)
        pdf.rect(0, page_height - 76, page_width, 76, fill=1, stroke=0)
        pdf.setStrokeColor(HexColor("#68C8B2"))
        pdf.setLineWidth(2)
        pdf.circle(49, page_height - 38, 17, fill=0, stroke=1)
        pdf.setFillColor(HexColor("#68C8B2"))
        pdf.circle(49, page_height - 38, 5, fill=1, stroke=0)
        pdf.setFillColor(HexColor("#FFFFFF"))
        pdf.setFont("Helvetica-Bold", 17 if page_number == 1 else 12)
        pdf.drawString(76, page_height - 34, "GeoSafe-FIS Assessment Report")
        pdf.setFont("Helvetica", 8.5)
        pdf.setFillColor(HexColor("#CBE4DE"))
        pdf.drawString(
            76,
            page_height - 50,
            "Preliminary multi-hazard screening - Basey, Samar",
        )
        pdf.setStrokeColor(border)
        pdf.setLineWidth(1)
        pdf.line(42, 35, page_width - 42, 35)
        pdf.setFillColor(muted)
        pdf.setFont("Helvetica", 7.5)
        pdf.drawString(42, 22, "Research prototype - verify against authoritative sources")
        pdf.drawRightString(page_width - 42, 22, f"Page {page_number}")
        y = page_height - 94

    def new_page() -> None:
        if page_number:
            pdf.showPage()
        draw_page_frame()

    def ensure_space(height: float) -> None:
        if y - height < 48:
            new_page()

    def wrap_for_width(
        value: str, font_name: str, font_size: float, width: float
    ) -> list[str]:
        words = value.split()
        if not words:
            return [""]
        rows: list[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if stringWidth(candidate, font_name, font_size) <= width:
                current = candidate
            else:
                rows.append(current)
                current = word
        rows.append(current)
        return rows

    def draw_locator_snapshot() -> None:
        nonlocal y, locator_drawn
        if locator_drawn or not assessment:
            return
        ensure_space(118)
        location = assessment.get("location", {})
        hazards = list(assessment.get("hazards", []))
        box_y = y - 103
        pdf.setFillColor(pale)
        pdf.setStrokeColor(border)
        pdf.roundRect(42, box_y, page_width - 84, 96, 8, fill=1, stroke=1)
        pdf.setFillColor(navy)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(54, box_y + 78, "LOCATION AND LAYER SNAPSHOT")
        grid_x, grid_y, grid_w, grid_h = 54, box_y + 13, 205, 56
        pdf.setStrokeColor(HexColor("#C7DAD5"))
        for offset in range(0, 206, 41):
            pdf.line(grid_x + offset, grid_y, grid_x + offset, grid_y + grid_h)
        for offset in range(0, 57, 14):
            pdf.line(grid_x, grid_y + offset, grid_x + grid_w, grid_y + offset)
        pdf.setFillColor(teal)
        pdf.circle(grid_x + 112, grid_y + 29, 6, fill=1, stroke=0)
        pdf.setFillColor(navy)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(
            276,
            box_y + 60,
            _safe_text((location.get("barangay") or {}).get("name")),
        )
        pdf.setFont("Helvetica", 7.5)
        pdf.setFillColor(muted)
        pdf.drawString(
            276,
            box_y + 48,
            f"{_safe_text(location.get('latitude'))}, {_safe_text(location.get('longitude'))}",
        )
        pdf.drawString(276, box_y + 35, "Assessment-state locator (schematic)")
        chip_x = 276
        for hazard in hazards[:3]:
            hazard_type = _safe_text(hazard.get("hazard_type")).replace("_", " ").title()
            status = _safe_text(hazard.get("availability_status"))
            label = f"{hazard_type[:14]}: {status[:11]}"
            chip_width = min(
                92, max(68, stringWidth(label, "Helvetica", 5.8) + 10)
            )
            pdf.setFillColor(
                HexColor("#E4F1ED")
                if status == "available"
                else HexColor("#FFF0D0")
            )
            pdf.roundRect(chip_x, box_y + 14, chip_width, 14, 5, fill=1, stroke=0)
            pdf.setFillColor(ink)
            pdf.setFont("Helvetica", 5.8)
            pdf.drawCentredString(chip_x + chip_width / 2, box_y + 18.5, label)
            chip_x += chip_width + 5
        y = box_y - 8
        locator_drawn = True

    new_page()
    for index, raw_line in enumerate(report_lines):
        line_text = _safe_text(raw_line)
        if index == 0 and line_text == "GeoSafe-FIS Assessment Report":
            continue
        if index == 1 and "screening prototype" in line_text:
            pdf.setFillColor(muted)
            pdf.setFont("Helvetica", 8)
            pdf.drawString(42, y, line_text)
            y -= 17
            continue
        if not line_text:
            if (
                index + 1 < len(report_lines)
                and _safe_text(report_lines[index + 1]) in section_names
            ):
                continue
            y -= 5
            continue
        if line_text in section_names:
            section_space = {
                "APPLIED INDICATOR WEIGHTS": 58,
                "FUZZY RESULT": 62,
                "DISCLAIMER": 72,
            }.get(line_text, 42)
            ensure_space(section_space)
            y -= 5
            pdf.setStrokeColor(amber)
            pdf.setLineWidth(2)
            pdf.line(42, y + 11, 47, y + 11)
            pdf.setFillColor(navy)
            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawString(53, y + 7, line_text)
            y -= 14
            continue

        indented = line_text.startswith("  ") or line_text.startswith("-")
        x = 55 if indented else 42
        font_name = "Helvetica"
        font_size = 8.2
        rows = wrap_for_width(
            line_text.strip(), font_name, font_size, page_width - x - 42
        )
        ensure_space(len(rows) * 10.5 + 2)
        pdf.setFillColor(ink)
        pdf.setFont(font_name, font_size)
        for row in rows:
            pdf.drawString(x, y, row)
            y -= 10.5
        y -= 1.5
        if line_text.startswith("Barangay:"):
            draw_locator_snapshot()

    pdf.save()
    return output.getvalue()
