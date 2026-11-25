"""The "Your fields" editor (a tab of the settings window): the user's fields file
(core.userfields.fields_path) as text, checked as it is typed against the open run, and
saved and applied at once (core.userfields.reload: every open run's fields, then this
page's menus and views through on_applied)."""

import html
import os

import panel as pn

from ..core import userfields as U
from ..theme import CSS

OK, ERR, WARN = "#4ade80", "#f87171", "#f59e0b"
_MONO = ("textarea { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "
         "monospace; font-size: 12.5px; line-height: 1.45; }")

# examples the Add select appends ({name} is made unique)
EXAMPLES = {
    "A unit conversion": '''
[fields.{name}]
label = "Temperature"
units = "°F"
expr  = "tempc * 9/5 + 32"
''',
    "A layer mean": '''
[fields.{name}]
label = "Mean updraft 0–3 km"
units = "m/s"
expr  = "layer_mean(maximum(w, 0), 0, 3)"
''',
    "A layer integral": '''
[fields.{name}]
label = "Vertically integrated rain 0–6 km"
units = "g/kg m"
expr  = "layer_integral(qr, 0, 6)"
''',
    "Values at two heights": '''
[fields.{name}]
label = "Lapse rate 1–3 km"
units = "K/km"
expr  = "(at_height(tempc, 1) - at_height(tempc, 3)) / 2"
''',
    "A layer maximum": '''
[fields.{name}]
label = "Max vertical vorticity 0–2 km"
units = "1/s"
expr  = "layer_max(zvort, 0, 2)"
diverging = true
''',
}
_PICK = "Add an example…"


def _html(text="", **kw):
    return pn.pane.HTML(text, stylesheets=[CSS], **kw)


def _note(text, color=None):
    col = f' style="color:{color}"' if color else ""
    return f'<div class="cv-hint"{col}>{text}</div>'


def unique_name(text, base):
    """base, or base2, base3, ...: a [fields.<name>] not in `text` yet."""
    n, k = base, 1
    while f"[fields.{n}]" in text:
        k += 1
        n = f"{base}{k}"
    return n


def report(text, F=None):
    """(ok, html) of fields-file text: whether it can be saved (it is TOML of
    [fields.<name>] tables), and a line for each field: what it is on run F's data
    (fields F: the open run's, or None: definitions checked alone), or why it cannot
    be made."""
    defs, problem = U.parse_text(text)
    if problem:
        return False, _note(f"Not TOML atmo3d can read, so not saved: "
                            f"{html.escape(problem)}", ERR)
    if not defs:
        return True, _note("No fields yet: add one with the select above, or write a "
                           "<code>[fields.&lt;name&gt;]</code> table.")
    made, off = ({}, {}) if F is None else F.bind_user(defs, mark=False)
    made = {d.name: d for d in made} if F is not None else {}
    why = {u["name"]: w for u, w in off} if F is not None else {}
    rows = []
    for d in defs:
        name = html.escape(d["name"])
        if d["error"]:
            rows.append(f'<span style="color:{ERR}">✗ <b>{name}</b>: '
                        f'{html.escape(d["error"])}</span>')
        elif F is None:
            rows.append(f'<span style="color:{OK}">✓ <b>{name}</b></span> '
                        f'{html.escape(d["label"])}')
        elif d["name"] in made:
            fd = made[d["name"]]
            if fd.column:
                z0, z1 = fd.layer
                top = "the model top" if z1 is None else f"{z1:g} km"
                kind = f"column field (2D, reads {max(z0, 0):g} km to {top})"
            else:
                kind = f"{fd.ndim}D field"
            rows.append(f'<span style="color:{OK}">✓ <b>{name}</b></span> '
                        f'{html.escape(d["label"])} · {kind}')
        else:
            rows.append(f'<span style="color:{WARN}">– <b>{name}</b>: not on this run: '
                        f'{html.escape(why.get(d["name"], "left out"))}</span>')
    return True, _note("<br>".join(rows))


