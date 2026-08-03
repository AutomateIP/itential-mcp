# Copyright (c) 2025 Itential, Inc
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import inspect

from typing import Annotated, Literal

from pydantic import BaseModel, Field, RootModel, field_validator


class GetIntegrationModelsElement(BaseModel):
    """Represents a single integration model element.

    This model represents an individual integration model returned by the
    get integration models API endpoint, containing information about the
    model's identity, version, and description.

    Attributes:
        id: Unique identifier assigned by Itential Platform.
        title: Model title from the OpenAPI spec info block.
        version: Model version from the OpenAPI spec info block.
        description: Optional model description.
    """

    id: Annotated[
        str,
        Field(
            description=inspect.cleandoc(
                """
                Unique identifier assigned by Itential Platform
                """
            )
        ),
    ]

    title: Annotated[
        str,
        Field(
            description=inspect.cleandoc(
                """
                Model title from the OpenAPI spec info block
                """
            )
        ),
    ]

    version: Annotated[
        str,
        Field(
            description=inspect.cleandoc(
                """
                Model version from the OpenAPI spec info block
                """
            )
        ),
    ]

    description: Annotated[
        str | None,
        Field(
            default=None,
            description=inspect.cleandoc(
                """
                Optional model description
                """
            ),
        ),
    ]


class GetIntegrationModelsResponse(RootModel):
    """Response model for the get integration models API endpoint.

    This root model wraps a list of GetIntegrationModelsElement objects representing
    all integration models on the Itential Platform server.

    Attributes:
        root: List of integration model elements, each containing model details.
    """

    root: Annotated[
        list[GetIntegrationModelsElement],
        Field(
            description=inspect.cleandoc(
                """
                A list of elements where each element represents an integration
                model from the server
                """
            )
        ),
    ]


class CreateIntegrationModelResponse(BaseModel):
    """Response model for the create integration model API operation.

    This model represents the response returned when creating an integration model,
    containing the operation status and descriptive message.

    Attributes:
        status: Operation status (OK or CREATED). Casing is normalized on
            input, so any casing variant returned by the platform (e.g.
            "Created", "created") is accepted.
        message: Descriptive message about the operation.
    """

    status: Annotated[
        Literal["OK", "CREATED"],
        Field(
            description=inspect.cleandoc(
                """
                Operation status (OK or CREATED). Casing is normalized on
                input.
                """
            )
        ),
    ]

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status_case(cls, value: object) -> object:
        """Normalize the casing of the incoming status value.

        The Itential Platform has been observed returning the status value
        with inconsistent casing (e.g. "Created" instead of "CREATED"). This
        validator upper-cases string values before Literal validation so any
        casing variant is accepted. Non-string values are passed through
        unchanged so Pydantic's normal type-error handling still applies.

        Args:
            value: The raw status value provided to the model.

        Returns:
            The upper-cased string if value is a string, otherwise value
            unchanged.
        """
        if isinstance(value, str):
            return value.upper()
        return value

    message: Annotated[
        str,
        Field(
            description=inspect.cleandoc(
                """
                Descriptive message about the operation
                """
            )
        ),
    ]


class GetIntegrationsElement(BaseModel):
    """Represents a single integration instance element.

    This model represents an individual integration instance returned by the
    get integrations API endpoint, containing information about the
    integration's name, associated model, and configuration properties.

    Attributes:
        name: Name of the integration instance.
        model: Integration model associated with this instance.
        properties: The integration model schema and configuration.
    """

    name: Annotated[
        str,
        Field(
            description=inspect.cleandoc(
                """
                Name of the integration instance
                """
            )
        ),
    ]

    model: Annotated[
        str,
        Field(
            description=inspect.cleandoc(
                """
                Integration model assoicated with this instance
                """
            )
        ),
    ]

    properties: Annotated[
        dict,
        Field(
            description=inspect.cleandoc(
                """
                The integration model schema
                """
            )
        ),
    ]


class GetIntegrationsResponse(RootModel):
    """Response model for the get integrations API endpoint.

    This root model wraps a list of GetIntegrationsElement objects representing
    all integration instances on the Itential Platform server.

    Attributes:
        root: List of integration instance elements, each containing instance details.
    """

    root: Annotated[
        list[GetIntegrationsElement],
        Field(
            description=inspect.cleandoc(
                """
                A list of elements where each element represents an integration
                instance from the server
                """
            )
        ),
    ]
