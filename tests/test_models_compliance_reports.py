# Copyright (c) 2025 Itential, Inc
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest
from pydantic import ValidationError

from itential_mcp.models import compliance_reports as models


class TestDescribeComplianceReportResponse:
    """Test the DescribeComplianceReportResponse model."""

    def test_model_creation_with_basic_data(self):
        """Test creating the model with basic data."""
        data = {"report_id": "123", "status": "complete"}
        response = models.DescribeComplianceReportResponse(result=data)

        assert response.result == data
        assert response.result["report_id"] == "123"
        assert response.result["status"] == "complete"

    def test_model_creation_with_complex_data(self):
        """Test creating the model with complex compliance report data."""
        data = {
            "report_id": "compliance-report-456",
            "status": "complete",
            "devices": [
                {"name": "device1", "compliance_status": "compliant", "violations": []},
                {
                    "name": "device2",
                    "compliance_status": "non-compliant",
                    "violations": [{"rule": "rule1", "severity": "high"}],
                },
            ],
            "summary": {
                "total_devices": 2,
                "compliant_devices": 1,
                "non_compliant_devices": 1,
            },
        }

        response = models.DescribeComplianceReportResponse(result=data)

        assert response.result == data
        assert len(response.result["devices"]) == 2
        assert response.result["summary"]["total_devices"] == 2

    def test_model_serialization(self):
        """Test that the model can be serialized to JSON."""
        data = {"report_id": "789", "status": "running"}
        response = models.DescribeComplianceReportResponse(result=data)

        json_data = response.model_dump()
        assert json_data == {"result": data}

        json_str = response.model_dump_json()
        assert '"report_id":"789"' in json_str
        assert '"status":"running"' in json_str


def _make_totals(**overrides):
    """Build a valid totals dict, allowing field overrides for negative tests."""
    data = {"errors": 1, "warnings": 2, "infos": 3, "passes": 10}
    data.update(overrides)
    return data


def _make_brief(**overrides):
    """Build a valid compliance report brief dict, allowing field overrides."""
    data = {
        "id": "67ead32d5f12757d048a48d1",
        "batchId": "67ead32d5f12757d048a48df",
        "treeId": "67ead32d5f12757d048a48d2",
        "version": "initial",
        "nodePath": "base/US East/Atlanta",
        "deviceName": "router1",
        "timestamp": "2026-08-18T00:00:00Z",
        "totals": _make_totals(),
    }
    data.update(overrides)
    return data


class TestComplianceReportTotals:
    """Test cases for ComplianceReportTotals model."""

    def test_create_valid_totals(self):
        """Test creating a valid ComplianceReportTotals instance."""
        totals = models.ComplianceReportTotals(**_make_totals())

        assert totals.errors == 1
        assert totals.warnings == 2
        assert totals.infos == 3
        assert totals.passes == 10

    def test_totals_missing_required_fields(self):
        """Test that ComplianceReportTotals raises ValidationError for missing fields."""
        with pytest.raises(ValidationError) as exc_info:
            models.ComplianceReportTotals()

        errors = exc_info.value.errors()
        required_fields = {"errors", "warnings", "infos", "passes"}
        missing_fields = {
            error["loc"][0] for error in errors if error["type"] == "missing"
        }
        assert required_fields.issubset(missing_fields)

    def test_totals_non_int_value_rejected(self):
        """Test that ComplianceReportTotals enforces int type on its fields."""
        with pytest.raises(ValidationError) as exc_info:
            models.ComplianceReportTotals(**_make_totals(errors="not-a-number"))

        errors = exc_info.value.errors()
        errors_field_errors = [e for e in errors if e["loc"][0] == "errors"]
        assert len(errors_field_errors) > 0
        assert "int_parsing" in errors_field_errors[0]["type"]


class TestComplianceReportBrief:
    """Test cases for ComplianceReportBrief model."""

    def test_create_valid_brief(self):
        """Test creating a valid ComplianceReportBrief instance with all fields."""
        brief = models.ComplianceReportBrief(**_make_brief())

        assert brief.id == "67ead32d5f12757d048a48d1"
        assert brief.batchId == "67ead32d5f12757d048a48df"
        assert brief.treeId == "67ead32d5f12757d048a48d2"
        assert brief.version == "initial"
        assert brief.nodePath == "base/US East/Atlanta"
        assert brief.deviceName == "router1"
        assert brief.timestamp == "2026-08-18T00:00:00Z"
        assert brief.totals.errors == 1
        assert brief.totals.warnings == 2
        assert brief.totals.infos == 3
        assert brief.totals.passes == 10

    def test_brief_missing_required_fields(self):
        """Test that ComplianceReportBrief raises ValidationError for missing fields."""
        with pytest.raises(ValidationError) as exc_info:
            models.ComplianceReportBrief()

        errors = exc_info.value.errors()
        required_fields = {
            "id",
            "batchId",
            "treeId",
            "version",
            "nodePath",
            "deviceName",
            "timestamp",
            "totals",
        }
        missing_fields = {
            error["loc"][0] for error in errors if error["type"] == "missing"
        }
        assert required_fields.issubset(missing_fields)


class TestGetComplianceReportsByBatchResponse:
    """Test cases for GetComplianceReportsByBatchResponse model."""

    def test_create_valid_response(self):
        """Test creating a valid GetComplianceReportsByBatchResponse instance."""
        brief1 = models.ComplianceReportBrief(**_make_brief())
        brief2 = models.ComplianceReportBrief(
            **_make_brief(id="67ead32d5f12757d048a48d9", deviceName="router2")
        )

        response = models.GetComplianceReportsByBatchResponse(reports=[brief1, brief2])

        assert len(response.reports) == 2
        assert response.reports[0].deviceName == "router1"
        assert response.reports[1].deviceName == "router2"

    def test_empty_reports_list(self):
        """Test creating response with an empty reports list."""
        response = models.GetComplianceReportsByBatchResponse(reports=[])
        assert response.reports == []

    def test_response_missing_reports_field(self):
        """Test that GetComplianceReportsByBatchResponse raises ValidationError for missing reports field."""
        with pytest.raises(ValidationError) as exc_info:
            models.GetComplianceReportsByBatchResponse()

        errors = exc_info.value.errors()
        reports_errors = [error for error in errors if error["loc"][0] == "reports"]
        assert len(reports_errors) > 0
