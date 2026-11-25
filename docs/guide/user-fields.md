# Your own derived fields

You can add a field of your own by writing it as an expression in a small file. You do
not need to fork, change code or open a pull request. It then appears in every field
menu (map, cross-section, 3D, series, figures), under **User**.

**Write inputs in display units**: the numbers the viewer shows. qv is in g/kg, p′ in
hPa, temperatures in °C or K as each field's units say, and derivatives are per metre.
These are not always the units in the files (qv there is kg/kg).

## A first field

Open **⚙ Settings → Your fields**, or choose **✎ Your fields…** at the bottom of any field
menu. This shows your fields file, `fields.toml` beside your settings file
(`~/.config/atmo3d/fields.toml`, or the folder of `$ATMO3D_CONFIG`). Put this in it:

```toml
[fields.tempf]
label = "Temperature"
units = "°F"
expr  = "tempc * 9/5 + 32"
```

Each field is checked as you type: a line under the text says what it is on the open
run (a 3D field, a column field) or why it cannot be made there. Press **Save and
apply**. The field is then under **User** in every field menu of the page, as
*Temperature [tempf] (user)*, with no restart. Its tooltip shows the expression and
says it is user-defined and not reviewed. A changed field that is on the map, a section
or a figure is drawn again with its new definition.

*Add an example…* above the text puts a field to start from at the end of the file. You
can also edit the file in any text editor: atmo3d then reads it when it starts (or press
Save and apply in the tab).

The `fields_file` [setting](../settings.md) can point to another file, for example a
group's shared one.

## The settings of a field

Each field is a table `[fields.<name>]`. Only `expr` is required.

| Setting | Default | What |
|---|---|---|
| `expr` | (required) | The expression (below). At most 500 characters. |
| `label` | the name | The name shown in the menus. |
| `units` | none | Shown with the label and on colour bars. atmo3d does not check them. |
| `group` | `User` | A submenu under **User**: `group = "Mine"` lists it under *User · Mine*. |
| `cmap` | `viridis` | The starting colormap, as named in the Colormap select. |
| `vrange` | auto | The starting colour range, `[low, high]`. |
| `diverging` | `false` | `true` centres the colour range on 0. |
| `note` | none | A line for the tooltip: what the field is, where its equation is from. |

The name uses letters, digits and `_`, and starts with a letter (`tempf`, `dbz_lowered`).
It cannot be the name of a function below.

## What an expression can use

- **Fields of the run**:
  - The role names, the same in every model: `theta`, `qv`, `u`, `v`, `w`, `pres`,
    `zvort`, ...
  - The data type's own names: CM1's `th`, `qr`; WoFS's `QVAPOR`, ...
  - The built-in derived fields: `tempc`, `rh`, `thetae`, `buoy`, `thpert`, ... (see
    [Derived fields](derived-fields.md)).
  - Your other fields.
