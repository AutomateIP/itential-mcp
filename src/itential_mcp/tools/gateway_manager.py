# Copyright (c) 2025 Itential, Inc
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Annotated, Any

from pydantic import Field

from fastmcp import Context

from itential_mcp.utilities import json as jsonutils
from itential_mcp.core import exceptions

from itential_mcp.models import gateway_manager as models


__tags__ = ("gateway_manager",)


async def get_services(
    ctx: Annotated[Context, Field(description="The FastMCP Context object")],
) -> models.GetServicesResponse:
    """
    Get the list of all know services from Itential Platform Gateway Manager

    Args:
        ctx (Context): The FastMCP Context object

    Returns:
        GetServicesResponse: List of service objects with the following fields:
            - name: The service name
            - cluster: The cluster name
            - type: The service type (ansible-playbook, python-script, opentofu-plan)
            - description: Short description of the service
            - decorator: JSON schema that defines the service input

    Raises:
        Exception: If there is an error retrieving services from Gateway Manager
    """
    await ctx.debug("inside get_services(...)")

    client = ctx.request_context.lifespan_context.get("client")

    data = await client.gateway_manager.get_services()

    results = []

    for ele in data:
        results.append(
            models.ServiceElement(
                name=ele["service_metadata"]["name"],
                cluster=ele["service_metadata"]["location"],
                type=ele["service_metadata"]["type"],
                description=ele["service_metadata"]["description"],
                decorator=ele["service_metadata"]["decorator"],
            )
        )

    return models.GetServicesResponse(results)


async def get_gateways(
    ctx: Annotated[Context, Field(description="The FastMCP Context object")],
) -> models.GetGatewaysResponse:
    """
    Get the list of all know services from Itential Platform Gateway Manager

    Args:
        ctx (Context): The FastMCP Context object

    Returns:
        GetGatewaysResponse: List of gateway objects with the following fields:
            - name: The gateway name
            - cluster: The cluster name
            - description: Short description of the gateway
            - status: Current status of the gateway connection
            - enabled: Whether or not the gateway is enabled and usable

    Raises:
        Exception: If there is an error retrieving gateways from Gateway Manager
    """
    await ctx.debug("inside get_gateways(...)")

    client = ctx.request_context.lifespan_context.get("client")

    data = await client.gateway_manager.get_gateways()

    results = []

    # XXX (privateip) The results are filtered to only return gateways that
    # have a connection status of `connected` since we do not care about
    # disconnected gateways.  Additionally if a gateway status is disconnected,
    # the API does not return the name property.

    # Handle both response formats: direct array or wrapped in "results" key
    gateway_list = data.get("results", data) if isinstance(data, dict) else data

    for ele in gateway_list:
        if (
            ele.get("connection_status") == "connected"
            or ele.get("status") == "connected"
        ):
            results.append(
                models.GatewayElement(
                    name=ele.get("name", ele.get("gateway_name", "")),
                    cluster=ele.get("cluster", ele.get("cluster_id", "")),
                    description=ele.get("description", ""),
                    status=ele.get("status", ele.get("connection_status", "")),
                    enabled=ele.get("enabled", False),
                )
            )

    return models.GetGatewaysResponse(results)


async def run_service(
    ctx: Annotated[Context, Field(description="The FastMCP Context object")],
    name: Annotated[str, Field(description="The name of the service to run")],
    cluster: Annotated[
        str, Field(description="The name of the cluster where the service lives")
    ],
    input_params: Annotated[
        dict | str | None,
        Field(
            description="Optional input parameters to pass to the service", default=None
        ),
    ],
) -> models.RunServiceResponse:
    """
    Run an existing service using the optional input parameters

    Args:
        ctx (Context): The FastMCP Context object
        name (str): The name of the service to run
        cluster (str): The name of the cluster that owns the service
        input_params (dict): Optional input parameters to pass to the service

    Returns:
        RunServiceResponse: An object that represents output from the service
            with the following fields:
                - stdout: The output sent to stdout
                - stderr: The output sent to stderr
                - return_code: The return code generated by the service
                - start_time: The start time when the service was started
                - end_time: The end time when the service run completed
                - elapsed_time: The number of seconds the service ran for

    Raises:
        Exception: If there is an error running the service on Gateway Manager
    """
    await ctx.debug("inside run_service(...)")

    client = ctx.request_context.lifespan_context.get("client")

    # Parse input_params if it's a JSON string
    if isinstance(input_params, str):
        input_params = jsonutils.loads(input_params)

    res = await client.gateway_manager.run_service(
        name, cluster, input_params=input_params
    )

    if "error" in res:
        raise ValueError(res["error"]["data"])

    # Attempt to parse stdout as JSON, but keep raw string if parsing fails
    try:
        stdout_json = jsonutils.loads(res["result"]["stdout"])
        res["result"]["stdout"] = stdout_json
    except (exceptions.ValidationException, ValueError, TypeError):
        # Not valid JSON, keep as raw string
        pass

    return models.RunServiceResponse(**res["result"])


