"""CLI smoke tests.

Typer resolves parameter annotations at runtime, so a type that is only
imported under ``TYPE_CHECKING`` blows up when the command is registered.
These tests exercise every command's help path to catch that.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from cpy_download.cli import app

runner = CliRunner()


@pytest.mark.parametrize("command", ["grab", "copy", "version"])
def test_command_help(command: str) -> None:
    result = runner.invoke(app, [command, "--help"])
    assert result.exit_code == 0, result.output


def test_root_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    for command in ("grab", "copy", "version"):
        assert command in result.output


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0, result.output
    assert "cpydl" in result.output
