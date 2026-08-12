"""Generate ignored project secrets without ever displaying their values."""

import argparse
import base64
import os
from pathlib import Path
from typing import Iterable


BOOTSTRAP_NAMES = (
    "primary-admin-password.txt",
    "mqtt-admin-password.txt",
    "development-admin-password.txt",
    "test-admin-password.txt",
    "primary-encoding-key.txt",
    "mqtt-encoding-key.txt",
    "development-encoding-key.txt",
    "test-encoding-key.txt",
    "mysql-root-password.txt",
    "mysql-primary-password.txt",
)

PHASE3_SELECTORS = {
    "mqtt-primary-transmission-password": "mqtt-primary-transmission-password.txt",
    "mqtt-development-engine-password": "mqtt-development-engine-password.txt",
    "mqtt-test-engine-password": "mqtt-test-engine-password.txt",
}

# Existing administrative credentials may be rotated only by an explicit,
# separately allowlisted selector.  Keeping this distinct from --only avoids
# making a normal Phase 3 application-secret invocation capable of replacing a
# bootstrap secret.
ROTATABLE_SELECTORS = {
    "primary-admin-password": "primary-admin-password.txt",
}


def secret_value(filename: str) -> bytes:
    """Return a newline-free cryptographically random secret."""
    raw = os.urandom(32)
    if filename.endswith("encoding-key.txt"):
        return base64.b64encode(raw)
    return base64.urlsafe_b64encode(raw)


def validate_selectors(selectors: Iterable[str]) -> tuple[str, ...]:
    selectors = tuple(selectors)
    if not selectors:
        raise ValueError("at least one --only selector is required")
    if any(not selector for selector in selectors):
        raise ValueError("empty --only selector")
    if len(set(selectors)) != len(selectors):
        raise ValueError("duplicate --only selector")
    unknown = sorted(set(selectors).difference(PHASE3_SELECTORS))
    if unknown:
        raise ValueError(f"unknown --only selector: {unknown[0]}")
    return tuple(PHASE3_SELECTORS[selector] for selector in selectors)


def validate_rotation_selector(selectors: Iterable[str]) -> str:
    """Return the one administrative credential that may be rotated."""
    selectors = tuple(selectors)
    if len(selectors) != 1:
        raise ValueError("exactly one --rotate selector is required")
    selector = selectors[0]
    if not selector:
        raise ValueError("empty --rotate selector")
    if selector not in ROTATABLE_SELECTORS:
        raise ValueError(f"unknown --rotate selector: {selector}")
    return ROTATABLE_SELECTORS[selector]


def write_secret_exclusive(path: Path, value: bytes) -> None:
    """Create one mode-0600 file atomically; never overwrite an existing file."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(value)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(path, 0o600)
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def replace_secret_atomically(path: Path, value: bytes) -> None:
    """Atomically replace one existing mode-0600 secret without printing it."""
    if not path.is_file():
        raise FileNotFoundError(path)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.rotate")
    try:
        write_secret_exclusive(temporary, value)
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--only",
        action="append",
        metavar="SELECTOR",
        help="repeatable Phase 3 allowlisted output selector",
    )
    parser.add_argument(
        "--rotate",
        action="append",
        metavar="SELECTOR",
        help="rotate one explicitly allowlisted existing administrative credential",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    os.umask(0o077)

    if args.only is not None and args.rotate is not None:
        raise SystemExit("error: --only and --rotate cannot be used together")

    try:
        filenames = validate_selectors(args.only) if args.only is not None else BOOTSTRAP_NAMES
        rotation_filename = validate_rotation_selector(args.rotate) if args.rotate is not None else None
    except ValueError as exc:
        raise SystemExit(f"error: {exc}")

    if rotation_filename is not None:
        try:
            replace_secret_atomically(output / rotation_filename, secret_value(rotation_filename))
        except FileNotFoundError:
            raise SystemExit(f"error: refusing to rotate missing secret file: {rotation_filename}")
        print(f"rotated 1 secret file(s): {rotation_filename}")
        return 0

    existing = [name for name in filenames if (output / name).exists()]
    if existing:
        raise SystemExit(f"error: refusing to overwrite existing secret file: {existing[0]}")

    for filename in filenames:
        write_secret_exclusive(output / filename, secret_value(filename))

    # Filenames and count are safe to report; values never leave this process.
    print(f"generated {len(filenames)} secret file(s): {', '.join(filenames)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
