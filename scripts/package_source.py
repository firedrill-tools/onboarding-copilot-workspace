"""Complete deterministic monorepo source, independent of installed caches/Git."""

import argparse
import gzip
import hashlib
import io
import json
import tarfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = tomllib.loads((ROOT / "backend/pyproject.toml").read_text())["project"][
    "version"
]
PREFIX = f"onboarding-copilot-workspace-{VERSION}"
ROOTS = (
    "backend/src",
    "backend/data",
    "backend/fixtures",
    "backend/tests",
    "backend/pyproject.toml",
    "backend/uv.lock",
    "backend/README.md",
    "backend/AGENTS.md",
    "frontend/app",
    "frontend/e2e",
    "frontend/AGENTS.md",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/playwright.config.ts",
    "frontend/tsconfig.json",
    "frontend/next.config.ts",
    "frontend/next-env.d.ts",
    "fixtures",
    "scenarios",
    "scripts",
    ".github",
    "README.md",
    "AGENTS.md",
    "PLAN.md",
    "COMPATIBILITY.md",
    ".gitignore",
    ".env.example",
)


def source_files():
    result = []
    for name in ROOTS:
        path = ROOT / name
        if not path.exists():
            raise ValueError(f"missing source input {name}")
        if path.is_symlink():
            raise ValueError("source inputs must not be aliases")
        for candidate in sorted(path.rglob("*")) if path.is_dir() else [path]:
            if "__pycache__" in candidate.parts or candidate.suffix == ".pyc":
                continue
            if candidate.is_symlink():
                raise ValueError("source inputs must not be aliases")
            if candidate.is_file():
                result.append(candidate)
    return sorted(result, key=lambda path: path.relative_to(ROOT).as_posix())


def build(destination=None):
    manifest = {
        "schema_version": 1,
        "project": "onboarding-copilot-workspace",
        "version": VERSION,
        "files": [
            {
                "path": p.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "bytes": p.stat().st_size,
                "mode": 0o755 if p.stat().st_mode & 0o111 else 0o644,
            }
            for p in source_files()
        ],
    }
    memory = io.BytesIO()
    with tarfile.open(fileobj=memory, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        entries = [
            (row["path"], (ROOT / row["path"]).read_bytes(), row["mode"])
            for row in manifest["files"]
        ]
        entries.append(
            (
                "source-manifest.json",
                (json.dumps(manifest, indent=2) + "\n").encode(),
                0o644,
            )
        )
        for path, raw, mode in entries:
            item = tarfile.TarInfo(f"{PREFIX}/{path}")
            item.size, item.mode = len(raw), mode
            item.uid = item.gid = item.mtime = 0
            item.uname = item.gname = ""
            archive.addfile(item, io.BytesIO(raw))
    output = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as compressed:
        compressed.write(memory.getvalue())
    raw = output.getvalue()
    destination = (
        Path(destination) if destination else ROOT / "dist" / f"{PREFIX}-source.tar.gz"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
    return {
        "path": str(destination),
        "files": len(manifest["files"]),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    print(json.dumps(build(parser.parse_args().output)))
