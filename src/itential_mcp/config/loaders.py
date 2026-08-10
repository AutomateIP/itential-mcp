# Copyright (c) 2025 Itential, Inc
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Configuration loaders for various sources.

This module handles loading configuration from different sources including
environment variables, configuration files, and command-line arguments.
It provides a clean separation between parsing logic and data models.
"""

from __future__ import annotations

import os
import functools
import configparser

from pathlib import Path
from typing import Any

from ..core.exceptions import ConfigurationException
from .models import (
    Config,
    ServerConfig,
    AuthConfig,
    PlatformConfig,
    Tool,
    EndpointTool,
    ServiceTool,
)

# Top-level section names recognized in config files, in addition to any
# section matching the "tool:<name>" pattern.
_RECOGNIZED_SECTIONS = frozenset({"server", "auth", "platform"})


def _parse_tool_env_variables() -> dict[str, dict[str, str]]:
    """Parse tool configuration from environment variables.

    Parses environment variables with the pattern ITENTIAL_MCP_TOOL_<tool_name>_<key>
    and returns a nested dictionary structure organized by tool name.

    Expected format: ITENTIAL_MCP_TOOL_<tool_name>_<key>=<value>

    The parsing splits on the LAST underscore to support underscores in tool names.
    For example: ITENTIAL_MCP_TOOL_RUN_CLI_COMMAND_TYPE splits into:
    - tool_name: RUN_CLI_COMMAND
    - key: TYPE

    Security Note:
        This function reads from environment variables to enable dynamic tool
        configuration. It should ONLY be used in trusted environments where
        users cannot set arbitrary environment variables. In shared or
        multi-tenant environments, ensure proper isolation (containers, VMs)
        and access controls are in place.

    Returns:
        Nested dictionary where keys are tool names and values are
        dictionaries of configuration key-value pairs for each tool.
        Example: {"RUN_CLI_COMMAND": {"type": "service", "name": "..."}}

    Raises:
        ValueError: If environment variable format is invalid or missing required parts.
    """
    tool_config: dict[str, dict[str, str]] = {}
    prefix = "ITENTIAL_MCP_TOOL_"

    # Filter and process environment variables in a single pass
    for env_key, env_value in os.environ.items():
        if not env_key.startswith(prefix):
            continue

        # Remove prefix
        remaining = env_key[len(prefix) :]

        # Split on the LAST underscore to support underscores in tool names
        if "_" not in remaining:
            raise ValueError(
                f"Invalid tool environment variable format: {env_key}. "
                f"Expected format: {prefix}<tool_name>_<key>=<value>"
            )

        # Split from the right on the last underscore
        tool_name, config_key = remaining.rsplit("_", 1)

        if not tool_name or not config_key:
            raise ValueError(f"Tool name and config key cannot be empty in: {env_key}")

        # Initialize tool config if not exists
        if tool_name not in tool_config:
            tool_config[tool_name] = {}

        # Convert config_key to lowercase for consistency
        config_key_lower = config_key.lower()
        tool_config[tool_name][config_key_lower] = env_value

    return tool_config


def _create_tool_from_dict(tool_data: dict[str, Any]) -> Tool:
    """Create a Tool instance from a dictionary of configuration data.

    Args:
        tool_data: Dictionary containing tool configuration with at least
            'tool_name' and 'type' keys.

    Returns:
        Tool instance (Tool, EndpointTool, or ServiceTool) based on type.

    Raises:
        KeyError: If required keys are missing from tool_data.
    """
    tool_type = tool_data.get("type")

    if tool_type == "endpoint":
        return EndpointTool(**tool_data)
    if tool_type == "service":
        return ServiceTool(**tool_data)
    return Tool(**tool_data)


def _parse_config_file(file_path: Path) -> tuple[dict[str, Any], list[Tool]]:
    """Parse configuration from an INI-style config file.

    Args:
        file_path: Path to the configuration file.

    Returns:
        Tuple containing:
            - Dictionary of flat configuration key-value pairs
            - List of Tool instances parsed from tool sections

    Raises:
        FileNotFoundError: If the config file does not exist.
        ConfigurationException: If the config file contains a top-level
            section name that is not recognized (not one of "server",
            "auth", "platform", or "tool:<name>").
    """
    if not file_path.is_file():
        raise FileNotFoundError(f"Config file not found: {file_path}")

    parser = configparser.ConfigParser()
    parser.read(file_path)

    config_data: dict[str, Any] = {}
    tools: list[Tool] = []
    tool_env_config = _parse_tool_env_variables()

    for section in parser.sections():
        if section.startswith("tool:"):
            # Parse tool configuration
            _, tool_name = section.split(":", 1)
            tool_data = {"tool_name": tool_name}

            for key, value in parser.items(section):
                tool_data[key] = value

            # Merge with environment variable overrides
            if tool_name in tool_env_config:
                tool_data.update(tool_env_config[tool_name])

            tools.append(_create_tool_from_dict(tool_data))

        elif section in _RECOGNIZED_SECTIONS:
            # Parse regular configuration sections
            for key, value in parser.items(section):
                config_key = f"{section}_{key}"
                config_data[config_key] = value

        else:
            valid_sections = ", ".join(sorted(_RECOGNIZED_SECTIONS) + ["tool:<name>"])
            raise ConfigurationException(
                f"Invalid config file section: [{section}]. "
                f"Valid section names are: {valid_sections}."
            )

    # Add any remaining environment tools not found in config file
    for tool_name, tool_data in tool_env_config.items():
        if not any(t.tool_name == tool_name for t in tools):
            tool_data["tool_name"] = tool_name
            tools.append(_create_tool_from_dict(tool_data))

    return config_data, tools


def _env_key_for_field(cls: type, field_name: str) -> str | None:
    """Return the env var name backing a config field, or None.

    Reads the env key embedded in the field's ``default_factory``
    (``partial(env_getter, env_key, default)``) via Pydantic's
    ``__pydantic_fields__`` introspection attribute. This is necessary
    because the env key is not always mechanically derivable from the
    section name (e.g. auth fields are backed by
    ``ITENTIAL_MCP_SERVER_AUTH_*``, not ``ITENTIAL_MCP_AUTH_*``).

    Args:
        cls: The Pydantic dataclass to inspect (e.g. ServerConfig).
        field_name: The name of the field to resolve the env key for.

    Returns:
        The environment variable name backing the field's default_factory,
        or None if the field is unknown or has no env-backed default_factory.

    Raises:
        None.
    """
    field_info = cls.__pydantic_fields__.get(field_name)
    if field_info is None:
        return None
    factory = getattr(field_info, "default_factory", None)
    if isinstance(factory, functools.partial) and factory.args:
        return factory.args[0]
    return None


def _filter_file_data(cls: type, data: dict[str, Any]) -> dict[str, Any]:
    """Drop file-derived keys whose env var is already set.

    Preserves the documented precedence of env var (and CLI flag, already
    funneled into ``os.environ`` by ``runtime/parser.py``) beating the
    config file. Keys with no env-backed field are passed through
    unchanged so unrecognized keys still reach the constructor and raise
    as they do today.

    Args:
        cls: The Pydantic dataclass the data will be used to construct
            (e.g. ServerConfig).
        data: The file-derived kwargs dict for that class.

    Returns:
        A new dict with any key whose backing env var is present in
        os.environ removed, allowing that field's default_factory to run
        and read the environment instead.

    Raises:
        None.
    """
    result: dict[str, Any] = {}
    for key, value in data.items():
        env_key = _env_key_for_field(cls, key)
        if env_key is not None and env_key in os.environ:
            continue  # env var (or CLI flag already in os.environ) wins
        result[key] = value
    return result


def _split_comma_separated(value: str | None) -> list[str]:
    """Convert comma-separated string to a list of trimmed values.

    Args:
        value: Comma separated string value to parse, or None.

    Returns:
        List of trimmed values, excluding empty entries.
        Returns empty list if value is None.

    Raises:
        None.
    """
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _split_space_or_comma_separated(value: str | None) -> list[str]:
    """Convert space or comma separated string to a list of trimmed values.

    Args:
        value: Space or comma separated string value to parse, or None.

    Returns:
        List of trimmed values, excluding empty entries.
        Returns empty list if value is None.

    Raises:
        None.
    """
    if value is None:
        return []
    # Normalize both separators to spaces
    normalized = value.replace(",", " ")
    return [item.strip() for item in normalized.split() if item.strip()]


def load_config() -> Config:
    """Load configuration from all available sources.

    Configuration is loaded with the following precedence:
    1. Environment variables, including CLI flags (highest priority --
       runtime/parser.py funnels CLI flags into os.environ before this
       function runs, so a real env var also beats a CLI flag)
    2. Configuration file (if ITENTIAL_MCP_CONFIG is set)
    3. Default values (lowest priority)

    File-derived values are filtered via _filter_file_data() before being
    passed to the ServerConfig/AuthConfig/PlatformConfig constructors so
    that any field whose env var is already set in os.environ is omitted
    from the constructor kwargs. This allows that field's env-backed
    default_factory to run instead of the explicit kwarg silently taking
    priority, which previously caused the config file to incorrectly win
    over the environment.

    The configuration file path is determined by the ITENTIAL_MCP_CONFIG
    environment variable.

    Returns:
        Complete Config instance with all sections populated.

    Raises:
        FileNotFoundError: If a configuration file is specified but not found.
    """
    from ..core import env as envmodule

    config_file_path = envmodule.getstr("ITENTIAL_MCP_CONFIG", None)

    file_config_data: dict[str, Any] = {}
    tools: list[Tool] = []

    if config_file_path:
        file_path = Path(config_file_path)
        file_config_data, tools = _parse_config_file(file_path)
    else:
        # No config file, but check for environment tool variables
        tool_env_config = _parse_tool_env_variables()
        for tool_name, tool_data in tool_env_config.items():
            tool_data["tool_name"] = tool_name
            tools.append(_create_tool_from_dict(tool_data))

    # Build nested configuration objects
    # Environment variables are automatically loaded via default_factory in models

    # For file config, we need to update the data dict if values exist
    server_data = {}
    auth_data = {}
    platform_data = {}

    # Extract server config from file
    for key, value in file_config_data.items():
        if key.startswith("server_"):
            server_data[key.replace("server_", "")] = value
        elif key.startswith("auth_") or key.startswith("server_auth_"):
            # Handle both auth_ and server_auth_ prefixes
            clean_key = key.replace("server_auth_", "").replace("auth_", "")
            auth_data[clean_key] = value
        elif key.startswith("platform_"):
            platform_data[key.replace("platform_", "")] = value

    # Create config objects. Env-backed keys are filtered out of the
    # file-derived kwargs so the corresponding default_factory fires and
    # env vars (and CLI flags, already in os.environ) take precedence.
    server_config = ServerConfig(**_filter_file_data(ServerConfig, server_data))
    auth_config = AuthConfig(**_filter_file_data(AuthConfig, auth_data))
    platform_config = PlatformConfig(**_filter_file_data(PlatformConfig, platform_data))

    return Config(
        server=server_config,
        auth=auth_config,
        platform=platform_config,
        tools=tools,
    )
