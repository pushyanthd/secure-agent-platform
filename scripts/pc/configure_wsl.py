"""Create an ignored, machine-local profile for verified Windows CUDA inference."""

import argparse
import json
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--windows-root", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    artifact_root = args.windows_root.resolve()
    profile = json.loads((root / "config/model-mac-medium.json").read_text())
    runtime = json.loads((root / "config/pc-windows-runtime.json").read_text())
    profile["profile"] = "pc-wsl"
    profile["platform"] = "Linux-x86_64"
    profile["runtime"] = runtime | {"format": "windows-cuda-zip"}
    profile["artifact_root"] = str(artifact_root)
    profile["server_model_path"] = subprocess.check_output(
        ["wslpath", "-w", str(artifact_root / "artifacts/models" / profile["model"]["filename"])],
        text=True,
    ).strip()
    destination = root / "artifacts/pc-wsl/model-profile.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if json.loads(destination.read_text()) != profile:
            raise SystemExit("Refusing to replace a different local PC profile")
    else:
        destination.write_text(json.dumps(profile, indent=2) + "\n")
    print(f"PC model profile: {destination}")


if __name__ == "__main__":
    main()
