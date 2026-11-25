"""FieldSelect: a field picker with cascading menus, in place of a grouped Select.

The field lists (core.fields.group_options) name their groups "Kinematics", "Derived ·
Thermodynamics", "Other · Turbulence", "Hidden · Swaths & 2D".  A long grouped
dropdown of them is hard to scan, so FieldSelect shows a button with the field chosen;
clicking it opens a short menu of the sections, each opening its fields on hover, with
"Derived", "Other" (and "Hidden") entries that open their own sections first:

    Radar          ▸
    Kinematics     ▸  → u, v, Vertical velocity, ...
    ...
    ───────────
    Derived        ▸  → Thermodynamics ▸ → θ′, p′, ...
    Other          ▸  → Turbulence ▸ → ...
    User           ▸  → your own fields (core.userfields), and greyed out the ones
                        this run cannot compute, why as their tooltip

A search box at the top lists every field whose label matches what is typed (Enter
takes the first, Escape closes).

It keeps a Select's interface for the code using it: value, groups (assigning new ones
rebuilds the menu), options ({label: value}, flat), values, labels, name (the label
above it), description (its tooltip), width, disabled, visible, and param.watch on
value.  As a Select, a value not in the options is kept (a saved figure's hidden field):
the button shows its name."""

import weakref

import param
from panel.custom import JSComponent

from ..core.fields import DERIVED_PREFIX, HIDDEN_PREFIX, OTHER_PREFIX, USER_PREFIX, Groups
from ..theme import ACCENT, GRID, HOVER_LINE, MUTED, RAISED, TEXT

# the entries that open sections of their own, in the menu's order after the plain
# sections: (prefix of their groups, entry label)
NESTED = ((DERIVED_PREFIX, "Derived"), (OTHER_PREFIX, "Other"), (HIDDEN_PREFIX, "Hidden"),
          (USER_PREFIX, "User"))


def derived_docs_link():
    """The derived-fields page under the docs_url setting ("": the setting is blank, or
    not an http(s) address: no link)."""
    from .. import config
    url = str(config.get("docs_url") or "").strip().rstrip("/")
    return f"{url}/guide/derived-fields/" if url.lower().startswith(("http://", "https://")) else ""


def menu_tree(groups):
    """The menu of grouped options {group: {label: value}}: a list of nodes
    {"l": label, "c": [children]} (a section) or {"l": label, "v": value} (a field),
    and {"sep": True} between the plain sections and Derived / Other / Hidden / User.  A
    field with a note (groups.tips, from fields.group_options) has it as "t": its
    tooltip.  User fields a run cannot compute (groups.off) are {"l": label, "off": why}:
    shown greyed out, not chosen.  The user fields of no group of their own ("User · ")
    are listed straight under User."""
    tips = getattr(groups, "tips", {})
    plain, nested = [], {p: [] for p, _ in NESTED}
    sections = {}
    for g, opts in (groups or {}).items():
        if not opts:
            continue
        leaves = [{"l": str(lab), "v": v} | ({"t": tips[v]} if tips.get(v) else {})
                  for lab, v in opts.items()]
        prefix = next((p for p, _ in NESTED if str(g).startswith(p)), None)
        if prefix is None:
            if g:
                plain.append({"l": str(g), "c": leaves})
            else:  # (options outside any group: on the top level itself)
                plain.extend(leaves)
        elif str(g) == prefix:  # (straight under its entry)
            nested[prefix].extend(leaves)
        else:
            node = {"l": str(g)[len(prefix):], "c": leaves}
            sections[str(g)] = node
            nested[prefix].append(node)
    for g, lab, why in getattr(groups, "off", ()) or ():
        leaf = {"l": str(lab), "off": str(why)}
        if g == USER_PREFIX:
            nested[USER_PREFIX].append(leaf)
        elif g in sections:
            sections[g]["c"].append(leaf)
        else:
            sections[g] = {"l": g[len(USER_PREFIX):], "c": [leaf]}
            nested[USER_PREFIX].append(sections[g])
    tail = [{"l": lab, "c": nested[p]} for p, lab in NESTED if nested[p]]
    return plain + ([{"sep": True}] if plain and tail else []) + tail


