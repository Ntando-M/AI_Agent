"""
Tests for the AnalysisResponse contract.

The confidence field is the one LLMs get wrong most often: they
return a percentage (100) when the schema says 0.0-1.0. The
validator clamps rather than rejecting, so a confident answer
does not fail the whole response.
"""

import pytest

from models.response_models import AnalysisResponse


def _payload(**overrides):
    payload = {
        "answer": "Laptop generated the most revenue.",
        "analysis_type": "dataset",
        "confidence": 0.9,
    }
    payload.update(overrides)
    return payload


class TestConfidenceClamping:
    def test_percentage_is_clamped_to_one(self):
        response = AnalysisResponse.model_validate(
            _payload(confidence=100)
        )

        assert response.confidence == 1.0

    def test_fraction_passes_through(self):
        response = AnalysisResponse.model_validate(
            _payload(confidence=0.75)
        )

        assert response.confidence == 0.75

    def test_boundary_values_are_accepted(self):
        assert (
            AnalysisResponse.model_validate(
                _payload(confidence=0.0)
            ).confidence
            == 0.0
        )
        assert (
            AnalysisResponse.model_validate(
                _payload(confidence=1.0)
            ).confidence
            == 1.0
        )

    def test_above_one_is_clamped(self):
        response = AnalysisResponse.model_validate(
            _payload(confidence=2.5)
        )

        assert response.confidence == 1.0

    def test_negative_is_clamped_to_zero(self):
        response = AnalysisResponse.model_validate(
            _payload(confidence=-5)
        )

        assert response.confidence == 0.0

    def test_none_becomes_zero(self):
        response = AnalysisResponse.model_validate(
            _payload(confidence=None)
        )

        assert response.confidence == 0.0

    def test_non_numeric_becomes_zero(self):
        response = AnalysisResponse.model_validate(
            _payload(confidence="very confident")
        )

        assert response.confidence == 0.0

    def test_string_number_is_parsed(self):
        response = AnalysisResponse.model_validate(
            _payload(confidence="0.6")
        )

        assert response.confidence == 0.6


class TestAnalysisType:
    @pytest.mark.parametrize(
        "analysis_type",
        [
            "general",
            "document",
            "dataset",
            "database",
            "visualisation",
        ],
    )
    def test_valid_types_are_accepted(self, analysis_type):
        response = AnalysisResponse.model_validate(
            _payload(analysis_type=analysis_type)
        )

        assert response.analysis_type == analysis_type

    def test_invalid_type_is_rejected(self):
        with pytest.raises(Exception):
            AnalysisResponse.model_validate(
                _payload(analysis_type="spreadsheet")
            )


class TestDefaults:
    def test_optional_fields_default_to_empty(self):
        response = AnalysisResponse.model_validate(
            _payload()
        )

        assert response.datasets_used == []
        assert response.calculations_performed == []
        assert response.key_findings == []
        assert response.sources == []

    def test_answer_is_required(self):
        with pytest.raises(Exception):
            AnalysisResponse.model_validate(
                {"analysis_type": "general"}
            )