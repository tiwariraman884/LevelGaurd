"""
Legal Unit Symbol Validator for LG-UNIT-SYMBOL compliance rule.

Under Legal Metrology Act, 2009 (Sections 11 & 12) and Legal Metrology
(Packaged Commodities) Rules, 2011 (Rule 13 and Second Schedule):
- Every declaration of quantity must be expressed in terms of the standard
  units of weight, measure or number using standard legal unit symbols.
- Prescribed standard symbols:
    * Mass: 'g', 'kg', 'mg' (prohibits 'gm', 'gms', 'kgs', 'g.', 'gm.', 'gms.')
    * Volume: 'ml', 'mL', 'l', 'L', 'kl', 'kL' (prohibits 'mls', 'ltr', 'ltrs', 'lt', 'lts')
    * Length: 'm', 'cm', 'mm', 'km' (prohibits 'mtr', 'mtrs', 'cms')
    * Area: 'm2', 'm²', 'cm2', 'cm²', 'sq.m', 'sq.cm', 'sq m', 'sq cm'
    * Number/Count: 'N', 'U', 'number', 'piece', 'pieces', 'units', 'nos', 'pcs'
- Non-standard symbols, colloquial abbreviations, or improper pluralization
  (e.g., '17 gms', '5 kgs', '500 ltr', '200 mls') are statutory non-compliances.
"""

from __future__ import annotations

import ast
import json
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.models.declaration import Declaration


# ---------------------------------------------------------------------------
# Authoritative Unit Symbol Dictionaries (Rule 13 & Second Schedule)
# ---------------------------------------------------------------------------

# Standard / Allowed Legal Unit Symbols mapped to (normalized_unit, category)
LEGAL_UNIT_SYMBOLS: dict[str, tuple[str, str]] = {
    # Mass (SI / Legal Metrology standard symbols & words)
    "g": ("g", "mass"),
    "kg": ("kg", "mass"),
    "mg": ("mg", "mass"),
    "t": ("t", "mass"),
    "tonne": ("t", "mass"),
    "gram": ("g", "mass"),
    "grams": ("g", "mass"),
    "kilogram": ("kg", "mass"),
    "kilograms": ("kg", "mass"),
    "milligram": ("mg", "mass"),
    "milligrams": ("mg", "mass"),

    # Volume (SI / Legal Metrology standard symbols & words)
    "ml": ("ml", "volume"),
    "l": ("l", "volume"),
    "kl": ("kl", "volume"),
    "litre": ("l", "volume"),
    "litres": ("l", "volume"),
    "liter": ("l", "volume"),
    "liters": ("l", "volume"),
    "millilitre": ("ml", "volume"),
    "millilitres": ("ml", "volume"),
    "milliliter": ("ml", "volume"),
    "milliliters": ("ml", "volume"),

    # Length (SI / Legal Metrology standard symbols & words)
    "m": ("m", "length"),
    "cm": ("cm", "length"),
    "mm": ("mm", "length"),
    "km": ("km", "length"),
    "metre": ("m", "length"),
    "metres": ("m", "length"),
    "meter": ("m", "length"),
    "meters": ("m", "length"),
    "centimetre": ("cm", "length"),
    "centimetres": ("cm", "length"),

    # Area (SI / Legal Metrology standard symbols & words)
    "m2": ("m2", "area"),
    "m²": ("m2", "area"),
    "cm2": ("cm2", "area"),
    "cm²": ("cm2", "area"),
    "mm2": ("mm2", "area"),
    "mm²": ("mm2", "area"),
    "sq.m": ("m2", "area"),
    "sq.cm": ("cm2", "area"),
    "sq m": ("m2", "area"),
    "sq cm": ("cm2", "area"),

    # Number / Count
    "n": ("N", "count"),
    "u": ("U", "count"),
    "number": ("N", "count"),
    "numbers": ("N", "count"),
    "piece": ("N", "count"),
    "pieces": ("N", "count"),
    "unit": ("U", "count"),
    "units": ("U", "count"),
    "no": ("N", "count"),
    "no.": ("N", "count"),
    "nos": ("N", "count"),
    "nos.": ("N", "count"),
    "pc": ("N", "count"),
    "pcs": ("N", "count"),
    "pcs.": ("N", "count"),
}

