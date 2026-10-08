"""Copy current source changes into the Ubuntu workspace with canonical text endings."""

import argparse
import subprocess
from pathlib import Path


def git_paths(root: Path, *arguments: str) -> list[str]:
    return list(
        filter(
            None,
            subprocess.check_output(
                ["git", "-c", "core.safecrlf=false", *arguments, "-z"], cwd=root
            )
            .decode()
            .split("\0"),
        )
    )


def copy_changes(source: Path, target: Path, *, repair_initial_copy: bool = False) -> None:
    changed = set(git_paths(source, "diff", "--name-only", "HEAD"))
    changed.update(git_paths(source, "ls-files", "--others", "--exclude-standard"))
    if repair_initial_copy:
        for name in git_paths(source, "ls-files", "--cached"):
            if name not in changed:
                destination = target / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(
                    subprocess.check_output(["git", "show", f"HEAD:{name}"], cwd=target)
                )
    for name in changed:
        original, destination = source / name, target / name
        if not original.is_file():
            continue
        content = original.read_bytes()
        if not name.startswith("docs/evidence/") and b"\0" not in content[:8192]:
            content = content.replace(b"\r\n", b"\n")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    print(f"Copied {len(changed)} source changes to {target}; ignored artifacts preserved.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=Path.home() / "secure-agent-platform")
    parser.add_argument("--repair-initial-copy", action="store_true")
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[2]
    target = args.target.resolve()
    if not (target / ".git").is_dir() or not target.is_relative_to(Path.home()):
        raise SystemExit("Expected a project working copy inside the Ubuntu home directory")
    copy_changes(source, target, repair_initial_copy=args.repair_initial_copy)


if __name__ == "__main__":
    main()