def flat_options(groups):
    """{label: value} of grouped options (as a Select's options)."""
    out = {}
    for opts in (groups or {}).values():
        out.update(opts or {})
    return out


class FieldSelect(JSComponent):
    """A field picker with cascading menus (module docstring)."""

    value = param.Parameter(default=None)
    groups = param.Dict(default={})  # (Python only: tree is sent, see _rename)
    options = param.Dict(default={})  # {label: value} (the button's text)
    tree = param.List(default=[])
    name = param.String(default="")
    description = param.String(default="")
    docs_link = param.String(default="")  # (the derived-fields page's address, or "")
    # the menu's "Your fields…" link (a page that can edit them: on_edit), and its clicks
    edit_link = param.Boolean(default=False)
    edit_clicks = param.Integer(default=0)
    disabled = param.Boolean(default=False)

    _rename = {"groups": None}

    def __init__(self, groups=None, options=None, **params):
        if groups is None and options is not None:
            groups = {"": dict(options)}
        tips, off = getattr(groups, "tips", {}), getattr(groups, "off", ())
        user_ndim = getattr(groups, "user_ndim", "?")
        groups = Groups(groups or {})  # (a copy that keeps the notes)
        groups.tips, groups.off, groups.user_ndim = tips, off, user_ndim
        params.pop("tree", None)  # (made from groups: a clone() passes its own too)
        # no name given: none shown (param would make up "FieldSelect00506" and the
        # button would show it as its label)
        params.setdefault("name", "")
        params.setdefault("docs_link", derived_docs_link())
        params.setdefault("edit_link", user_ndim != "?")  # (a menu of a run's fields)
        params.setdefault("height", 52 if params.get("name") else 32)
        params.setdefault("margin", (5, 10))  # (a widget's, as the Select's was)
        if "sizing_mode" not in params:
            params.setdefault("width", 300)  # (the Select's default width)
        super().__init__(groups=groups, options=flat_options(groups),
                         tree=menu_tree(groups), **params)
        _OPEN.add(self)

    @param.depends("edit_clicks", watch=True)
    def _on_edit(self):
        import panel as pn
        cb = _EDIT.get(pn.state.curdoc)
        if cb is not None:
            cb()

    @param.depends("groups", watch=True)
    def _new_groups(self):
        self.param.update(options=flat_options(self.groups), tree=menu_tree(self.groups))

    @property
    def values(self):
        return list(self.options.values())

    @property
    def labels(self):
        return list(self.options)

    _stylesheets = [f"""
:host {{ display: block; }}
.fs {{ font-family: inherit; font-size: 13px; position: relative; width: 100%; }}
.fs-name {{ display: block; margin: 0 0 3px 0; font-size: 13px; color: {TEXT};
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.fs-btn {{ width: 100%; height: 31px; text-align: left; padding: 0 22px 0 8px;
  border: 1px solid {GRID}; border-radius: 4px; background: #0d131e; cursor: pointer;
  font: inherit; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  position: relative; color: {TEXT}; }}
.fs-btn:hover {{ border-color: {HOVER_LINE}; }}
.fs-btn::after {{ content: "▾"; position: absolute; right: 7px; top: 6px; color: {MUTED}; }}
.fs-btn:disabled {{ opacity: .45; cursor: not-allowed; }}
.fs-btn:focus {{ outline: none; border-color: rgba(34,211,238,.7);
  box-shadow: 0 0 0 2px rgba(34,211,238,.15); }}
.fs-menu, .fs-sub {{ position: fixed; z-index: 10000; background: {RAISED};
  border: 1px solid {GRID}; border-radius: 6px; box-shadow: 0 10px 30px rgba(0,0,0,.55);
  min-width: 180px; max-width: 460px; overflow-y: auto; padding: 3px 0; color: {TEXT}; }}
.fs-search {{ box-sizing: border-box; width: calc(100% - 10px); margin: 2px 5px 4px;
  padding: 4px 6px; border: 1px solid {GRID}; border-radius: 4px; font: inherit;
  background: #0d131e; color: {TEXT}; }}
.fs-search:focus {{ outline: none; border-color: rgba(34,211,238,.7); }}
.fs-item {{ padding: 4px 22px 4px 10px; cursor: pointer; white-space: nowrap;
  position: relative; overflow: hidden; text-overflow: ellipsis; }}
.fs-item:hover, .fs-item.fs-open, .fs-item.fs-first {{ background: rgba(34,211,238,.14); }}
.fs-item.fs-cur {{ color: {ACCENT}; }}
.fs-item.fs-sec::after {{ content: "▸"; position: absolute; right: 8px; color: {MUTED}; }}
.fs-path {{ color: {MUTED}; font-size: 11px; margin-left: 6px; }}
.fs-sep {{ border-top: 1px solid {GRID}; margin: 3px 0; }}
.fs-docs {{ display: block; padding: 5px 10px 3px; margin-top: 3px; border-top: 1px solid {GRID};
  color: {ACCENT}; text-decoration: none; }}
.fs-docs:hover {{ text-decoration: underline; }}
.fs-none {{ padding: 4px 10px; color: {MUTED}; }}
.fs-item.fs-off {{ color: {MUTED}; opacity: .6; cursor: default; font-style: italic; }}
.fs-item.fs-off:hover {{ background: none; }}
"""]

    _esm = """
export function render({ model, el }) {
  const wrap = document.createElement('div'); wrap.className = 'fs'
  const name = document.createElement('label'); name.className = 'fs-name'
  const btn = document.createElement('button'); btn.className = 'fs-btn'
  btn.type = 'button'
  wrap.append(name, btn); el.append(wrap)
  let menu = null, subs = [], onDoc = null

  function labelOf(v) {
    for (const [lab, val] of Object.entries(model.options || {})) {
      if (val === v) return lab
    }
    return (v === null || v === undefined || v === '') ? '—' : String(v)
  }
  function paint() {
    name.textContent = model.name || ''
    name.style.display = model.name ? '' : 'none'
    name.title = model.description || ''
    const t = labelOf(model.value)
    btn.textContent = t
    btn.title = (model.description ? model.description + '\\n\\n' : '') + t
    btn.disabled = !!model.disabled
  }
  function leaves(nodes, path, out) {
    for (const n of nodes) {
      if (n.sep || n.off !== undefined) continue
      if (n.c) leaves(n.c, path.concat([n.l]), out)
      else out.push([n, path])
    }
    return out
  }
  function hasCur(n) {
    return n.c ? n.c.some(hasCur) : n.v === model.value
  }
  function moveTo(box, x, y) {
    // put the box's top left corner at (x, y) in the window.  A transformed or
    // contained ancestor (a layout, a floating panel) makes position: fixed count from
    // it rather than from the window: what the box lands off by is taken back
    box.style.left = x + 'px'; box.style.top = y + 'px'
    const r = box.getBoundingClientRect()
    const dx = r.left - x, dy = r.top - y
    if (Math.abs(dx) > 0.5 || Math.abs(dy) > 0.5) {
      box.style.left = (x - dx) + 'px'; box.style.top = (y - dy) + 'px'
    }
  }
  function place(box, x, y, flipFrom) {
    // at (x, y) in the window, kept in it (flipped left of flipFrom if needed)
    box.style.maxHeight = (window.innerHeight - 16) + 'px'
    moveTo(box, x, y)
    const r = box.getBoundingClientRect()
    let nx = x, ny = y
    if (r.right > window.innerWidth - 4) {
      nx = Math.max(4, flipFrom !== undefined ? flipFrom - r.width + 2
                                              : window.innerWidth - 4 - r.width)
    }
    if (r.bottom > window.innerHeight - 8) {
      ny = Math.max(8, window.innerHeight - 8 - r.height)
    }
    if (nx !== x || ny !== y) moveTo(box, nx, ny)
  }
  function closeFrom(level) {
    while (subs.length > level) {
      const s = subs.pop(); s.box.remove()
      if (s.item) s.item.classList.remove('fs-open')
    }
  }
  function pick(v) {
    model.value = v
    close()
  }
  function fill(box, nodes, level) {
    for (const n of nodes) {
      if (n.sep) {
        const d = document.createElement('div'); d.className = 'fs-sep'; box.append(d)
        continue
      }
      const it = document.createElement('div'); it.className = 'fs-item'
      it.textContent = n.l; it.title = n.t ? n.l + '\\n\\n' + n.t : n.l
      if (hasCur(n)) it.classList.add('fs-cur')
      if (n.off !== undefined) {
        it.classList.add('fs-off')
        it.title = n.l + '\\n\\nNot available: ' + n.off
        it.addEventListener('mouseenter', () => closeFrom(level))
      } else if (n.c) {
        it.classList.add('fs-sec')
        it.addEventListener('mouseenter', () => openSub(it, n.c, level + 1))
        it.addEventListener('click', (e) => { e.stopPropagation(); openSub(it, n.c, level + 1) })
      } else {
        it.addEventListener('mouseenter', () => closeFrom(level))
        it.addEventListener('click', (e) => { e.stopPropagation(); pick(n.v) })
      }
      box.append(it)
    }
  }
  function openSub(item, nodes, level) {
    if (subs.length > level - 1 && subs[level - 1] && subs[level - 1].item === item) return
    closeFrom(level - 1)
    const box = document.createElement('div'); box.className = 'fs-sub'
    fill(box, nodes, level)
    wrap.append(box)
    const r = item.getBoundingClientRect()
    place(box, r.right - 2, r.top - 4, r.left)
    item.classList.add('fs-open')
    subs.push({ box, item })
  }
  function close() {
    closeFrom(0)
    if (menu) { menu.remove(); menu = null }
    if (onDoc) { document.removeEventListener('mousedown', onDoc, true); onDoc = null }
  }
  function open() {
    close()
    menu = document.createElement('div'); menu.className = 'fs-menu'
    const search = document.createElement('input'); search.className = 'fs-search'
    search.placeholder = 'Search fields…'
    const list = document.createElement('div')
    menu.append(search, list)
    if (model.docs_link) {
      const a = document.createElement('a'); a.className = 'fs-docs'
      a.href = model.docs_link; a.target = '_blank'; a.rel = 'noopener noreferrer'
      a.textContent = 'ⓘ Field documentation'
      a.title = 'What each derived field computes, and what it leaves out'
      menu.append(a)
    }
    if (model.edit_link) {
      const a = document.createElement('a'); a.className = 'fs-docs'; a.href = '#'
      a.textContent = '✎ Your fields…'
      if (model.docs_link) { a.style.borderTop = 'none'; a.style.marginTop = '0' }
      a.title = 'Define fields of your own: expressions of the fields of the run'
      a.addEventListener('click', (e) => {
        e.preventDefault(); close(); model.edit_clicks = (model.edit_clicks || 0) + 1 })
      menu.append(a)
    }
    const tree = model.tree || []
    fill(list, tree, 0)
    let first = null
    search.addEventListener('input', () => {
      closeFrom(0); list.innerHTML = ''; first = null
      const q = search.value.trim().toLowerCase()
      if (!q) { fill(list, tree, 0); return }
      const hits = leaves(tree, [], []).filter(([n, p]) =>
        (n.l + ' ' + p.join(' ')).toLowerCase().includes(q))
      if (!hits.length) {
        const d = document.createElement('div'); d.className = 'fs-none'
        d.textContent = 'No field matches'; list.append(d); return
      }
      for (const [n, p] of hits.slice(0, 200)) {
        const it = document.createElement('div'); it.className = 'fs-item'
        it.textContent = n.l; it.title = n.t ? n.l + '\\n\\n' + n.t : n.l
        const s = document.createElement('span'); s.className = 'fs-path'
        s.textContent = p.join(' › '); it.append(s)
        it.addEventListener('click', (e) => { e.stopPropagation(); pick(n.v) })
        if (first === null) { first = n; it.classList.add('fs-first') }
        list.append(it)
      }
    })
    search.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') { close(); btn.focus() }
      else if (e.key === 'Enter' && first !== null) pick(first.v)
    })
    wrap.append(menu)
    const r = btn.getBoundingClientRect()
    menu.style.minWidth = Math.max(180, r.width) + 'px'
    place(menu, r.left, r.bottom + 2)
    onDoc = (e) => { if (!e.composedPath().includes(wrap)) close() }
    document.addEventListener('mousedown', onDoc, true)
    search.focus()
  }
  btn.addEventListener('click', () => { if (menu) close(); else if (!model.disabled) open() })
  model.on('value', paint)
  model.on('options', paint)
  model.on('name', paint)
  model.on('description', paint)
  model.on('disabled', () => { paint(); if (model.disabled) close() })
  model.on('tree', () => { if (menu) close() })
  model.on('remove', close)
  paint()
}
"""


