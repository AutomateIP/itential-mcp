# Copyright (c) 2025 Itential, Inc
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import asyncio

from datetime import datetime
from typing import Annotated

from pydantic import Field

from fastmcp import Context

from itential_mcp.core.exceptions import ValidationException
from itential_mcp.utilities import time as timeutils
from itential_mcp.models import agent_session_manager as models


__tags__ = ("agent_session_manager",)


def _filter_sessions(
    sessions: list[dict],
    *,
    agent_name: str | None,
    include_failed: bool,
    after_dt: datetime | None,
    before_dt: datetime | None,
) -> list[dict]:
    """
    Filter session dicts by agent name, status, and started_at window.

    Args:
        sessions (list[dict]): Normalized session dicts as returned by
            client.agent_session_manager.get_sessions.
        agent_name (str | None): Filter to agent names containing this
            substring (case-insensitive). When None, no name filtering is
            applied.
        include_failed (bool): Also allow FAILED sessions alongside
            COMPLETE ones.
        after_dt (datetime | None): When provided, only sessions started at
            or after this time are kept.
        before_dt (datetime | None): When provided, only sessions started at
            or before this time are kept.

    Returns:
        list[dict]: The subset of sessions matching all provided filters.

    Raises:
        ValidationException: If a session's started_at value is not a valid
            ISO 8601 timestamp.
    """
    filtered = []
    for item in sessions:
        item_agent_name = item.get("agent_name")

        if agent_name is not None:
            if item_agent_name is None:
                continue
            if agent_name.lower() not in item_agent_name.lower():
                continue

        item_status = item.get("status")
        allowed_statuses = ("COMPLETE", "FAILED") if include_failed else ("COMPLETE",)
        if item_status not in allowed_statuses:
            continue

        if after_dt is not None or before_dt is not None:
            raw_started_at = item.get("started_at")
            if isinstance(raw_started_at, int):
                started_at_dt = _parse_timestamp(
                    timeutils.epoch_to_timestamp(raw_started_at)
                )
            elif raw_started_at is not None:
                started_at_dt = _parse_timestamp(raw_started_at)
            else:
                started_at_dt = None

            if started_at_dt is None:
                continue
            if after_dt is not None and started_at_dt < after_dt:
                continue
            if before_dt is not None and started_at_dt > before_dt:
                continue

        filtered.append(item)

    return filtered


def _extract_token_usage(raw: dict) -> models.SessionTurnTokenUsage | None:
    """
    Extract token usage figures from a raw inference-succeeded tokenUsage dict.

    # tokenUsage key names are inferred from the swagger's prose description
    # only — no schema exists. Confirm actual key names against a live
    # inference-succeeded event before merge.

    Args:
        raw (dict): The raw tokenUsage dict from a session message's
            data field.

    Returns:
        models.SessionTurnTokenUsage | None: The extracted token usage, or
            None if raw is falsy.
    """
    if not raw:
        return None

    input_tokens = None
    for key in ("inputTokens", "input_tokens", "promptTokens", "prompt_tokens"):
        if key in raw:
            input_tokens = raw[key]
            break

    output_tokens = None
    for key in (
        "outputTokens",
        "output_tokens",
        "completionTokens",
        "completion_tokens",
    ):
        if key in raw:
            output_tokens = raw[key]
            break

    total_tokens = None
    for key in ("totalTokens", "total_tokens"):
        if key in raw:
            total_tokens = raw[key]
            break
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    return models.SessionTurnTokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        raw=raw,
    )


def _parse_timestamp(value: str) -> datetime:
    """
    Parse an ISO 8601 / RFC3339 timestamp string into a timezone-aware datetime.

    Accepts a trailing "Z" designator (converted to "+00:00" for compatibility
    with datetime.fromisoformat).

    Args:
        value (str): The timestamp string to parse.

    Returns:
        datetime: The parsed timezone-aware datetime object.

    Raises:
        ValidationException: If the value is not a valid ISO 8601 timestamp.
    """
    normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValidationException(f"Invalid ISO 8601 timestamp: {value!r}") from exc


