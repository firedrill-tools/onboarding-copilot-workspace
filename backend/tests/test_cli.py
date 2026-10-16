import json
import os
import subprocess
import sys
from pathlib import Path


def cli(args, cwd):
    env = dict(os.environ)
    for key in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GEMINI_MODEL"):
        env.pop(key, None)
    return subprocess.run(
        [sys.executable, "-m", "onboarding_workspace", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_model_free_cli_initializes_reads_resets_every_private_case_outside_checkout(
    tmp_path,
):
    listed = cli(["datasets"], tmp_path)
    assert listed.returncode == 0, listed.stderr
    cases = json.loads(listed.stdout)
    assert len(cases) == 12
    for case in cases:
        file = tmp_path / (case["id"] + ".json")
        created = cli(
            ["init", "--workspace", str(file), "--case", case["id"]], tmp_path
        )
        assert created.returncode == 0, created.stdout + created.stderr
        original = file.read_bytes()
        details = json.loads(
            cli(["workspace", "--workspace", str(file)], tmp_path).stdout
        )
        assert details["original_seed_match"] and file.stat().st_mode & 0o777 == 0o600
        fresh = cli(
            [
                "reset",
                "--workspace",
                str(file),
                "--destination",
                str(file) + ".fresh.json",
            ],
            tmp_path,
        )
        assert (
            fresh.returncode == 0
            and json.loads(fresh.stdout)["instance_id"]
            != json.loads(created.stdout)["instance_id"]
        )
        assert file.read_bytes() == original


def test_cli_collision_and_missing_source_do_not_repair_or_overwrite(tmp_path):
    file = tmp_path / "state.json"
    assert cli(["init", "--workspace", str(file)], tmp_path).returncode == 0
    before = file.read_bytes()
    assert (
        cli(["init", "--workspace", str(file)], tmp_path).returncode == 1
        and file.read_bytes() == before
    )
    Path(str(file) + ".source.json").unlink()
    assert (
        cli(["workspace", "--workspace", str(file)], tmp_path).returncode == 1
        and file.read_bytes() == before
    )
