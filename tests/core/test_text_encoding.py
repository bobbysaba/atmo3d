"""Every text file atmo3d opens says encoding="utf-8".  Without it Python uses the
system's encoding, cp1252 on Windows: saving a figure bundle (its "−" signs) or a storm
file ("ζ") fails there, and a file written on one OS reads garbled on another.  Linux
and macOS default to UTF-8, so only this check catches a missing one there."""
import ast
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCES = [os.path.join(d, f)
           for top in ("packages", "tools")
           for d, _, fs in os.walk(os.path.join(ROOT, top))
           for f in fs if f.endswith(".py")]


def _unencoded(path):
    tree = ast.parse(open(path, encoding="utf-8").read(), path)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        builtin_open = isinstance(f, ast.Name) and f.id == "open"
        path_text = isinstance(f, ast.Attribute) and f.attr in ("read_text", "write_text")
        if not (builtin_open or path_text):
            continue
        if any(k.arg == "encoding" for k in node.keywords):
            continue
        mode = node.args[1] if builtin_open and len(node.args) > 1 else next(
            (k.value for k in node.keywords if k.arg == "mode"), None)
        if isinstance(mode, ast.Constant) and "b" in str(mode.value):
            continue  # (binary)
        if builtin_open and not node.args:
            continue  # (not the builtin: no file named)
        yield f"{os.path.relpath(path, ROOT)}:{node.lineno}"


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: os.path.relpath(p, ROOT))
def test_text_files_are_opened_as_utf8(path):
    bad = list(_unencoded(path))
    assert not bad, "open() / read_text() / write_text() without encoding=: " + ", ".join(bad)
