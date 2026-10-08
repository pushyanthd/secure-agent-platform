"""Inspect built artifacts and exercise the installed wheel outside the source checkout."""

import argparse
import hashlib
import json
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    directory = args.dist.resolve()
    wheels, sources = list(directory.glob("*.whl")), list(directory.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1:
        parser.error("Expected one wheel and one source distribution in a fresh directory")
    with zipfile.ZipFile(wheels[0]) as wheel:
        names = set(wheel.namelist())
        required = {
            "agentguard/cli.py",
            "agentguard/artifact_volume.py",
            "agentguard/bounded_storage.py",
            "agentguard/ui/index.html",
        }
        if not required <= names:
            parser.error("Wheel lacks the CLI, quota implementation or built console")
        if not any(n.startswith("agentguard/ui/assets/") and n.endswith(".js") for n in names):
            parser.error("Built console assets are missing")
    with tarfile.open(sources[0]) as source:
        entries = {Path(name).parts[1:] for name in source.getnames()}
        if ("uv.lock",) not in entries or ("docs", "release-notes.md") not in entries:
            parser.error("Source archive lacks the lockfile or declared release scope")
        forbidden = {"artifacts", "node_modules", ".venv"}
        if any(forbidden.intersection(parts) for parts in entries):
            parser.error("Source archive includes local runtime artifacts")
        for document in (ROOT / "docs").rglob("README.md"):
            if document.is_file() and document.relative_to(ROOT).parts not in entries:
                relative = document.relative_to(ROOT)
                parser.error(f"Source archive omits portfolio evidence: {relative}")
    uv = shutil.which("uv") or str(ROOT / ".venv/bin/uv")
    with tempfile.TemporaryDirectory(prefix="agentguard-package-") as temporary:
        sandbox = Path(temporary)
        environment = sandbox / "env"
        subprocess.run([uv, "venv", str(environment)], check=True, cwd=sandbox)
        python = environment / "bin/python"
        requirements = sandbox / "runtime.txt"
        with requirements.open("w") as stream:
            subprocess.run(
                [
                    uv,
                    "export",
                    "--locked",
                    "--no-dev",
                    "--no-emit-project",
                    "--format",
                    "requirements-txt",
                ],
                check=True,
                cwd=ROOT,
                stdout=stream,
            )
        subprocess.run(
            [uv, "pip", "install", "--python", str(python), "-r", str(requirements)],
            check=True,
            cwd=sandbox,
        )
        subprocess.run(
            [uv, "pip", "install", "--python", str(python), "--no-deps", str(wheels[0])],
            check=True,
            cwd=sandbox,
        )
        subprocess.run(
            [str(python), "-I", "-m", "agentguard.cli", "--help"],
            check=True,
            cwd=sandbox,
            stdout=subprocess.DEVNULL,
        )
        subprocess.run(
            [
                str(python),
                "-I",
                "-m",
                "agentguard.cli",
                "control-init",
                "--fixture",
                "--directory",
                str(sandbox / "control"),
            ],
            check=True,
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
        )
        # Initialization requires repository fixtures. -I ensures only the
        # installed wheel is imported, including when cwd is the repository.
        code = (
            "from pathlib import Path; import agentguard; "
            "from agentguard.control_setup import ControlSettings, prepare_control; "
            f"assert Path(agentguard.__file__).is_relative_to({str(environment)!r}); "
            f"settings_path=Path({str(sandbox / 'control/settings.json')!r}); "
            "s=ControlSettings.model_validate_json(settings_path.read_bytes()); "
            "c,w=prepare_control(s); assert c.mode=='authored_fixture'; "
            "assert w.run_once() is None"
        )
        subprocess.run([str(python), "-I", "-c", code], check=True, cwd=sandbox)
    shutil.copyfile(ROOT / "docs/release-notes.md", directory / "RELEASE_NOTES.md")
    hashes = {}
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.name != "SHA256SUMS.json":
            with path.open("rb") as stream:
                hashes[path.name] = hashlib.file_digest(stream, "sha256").hexdigest()
    (directory / "SHA256SUMS.json").write_text(json.dumps(hashes, indent=2) + "\n")
    print("PASS: archives, installed CLI, built console and fixture setup; zero model calls.")


if __name__ == "__main__":
    main()