async def export_gateway_configuration(
    ctx: Annotated[Context, Field(description="The FastMCP Context object")],
    cluster_id: Annotated[
        str, Field(description="The cluster ID of the target gateway, e.g. 'cluster_1'")
    ],
) -> models.ExportGatewayConfigurationResponse:
    """
    Export a gateway cluster's full DB configuration as a DSL document

    The gateway must be connected and active. The returned document can be
    passed unchanged as the content of a future import_gateway_configuration
    call.

    Args:
        ctx (Context): The FastMCP Context object
        cluster_id (str): The cluster ID of the target gateway

    Returns:
        ExportGatewayConfigurationResponse: The exported DSL configuration
            document

    Raises:
        Exception: If there is an error exporting the configuration from
            Gateway Manager
    """
    await ctx.debug("inside export_gateway_configuration(...)")

    client = ctx.request_context.lifespan_context.get("client")

    document = await client.gateway_manager.export_configuration(cluster_id)

    return models.ExportGatewayConfigurationResponse(document)


async def import_gateway_configuration(
    ctx: Annotated[Context, Field(description="The FastMCP Context object")],
    cluster_id: Annotated[
        str, Field(description="The cluster ID of the target gateway")
    ],
    content: Annotated[
        dict | str | None,
        Field(
            description=(
                "Inline DSL document to import — either the object returned by "
                "export_gateway_configuration, or a raw YAML/JSON string. "
                "Mutually exclusive with the git_* parameters."
            ),
            default=None,
        ),
    ],
    git_url: Annotated[
        str | None,
        Field(
            description="Git repository URL to import from. Requires git_file. Mutually exclusive with content.",
            default=None,
        ),
    ],
    git_file: Annotated[
        str | None,
        Field(
            description="Path to the DSL file within the git repository. Required when git_url is set.",
            default=None,
        ),
    ],
    git_reference: Annotated[
        str | None,
        Field(
            description="Branch, tag, or SHA to check out. Defaults to the repository's default branch.",
            default=None,
        ),
    ],
    git_username: Annotated[
        str | None,
        Field(
            description="HTTP basic auth username for HTTPS git repositories.",
            default=None,
        ),
    ],
    git_password: Annotated[
        str | None,
        Field(
            description=(
                "HTTP basic auth password for HTTPS git repositories. Supports "
                "$GATEWAYSECRET_(alias) references resolved by the gateway."
            ),
            default=None,
        ),
    ],
    git_private_key: Annotated[
        str | None,
        Field(
            description="SSH private key file path on the gateway host filesystem.",
            default=None,
        ),
    ],
    force: Annotated[
        bool, Field(description="Overwrite existing resources.", default=False)
    ],
    validate: Annotated[
        bool,
        Field(
            description="Parse and validate only, with no writes. Mutually exclusive with check.",
            default=False,
        ),
    ],
    check: Annotated[
        bool,
        Field(
            description="Dry-run diff showing what would change, with no writes. Mutually exclusive with validate.",
            default=False,
        ),
    ],
) -> models.ImportGatewayConfigurationResponse:
    """
    Import a DB configuration into a connected gateway cluster

    The configuration content may be supplied inline via content, or fetched
    from a git repository via the git_* parameters. The gateway must be
    connected and active.

    Args:
        ctx (Context): The FastMCP Context object
        cluster_id (str): The cluster ID of the target gateway
        content (dict | str | None): Inline DSL document to import
        git_url (str | None): Git repository URL to import from
        git_file (str | None): Path to the DSL file within the git repository
        git_reference (str | None): Branch, tag, or SHA to check out
        git_username (str | None): HTTP basic auth username for the git repository
        git_password (str | None): HTTP basic auth password for the git repository
        git_private_key (str | None): SSH private key file path on the gateway host
        force (bool): Overwrite existing resources
        validate (bool): Parse and validate only, with no writes
        check (bool): Dry-run diff showing what would change, with no writes

    Returns:
        ImportGatewayConfigurationResponse: Summary of resources added,
            replaced, and skipped by the import

    Raises:
        ValidationException: If validate and check are both set, if content
            and git parameters are both set, if neither is set, or if only
            one of git_url/git_file is set
        Exception: If there is an error importing the configuration into
            Gateway Manager
    """
    await ctx.debug("inside import_gateway_configuration(...)")

    if validate and check:
        raise exceptions.ValidationException(
            "validate and check are mutually exclusive"
        )

    git_params = (
        git_url,
        git_file,
        git_reference,
        git_username,
        git_password,
        git_private_key,
    )

    if content is not None and any(param is not None for param in git_params):
        raise exceptions.ValidationException(
            "content and the git_* parameters are mutually exclusive"
        )

    if content is None and git_url is None:
        raise exceptions.ValidationException(
            "either content or git_url must be provided"
        )

    if (git_url is None) != (git_file is None):
        raise exceptions.ValidationException(
            "git_url and git_file are both required together for a git source"
        )

    client = ctx.request_context.lifespan_context.get("client")

    source = "content" if content is not None else "git"

    git: dict[str, Any] | None = None
    if source == "git":
        git = {"url": git_url, "file": git_file}
        if git_reference is not None:
            git["reference"] = git_reference
        if git_username is not None:
            git["username"] = git_username
        if git_password is not None:
            git["password"] = git_password
        if git_private_key is not None:
            git["privateKey"] = git_private_key

    result = await client.gateway_manager.import_configuration(
        cluster_id,
        source=source,
        content=content,
        git=git,
        force=force,
        validate=validate,
        check=check,
    )

    return models.ImportGatewayConfigurationResponse(**result)
