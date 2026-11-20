"""MkDocs hook: build site pages from files at the top of the repo, so the repo and the
site say the same thing: the home page from README.md, Contributing from CONTRIBUTING.md.
Their links are rewritten for the site (docs/x.md -> x.md, the other top-level page ->
its site page, other repo files -> GitHub)."""
import os
import re

from mkdocs.structure.files import File

REPO = "https://github.com/bobbysaba/atmo3d/blob/master/"
PAGES = {"README.md": "index.md", "CONTRIBUTING.md": "contributing.md"}


def _link(m):
    target = m.group(1)
    if re.match(r"[a-z]+:|#", target):
        return m.group(0)
    if target.startswith("docs/"):
        return f"]({target[5:]})"
    path, _, anchor = target.partition("#")
    if path in PAGES:
        return f"]({PAGES[path]}{'#' + anchor if anchor else ''})"
    return f"]({REPO}{target})"


def on_files(files, config):
    root = os.path.dirname(config.config_file_path)
    for source, page in PAGES.items():
        with open(os.path.join(root, source)) as f:
            text = re.sub(r"\]\(([^)]+)\)", _link, f.read())
        files.append(File.generated(config, page, content=text))
    return files