async def get_sessions(
    ctx: Annotated[Context, Field(description="The FastMCP Context object")],
    agent_name: Annotated[
        str | None,
        Field(
            description="Optional agent name used to filter sessions",
            default=None,
        ),
    ],
) -> models.GetSessionsResponse:
    """
    List agent sessions from Itential Platform.

    Agent sessions are created when an agent automation is triggered via an
    endpoint trigger. Each session records the agent that ran, its execution
    status, and timing information.

    Args:
        ctx (Context): The FastMCP Context object.
        agent_name (str | None): Filter sessions to a specific agent by name.
            When omitted, all sessions are returned.

    Returns:
        models.GetSessionsResponse: List of session objects with the following fields:
            - session_id: Unique session identifier (use with describe_session)
            - agent_name: Name of the agent that ran
            - status: Session status (RUNNING, COMPLETE, FAILED)
            - started_at: ISO 8601 start timestamp
            - end_time: ISO 8601 end timestamp (None if still running)
            - duration_ms: Total session duration in milliseconds

    Notes:
        - Use describe_session with a session_id to get the full event log and output
        - Timestamps are converted from epoch milliseconds to ISO 8601 format
    """
    await ctx.debug("inside get_sessions(...)")

    client = ctx.request_context.lifespan_context.get("client")

    data = await client.agent_session_manager.get_sessions(agent_name)

    session_elements = []

    for item in data:
        started_at = item.get("started_at")
        if isinstance(started_at, int):
            started_at = timeutils.epoch_to_timestamp(started_at)

        end_time = item.get("end_time")
        if isinstance(end_time, int):
            end_time = timeutils.epoch_to_timestamp(end_time)

        session_element = models.SessionElement(
            session_id=item["session_id"],
            agent_name=item.get("agent_name"),
            status=item["status"],
            started_at=started_at,
            end_time=end_time,
            duration_ms=item.get("duration_ms"),
        )
        session_elements.append(session_element)

    return models.GetSessionsResponse(root=session_elements)


async def describe_session(
    ctx: Annotated[Context, Field(description="The FastMCP Context object")],
    session_id: Annotated[
        str,
        Field(description="The session ID to retrieve full details for"),
    ],
) -> models.DescribeSessionResponse:
    """
    Get detailed information about a specific agent session.

    Returns the full session record including all event messages emitted
    during agent execution and the final text output produced by the agent.

    Args:
        ctx (Context): The FastMCP Context object.
        session_id (str): Unique session identifier. Session IDs are returned
            by get_sessions.

    Returns:
        models.DescribeSessionResponse: Full session details with the following fields:
            - session_id: Unique session identifier
            - agent_name: Name of the agent that ran
            - status: Session status (RUNNING, COMPLETE, FAILED)
            - output: Final text produced by the agent (None if not yet complete)
            - started_at: ISO 8601 start timestamp
            - end_time: ISO 8601 end timestamp (None if still running)
            - duration_ms: Total session duration in milliseconds
            - messages: Ordered list of session event messages

    Notes:
        - The output field is extracted from the inference-succeeded event message
        - Message timestamps are converted from epoch milliseconds to ISO 8601 format
    """
    await ctx.debug("inside describe_session(...)")

    client = ctx.request_context.lifespan_context.get("client")

    session, raw_messages = await asyncio.gather(
        client.agent_session_manager.get_session(session_id),
        client.agent_session_manager.get_session_messages(session_id),
    )

    agent_snapshot = session.get("agentSnapshot") or {}
    agent_name = agent_snapshot.get("name")

    started_at = session.get("startedAt")
    if isinstance(started_at, int):
        started_at = timeutils.epoch_to_timestamp(started_at)

    end_time = session.get("endTime")
    if isinstance(end_time, int):
        end_time = timeutils.epoch_to_timestamp(end_time)

    messages = []
    output = None

    for raw in raw_messages:
        msg_timestamp = raw.get("timestamp")
        if isinstance(msg_timestamp, int):
            msg_timestamp = timeutils.epoch_to_timestamp(msg_timestamp)

        msg = models.SessionMessage(
            type=raw.get("type", ""),
            category=raw.get("category"),
            text=raw.get("text"),
            timestamp=msg_timestamp,
        )
        messages.append(msg)

        if raw.get("type") == "inference-succeeded" and raw.get("text") is not None:
            output = raw["text"]

    return models.DescribeSessionResponse(
        session_id=session.get("sessionId", session_id),
        agent_name=agent_name,
        status=session.get("status", ""),
        output=output,
        started_at=started_at,
        end_time=end_time,
        duration_ms=session.get("durationMs"),
        messages=messages,
    )