class FieldsEditor:
    """`body`: the editor.  fields_of(): the open run's Fields (None: no run, on the
    landing page); on_applied(): after a save, once every run has the new fields."""

    def __init__(self, fields_of=None, on_applied=None):
        self.fields_of, self.on_applied = fields_of, on_applied
        self.path_html = _html()
        self.text = pn.widgets.TextAreaInput(sizing_mode="stretch_width", height=330,
                                             stylesheets=[_MONO])
        self.add = pn.widgets.Select(options=[_PICK, *EXAMPLES], value=_PICK, width=220,
                                     margin=(4, 10))
        self.save_btn = pn.widgets.Button(name="Save and apply", button_type="primary",
                                          width=150)
        self.revert_btn = pn.widgets.Button(
            name="Revert", button_type="light", button_style="outline", width=90,
            description="Put back the file as it is saved")
        self.check = _html(margin=(4, 10), styles={"max-height": "180px",
                                                   "overflow-y": "auto"})
        self.msg = _html(margin=(4, 10))
        help_ = _note(
            "One <code>[fields.&lt;name&gt;]</code> table per field, its <code>expr</code> "
            "an expression of the run's fields in the units the viewer shows. Layer "
            "functions make a 2D column field: <code>layer_mean(x, z0, z1)</code>, "
            "<code>layer_integral</code>, <code>layer_max</code>, <code>layer_min</code> "
            "(km above ground, <code>top</code>: the model top) and "
            "<code>at_height(x, z)</code>. Saving applies them at once, in every menu.")
        self.body = pn.Column(self.path_html, help_, pn.Row(self.add), self.text,
                              self.check, pn.Row(self.save_btn, self.revert_btn),
                              self.msg, margin=0, sizing_mode="stretch_width")
        self._typed = ""  # (the text as last typed or set: value_input lags a set value)
        self.text.param.watch(self._on_text, ["value_input", "value"])
        self.add.param.watch(self._on_add, "value")
        self.save_btn.on_click(self._save)
        self.revert_btn.on_click(lambda e: self.load())

    def _fields(self):
        try:
            return self.fields_of() if self.fields_of is not None else None
        except Exception:  # noqa: BLE001  (no run: definitions checked alone)
            return None

    def load(self):
        """Show the file as saved (when the tab opens; Revert)."""
        path = U.fields_path()
        there = os.path.isfile(path)
        self.path_html.object = _note(
            f"<code>{html.escape(path)}</code>" + ("" if there else
                                                   " (not written yet: Save makes it)"))
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read() if there else ""
        except (OSError, UnicodeDecodeError) as e:
            text = ""
            self.msg.object = _note(f"Could not read it: {html.escape(str(e))}", ERR)
        else:
            self.msg.object = ""
        self.text.value = text
        self._check()

    def _on_text(self, ev):
        self._typed = ev.new or ""
        self._check()

    def _current(self):
        return self._typed

    def _check(self):
        ok, rows = report(self._current(), self._fields())
        self.check.object = rows
        self.save_btn.disabled = not ok

    def _on_add(self, ev):
        if ev.new == _PICK:
            return
        text = self._current().rstrip("\n")
        name = unique_name(text, "my_field")
        self.text.value = (text + "\n" if text else "") + EXAMPLES[ev.new].format(name=name)
        self.add.value = _PICK
        self.msg.object = _note(f"Added <b>{name}</b> at the end: rename it and edit its "
                                "expression, then Save and apply.")

    def _save(self, ev=None):
        text = self._current()
        try:
            path = U.write_file(text)
        except (OSError, ValueError) as e:
            self.msg.object = _note(f"Not saved: {html.escape(str(e))}", ERR)
            return
        self.text.value = text
        problems = U.reload()
        note = f"Saved to <code>{html.escape(path)}</code> and applied."
        if problems:
            note += " " + html.escape("; ".join(problems))
        if self.on_applied is not None:
            try:
                self.on_applied()
            except Exception as e:  # noqa: BLE001  (saved and bound: the page says why)
                note += f" The page could not redraw: {html.escape(str(e))}"
        self.msg.object = _note(note, OK if not problems else WARN)
        self._check()