# ------------------------------------------------------------------ user fields changed
_OPEN = weakref.WeakSet()  # (every FieldSelect made: refresh_user)
_EDIT = weakref.WeakKeyDictionary()  # (page -> what its menus' "Your fields…" opens)


def on_edit(doc, callback):
    """Menus on page `doc` open callback() from their "Your fields…" link."""
    if doc is not None:
        _EDIT[doc] = callback


def _user_ndim(groups, F):
    """The ndim a menu's User section is made for (Groups.user_ndim; a menu built by
    hand: 3 if every field it lists is 3D, else None), or "skip": not a field menu
    for user fields (it lists none, nor any field of F)."""
    from ..core.fields import USER_PREFIX
    nd = getattr(groups, "user_ndim", "?")
    if nd != "?":
        return nd
    if any(g.startswith(USER_PREFIX) for g in groups) or getattr(groups, "off", ()):
        known = [F.defs[v].ndim for g, o in groups.items() if not g.startswith(USER_PREFIX)
                 for v in o.values() if v in F.defs]
        return 3 if known and all(k == 3 for k in known) else None
    return "skip"


def with_user(groups, F):
    """Menu `groups` with its User section made again from F (the definitions changed):
    the other sections, their order and the extra entries (None, "Along the
    streamline") are kept; None if the menu is not one for user fields."""
    from ..core.fields import USER_PREFIX
    nd = _user_ndim(groups, F)
    if nd == "skip":
        return None
    fresh = F.groups(nd)
    out = Groups((g, o) for g, o in groups.items() if not g.startswith(USER_PREFIX))
    out.update((g, o) for g, o in fresh.items() if g.startswith(USER_PREFIX))
    user = {v for g, o in fresh.items() if g.startswith(USER_PREFIX) for v in o.values()}
    old = getattr(groups, "tips", {})
    out.tips = {**{k: v for k, v in old.items() if k not in user},
                **{k: v for k, v in fresh.tips.items() if k in user}}
    out.off, out.user_ndim = fresh.off, nd
    return out


def refresh_user(F, doc=None):
    """Make the User section of every field menu of page `doc` (default: the current
    one) again from Fields F, after the user fields changed (the editor's Save, a
    session's definitions).  A menu whose field is gone keeps it chosen (as a Select
    keeps a value not in its options).  Returns how many menus changed."""
    import panel as pn
    doc = doc if doc is not None else pn.state.curdoc
    n = 0
    for w in list(_OPEN):
        if doc is not None and w._models and not any(
                m.document is doc for m, _ in w._models.values()):
            continue  # (another page's: it refreshes on its own)
        g = with_user(w.groups, F)
        if g is not None and (dict(g) != dict(w.groups)
                              or list(g.off) != list(getattr(w.groups, "off", ()))
                              or g.tips != getattr(w.groups, "tips", {})):
            w.param.update(groups=g, edit_link=True)
            n += 1
    return n

