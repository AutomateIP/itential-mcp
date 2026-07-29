# Copyright (c) 2025 Itential, Inc
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import asyncio

from .runtime import parse_args
from .core import env
from .core import logging
from .core import heuristics


def run() -> int:
    """
    Main entry point for the application.

    Returns:
        int: The application return code (0 for success, 1 for failure)

    Raises:
        SystemExit: Always exits with the return code
    """
    try:
        handler_func, handler_args, handler_kwargs = parse_args(sys.argv[1:])
        return asyncio.run(handler_func(*handler_args, **handler_kwargs))
    except KeyboardInterrupt:
        logging.info("Application interrupted by user")
        return 130  # Standard exit code for SIGINT
    except SystemExit:
        # Re-raise SystemExit (from argument parsing errors)
        raise
    except Exception as e:
        logging.error(f"Application error: {e}")
        # Always print a clean, single-line error message to stderr. The
        # application logger is pinned above FATAL by default, so this is
        # the only guaranteed-visible error output unless the caller has
        # configured logging explicitly. This message may now carry
        # upstream HTTP response bodies, so it is run through the same
        # sensitive-data redaction pipeline used by core.logging before
        # being printed.
        print(heuristics.scan_and_redact(f"ERROR: {e}"), file=sys.stderr)
        if env.getbool("ITENTIAL_MCP_DEBUG", False):
            import traceback

            traceback.print_exc()
        return 1
