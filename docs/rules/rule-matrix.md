# LABELGUARD Rule Matrix

**Regulation**: PS 26034 — Legal Metrology (Packaged Commodities) Rules, 2011  
**Active Rules**: 12  
**Last Updated**: 2026-09-10

---

## Rule Summary Table

| Rule Code | Title | Field Validated | Operator | Severity | Applicability Condition |
|---|---|---|---|---|---|
| `LG-MFR` | Manufacturer / Packer / Importer | `manufacturer` | `required_any` | Major | Always |
| `LG-COMMODITY` | Common or Generic Name | `product_name` | `required` | Major | Always |
| `LG-QTY` | Net Quantity | `net_quantity` | `required` | Major | Always |
| `LG-MRP` | Maximum Retail Price | `mrp` | `required` | Major | Always |
| `LG-DATE` | Manufacture / Packing / Import Date | `manufacturing_date` | `required_any` | Major | Always |
| `LG-CARE` | Consumer Care Details | `consumer_care` | `required` | Major | Always |
| `LG-BBE` | Best Before / Use By | `best_before` | `required_any` | Major | `date_sensitive_commodity = true` |
| `LG-BATCH` | Batch / Lot Number | `batch_number` | `required` | Major | Always |
| `LG-LEGIBILITY` | Legibility and Prominence | `declaration_legibility` | `minimum` | Major | Always |
| `LG-USP` | Unit Sale Price | `unit_sale_price` | `required` | Major | Quantity > 1g / 1ml / 1 piece |
| `LG-UNIT-SYMBOL` | Legal Unit Symbol | `unit_symbol` | `required` | Major | Always |
| `LG-COO` | Country of Origin | `country_of_origin` | `required` | Major | `imported = true` AND field exists |

---

## Rule Details

### LG-MFR — Manufacturer / Packer / Importer

**Requirement**: Applicable manufacturer, packer or importer name and address must be declared on the package.  
**Field**: `manufacturer`  
**Operator**: `required_any`  
**Condition**: Always applicable.  
**Validator**: Standard presence check — passes if field is extracted with confidence ≥ 35%.

---

### LG-COMMODITY — Common or Generic Name

**Requirement**: The common or generic name of the commodity must be declared.  
**Field**: `product_name`  
**Operator**: `required`  
**Condition**: Always applicable.  
**Validator**: Standard presence check.

---

### LG-QTY — Net Quantity

**Requirement**: Net quantity must be declared using an appropriate unit of weight, measure or number.  
**Field**: `net_quantity`  
**Operator**: `required`  
**Condition**: Always applicable.  
**Validator**: Standard presence check — structured value `{quantity, unit, raw_unit}` expected.

---

### LG-MRP — Maximum Retail Price

**Requirement**: MRP inclusive of applicable taxes must be declared in the prescribed manner.  
**Field**: `mrp`  
**Operator**: `required`  
**Condition**: Always applicable.  
**Validator**: Standard presence check — numeric value extracted via image-aware MRP stamp detector.

---

### LG-DATE — Manufacture / Packing / Import Date

**Requirement**: Applicable month and year of manufacture, packing or import must be provided.  
**Field**: `manufacturing_date`  
**Operator**: `required_any`  
**Expected**: `manufacturing_date, packing_date, import_date`  
**Condition**: Always applicable.  
**Validator**: Accepts any one of the three date variants.

---

### LG-CARE — Consumer Care Details

**Requirement**: Consumer care contact details (telephone, email or prescribed contact) must be declared.  
**Field**: `consumer_care`  
**Operator**: `required`  
**Condition**: Always applicable.  
**Validator**: Standard presence check.

---

### LG-BBE — Best Before / Use By

**Requirement**: Best-before or use-by date must be provided for commodities where applicable.  
**Field**: `best_before`  
**Operator**: `required_any`  
**Expected**: `best_before, expiry_date`  
**Condition**: `date_sensitive_commodity = true` (derived from commodity category + expiry date evidence).  
**Validator**: Rule is `not_applicable` when commodity is not date-sensitive.

---

### LG-BATCH — Batch / Lot Number

