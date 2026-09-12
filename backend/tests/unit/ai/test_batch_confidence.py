"""
tests/unit/ai/test_batch_confidence.py
Unit tests for _calibrate_batch_confidence()  (tests A-I + separation checks
+ production-path regression tests).

The calibration must satisfy the LABELGUARD safety property: a random
alphanumeric OCR token with weak/no semantic evidence must NOT reach the
compliance threshold (>= 35) merely because it has letters, digits and an
acceptable length.  Only genuine evidence (source trustworthiness, explicit
spatial flags, justified normalization, independent agreement) may lift a
low-raw-confidence reading above the threshold.

Run:   pytest tests/unit/ai/test_batch_confidence.py -v
"""

import pytest
from app.ai.extraction.declaration_extractor import _calibrate_batch_confidence


def make(value, raw_conf, source="direct_stamp_ocr", psm=11,
         norm_ev=None, score_bonus=37.0, spatial=None):
    ne = norm_ev if norm_ev is not None else []
    return {
        "type": "batch", "value": value, "raw_value": value,
        "confidence": raw_conf, "score": raw_conf + score_bonus,
        "source": source, "psm": psm, "normalization_evidence": ne,
        "bbox": {"x": 255, "y": 1208, "width": 150, "height": 23},
        "spatial_evidence": spatial or {},
    }


# A -------------------------------------------------------------------
class TestA_HighConfidenceValid:
    def test_high_conf_all_evidence(self):
        b = make("ABC12345", 85.0, norm_ev=["ocr-confusion:first-char-O-to-D"])
        cal, _ = _calibrate_batch_confidence(b, [b])
        assert cal >= 70.0

    def test_bounded_at_99(self):
        b = make("ABC12345", 99.0, norm_ev=["ocr-confusion:first-char-O-to-D"], score_bonus=50.0)
        cal, _ = _calibrate_batch_confidence(b, [b, b, b])
        assert cal <= 99.0


# B -------------------------------------------------------------------
class TestB_LowOCRStrongEvidence:
    def test_D63240194_exceeds_pass_threshold(self):
        b = make("D63240194", 9.0, norm_ev=["ocr-confusion:first-char-O-to-D"], score_bonus=37.0)
        cal, reasons = _calibrate_batch_confidence(b, [b])
        assert cal >= 35.0, f"Expected >= 35 (PASS threshold), got {cal}. {reasons}"

    def test_calibrated_materially_above_raw_ocr(self):
        b = make("D63240194", 9.0, norm_ev=["ocr-confusion:first-char-O-to-D"], score_bonus=37.0)
        cal, _ = _calibrate_batch_confidence(b, [b])
        assert cal > 9.0 + 20


# C -------------------------------------------------------------------
class TestC_NoSpatialEvidence:
    def test_no_evidence_below_compliance_threshold(self):
        b = make("XY9ZAB", 15.0, source="direct_word_ocr", psm=6, norm_ev=[], score_bonus=0.0)
        cal, _ = _calibrate_batch_confidence(b, [b])
        assert cal < 35.0, f"random weak token must stay REVIEW, got {cal}"


# D -------------------------------------------------------------------
class TestD_QuantityLike:
    def test_quantity_token_below_compliance_threshold(self):
        b = make("17G", 50.0, source="direct_word_ocr", psm=6, norm_ev=[], score_bonus=0.0)
        cal, _ = _calibrate_batch_confidence(b, [b])
        assert cal < 35.0, f"quantity-like token must stay REVIEW, got {cal}"


# E -------------------------------------------------------------------
class TestE_DateLike:
    def test_date_like_below_compliance_threshold(self):
        b = make("30JUN26", 40.0, source="direct_word_ocr", psm=6, norm_ev=[], score_bonus=5.0)
        cal, _ = _calibrate_batch_confidence(b, [b])
        assert cal < 35.0, f"date-like token must stay REVIEW, got {cal}"


# F -------------------------------------------------------------------
class TestF_PriceLike:
    def test_price_like_below_compliance_threshold(self):
        b = make("RS099", 20.0, source="direct_word_ocr", psm=6, norm_ev=[], score_bonus=0.0)
        cal, _ = _calibrate_batch_confidence(b, [b])
        assert cal < 35.0, f"price-like token must stay REVIEW, got {cal}"


# G -------------------------------------------------------------------
class TestG_OtoDNormalization:
    def test_reason_present(self):
        b = make("D63240194", 9.0, norm_ev=["ocr-confusion:first-char-O-to-D"], score_bonus=37.0)
        _, reasons = _calibrate_batch_confidence(b, [b])
        assert any("O-to-D" in r or "first-char" in r for r in reasons)

    def test_increases_confidence_vs_no_normalization(self):
        b_norm = make("D63240194", 9.0, norm_ev=["ocr-confusion:first-char-O-to-D"], score_bonus=37.0)
        b_none = make("D63240194", 9.0, norm_ev=[], score_bonus=37.0)
        cal_n, _ = _calibrate_batch_confidence(b_norm, [b_norm])
        cal_0, _ = _calibrate_batch_confidence(b_none, [b_none])
        assert cal_n > cal_0


# H -------------------------------------------------------------------
class TestH_MultiRunAgreement:
    def test_agreement_bonus_applied(self):
        b1 = make("D63240194", 9.0, norm_ev=["ocr-confusion:first-char-O-to-D"], score_bonus=37.0)
        b2 = make("D63240194", 12.0, norm_ev=["ocr-confusion:first-char-O-to-D"], psm=6, score_bonus=27.0)
        cal_s, _ = _calibrate_batch_confidence(b1, [b1])
        cal_a, reasons = _calibrate_batch_confidence(b1, [b1, b2])
        assert cal_a > cal_s
        assert any("agreement" in r for r in reasons)


