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

A search box at the top lists every field whose label matches what is typed (Enter
takes the first, Escape closes).

It keeps a Select's interface for the code using it: value, groups (assigning new ones
rebuilds the menu), options ({label: value}, flat), values, labels, name (the label
above it), description (its tooltip), width, disabled, visible, and param.watch on
value.  As a Select, a value not in the options is kept (a saved figure's hidden field):
the button shows its name."""

import param
from panel.custom import JSComponent

from ..core.fields import DERIVED_PREFIX, HIDDEN_PREFIX, OTHER_PREFIX
from ..theme import ACCENT, GRID, HOVER_LINE, MUTED, RAISED, TEXT

# the entries that open sections of their own, in the menu's order after the plain
# sections: (prefix of their groups, entry label)
NESTED = ((DERIVED_PREFIX, "Derived"), (OTHER_PREFIX, "Other"), (HIDDEN_PREFIX, "Hidden"))


def menu_tree(groups):
    """The menu of grouped options {group: {label: value}}: a list of nodes
    {"l": label, "c": [children]} (a section) or {"l": label, "v": value} (a field),
    and {"sep": True} between the plain sections and Derived / Other / Hidden."""
    plain, nested = [], {p: [] for p, _ in NESTED}
    for g, opts in (groups or {}).items():
        if not opts:
            continue
        leaves = [{"l": str(lab), "v": v} for lab, v in opts.items()]
        prefix = next((p for p, _ in NESTED if str(g).startswith(p)), None)
        if prefix is None:
            if g:
                plain.append({"l": str(g), "c": leaves})
            else:  # (options outside any group: on the top level itself)
                plain.extend(leaves)
        else:
            nested[prefix].append({"l": str(g)[len(prefix):], "c": leaves})
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
    disabled = param.Boolean(default=False)

    _rename = {"groups": None}

    def __init__(self, groups=None, options=None, **params):
        if groups is None and options is not None:
            groups = {"": dict(options)}
        groups = dict(groups or {})
        params.pop("tree", None)  # (made from groups: a clone() passes its own too)
        params.setdefault("height", 52 if params.get("name") else 32)
        params.setdefault("margin", (5, 10))  # (a widget's, as the Select's was)
        if "sizing_mode" not in params:
            params.setdefault("width", 300)  # (the Select's default width)
        super().__init__(groups=groups, options=flat_options(groups),
                         tree=menu_tree(groups), **params)

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
.fs-none {{ padding: 4px 10px; color: {MUTED}; }}
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
      if (n.sep) continue
      if (n.c) leaves(n.c, path.concat([n.l]), out)
      else out.push([n, path])
    }
    return out
  }
  function hasCur(n) {
    return n.c ? n.c.some(hasCur) : n.v === model.value
  }
  function place(box, x, y, flipFrom) {
    // fixed position at (x, y), kept in the window (flipped left of flipFrom if needed)
    box.style.left = x + 'px'; box.style.top = y + 'px'
    box.style.maxHeight = (window.innerHeight - 16) + 'px'
    const r = box.getBoundingClientRect()
    if (r.right > window.innerWidth - 4) {
      const left = flipFrom !== undefined ? flipFrom - r.width + 2 : window.innerWidth - 4 - r.width
      box.style.left = Math.max(4, left) + 'px'
    }
    if (r.bottom > window.innerHeight - 8) {
      box.style.top = Math.max(8, window.innerHeight - 8 - r.height) + 'px'
    }
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
      it.textContent = n.l; it.title = n.l
      if (hasCur(n)) it.classList.add('fs-cur')
      if (n.c) {
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
        it.textContent = n.l; it.title = n.l
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
