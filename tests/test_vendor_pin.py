"""Vendored tarballs must still be the bytes we verified before pinning them.

`vendor/PINS.txt` records a content SHA for each vendored source; the Render
build installs those files by name. A filename that carries a commit id looks
like a pin but checks nothing — swap the bytes and the build installs whatever
is there. This test is the crossing between the two.

The failure mode is not hypothetical. organum hit its near-miss the same week:
git's newline normalization rewrote a vendored file on checkout, so their
content SHA held in the working tree and broke only in a clean clone — and it
broke wearing the worst possible face, "our cryptographic test vectors are
corrupt". They warned every house that pins vendored content; this is our
answer to that warning.
"""

from __future__ import annotations

import hashlib
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor"
PINS = VENDOR / "PINS.txt"


def _pins() -> list[tuple[str, str, str, str]]:
    rows = []
    for line in PINS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        assert len(parts) == 4, f"malformed pin row: {line!r}"
        rows.append(tuple(parts))
    return rows


def test_pins_file_is_not_empty():
    """An empty manifest would make every other check below vacuously pass."""
    assert _pins(), "vendor/PINS.txt records no pins — the crossing is not wired"


@pytest.mark.parametrize("name,sha,commit,version", _pins())
def test_vendored_file_matches_its_pinned_content(name, sha, commit, version):
    path = VENDOR / name
    assert path.is_file(), f"{name} is pinned but missing from vendor/"
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    assert actual == sha, (
        f"{name} does not match its pin\n  pinned: {sha}\n  actual: {actual}\n"
        f"Regenerate with `git archive -o vendor/{name} {commit}` from the "
        f"upstream repo, or update PINS.txt if the change is intended."
    )


@pytest.mark.parametrize("name,sha,commit,version", _pins())
def test_pinned_version_is_what_the_tarball_actually_contains(name, sha, commit, version):
    """The manifest names a version; the tarball carries one. Two copies of a
    fact with nothing crossing them drift — that is the whole reason this file
    exists, so it applies to the manifest's own columns too."""
    with tarfile.open(VENDOR / name) as tf:
        member = next((m for m in tf.getmembers()
                       if Path(m.name).name == "pyproject.toml"
                       and Path(m.name).parent.as_posix() in ("", ".")), None)
        assert member is not None, f"{name} has no top-level pyproject.toml"
        text = tf.extractfile(member).read().decode("utf-8")
    declared = next((ln.split("=", 1)[1].strip().strip('"')
                     for ln in text.splitlines()
                     if ln.strip().startswith("version")), None)
    assert declared == version, (
        f"PINS.txt calls {name} version {version}, the tarball declares {declared}"
    )


def test_every_vendored_archive_is_pinned():
    """A new tarball dropped into vendor/ without a pin row is unchecked, which
    is the state this file exists to end."""
    pinned = {row[0] for row in _pins()}
    present = {p.name for p in VENDOR.iterdir()
               if p.is_file() and p.suffixes[-2:] == [".tar", ".gz"]}
    assert present <= pinned, f"unpinned vendored archives: {sorted(present - pinned)}"
