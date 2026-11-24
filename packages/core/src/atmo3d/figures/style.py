"""Figure editor: figure templates (a figure's layout and look, applied to another run), and the
names of the figure styles (Look: Style).

A mixin of the FigureEditor (figures/editor.py)."""

import html
import os

import panel as pn

from . import spec as fg

STYLE_LABELS = {"default": "Default", "ams": "AMS journal", "talk": "Talk", "dark": "Dark"}


class FigureStyle:
    def _build_style(self):
        """The template boxes of the Export dialog."""
        self.tpl_name = pn.widgets.TextInput(name="Template name", placeholder="e.g. 2x3 dbz w")
        self.tpl_sel = pn.widgets.Select(name="Template", options={})
        self._list_templates()

    # ------------------------------------------------------------ templates
    def _list_templates(self):
        try:
            tpls = fg.list_templates()
        except OSError:
            tpls = {}
        keep = self.tpl_sel.value
        self.tpl_sel.options = tpls  # (a Select does not take a value from new options)
        self.tpl_sel.value = keep if keep in tpls.values() else next(iter(tpls.values()), None)

    def _save_template(self):
        try:
            path = fg.save_template(self._figure_now(), self.tpl_name.value.strip())
        except (OSError, ValueError) as e:
            self._msg(f"Could not save the template: {html.escape(str(e))}", True)
            return
        self._list_templates()
        self.tpl_sel.value = path
        self._msg(f"Saved the template <code>{html.escape(path)}</code>")

    def _apply_template(self, path):
        """Open a template on this run.  True when it opened."""
        try:
            spec = fg.from_template(fg.load_template(path), self.run, self.v.t)
        except (OSError, ValueError) as e:
            self._msg(f"Could not apply <code>{html.escape(str(path))}</code>: "
                      f"{html.escape(str(e))}", True)
            return False
        note = f"Applied the template <b>{html.escape(os.path.basename(path)[:-5])}</b> to this run"
        if fg.is_doc(spec):
            self.quick.hide()
            self.shell.open_doc(spec, note)
            return True
        return self._open_spec(spec, note)
