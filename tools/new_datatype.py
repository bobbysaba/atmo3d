#!/usr/bin/env python
"""Start a new atmo3d data type: a copy of the worked example (packages/example) under a
new name, with its tests.

    python tools/new_datatype.py mpas --label "MPAS"            # in this repository
    python tools/new_datatype.py mpas --label "MPAS" --out DIR  # a package of your own

In this repository it writes
    packages/<name>/                 pyproject.toml (atmo3d-<name>, its entry point),
                                     README.md, src/atmo3d_<name>/ (the example's
                                     modules, renamed)
    tests/<name>/test_<name>.py      the contract check on the synthetic run, and on a
                                     real one with pytest -m real (ATMO3D_<NAME>_ROOT);
                                     tests/<name>/ holds the package's tests
and adds a commented line for the package's owners to .github/CODEOWNERS.  It prints
what is left to do by hand (CI, the environment, the root pyproject).

With --out DIR it writes DIR/atmo3d-<name>/, a package of its own: the same, with the
test under its own tests/ and pytest's settings in its pyproject.toml.  Nothing in this
repository changes.

The copy reads the example's layout (gridded netCDF with named x, y, z and time) and
passes atmo3d.testing.check_datatype as it is; its comments describe that layout until
you change them.  Then adapt, in order: model.PATTERN, run.py's constants (and _info,
TimeView if your files differ more), catalog.py, synthetic.py to your files' layout, and
the tests.  https://bobbysaba.com/docs/atmo3d/extend/data-types/ is the contract.

It writes nothing outside the new files and the CODEOWNERS line, and refuses a name in use."""

import argparse
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# keys and names a new data type cannot take
TAKEN = {"core", "example", "cm1", "wofs", "radar", "auto", "atmo3d"}
SKIP = ("__pycache__", ".egg-info", ".pyc")


def camel(name):
    return "".join(p[:1].upper() + p[1:] for p in name.split("_"))


def renames(name, label):
    """(old, new) text replacements, in order: the example's names to the new type's."""
    c = camel(name)
    return [
        ('"Example (gridded netCDF)"', repr_str(label)),  # Model.label
        ('"Example gridded netCDF"', repr_str(label)),    # Run.model_label
        ("atmo3d_example", f"atmo3d_{name}"),
        ("atmo3d-example", f"atmo3d-{name}"),
        ("test_example.py", f"test_{name}.py"),
        ("--demo example", f"--demo {name}"),
        ("atmo3d example:", f"atmo3d {name}:"),
        ("ExampleRun", f"{c}Run"),
        (re.compile(r"\bExample\b"), c),
        ('"example"', f'"{name}"'),
        ('\nexample = "', f'\n{name} = "'),  # (the entry point)
    ]


def repr_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def rename(text, name, label):
    for old, new in renames(name, label):
        text = old.sub(new, text) if isinstance(old, re.Pattern) else text.replace(old, new)
    return text


INIT_DOC = '''"""atmo3d data type: {label} (key "{name}").

Started by tools/new_datatype.py as a copy of packages/example, the worked example:
until they are changed, its comments describe the example's layout (gridded netCDF with
named x, y, z and time), not this data type's files.  Every file says what is REQUIRED
and what is optional.

  model.py      the Model: is a folder one of these runs, how many times, how to open it
  catalog.py    the field catalog: the files' names, how they show, the roles
  run.py        the reader: a core.run.Run subclass
  synthetic.py  writes a small run with known values, for the tests

The contract is at https://bobbysaba.com/docs/atmo3d/extend/data-types/; atmo3d.testing.check_datatype checks it.
"""'''

README = """# atmo3d-{name}

The {label} data type for atmo3d. Started from atmo3d's worked example
(`packages/example`) by `tools/new_datatype.py`.

    pip install -e .        # in this folder, in atmo3d's environment: then atmo3d finds it

and from {where}:

    pytest {tests}            # the contract check on the synthetic run
    ATMO3D_{NAME}_ROOT=/path/to/run pytest -m real {tests}
"""