**Requirement**: A batch number, lot number or code number must be declared for traceability.  
**Field**: `batch_number`  
**Operator**: `required`  
**Condition**: Always applicable.  
**Validator**: Standard presence check. Batch extraction uses image-aware stamp/ROI detector with +100 score bonus over noisy OCR candidates, ensuring physical stamp evidence takes priority over ambiguous text tokens.

---

### LG-LEGIBILITY — Legibility and Prominence

**Requirement**: Mandatory declarations must be legible, prominent and presented in the prescribed manner.  
**Field**: `declaration_legibility`  
**Operator**: `minimum`  
**Expected**: `acceptable`  
**Condition**: Always applicable.  
**Validator**: `validate_legibility()` — scores required fields by presence and confidence; pass ≥ 70, review ≥ 40, fail below 40. No additional OCR pass is performed; uses already-merged evidence.

---

### LG-USP — Unit Sale Price

**Requirement**: Unit Sale Price (price per unit of weight/volume/number) must be declared on packages where net quantity > 1g / 1ml / 1 piece.  
**Field**: `unit_sale_price`  
**Operator**: `required`  
**Condition**: Net quantity > threshold (determined by `validate_unit_sale_price()`).  
**Validator**: `validate_unit_sale_price()` — returns `not_applicable` when quantity is ≤ threshold or quantity/unit is missing. Returns `pass` when structured `{price, unit}` value is extracted; `review` when low-confidence.

---

### LG-UNIT-SYMBOL — Legal Unit Symbol

**Requirement**: Unit symbols must strictly conform to LM(PC) Rules 2011 — Second Schedule and Legal Metrology Act 2009 (Sections 11 & 12). Non-standard symbols (`gm`, `gms`, `kgs`, `ltr`, `mls`) are prohibited.  
**Field**: `unit_symbol`  
**Operator**: `required`  
**Condition**: Always applicable when net quantity is declared.  
**Validator**: `validate_unit_symbol()` — checks the raw printed token against the legal symbol whitelist. The normalized quantity is preserved unchanged; only the **printed symbol** is evaluated.

**Legal symbol whitelist examples**:

| Quantity Type | Legal Symbols | Common Non-Standard (Rejected) |
|---|---|---|
| Mass | `g`, `kg`, `mg`, `t` | `gm`, `gms`, `kgs`, `Kgs` |
| Volume | `ml`, `mL`, `l`, `L` | `mls`, `ltr`, `ltrs`, `Ltr` |
| Length | `m`, `cm`, `mm`, `km` | — |
| Number/Pieces | `N`, `U`, `No`, `Pcs` | `nos`, `pcs` (lowercase inconsistency) |

---

### LG-COO — Country of Origin

**Requirement**: Country of origin must be declared for imported packages.  
**Field**: `country_of_origin`  
**Operator**: `required`  
**Condition**: `imported = true` AND `country_of_origin` field exists in declarations.  
**Validator**: Standard presence check. Derived `imported` field is computed from manufacturer address and country-of-origin evidence — rule is `not_applicable` for domestically produced goods.

---

## Bulk Scan Conflict Handling

When multiple images are submitted in a single inspection, the analysis pipeline detects cross-image declaration conflicts for key fields:

| Field | Conflict Trigger | Behaviour |
|---|---|---|
| `mrp` | Price difference > Rs. 0.50 across images | Field → `status: review`, `conflict: true` |
| `net_quantity` | Quantity difference > 0.5 or different units | Field → `status: review`, `conflict: true` |
| `manufacturing_date` | Different date strings across images | Field → `status: review`, `conflict: true` |
| `expiry_date` | Different date strings across images | Field → `status: review`, `conflict: true` |
| `country_of_origin` | Different country names across images | Field → `status: review`, `conflict: true` |

Conflicting declarations are preserved in `conflicting_candidates[]` with per-image provenance (`image_id`, `image_type`, `value`, `confidence`). Compliance evaluation then receives `review` status for conflicted fields.

---

## Verdict Mapping

| Rule Result | Inspection Impact |
|---|---|
| All rules → `pass` or `not_applicable` | `COMPLIANT` |
| Any rule → `review` | `REVIEW` |
| Any rule → `fail` | `NON_COMPLIANT` |

---

*Generated by LABELGUARD compliance engine. Do not edit manually — update via `legal_metrology_seed.py` and re-seed.*
