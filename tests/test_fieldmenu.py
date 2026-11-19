"""The field picker with cascading menus (viewer.fieldmenu): its menu tree and its
Select-like interface (Phase 2b, 2026-11-18)."""

from atmo3d.viewer.fieldmenu import FieldSelect, flat_options, menu_tree

GROUPS = {
    "Kinematics": {"u [u]": "u", "w [w]": "w"},
    "Radar": {"Reflectivity [dbz]": "dbz"},
    "Derived · Thermodynamics": {"θ′ [thpert]": "thpert"},
    "Derived · Column fields": {"UH [uh25]": "uh25"},
    "Other · Turbulence": {"TKE [tke]": "tke"},
    "Hidden · Swaths & 2D": {"Latitude [XLAT]": "XLAT"},
}


def test_menu_tree_nests_derived_other_hidden():
    t = menu_tree(GROUPS)
    assert [n.get("l") for n in t] == ["Kinematics", "Radar", None, "Derived", "Other",
                                       "Hidden"]
    assert t[2] == {"sep": True}
    derived = t[3]["c"]
    assert [n["l"] for n in derived] == ["Thermodynamics", "Column fields"]
    assert derived[0]["c"] == [{"l": "θ′ [thpert]", "v": "thpert"}]
    assert t[0]["c"][1] == {"l": "w [w]", "v": "w"}


def test_menu_tree_edge_cases():
    assert menu_tree({}) == []
    # only nested entries: no separator; empty groups dropped
    t = menu_tree({"Other · X": {"a": "a"}, "Kinematics": {}})
    assert t == [{"l": "Other", "c": [{"l": "X", "c": [{"l": "a", "v": "a"}]}]}]
    # options outside any group sit on the top level
    assert menu_tree({"": {"a": "a"}}) == [{"l": "a", "v": "a"}]


def test_field_select_acts_like_a_select():
    w = FieldSelect(name="Field", groups=GROUPS, value="w", width=220)
    assert w.options == flat_options(GROUPS) and "w" in w.values and "u [u]" in w.labels
    assert w.width == 220 and w.name == "Field"
    seen = []
    w.param.watch(lambda e: seen.append(e.new), "value")
    w.value = "tke"
    assert seen == ["tke"]
    w.groups = {"Radar": {"Reflectivity [dbz]": "dbz"}}
    assert w.options == {"Reflectivity [dbz]": "dbz"} and w.tree[0]["l"] == "Radar"
    w.value = "not_listed"  # (kept, as a Select keeps it: a saved figure's hidden field)
    assert w.value == "not_listed"
    assert FieldSelect(options={"a": 1}).values == [1]
