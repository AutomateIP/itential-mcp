# Copyright (c) 2025 Itential, Inc
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import inspect

from typing import Annotated, Any

from pydantic import BaseModel, Field


class DescribeComplianceReportResponse(BaseModel):
    """
    Response model for describing a compliance report.

    This model represents the detailed compliance report results from Itential Platform,
    containing validation results, device compliance status, rule violations, and
    configuration analysis from running compliance checks against network infrastructure.
    """

    result: Annotated[
        dict[str, Any],
        Field(
            description=inspect.cleandoc(
                """
                Compliance report details containing validation results,
                device compliance status, rule violations, and configuration
                analysis
                """
            )
        ),
    ]


class ComplianceReportTotals(BaseModel):
    """
    Aggregate check-result counts for a single compliance report.

    Attributes:
        errors: Number of failed checks classified as errors.
        warnings: Number of failed checks classified as warnings.
        infos: Number of informational check results.
        passes: Number of checks that passed.
    """

    errors: Annotated[
        int,
        Field(
            description=inspect.cleandoc(
                """
                Number of failed checks classified as errors
                """
            )
        ),
    ]

    warnings: Annotated[
        int,
        Field(
            description=inspect.cleandoc(
                """
                Number of failed checks classified as warnings
                """
            )
        ),
    ]

    infos: Annotated[
        int,
        Field(
            description=inspect.cleandoc(
                """
                Number of informational check results
                """
            )
        ),
    ]

    passes: Annotated[
        int,
        Field(
            description=inspect.cleandoc(
                """
                Number of checks that passed
                """
            )
        ),
    ]


class ComplianceReportBrief(BaseModel):
    """
    Represents a summary compliance report entry from a compliance plan batch run.

    This model defines the structure for a single per-device compliance
    report as returned when listing all reports produced by a compliance
    plan run batch. Use the report's `id` with `describe_compliance_report`
    to retrieve the full report detail.

    Attributes:
        id: Unique identifier for this compliance report.
        batchId: Identifier of the batch run that produced this report.
        treeId: Identifier of the Golden Configuration tree checked.
        version: Version of the Golden Configuration tree checked.
        nodePath: Hierarchical path of the node checked within the tree.
        deviceName: Name of the device this report was generated for.
        timestamp: ISO8601 timestamp of when the report was generated.
        totals: Aggregate check-result counts for this report.
    """

    id: Annotated[
        str,
        Field(
            description=inspect.cleandoc(
                """
                Unique identifier for this compliance report
                """
            )
        ),
    ]

    batchId: Annotated[
        str,
        Field(
            description=inspect.cleandoc(
                """
                Identifier of the batch run that produced this report
                """
            )
        ),
    ]

    treeId: Annotated[
        str,
        Field(
            description=inspect.cleandoc(
                """
                Identifier of the Golden Configuration tree checked
                """
            )
        ),
    ]

    version: Annotated[
        str,
        Field(
            description=inspect.cleandoc(
                """
                Version of the Golden Configuration tree checked
                """
            )
        ),
    ]

    nodePath: Annotated[
        str,
        Field(
            description=inspect.cleandoc(
                """
                Hierarchical path of the node checked within the tree
                """
            )
        ),
    ]

    deviceName: Annotated[
        str,
        Field(
            description=inspect.cleandoc(
                """
                Name of the device this report was generated for
                """
            )
        ),
    ]

    timestamp: Annotated[
        str,
        Field(
            description=inspect.cleandoc(
                """
                ISO8601 timestamp of when the report was generated
                """
            )
        ),
    ]

    totals: Annotated[
        ComplianceReportTotals,
        Field(
            description=inspect.cleandoc(
                """
                Aggregate check-result counts for this report
                """
            )
        ),
    ]


class GetComplianceReportsByBatchResponse(BaseModel):
    """
    Response model for get_compliance_reports_by_batch function.

    This model represents the list of compliance report summaries produced
    by a single compliance plan run batch, as returned by the
    get_compliance_reports_by_batch function from the Configuration Manager.

    Attributes:
        reports: List of compliance report brief objects.
    """

    reports: Annotated[
        list[ComplianceReportBrief],
        Field(
            description=inspect.cleandoc(
                """
                List of compliance report brief objects
                """
            )
        ),
    ]