TEST = '''"""Tests of the {label} data type (atmo3d_{name}): the contract check
(atmo3d.testing.check_datatype) on its synthetic run, and on a real run when asked:

    ATMO3D_{NAME}_ROOT=/path/to/a/run pytest -m real {where}

(on a real run of a large grid, on a compute node).  Written by tools/new_datatype.py;
add tests of the reads here, checked against the formulas of atmo3d_{name}.synthetic, as
atmo3d's tests/example/test_example.py does for the example."""
import os

import pytest

from atmo3d.core import catalog, models
from atmo3d.testing import check_datatype

KEY = "{name}"


@pytest.fixture(scope="module")
def registered():
    """The data type, as its entry point registers it once the package is installed
    (pip install -e); registered here (and taken out afterwards) when it is not."""
    import atmo3d_{name}
    ours = KEY not in models.MODELS
    if ours:
        atmo3d_{name}.register()
    yield
    if ours:
        dict.pop(models.MODELS, KEY, None)
        catalog.CATALOGS.pop(KEY, None)


@pytest.fixture(scope="module")
def synthetic_folder(registered, tmp_path_factory):
    from atmo3d_{name} import synthetic
    folder = str(tmp_path_factory.mktemp(KEY) / "run")
    synthetic.write(folder)
    return folder


def test_contract(synthetic_folder):
    check_datatype(KEY, synthetic_folder)


@pytest.mark.real
def test_contract_real(registered):
    root = os.environ.get("ATMO3D_{NAME}_ROOT")
    if not root:
        pytest.skip("set ATMO3D_{NAME}_ROOT to a run folder")
    check_datatype(KEY, root)
'''

PYTEST_OUT = '''
[project.optional-dependencies]
test = ["pytest>=8"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-m 'not real'"
markers = ["real: checks on your own run, ATMO3D_{NAME}_ROOT=/path (pytest -m real)"]
'''

CODEOWNERS = ("# {name}: uncomment with its owners' GitHub names after Bobby's\n"
              "# /packages/{name}/          @bobbysaba @<their-github-name>\n")


def check_name(name):
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,30}", name) or name.endswith("_"):
        sys.exit(f"name {name!r}: lowercase letters, digits and _, starting with a letter "
                 f"(it becomes the key, atmo3d_{name} and atmo3d-{name})")
    if name in TAKEN:
        sys.exit(f"name {name!r} is taken (not one of {', '.join(sorted(TAKEN))})")


def copy_package(example, dest, name, label):
    """The example's package files (from the folder `example`), renamed, into dest
    (which must not exist); returns the text of its pyproject.toml."""
    src_pkg = os.path.join(example, "src", "atmo3d_example")
    dst_pkg = os.path.join(dest, "src", f"atmo3d_{name}")
    os.makedirs(dst_pkg)
    for f in sorted(os.listdir(src_pkg)):
        if f.endswith(".py"):
            text = rename(_read(os.path.join(src_pkg, f)), name, label)
            if f == "__init__.py":
                text = re.sub(r'\A""".*?"""', lambda _: INIT_DOC.format(name=name, label=label),
                              text, count=1, flags=re.S)
            _write(os.path.join(dst_pkg, f), text)
    py = rename(_read(os.path.join(example, "pyproject.toml")), name, label)
    py = re.sub(r"\A(#[^\n]*\n)+", f"# atmo3d data type: {label}.  Started from atmo3d's "
                f"packages/example (tools/new_datatype.py).\n", py)
    py = re.sub(r"^authors = .*$", 'authors = [{ name = "<your name>" }]  # REQUIRED: you',
                py, flags=re.M)
    py = re.sub(r'^description = ".*"$', f'description = {repr_str("atmo3d data type: " + label)}',
                py, flags=re.M)
    return py


