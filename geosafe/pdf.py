"""Dependency-free PDF report generation for saved assessments."""

from __future__ import annotations

import json
import textwrap
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any


def _safe_text(value: Any) -> str:
    if value is None:
        return "Unavailable"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value).replace("\r", " ").replace("\n", " ")


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
        f"Generated: {_safe_text(assessment.get('created_at'))}",
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
                "Assessment incomplete — no score or vulnerability category was assigned.",
                f"Missing required inputs: {', '.join(result.get('missing_inputs', [])) or 'Unavailable'}",
                "Missing information was not interpreted as low vulnerability.",
            ]
        )

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
            f"{_safe_text(incident.get('incident_date'))} — "
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
    for source in sources.get("hazard_datasets", []):
        lines.append(
            _provenance_line(
                _safe_text(source.get("dataset_name", "Hazard dataset")), source
            )
        )
    for source in sources.get("historical_incident_sources", []):
        lines.append(
            _provenance_line(
                f"Historical incident {source.get('incident_id')}", source
            )
        )
    for source in sources.get("clup_sources", []):
        lines.append(
            _provenance_line(
                f"CLUP reference {source.get('reference_id')}", source
            )
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
    lines.extend(
        [
            "",
            "DISCLAIMER",
            disclaimer,
            "",
            "Machine-readable assessment snapshot:",
            json.dumps(
                {
                    "assessment_id": assessment.get("id"),
                    "status": assessment.get("status"),
                    "score": result.get("score"),
                    "category": result.get("category"),
                    "model_version": result.get("model_version"),
                },
                separators=(",", ":"),
            ),
        ]
    )
    return lines


def _wrapped_lines(lines: Iterable[str], width: int = 94) -> list[str]:
    wrapped: list[str] = []
    for line in lines:
        if not line:
            wrapped.append("")
            continue
        wrapped.extend(
            textwrap.wrap(
                line,
                width=width,
                replace_whitespace=True,
                drop_whitespace=True,
                break_long_words=False,
                break_on_hyphens=False,
            )
            or [""]
        )
    return wrapped


def _pdf_escape(line: str) -> bytes:
    sanitized = (
        line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    )
    return sanitized.encode("cp1252", errors="replace")


def generate_pdf(lines: Iterable[str], title: str = "GeoSafe-FIS Assessment") -> bytes:
    """Generate a standards-compatible, text-only, multi-page PDF."""
    report_lines = _wrapped_lines(lines)
    lines_per_page = 54
    pages = [
        report_lines[index : index + lines_per_page]
        for index in range(0, len(report_lines), lines_per_page)
    ] or [["No report content is available."]]

    # Object numbers: 1 catalog, 2 pages, 3 font, then page/content pairs.
    objects: dict[int, bytes] = {}
    page_numbers: list[int] = []
    next_number = 4
    for page_index, page_lines in enumerate(pages, start=1):
        page_number = next_number
        content_number = next_number + 1
        next_number += 2
        page_numbers.append(page_number)
        commands = [
            b"BT",
            b"/F1 10 Tf",
            b"13 TL",
            b"50 760 Td",
        ]
        for line_index, line in enumerate(page_lines):
            if line_index:
                commands.append(b"T*")
            commands.append(b"(" + _pdf_escape(line) + b") Tj")
        commands.extend(
            [
                b"ET",
                b"BT /F1 8 Tf 500 24 Td "
                + _pdf_escape(f"Page {page_index} of {len(pages)}")
                + b" Tj ET",
            ]
        )
        stream = b"\n".join(commands)
        objects[page_number] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> "
            f"/Contents {content_number} 0 R >>"
        ).encode("ascii")
        objects[content_number] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"\nendstream"
        )

    kids = " ".join(f"{number} 0 R" for number in page_numbers)
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[2] = (
        f"<< /Type /Pages /Count {len(page_numbers)} /Kids [{kids}] >>"
    ).encode("ascii")
    objects[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    metadata_number = next_number
    created = datetime.now(timezone.utc).strftime("D:%Y%m%d%H%M%SZ")
    safe_title = _pdf_escape(title)
    objects[metadata_number] = (
        b"<< /Title (" + safe_title + b") /Producer (GeoSafe-FIS) "
        b"/CreationDate (" + created.encode("ascii") + b") >>"
    )

    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: dict[int, int] = {}
    for number in sorted(objects):
        offsets[number] = len(pdf)
        pdf.extend(f"{number} 0 obj\n".encode("ascii"))
        pdf.extend(objects[number])
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    max_number = max(objects)
    pdf.extend(f"xref\n0 {max_number + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for number in range(1, max_number + 1):
        if number in offsets:
            pdf.extend(f"{offsets[number]:010d} 00000 n \n".encode("ascii"))
        else:
            pdf.extend(b"0000000000 00000 f \n")
    pdf.extend(
        (
            f"trailer\n<< /Size {max_number + 1} /Root 1 0 R "
            f"/Info {metadata_number} 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(pdf)