- **Derivatives** of the run's own fields: `ddz.w`, `ddx.u`, `ddy.theta`, `gradh.qv`
  (per metre, as the [Derivative select](fields.md#derivatives-of-any-field) gives
  them).
- **Arithmetic**: `+ - * / // % **`, and brackets.
- **Comparisons**: `< <= > >= == !=`. Combine them with `&` (and), `|` (or) and `~` (not).
  Put each comparison in brackets: `(w > 5) & (qr > 1)`.
- **Functions**: `sqrt exp log log10 abs sin cos tan arcsin arccos arctan arctan2 hypot
  minimum maximum where clip isfinite floor ceil sign` (numpy's, taking angles in
  radians). `where(cond, a, b)` is a if cond, else b. `minimum` and `maximum` compare two
  fields point by point. To get one number for the whole domain, use a series.
- **Constants**: `pi`, `e`, `nan`, `inf`, and numbers.

Nothing else is allowed: no attributes (`np.x`), no indexing (`a[0]`), no text, no
keyword arguments, and no `and`, `or`, `not` or `if … else`, which do not work on whole
fields (use `&`, `|`, `~` and `where`). This is for safety: figures you are sent carry
their fields' expressions, and atmo3d evaluates them.

A field is 3D if any of its inputs is, else 2D. A 2D input is used at every level of a
3D one (`theta + 0 * sws` is θ on every level).

## Layer functions: column fields

A layer function turns a 3D field into one value per column, as the built-in updraft
helicity and bulk shear are:

| Function | Gives |
|---|---|
| `layer_mean(x, z0, z1)` | the mean of x between z0 and z1 km above ground, each level weighted by the part of its cell in the layer |
| `layer_integral(x, z0, z1)` | ∫ x dz over the layer, dz in metres (units: x's times m) |
| `layer_max(x, z0, z1)`, `layer_min(x, z0, z1)` | the largest and smallest value on the levels whose cells reach into the layer |
| `at_height(x, z)` | x at z km above ground, linearly between the levels (the lowest or highest level's value beyond them) |

`x` is any expression of 3D fields (`maximum(w, 0) * qr`, `tempc`, a field of your own).
The heights are numbers in km above ground; `top` as z1 is the model top. A column with no
value in the layer is left blank.

An expression with layer functions is a **2D column field**. It is listed with the 2D
fields (on the map, in series and figures, not in sections or 3D), and it reads only
the levels of its layers. In it, every field goes inside a layer function, and the
results combine as numbers do:

```toml
# A layer mean
[fields.wmean03]
label = "Mean updraft 0–3 km"
units = "m/s"
expr  = "layer_mean(maximum(w, 0), 0, 3)"

# An integral: rain water in the lowest 6 km
[fields.rain06]
label = "Integrated rain 0–6 km"
units = "g/kg m"
expr  = "layer_integral(qr, 0, 6)"

# The difference of two layers
[fields.dtheta]
label = "θ 3–6 km − θ 0–1 km"
units = "K"
expr  = "layer_mean(theta, 3, 6) - layer_mean(theta, 0, 1)"
diverging = true

# Values at two heights: a lapse rate
[fields.lapse13]
label = "Lapse rate 1–3 km"
units = "K/km"
expr  = "(at_height(tempc, 1) - at_height(tempc, 3)) / 2"

# The strongest low-level rotation, to the model top
[fields.zvort_max]
label = "Max vertical vorticity 1 km to top"
units = "1/s"
expr  = "layer_max(zvort, 1, top)"
diverging = true
```

## Recipes

```toml
# A unit conversion
[fields.wspd_kt]
label = "Wind speed"
units = "kt"
expr  = "wspd3d / 0.514444"

# A ratio, left blank where it would divide by zero
[fields.qr_frac]
label = "Rain fraction of the condensate"
units = ""
expr  = "where(qcloud + qprecip > 0.01, qr / (qcloud + qprecip), nan)"
vrange = [0, 1]

# A custom index
[fields.updraft_rain]
label = "Updraft × rain"
units = "m/s g/kg"
group = "Indices"
expr  = "maximum(w, 0) * qr"
note  = "Where updrafts carry rain; my own index, not from a paper."

# A derivative inside an expression
[fields.stretch]
label = "Vertical stretching"
units = "1/s²"
expr  = "zvort * ddz.w"
diverging = true

# A field of your own field
[fields.tempf_anom]
label = "Temperature − 70 °F"
units = "°F"
expr  = "tempf - 70"
diverging = true
```

Check each recipe's inputs against the units your run's menus show: `qcloud`, `qprecip`
and `qr` are in g/kg here.

## When a field cannot be computed

A field is offered only on runs that have its inputs. One that a run cannot compute is
listed **greyed out** under User, and its tooltip says why:

| Reason | What to do |
|---|---|
| needs qhail, which this run lacks | Nothing: the field works on runs that have it. |
| shadows the built-in field rh | Rename yours. The built-in field keeps its name. |
| uses uh25, a column field | Column fields (UH, CAPE, shear, helicity, and yours with layer functions) cannot be inputs. Write the layer function into this field's own expression. |
| uses w outside a layer function | In an expression with layer functions every field goes inside one: `layer_mean(w, 0, 3) - layer_mean(w, 3, 6)`, not `layer_mean(w, 0, 3) - w`. |
| uses ddz.w: derivatives cannot be used inside layer functions | Use the fields themselves (a derivative's layer mean is the difference of two at_height values over the depth). |
| uses sws, which is 2D | Layer functions work on 3D fields. |
| uses layer functions, which need a grid this run lacks | Radar volumes have no levels: regrid the volume (radar guide) to use them. |
| uses ddz.tempc: derivatives of derived fields cannot be inputs | Use the derivatives of the run's own fields. In the viewer, the Derivative select works on any field, yours too. |
| its inputs use it in turn: a → b → a | Two fields use each other: break the loop. |
| not an expression (column 12) … | A typing error: the message says where. |
| uses derivatives, which need a grid this run lacks | Radar volumes have no grid, so only pointwise fields work there. |
| needs a storm motion, which this run has none | The field uses a storm-relative input. |

A file that is not valid TOML is shown as one greyed entry, and the error is in the log.
atmo3d still opens. The editor does not save text that is not valid TOML: it says where
the error is.

## Figures, sessions and exports

- **A figure or session you save** records the definition of every field of yours it
  uses. A figure you send to someone still works for them.
- **Opening one** where the field is not defined adds the figure's definition for as long
  as it is open, labelled *(from figure)*. It is never written into your file.
- **If your definition differs** from the one the figure recorded (another expression or
  units), the figure uses its own, under the name `<name>_<6 letters>`. The note shown
  when it loads says so. This means a figure draws what it drew when it was saved.
- **A data export** (netCDF) stores a field of yours with its expression
  (`atmo3d_expr`), its inputs (`atmo3d_inputs`) and the comment "user-defined field …,
  not reviewed".

A session brings its fields into its figures and into the viewer's field menus as it
loads.

## Limits

- **Edits made outside atmo3d** are read when it starts, or when you press Save and apply
  in *Your fields*. Other pages open on the same atmo3d get the new fields in their menus;
  what they show is drawn again the next time it changes.
- **Your fields are not reviewed.** The built-in fields are checked against analytic
  answers before they are listed (see [Derived fields](derived-fields.md)), but yours
  are only checked for safety. Their menu labels say *(user)*.
- **Pointwise, derivatives and layers.** Layer means, integrals, extremes and values at a
  height (above), but no smoothing, no horizontal averages and no values from other times.
- **Units are yours.** atmo3d does not convert or check them: a field in hPa plus one
  in Pa gives a wrong number with no warning.

A field that is useful to others can become a built-in field, reviewed and tested:
[Developing](../developing.md#adding-a-derived-field) has the checklist.

## From a package

An installed package can supply fields in the same form, through the entry-point group
`atmo3d.fields`:

```toml
# the package's pyproject.toml
[project.entry-points."atmo3d.fields"]
mine = "mypkg.fields:FIELDS"
```

```python
# mypkg/fields.py: a list of definitions (or a function returning one)
FIELDS = [
    {"name": "tempf", "label": "Temperature", "units": "°F",
     "expr": "tempc * 9/5 + 32"},
]
```

They are listed the same way as yours, and their tooltip names the package. When your
file and a package define the same name, your file's definition is used.
