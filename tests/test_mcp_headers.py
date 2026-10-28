"""scripts/mcp_headers.sh, run against a fake gcloud."""

import json
import os
import pathlib
import shutil
import subprocess

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "mcp_headers.sh"
BASH = shutil.which("bash")


@pytest.fixture
def fake_gcloud(tmp_path):
    """A gcloud stand-in that records its arguments and prints a token."""
    log = tmp_path / "args.log"
    gcloud = tmp_path / "bin" / "gcloud"
    gcloud.parent.mkdir()
    gcloud.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > "{log}"\nprintf "%s" "${{FAKE_TOKEN-tok123}}"\n')
    gcloud.chmod(0o755)
    return gcloud, log


def run(args, env=None):
    base = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent"}
    return subprocess.run(
        [BASH, str(SCRIPT), *args], capture_output=True, text=True, env={**base, **(env or {})}
    )


def test_prints_authorization_header_from_active_account(fake_gcloud):
    gcloud, log = fake_gcloud

    result = run(["--gcloud", str(gcloud)])

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"Authorization": "Bearer tok123"}
    assert log.read_text().split() == ["auth", "print-identity-token"]


def test_account_flag_selects_the_gcloud_account(fake_gcloud):
    gcloud, log = fake_gcloud

    run(["--gcloud", str(gcloud), "--account", "me@example.org"])

    assert log.read_text().split() == ["auth", "print-identity-token", "--account", "me@example.org"]


def test_impersonation_uses_the_server_origin_as_audience(fake_gcloud):
    gcloud, log = fake_gcloud

    result = run(
        ["--gcloud", str(gcloud), "--impersonate", "caller@p.iam.gserviceaccount.com"],
        env={"CLAUDE_CODE_MCP_SERVER_URL": "https://mcp-front-abc-uc.a.run.app/mcp"},
    )

    assert result.returncode == 0, result.stderr
    assert log.read_text().split() == [
        "auth",
        "print-identity-token",
        "--impersonate-service-account",
        "caller@p.iam.gserviceaccount.com",
        "--audiences",
        "https://mcp-front-abc-uc.a.run.app",
    ]


def test_impersonation_needs_the_server_url(fake_gcloud):
    gcloud, _ = fake_gcloud

    result = run(["--gcloud", str(gcloud), "--impersonate", "caller@p.iam.gserviceaccount.com"])

    assert result.returncode != 0
    assert "CLAUDE_CODE_MCP_SERVER_URL" in result.stderr


def test_empty_token_fails_instead_of_sending_a_blank_header(fake_gcloud):
    gcloud, _ = fake_gcloud

    result = run(["--gcloud", str(gcloud)], env={"FAKE_TOKEN": ""})

    assert result.returncode != 0
    assert result.stdout == ""


def test_finds_gcloud_in_a_mise_install_when_not_on_path(fake_gcloud, tmp_path):
    gcloud, _ = fake_gcloud
    home = tmp_path / "home"
    mise_bin = home / ".local/share/mise/installs/gcloud/585.0.0/bin"
    mise_bin.mkdir(parents=True)
    os.symlink(gcloud, mise_bin / "gcloud")

    result = run([], env={"HOME": str(home)})

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["Authorization"] == "Bearer tok123"


def test_reports_missing_gcloud(tmp_path):
    result = run([], env={"HOME": str(tmp_path)})

    assert result.returncode != 0
    assert "--gcloud" in result.stderr


def test_points_gcloud_at_a_new_enough_python(fake_gcloud, tmp_path):
    gcloud, _ = fake_gcloud
    gcloud.write_text('#!/bin/sh\nprintf "%s" "$CLOUDSDK_PYTHON"\n')
    home = tmp_path / "home"
    py_bin = home / ".local/share/mise/installs/python/3.13.0/bin"
    py_bin.mkdir(parents=True)
    fake_python = py_bin / "python3"
    fake_python.write_text("#!/bin/sh\nexit 0\n")  # reports a supported version
    fake_python.chmod(0o755)

    result = run(["--gcloud", str(gcloud)], env={"HOME": str(home), "PATH": str(tmp_path / "nopython")})

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"Authorization": f"Bearer {fake_python}"}


def test_keeps_an_explicit_cloudsdk_python(fake_gcloud):
    gcloud, _ = fake_gcloud
    gcloud.write_text('#!/bin/sh\nprintf "%s" "$CLOUDSDK_PYTHON"\n')

    result = run(["--gcloud", str(gcloud)], env={"CLOUDSDK_PYTHON": "/custom/python"})

    assert json.loads(result.stdout) == {"Authorization": "Bearer /custom/python"}
