"""Build and install the Rust shared library for this Python checkout."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--debug", action="store_true", help="Build the development profile")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    command = ["cargo", "build", "--locked", "--manifest-path", str(root / "native/Cargo.toml"),
               "--message-format=json-render-diagnostics"]
    if not args.debug:
        command.append("--release")
    # Read Cargo's artifact paths instead of guessing CARGO_TARGET_DIR/target triples.
    result = subprocess.run(command, cwd=root, text=True, stdout=subprocess.PIPE)
    artifact = None
    for line in result.stdout.splitlines():
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if message.get("reason") == "compiler-artifact" and message["target"]["name"] == "factcheck_core":
            artifact = next((Path(name) for name in message["filenames"]
                             if Path(name).suffix in (".so", ".dylib", ".dll")), artifact)
    if result.returncode:
        raise SystemExit(result.returncode)
    if artifact is None:
        raise SystemExit("Cargo did not produce the factcheck-core shared library.")
    destination = root / "backend/_native"
    destination.mkdir(exist_ok=True)
    # Atomic replacement avoids truncating a library mapped by a running process.
    with tempfile.NamedTemporaryFile(dir=destination, delete=False) as output:
        temporary = Path(output.name)
    try:
        shutil.copyfile(artifact, temporary)
        os.replace(temporary, destination / artifact.name)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Installed {artifact.name}. Restart the backend after rebuilding.")


if __name__ == "__main__":
    main()