async def get_agent_token_usage(
    ctx: Annotated[Context, Field(description="The FastMCP Context object")],
    agent_name: Annotated[
        str | None,
        Field(
            description="Filter to agent names containing this substring (case-insensitive)",
            default=None,
        ),
    ],
    include_failed: Annotated[
        bool,
        Field(
            description=(
                "By default only COMPLETE sessions count toward usage "
                "(finished, billable work). Set true to also include FAILED "
                "sessions, which can still have consumed real tokens. "
                "Non-terminal statuses (PENDING, RUNNING, PAUSED, ...) are "
                "always excluded either way, since their totals aren't final."
            ),
            default=False,
        ),
    ],
    started_after: Annotated[
        str | None,
        Field(
            description=(
                "ISO 8601 timestamp — only include sessions started at or "
                "after this time"
            ),
            default=None,
        ),
    ],
    started_before: Annotated[
        str | None,
        Field(
            description=(
                "ISO 8601 timestamp — only include sessions started at or "
                "before this time"
            ),
            default=None,
        ),
    ],
) -> models.GetAgentTokenUsageResponse:
    """
    Aggregate agent session token usage grouped by agent name.

    Fetches agent sessions and groups them by agent name, computing token
    consumption statistics (sum, average, min, max) for both input and output
    tokens per agent. Sessions with missing or null token values are still
    counted toward session_count but contribute 0 to sum, average, and
    min/max calculations. Sessions with no agent name are grouped under a
    None-keyed entry rather than dropped. Only COMPLETE sessions are included
    by default — see include_failed to also include FAILED sessions.

    Args:
        ctx (Context): The FastMCP Context object.
        agent_name (str | None): Filter to agent names containing this
            substring (case-insensitive). When omitted, all agents are
            included.
        include_failed (bool): Also include FAILED sessions alongside
            COMPLETE ones. See parameter description for the default
            rationale.
        started_after (str | None): ISO 8601 timestamp. When provided, only
            sessions started at or after this time are included.
        started_before (str | None): ISO 8601 timestamp. When provided, only
            sessions started at or before this time are included.

    Returns:
        models.GetAgentTokenUsageResponse: List of per-agent token usage
            aggregation objects, sorted by total_tokens descending. Each
            entry has the following fields:
            - agent_name: Agent display name (None if sessions had no name)
            - session_count: Number of sessions in the group
            - total_input_tokens: Sum of input tokens (missing treated as 0)
            - total_output_tokens: Sum of output tokens (missing treated as 0)
            - total_tokens: total_input_tokens + total_output_tokens
            - avg_input_tokens, min_input_tokens, max_input_tokens
            - avg_output_tokens, min_output_tokens, max_output_tokens
            - total_duration_ms, avg_duration_ms, min_duration_ms, max_duration_ms

    Raises:
        ValidationException: If started_after, started_before, or a
            session's started_at value is not a valid ISO 8601 timestamp.

    Notes:
        - The underlying session fetch is unbounded — all pages are
          retrieved before filtering and aggregation.
        - agent_name filtering here is a substring match; the underlying
          service call is made without a filter so that all sessions are
          fetched first.
    """
    await ctx.debug("inside get_agent_token_usage(...)")

    client = ctx.request_context.lifespan_context.get("client")

    data = await client.agent_session_manager.get_sessions(None)

    after_dt = _parse_timestamp(started_after) if started_after is not None else None
    before_dt = _parse_timestamp(started_before) if started_before is not None else None

    filtered = _filter_sessions(
        data,
        agent_name=agent_name,
        include_failed=include_failed,
        after_dt=after_dt,
        before_dt=before_dt,
    )

    groups: dict[str | None, list[dict]] = {}
    for item in filtered:
        groups.setdefault(item.get("agent_name"), []).append(item)

    stats = []
    for group_agent_name, sessions in groups.items():
        input_tokens = [s.get("total_input_tokens") or 0 for s in sessions]
        output_tokens = [s.get("total_output_tokens") or 0 for s in sessions]
        durations = [s.get("duration_ms") or 0 for s in sessions]

        total_input = sum(input_tokens)
        total_output = sum(output_tokens)
        total_duration = sum(durations)
        session_count = len(sessions)

        stats.append(
            models.AgentTokenUsageStats(
                agent_name=group_agent_name,
                session_count=session_count,
                total_input_tokens=total_input,
                total_output_tokens=total_output,
                total_tokens=total_input + total_output,
                avg_input_tokens=total_input / session_count,
                min_input_tokens=min(input_tokens),
                max_input_tokens=max(input_tokens),
                avg_output_tokens=total_output / session_count,
                min_output_tokens=min(output_tokens),
                max_output_tokens=max(output_tokens),
                total_duration_ms=total_duration,
                avg_duration_ms=total_duration / session_count,
                min_duration_ms=min(durations),
                max_duration_ms=max(durations),
            )
        )

    stats.sort(key=lambda s: s.total_tokens, reverse=True)

    return models.GetAgentTokenUsageResponse(root=stats)