# Explicitly Illegal / Non-Standard Unit Symbols under Rule 13
ILLEGAL_UNIT_SYMBOLS: dict[str, tuple[str, str, str]] = {
    # Mass violations
    "gm": ("g", "mass", "Non-standard abbreviation 'gm'; Rule 13 requires standard symbol 'g'"),
    "gm.": ("g", "mass", "Non-standard abbreviation with period 'gm.'; Rule 13 requires standard symbol 'g'"),
    "gms": ("g", "mass", "Prohibited pluralized symbol 'gms'; Rule 13 requires singular standard symbol 'g'"),
    "gms.": ("g", "mass", "Prohibited symbol 'gms.'; Rule 13 requires standard symbol 'g'"),
    "g.": ("g", "mass", "Prohibited period after symbol 'g.'; Rule 13 requires symbol 'g' without punctuation"),
    "kgs": ("kg", "mass", "Prohibited pluralized symbol 'kgs'; Rule 13 requires standard symbol 'kg'"),
    "kgs.": ("kg", "mass", "Prohibited symbol 'kgs.'; Rule 13 requires standard symbol 'kg'"),
    "kg.": ("kg", "mass", "Prohibited period after symbol 'kg.'; Rule 13 requires symbol 'kg'"),
    "kilo": ("kg", "mass", "Informal term 'kilo'; Rule 13 requires standard symbol 'kg'"),
    "kilos": ("kg", "mass", "Informal term 'kilos'; Rule 13 requires standard symbol 'kg'"),
    "mgs": ("mg", "mass", "Prohibited pluralized symbol 'mgs'; Rule 13 requires standard symbol 'mg'"),
    "mgs.": ("mg", "mass", "Prohibited symbol 'mgs.'; Rule 13 requires standard symbol 'mg'"),
    "mg.": ("mg", "mass", "Prohibited period after symbol 'mg.'; Rule 13 requires standard symbol 'mg'"),

    # Volume violations
    "mls": ("ml", "volume", "Prohibited pluralized symbol 'mls'; Rule 13 requires standard symbol 'ml' or 'mL'"),
    "mls.": ("ml", "volume", "Prohibited symbol 'mls.'; Rule 13 requires standard symbol 'ml' or 'mL'"),
    "ml.": ("ml", "volume", "Prohibited period after symbol 'ml.'; Rule 13 requires standard symbol 'ml' or 'mL'"),
    "ltr": ("l", "volume", "Non-standard abbreviation 'ltr'; Rule 13 requires standard symbol 'l' or 'L'"),
    "ltr.": ("l", "volume", "Non-standard abbreviation 'ltr.'; Rule 13 requires standard symbol 'l' or 'L'"),
    "ltrs": ("l", "volume", "Prohibited pluralized symbol 'ltrs'; Rule 13 requires standard symbol 'l' or 'L'"),
    "ltrs.": ("l", "volume", "Prohibited symbol 'ltrs.'; Rule 13 requires standard symbol 'l' or 'L'"),
    "lt": ("l", "volume", "Non-standard abbreviation 'lt'; Rule 13 requires standard symbol 'l' or 'L'"),
    "lt.": ("l", "volume", "Non-standard abbreviation 'lt.'; Rule 13 requires standard symbol 'l' or 'L'"),
    "lts": ("l", "volume", "Prohibited pluralized symbol 'lts'; Rule 13 requires standard symbol 'l' or 'L'"),
    "lit": ("l", "volume", "Non-standard abbreviation 'lit'; Rule 13 requires standard symbol 'l' or 'L'"),
    "lit.": ("l", "volume", "Non-standard abbreviation 'lit.'; Rule 13 requires standard symbol 'l' or 'L'"),
    "l.": ("l", "volume", "Prohibited period after symbol 'l.'; Rule 13 requires standard symbol 'l' or 'L'"),

    # Length violations
    "mtr": ("m", "length", "Non-standard abbreviation 'mtr'; Rule 13 requires standard symbol 'm'"),
    "mtr.": ("m", "length", "Non-standard abbreviation 'mtr.'; Rule 13 requires standard symbol 'm'"),
    "mtrs": ("m", "length", "Prohibited pluralized symbol 'mtrs'; Rule 13 requires standard symbol 'm'"),
    "mtrs.": ("m", "length", "Prohibited symbol 'mtrs.'; Rule 13 requires standard symbol 'm'"),
    "cms": ("cm", "length", "Prohibited pluralized symbol 'cms'; Rule 13 requires standard symbol 'cm'"),
    "cms.": ("cm", "length", "Prohibited symbol 'cms.'; Rule 13 requires standard symbol 'cm'"),
    "cm.": ("cm", "length", "Prohibited period after symbol 'cm.'; Rule 13 requires standard symbol 'cm'"),
    "m.": ("m", "length", "Prohibited period after symbol 'm.'; Rule 13 requires standard symbol 'm'"),
    "mm.": ("mm", "length", "Prohibited period after symbol 'mm.'; Rule 13 requires standard symbol 'mm'"),

    # Area violations
    "sqm": ("m2", "area", "Non-standard abbreviation 'sqm'; Rule 13 requires standard symbol 'm²' or 'sq. m'"),
    "sqmtr": ("m2", "area", "Non-standard abbreviation 'sqmtr'; Rule 13 requires standard symbol 'm²' or 'sq. m'"),
    "sqcms": ("cm2", "area", "Prohibited pluralized symbol 'sqcms'; Rule 13 requires standard symbol 'cm²' or 'sq. cm'"),
}


