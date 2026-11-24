"""The Phase 2 checkpoint page (docs-dev/figures-ui-plan.md): every place of a figure with a panel
of every kind, each with the generic drawer built from the settings schema, Find over it, and the
document as it changes (with undo).  No run is read: fields are typed, times made up.

    python tools/schema_drawers.py [--port 5007]

then open the printed address (through the SSH tunnel it prints, as for the viewer)."""

import argparse
import json
import socket

import panel as pn

from atmo3d.figures.ui import drawer as D, find, samples


def app():
    host = samples.Host()
    places = samples.places(host.doc)
    pick = pn.widgets.Select(name="Place", options={w: n for n, (w, _, _) in
                                                     enumerate(places)}, size=24, width=330)
    holder = pn.Column(sizing_mode="stretch_width")
    said = pn.pane.HTML(sizing_mode="stretch_width")
    doc_view = pn.pane.JSON({}, depth=3, theme="dark", sizing_mode="stretch_width",
                            height=700)
    undo = pn.widgets.Button(name="Undo", button_type="light", width=90)
    count = pn.pane.HTML()

    class Page:
        def refresh(self):
            doc_view.object = json.loads(json.dumps(host.doc, default=float))
            count.object = f"<small>{len(host.undo)} edits</small>"
            said.object = "<br>".join(f'<span style="color:{"#f87171" if e else "#9ca3af"}">'
                                      f"{t}</span>" for t, e in host.said[-3:])

    page = Page()

    def show(n):
        _, where, part = places[n]
        rows = D.rows_at(host.doc, where, part)
        d = D.Drawer(host, where, rows)
        host.drawers[:] = [d, page]
        holder.objects = [pn.pane.HTML(f"<b>{places[n][0]}</b> · {len(rows)} settings in "
                                       f"{len(d.sections)} sections"), d.panel]
        page.refresh()

    def on_pick(row, where):
        for n, (_, w, _) in enumerate(places):
            if w == where:
                pick.value = n
                return
        host.say(f"{row.label}: at {where}, not in the list", True)
        page.refresh()

    def on_undo(ev):
        host.back()
        page.refresh()

    pick.param.watch(lambda ev: show(ev.new), "value")
    undo.on_click(on_undo)
    finder = find.Find(host, on_pick)
    show(0)
    return pn.Row(pn.Column(finder.panel, pick, width=340),
                  pn.Column(holder, said, width=520),
                  pn.Column(pn.Row(undo, count), doc_view, sizing_mode="stretch_width"),
                  sizing_mode="stretch_width")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=5007)
    args = ap.parse_args()
    pn.extension("codeeditor", "jsoneditor", sizing_mode="stretch_width")
    host = socket.gethostname()
    print(f"  Address:      http://localhost:{args.port}/drawers")
    print(f"  SSH tunnel:   ssh -N -L {args.port}:localhost:{args.port} <you>@{host}")
    pn.serve({"drawers": app}, port=args.port, address="127.0.0.1", show=False,
             title="Figure settings drawers (Phase 2)")


if __name__ == "__main__":
    main()