async def get_agent_session_token_usage(
    ctx: Annotated[Context, Field(description="The FastMCP Context object")],
    agent_name: Annotated[
        str,
        Field(
            description="Filter to agent names containing this substring (case-insensitive)"
        ),
    ],
    include_failed: Annotated[
        bool,
        Field(
            description=(
                "By default only COMPLETE sessions count toward usage "
                "(finished, billable work). Set true to also include FAILED "
                "sessions, which can still have consumed real tokens. "
                "Non-terminal statuses (PENDING, RUNNING, PAUSED, ...) are "
                "always excluded either way, since their totals aren't final."
            ),
            default=False,
        ),
    ],
    started_after: Annotated[
        str | None,
        Field(
            description=(
                "ISO 8601 timestamp — only include sessions started at or "
                "after this time"
            ),
            default=None,
        ),
    ],
    started_before: Annotated[
        str | None,
        Field(
            description=(
                "ISO 8601 timestamp — only include sessions started at or "
                "before this time"
            ),
            default=None,
        ),
    ],
) -> models.GetAgentSessionTokenUsageResponse:
    """
    List per-session token usage for a single agent, sorted chronologically.

    Fetches agent sessions filtered to the given agent name and returns one
    row per matching session (no aggregation), useful for time-series
    inspection of an agent's usage. Only COMPLETE sessions are included by
    default — see include_failed to also include FAILED sessions.

    Args:
        ctx (Context): The FastMCP Context object.
        agent_name (str): Filter to agent names containing this substring
            (case-insensitive). Required — this tool is single-agent scoped.
        include_failed (bool): Also include FAILED sessions alongside
            COMPLETE ones. See parameter description for the default
            rationale.
        started_after (str | None): ISO 8601 timestamp. When provided, only
            sessions started at or after this time are included.
        started_before (str | None): ISO 8601 timestamp. When provided, only
            sessions started at or before this time are included.

    Returns:
        models.GetAgentSessionTokenUsageResponse: List of per-session token
            usage objects, sorted by started_at ascending (sessions with no
            started_at sort last). Each entry has the following fields:
            - session_id, status, started_at, end_time, duration_ms
            - total_input_tokens, total_output_tokens
            - total_tokens: total_input_tokens + total_output_tokens
              (missing treated as 0)

    Raises:
        ValidationException: If started_after, started_before, or a
            session's started_at value is not a valid ISO 8601 timestamp.

    Notes:
        - The underlying session fetch is unbounded — all pages are
          retrieved before filtering.
        - agent_name filtering here is a substring match; the underlying
          service call is made without a filter so that all sessions are
          fetched first.
    """
    await ctx.debug("inside get_agent_session_token_usage(...)")

    client = ctx.request_context.lifespan_context.get("client")

    data = await client.agent_session_manager.get_sessions(None)

    after_dt = _parse_timestamp(started_after) if started_after is not None else None
    before_dt = _parse_timestamp(started_before) if started_before is not None else None

    filtered = _filter_sessions(
        data,
        agent_name=agent_name,
        include_failed=include_failed,
        after_dt=after_dt,
        before_dt=before_dt,
    )

    elements = []
    for item in filtered:
        input_tokens = item.get("total_input_tokens")
        output_tokens = item.get("total_output_tokens")

        elements.append(
            models.AgentSessionTokenUsageElement(
                session_id=item["session_id"],
                status=item["status"],
                started_at=item.get("started_at"),
                end_time=item.get("end_time"),
                duration_ms=item.get("duration_ms"),
                total_input_tokens=input_tokens,
                total_output_tokens=output_tokens,
                total_tokens=(input_tokens or 0) + (output_tokens or 0),
            )
        )

    elements.sort(key=lambda e: (e.started_at is None, e.started_at))

    return models.GetAgentSessionTokenUsageResponse(root=elements)