def _parse_quantity_details(
    decl: Declaration | None,
) -> tuple[float | None, str | None, str | None, float | None]:
    """
    Extract (quantity_num, normalized_unit, printed_unit, confidence) from Declaration.
    Preserves distinct raw/printed unit token vs normalized unit.
    """
    if decl is None or not decl.is_present:
        return None, None, None, None

    conf = float(decl.confidence or 0.0) if decl.confidence is not None else None
    val = decl.normalized_value
    extracted = decl.extracted_value

    parsed_dict: dict[str, Any] | None = None

    if isinstance(val, dict):
        parsed_dict = val
    elif isinstance(val, str) and val.strip().startswith("{") and val.strip().endswith("}"):
        try:
            parsed_dict = json.loads(val)
        except Exception:
            try:
                parsed_dict = ast.literal_eval(val)
            except Exception:
                pass

    if isinstance(parsed_dict, dict):
        q_raw = parsed_dict.get("quantity") or parsed_dict.get("value")
        try:
            q_num = float(q_raw) if q_raw is not None else None
        except (ValueError, TypeError):
            q_num = None

        norm_u = str(parsed_dict.get("unit") or "").strip() or None
        raw_u = str(
            parsed_dict.get("raw_unit")
            or parsed_dict.get("printed_unit")
            or norm_u
            or ""
        ).strip() or None

        # Check if extracted_value contains more specific printed unit token
        if extracted and not raw_u:
            m = re.search(r"(\d+(?:[.,]\d+)?)\s*([a-zA-Z².]+)", str(extracted))
            if m:
                raw_u = m.group(2).strip()

        return q_num, norm_u, raw_u, conf

    # Fallback to parsing string / extracted_value
    text_to_parse = str(val or extracted or "")
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*([a-zA-Z².]+)", text_to_parse)
    if m:
        try:
            q_num = float(m.group(1).replace(",", "."))
        except (ValueError, TypeError):
            q_num = None
        raw_u = m.group(2).strip()
        norm_u = raw_u.lower()
        return q_num, norm_u, raw_u, conf

    return None, None, None, conf


def validate_unit_symbol(
    declarations: dict[str, "Declaration"],
) -> dict[str, Any]:
    """
    Validate Legal Unit Symbol for Net Quantity (LG-UNIT-SYMBOL).

    Parameters
    ----------
    declarations : dict[str, Declaration]
        Inspection declaration map.

    Returns
    -------
    dict with keys:
        status     – "pass" | "fail" | "review" | "not_applicable"
        field_name – "net_quantity"
        value      – str | None
        confidence – float | None
        evidence   – str
        details    – dict
    """
    decl = declarations.get("net_quantity")
    if decl is None or not decl.is_present:
        return {
            "status": "review",
            "field_name": "net_quantity",
            "value": None,
            "confidence": None,
            "evidence": "Net quantity declaration was not identified to validate unit symbol",
            "details": {
                "unit_validity": "REVIEW",
                "reason": "Missing net quantity declaration",
            },
        }

    q_num, norm_u, raw_u, conf = _parse_quantity_details(decl)

    # Determine the printed unit token
    printed_unit = raw_u or norm_u
    if not printed_unit:
        return {
            "status": "review",
            "field_name": "net_quantity",
            "value": None,
            "confidence": conf,
            "evidence": "Net quantity unit symbol is missing or unreadable",
            "details": {
                "unit_validity": "REVIEW",
                "reason": "Unreadable unit symbol",
            },
        }

    token_clean = printed_unit.lower().strip()

    # 1. Check if token is an explicitly prohibited/illegal non-standard symbol
    if token_clean in ILLEGAL_UNIT_SYMBOLS:
        normalized_target, category, reason = ILLEGAL_UNIT_SYMBOLS[token_clean]
        return {
            "status": "fail",
            "field_name": "net_quantity",
            "value": printed_unit,
            "confidence": conf,
            "evidence": (
                f"Invalid unit symbol '{printed_unit}' for {category}: {reason}. "
                f"Statutory requirement under Rule 13 / Second Schedule requires standard symbol '{normalized_target}'."
            ),
            "details": {
                "printed_unit": printed_unit,
                "normalized_unit": normalized_target,
                "unit_validity": "FAIL",
                "category": category,
                "reason": reason,
            },
        }

    # 2. Check if token is an allowed standard legal unit symbol
    if token_clean in LEGAL_UNIT_SYMBOLS:
        normalized_target, category = LEGAL_UNIT_SYMBOLS[token_clean]
        return {
            "status": "pass",
            "field_name": "net_quantity",
            "value": printed_unit,
            "confidence": conf,
            "evidence": (
                f"Valid standard legal unit symbol '{printed_unit}' for {category} "
                f"under Rule 13 & Second Schedule of LM(PC) Rules, 2011."
            ),
            "details": {
                "printed_unit": printed_unit,
                "normalized_unit": normalized_target,
                "unit_validity": "PASS",
                "category": category,
            },
        }

    # 3. If token is unknown / ambiguous
    return {
        "status": "review",
        "field_name": "net_quantity",
        "value": printed_unit,
        "confidence": conf,
        "evidence": (
            f"Unit symbol '{printed_unit}' is ambiguous or non-standard; "
            f"manual verification required under Rule 13."
        ),
        "details": {
            "printed_unit": printed_unit,
            "normalized_unit": token_clean,
            "unit_validity": "REVIEW",
            "reason": "Unrecognized unit symbol",
        },
    }