def leftovers(folder):
    """Files under folder that still name the example (the renames missed them)."""
    bad = []
    for dirpath, _, files in os.walk(folder):
        for f in files:
            if f.endswith((".py", ".toml", ".md")):
                t = _read(os.path.join(dirpath, f))
                if re.search(r'atmo3d[_-]example|"example"|\bExample(Run)?\b', t):
                    bad.append(os.path.join(dirpath, f))
    return bad


def main(argv=None, root=ROOT):
    """The command (root: the repository, for the tests).  Returns the package's folder."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", help="the data type's key: lowercase, e.g. mpas")
    ap.add_argument("--label", help="its name in lists (default: the name in capitals)")
    ap.add_argument("--out", help="write a package of its own under this folder, not "
                                  "into this repository")
    a = ap.parse_args(argv)
    name, label = a.name, a.label or a.name.upper()
    check_name(name)
    NAME = name.upper()

    if a.out:
        dest = os.path.join(os.path.abspath(a.out), f"atmo3d-{name}")
        test_dir = os.path.join(dest, "tests")
    else:
        dest = os.path.join(root, "packages", name)
        test_dir = os.path.join(root, "tests", name)
    tests = f"tests/test_{name}.py" if a.out else f"tests/{name}"
    test_file = os.path.join(test_dir, f"test_{name}.py")
    for p in (dest, test_file):
        if os.path.exists(p):
            sys.exit(f"{p} exists: choose another name, or remove it first")

    try:
        py = copy_package(os.path.join(root, "packages", "example"), dest, name, label)
        if a.out:
            py += PYTEST_OUT.format(NAME=NAME)
        _write(os.path.join(dest, "pyproject.toml"), py)
        _write(os.path.join(dest, "README.md"),
               README.format(name=name, NAME=NAME, label=label, tests=tests,
                             where="the package's folder" if a.out
                             else "the repository's folder"))
        os.makedirs(test_dir, exist_ok=True)
        _write(test_file, TEST.format(name=name, NAME=NAME, label=label, where=tests))
    except BaseException:
        shutil.rmtree(dest, ignore_errors=True)
        if os.path.exists(test_file):
            os.remove(test_file)
        if not a.out and os.path.isdir(test_dir) and not os.listdir(test_dir):
            os.rmdir(test_dir)
        raise
    bad = leftovers(dest)
    if bad:
        print("note: these still name the example; check them:", *bad, sep="\n  ")

    if a.out:
        print(f"wrote {dest}\n\nnext:\n"
              f"  cd {dest}\n"
              f"  pip install -e .     (in the environment atmo3d is installed in)\n"
              f"  pytest\n"
              f"  then adapt it to your files: model.py PATTERN, run.py, catalog.py, "
              f"synthetic.py (https://bobbysaba.com/docs/atmo3d/extend/data-types/)")
        return dest

    owners = os.path.join(root, ".github", "CODEOWNERS")
    if os.path.isfile(owners):
        with open(owners, "a", encoding="utf-8") as f:
            f.write(CODEOWNERS.format(name=name))
    rel = os.path.relpath(dest, root)
    print(f"""wrote {rel}/, tests/{name}/test_{name}.py; a commented line in .github/CODEOWNERS

next:
  pytest tests/{name}                  (passes as it is: the example's layout)
  adapt it to your files: model.py PATTERN, run.py, catalog.py, synthetic.py, the tests
  (https://bobbysaba.com/docs/atmo3d/extend/data-types/ is the contract)

before the pull request, by hand:
  .github/workflows/tests.yml   a '{name}' filter ('{rel}/**', 'tests/{name}/**'),
                                its line in "Pick the tests", -e {rel} in the install step
  environment.yml               - -e ./{rel}
  pyproject.toml (root)         "atmo3d-{name}" in dependencies
  .github/CODEOWNERS            uncomment the line, with the package's owners""")
    return dest


def _read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def _write(p, text):
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)


if __name__ == "__main__":
    main()