async def describe_session_token_usage(
    ctx: Annotated[Context, Field(description="The FastMCP Context object")],
    session_id: Annotated[
        str,
        Field(description="The session ID to break down per inference turn"),
    ],
) -> models.DescribeSessionTokenUsageResponse:
    """
    Break down a single agent session's token usage per inference turn.

    Fetches the session's raw event messages and filters to inference turns
    (inference-succeeded, inference-failed), returning one entry per turn
    along with an aggregated summary. Non-inference events (tool calls,
    status transitions) are excluded from the breakdown.

    Args:
        ctx (Context): The FastMCP Context object.
        session_id (str): The session ID to break down per inference turn.

    Returns:
        models.DescribeSessionTokenUsageResponse: Summary and per-turn
            breakdown with the following fields:
            - summary.session_id, summary.turn_count
            - summary.total_duration_ms, summary.total_input_tokens,
              summary.total_output_tokens, summary.total_tokens (all
              missing values treated as 0)
            - turns[].sequence_number, turns[].timestamp,
              turns[].event_type ("succeeded" or "failed"),
              turns[].duration_ms, turns[].token_usage (succeeded only),
              turns[].error (failed only)

    Raises:
        Exception: Service-layer errors from get_session_messages propagate
            uncaught.

    Notes:
        - tokenUsage field names are unconfirmed against a live platform;
          see _extract_token_usage for the candidate-key extraction logic.
        - A session with zero inference turns returns a zeroed summary and
          an empty turns list, not an error.
    """
    await ctx.debug("inside describe_session_token_usage(...)")

    client = ctx.request_context.lifespan_context.get("client")

    raw_messages = await client.agent_session_manager.get_session_messages(session_id)

    turns = []
    for raw in raw_messages:
        raw_type = raw.get("type")
        if raw_type not in ("inference-succeeded", "inference-failed"):
            continue

        timestamp = raw.get("timestamp")
        if isinstance(timestamp, int):
            timestamp = timeutils.epoch_to_timestamp(timestamp)

        data = raw.get("data") or {}
        event_type = raw_type.removeprefix("inference-")

        token_usage = None
        error = None
        if raw_type == "inference-succeeded":
            token_usage = _extract_token_usage(data.get("tokenUsage") or {})
        else:
            # The swagger's data object for inference-failed events only
            # documents durationMs (no errorMessage) — the error is assumed
            # to be in the message's text field per its "text content or
            # error message" description. Confirm against a live
            # inference-failed event before merge.
            error = raw.get("text")

        turns.append(
            models.SessionTurnUsageElement(
                sequence_number=raw.get("sequenceNumber"),
                timestamp=timestamp,
                event_type=event_type,
                duration_ms=data.get("durationMs"),
                token_usage=token_usage,
                error=error,
            )
        )

    total_duration = sum(t.duration_ms or 0 for t in turns)
    total_input = sum(
        (t.token_usage.input_tokens or 0) if t.token_usage else 0 for t in turns
    )
    total_output = sum(
        (t.token_usage.output_tokens or 0) if t.token_usage else 0 for t in turns
    )

    summary = models.SessionTurnUsageSummary(
        session_id=session_id,
        turn_count=len(turns),
        total_duration_ms=total_duration,
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_tokens=total_input + total_output,
    )

    return models.DescribeSessionTokenUsageResponse(summary=summary, turns=turns)
