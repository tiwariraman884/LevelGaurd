"""
Unit Sale Price (USP) validator for LG-USP compliance rule.

Under Legal Metrology (Packaged Commodities) Rules, 2011 Rule 6(1)(e)
(as amended by Legal Metrology (Packaged Commodities) Amendment Rules, 2021/2022):
- Declaration of Unit Sale Price (USP) is mandatory on pre-packaged commodities
  where net quantity is greater than 1 g, 1 ml, or 1 number/piece.
- USP must indicate price per standard unit (e.g. per g, per kg, per ml, per l, per piece).
- Where declared, the USP should be mathematically consistent with declared MRP and
  Net Quantity within reasonable rounding/OCR tolerance.
- For small packages where Net Quantity <= 1 g / 1 ml / 1 number, USP is NOT_APPLICABLE.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.models.declaration import Declaration


LOW_USP_CONFIDENCE_THRESHOLD: float = 30.0


def _parse_numeric(val: Any) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    try:
        cleaned = re.sub(r"[^\d.]", "", str(val))
        return float(cleaned) if cleaned else None
    except (ValueError, TypeError):
        return None


def _parse_quantity(decl: Declaration | None) -> tuple[float | None, str | None]:
    if decl is None or not decl.is_present:
        return None, None

    val = decl.normalized_value or decl.extracted_value
    if isinstance(val, dict):
        q = _parse_numeric(val.get("quantity") or val.get("value"))
        u = str(val.get("unit") or "").lower().strip() or None
        return q, u

    if isinstance(val, str) and val.startswith("{") and val.endswith("}"):
        try:
            d = json.loads(val)
            q = _parse_numeric(d.get("quantity") or d.get("value"))
            u = str(d.get("unit") or "").lower().strip() or None
            return q, u
        except Exception:
            pass

    m = re.search(r"(\d+(?:\.\d+)?)\s*([a-zA-Z]+)", str(val or ""))
    if m:
        return _parse_numeric(m.group(1)), m.group(2).lower()

    return _parse_numeric(val), None


def _parse_usp(decl: Declaration | None) -> tuple[float | None, str | None, float | None]:
    if decl is None or not decl.is_present:
        return None, None, None

    val = decl.normalized_value or decl.extracted_value
    conf = float(decl.confidence or 0.0) if decl.confidence is not None else None

    if isinstance(val, dict):
        p = _parse_numeric(val.get("price") or val.get("value"))
        u = str(val.get("unit") or "").lower().strip() or None
        return p, u, conf

    if isinstance(val, str) and val.startswith("{") and val.endswith("}"):
        try:
            d = json.loads(val)
            p = _parse_numeric(d.get("price") or d.get("value"))
            u = str(d.get("unit") or "").lower().strip() or None
            return p, u, conf
        except Exception:
            pass

    # Regex parse string like "Rs.0.299/g" or "0.29/g" or "Rs.0.299"
    m = re.search(r"(\d+(?:\.\d+)?)(?:\s*/\s*([a-zA-Z]+))?", str(val or ""))
    if m:
        p = _parse_numeric(m.group(1))
        u = m.group(2).lower() if m.group(2) else None
        return p, u, conf

    return _parse_numeric(val), None, conf


def validate_unit_sale_price(
    declarations: dict[str, "Declaration"],
) -> dict[str, Any]:
    """
    Validate Unit Sale Price declaration (LG-USP).

    Returns
    -------
    dict with keys:
        status     – "pass" | "review" | "fail" | "not_applicable"
        field_name – "unit_sale_price"
        value      – Any
        confidence – float | None
        evidence   – str
        details    – dict
    """
    qty_val, qty_unit = _parse_quantity(declarations.get("net_quantity"))
    mrp_decl = declarations.get("mrp")
    mrp_val = _parse_numeric(mrp_decl.normalized_value or mrp_decl.extracted_value) if mrp_decl else None

    usp_decl = declarations.get("unit_sale_price")
    usp_price, usp_unit, usp_conf = _parse_usp(usp_decl)

    # 1. Applicability Check
    # If package quantity is <= 1 g / 1 ml / 1 piece, USP is not mandatory
    if qty_val is not None and qty_val <= 1.0:
        return {
            "status": "not_applicable",
            "field_name": "unit_sale_price",
            "value": None,
            "confidence": None,
            "evidence": f"Net quantity ({qty_val}{qty_unit or ''}) is <= 1 unit; Unit Sale Price is not mandatory under Rule 6(1)(e)",
            "details": {
                "applicable": False,
                "net_quantity": qty_val,
                "unit": qty_unit,
            },
        }

    # If quantity is missing or indeterminate, and USP is also missing
    if qty_val is None and (usp_decl is None or not usp_decl.is_present):
        return {
            "status": "review",
            "field_name": "unit_sale_price",
            "value": None,
            "confidence": None,
            "evidence": "Applicability of Unit Sale Price could not be determined without net quantity declaration",
            "details": {"applicable": None},
        }

    # 2. Presence Check
    if usp_decl is None or not usp_decl.is_present or usp_price is None:
        return {
            "status": "fail",
            "field_name": "unit_sale_price",
            "value": None,
            "confidence": None,
            "evidence": "Unit Sale Price (USP) declaration was not identified on the package as required under Rule 6(1)(e)",
            "details": {
                "applicable": True,
                "net_quantity": qty_val,
                "quantity_unit": qty_unit,
                "mrp": mrp_val,
            },
        }

    # 3. Value Validation
    if usp_price <= 0 or usp_price > 100000:
        return {
            "status": "fail",
            "field_name": "unit_sale_price",
            "value": usp_price,
            "confidence": usp_conf,
            "evidence": f"Declared Unit Sale Price value ({usp_price}) is non-positive or out of range",
            "details": {
                "declared_usp": usp_price,
                "declared_unit": usp_unit,
            },
        }

    # 4. Cross-Field Mathematical Consistency Check (when MRP & Qty are available)
    math_consistent = None
    expected_usp = None
    variance_pct = None

    if mrp_val is not None and qty_val is not None and qty_val > 0:
        expected_usp = mrp_val / qty_val
        variance_pct = abs(usp_price - expected_usp) / expected_usp
        # Allow up to 20% variance to accommodate standard rounding and OCR digit noise
        math_consistent = variance_pct <= 0.20

    # 5. Verdict Derivation
    effective_unit = usp_unit or qty_unit or "unit"
    conf = usp_conf or 0.0

    if math_consistent is True:
        # Cross-field mathematical alignment confirms the declaration
        return {
            "status": "pass",
            "field_name": "unit_sale_price",
            "value": f"Rs. {usp_price:.3f}/{effective_unit}",
            "confidence": max(conf, 70.0),
            "evidence": (
                f"Valid Unit Sale Price identified: Rs. {usp_price:.3f}/{effective_unit} "
                f"(MRP=Rs. {mrp_val}, Qty={qty_val}{qty_unit or ''}, expected=Rs. {expected_usp:.3f}/{effective_unit})"
            ),
            "details": {
                "applicable": True,
                "declared_usp": usp_price,
                "declared_unit": effective_unit,
                "mrp": mrp_val,
                "net_quantity": qty_val,
                "expected_usp": round(expected_usp, 4) if expected_usp else None,
                "variance_pct": round(variance_pct * 100, 2) if variance_pct is not None else None,
                "confidence": conf,
            },
        }

    if conf >= LOW_USP_CONFIDENCE_THRESHOLD:
        return {
            "status": "pass",
            "field_name": "unit_sale_price",
            "value": f"Rs. {usp_price:.3f}/{effective_unit}",
            "confidence": conf,
            "evidence": f"Unit Sale Price declaration identified: Rs. {usp_price:.3f}/{effective_unit} (conf={conf:.1f}%)",
            "details": {
                "applicable": True,
                "declared_usp": usp_price,
                "declared_unit": effective_unit,
                "confidence": conf,
            },
        }

    return {
        "status": "review",
        "field_name": "unit_sale_price",
        "value": f"Rs. {usp_price:.3f}/{effective_unit}",
        "confidence": conf,
        "evidence": f"Low-confidence Unit Sale Price declaration identified: Rs. {usp_price:.3f}/{effective_unit} (conf={conf:.1f}%)",
        "details": {
            "applicable": True,
            "declared_usp": usp_price,
            "declared_unit": effective_unit,
            "confidence": conf,
        },
    }
