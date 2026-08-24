#!/usr/bin/env python3
"""Compatibility entrypoint for the luucycle roster validator."""

from __future__ import annotations

from roster import legacy_check_main


if __name__ == "__main__":
    raise SystemExit(legacy_check_main())