# I -------------------------------------------------------------------
class TestI_GenuineUncertain:
    def test_uncertain_stays_below_35(self):
        b = make("AB12", 10.0, source="direct_word_ocr", psm=6, norm_ev=[], score_bonus=8.0)
        cal, _ = _calibrate_batch_confidence(b, [b])
        assert cal < 35.0


# SEP -----------------------------------------------------------------
class TestConfidenceSeparation:
    def test_raw_confidence_unchanged(self):
        b = make("D63240194", 9.0, norm_ev=["ocr-confusion:first-char-O-to-D"], score_bonus=37.0)
        _calibrate_batch_confidence(b, [b])
        assert b["confidence"] == 9.0

    def test_calibrated_ne_raw(self):
        b = make("D63240194", 9.0, norm_ev=["ocr-confusion:first-char-O-to-D"], score_bonus=37.0)
        cal, _ = _calibrate_batch_confidence(b, [b])
        assert cal != 9.0

    def test_calibrated_ne_score(self):
        b = make("D63240194", 9.0, norm_ev=["ocr-confusion:first-char-O-to-D"], score_bonus=37.0)
        cal, _ = _calibrate_batch_confidence(b, [b])
        assert cal != b["score"]

    def test_calibration_ignores_candidate_score(self):
        # The ranking/selection score must NEVER influence calibrated
        # confidence.  An absurd score must produce the same result.
        low = make("D63240194", 9.0, norm_ev=["ocr-confusion:first-char-O-to-D"], score_bonus=0.0)
        high = make("D63240194", 9.0, norm_ev=["ocr-confusion:first-char-O-to-D"], score_bonus=999.0)
        cal_low, _ = _calibrate_batch_confidence(low, [low])
        cal_high, _ = _calibrate_batch_confidence(high, [high])
        assert cal_low == cal_high


# REG -----------------------------------------------------------------
class TestProductionRegression:
    """Regression tests for the real benchmark + both candidate paths."""

    def test_benchmark_real_direct_word_path_passes(self):
        # Real inspection: raw OCR "D63'240194" (conf 9) normalized to
        # D63240194 via justified punctuation-strip, in the batch band.
        b = make(
            "D63240194", 9.0,
            source="direct_word_ocr", psm=6,
            norm_ev=["normalization:punctuation-stripped"],
            score_bonus=40.0,
            spatial={"batch_band": True, "near_quantity_line": False,
                     "dedicated_stamp_roi": False},
        )
        cal, reasons = _calibrate_batch_confidence(b, [b])
        assert cal >= 35.0, f"benchmark must PASS LG-BATCH, got {cal}. {reasons}"
        assert any("punctuation" in r for r in reasons)

    def test_direct_ocr_path_with_spatial_evidence(self):
        # direct_word_ocr + explicit near-quantity spatial flag.
        b = make(
            "AB1234", 12.0,
            source="direct_word_ocr", psm=6,
            norm_ev=[], score_bonus=38.0,
            spatial={"batch_band": True, "near_quantity_line": True,
                     "dedicated_stamp_roi": False},
        )
        cal, _ = _calibrate_batch_confidence(b, [b])
        assert cal >= 35.0

    def test_stamp_ocr_fallback_path_passes(self):
        # dedicated stamp ROI is the strongest source; low raw conf still
        # passes on genuine stamp evidence.
        b = make(
            "L63240", 5.0,
            source="direct_stamp_ocr", psm=11,
            norm_ev=[], score_bonus=35.0,
            spatial={"batch_band": True, "near_quantity_line": False,
                     "dedicated_stamp_roi": True},
        )
        cal, _ = _calibrate_batch_confidence(b, [b])
        assert cal >= 35.0

    def test_low_raw_conf_strong_evidence_passes(self):
        b = make(
            "D63240194", 4.0,
            source="direct_stamp_ocr", psm=11,
            norm_ev=["ocr-confusion:first-char-O-to-D"],
            score_bonus=37.0,
            spatial={"batch_band": True, "near_quantity_line": False,
                     "dedicated_stamp_roi": True},
        )
        cal, _ = _calibrate_batch_confidence(b, [b])
        assert cal >= 35.0

    def test_unjustified_normalization_penalized(self):
        b = make(
            "D63240194", 9.0,
            source="direct_word_ocr", psm=6,
            norm_ev=["mystery-substitution"],
            score_bonus=37.0,
            spatial={"batch_band": True, "near_quantity_line": False,
                     "dedicated_stamp_roi": False},
        )
        cal, _ = _calibrate_batch_confidence(b, [b])
        assert cal < 35.0, f"unjustified normalization must not help, got {cal}"

    def test_agreement_bonus_pushes_weak_raw_over_threshold(self):
        # Two independent readings of the same value = genuine agreement.
        b1 = make(
            "L24019", 8.0, source="direct_word_ocr", psm=6,
            norm_ev=["normalization:punctuation-stripped"], score_bonus=35.0,
            spatial={"batch_band": True, "near_quantity_line": True,
                     "dedicated_stamp_roi": False},
        )
        b2 = make(
            "L24019", 10.0, source="direct_word_ocr", psm=11,
            norm_ev=["normalization:punctuation-stripped"], score_bonus=30.0,
            spatial={"batch_band": True, "near_quantity_line": True,
                     "dedicated_stamp_roi": False},
        )
        cal, reasons = _calibrate_batch_confidence(b1, [b1, b2])
        assert any("agreement" in r for r in reasons)
        assert cal >= 35.0
