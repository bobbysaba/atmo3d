# Figures

The **Figure** workspace makes publication figures from anything in the viewer: plan
views, cross-sections, time–height plots, time series, soundings, distributions and 3D
scenes, across times and runs. The figure is previewed at its final size, every change can be
undone, and each saved figure comes with a stand-alone script and data that redraw the
same image without atmo3d.

This page covers how a figure starts, the editor's layout and how to save. The rest has a page
each:

| What | Page |
|---|---|
| The grid, what each kind of panel shows, times, runs | [Figure panels](figures-panels.md) |
| Fills, contours, vectors, series, soundings, distributions | [Figure layers](figures-layers.md) |
| Fonts, axes, colorbars, legends; text, arrows, your own code | [Style and annotations](figures-style.md) |
| Animations (GIF or video), templates, reopening | [Export, animations and the script](figures-export.md) |

## Starting a figure

A figure can start from

- the **picture buttons** in the items tray under the map: the map view, soundings, the
  section, a series, the 3D box. The figure then keeps the layers, fields and ranges you set up in
  the viewer;
- **Figure of these** in the Distribution tool; or
- the **New dialog**, which the Figure workspace shows the first time you open it (when
  no figure has been made from the viewer yet). The new-figure button in the top bar shows
  it again.

### The New dialog

| Setting | Meaning |
|---|---|
| **Panels show** | *Plan views*, *Vertical cross-sections*, *Time–height (series)*, *Time series*, *Soundings*, *Distributions*, *Vertical profiles*, *Joint distributions*, *Azimuthal means*, *Tables (sounding parameters, field statistics)* or *3D scene (one picture)*. |
| **Panels differ in** | (Plan views.) *Time*, *Field*, *Height*, *Run*, or *Nothing*; the panels fill the grid row by row. For a grid of two (e.g. runs × times), use *Fill panels* (Layout, at the figure) afterwards. Cross-sections start as x–z and y–z in turn. |
| **Colour fill** | The field every panel starts with. |
| **Rows**, **Columns** | The grid, up to 8 × 8 here; Layout takes any size. |
| **Width** | A size preset: 3.25 in (one journal column), 5 in, 6.5 in (full page width), 7.5 in, a 13.3 × 7.5 in slide, or custom. Default 8 in. |

**Make the figure** builds it, and Undo takes it back; **Keep this figure** closes the dialog and
leaves the figure as it is. **Reopen the last figure**, when there is one, brings back what you
were last working on in this run, saved or not.

**Or start from a template** applies a template you saved from *Export* to this run
([Templates](figures-export.md#templates)).

**Or open a saved figure** lists the figures saved in the *Figures* folder (⚙ Settings) by
folder, this run's first. Picking one fills in the path below it; **Open** opens it, ready to keep
editing ([Reopening a saved figure](figures-export.md#reopening-a-saved-figure)). **Or open one by
its path** takes a `_spec.json`, or the image or script saved with it, from anywhere.

Below them the same figures appear as thumbnails, newest first across all folders, 12 at a time
(**Show more**). **Thumbnails from** narrows them to one folder, and hovering over one shows its
folder and when it was saved. Click a thumbnail to open that figure. A figure saved before this
version gets its thumbnail from its image; one saved only as a PDF, SVG or EPS shows just its name
until it is saved again.

A note in the dialog says what to do next for the chosen kind. Time–height and time-series
figures start with no series, so nothing is computed until you add one. Soundings and
distributions start with the viewer's soundings or distributions.

## The editor

The Figure workspace is laid out as the viewer: a top bar, a tool rail on the left, one drawer
open beside it, and the preview.

- The **top bar**: **Runs** (naming the figure's runs: opens the Runs tool), the **Find** box,
  the new-figure button (the New dialog), **↶ ↷**, **Auto-redraw**, **Redraw** and **Export**.
- The **tool rail** opens one drawer at a time; its lit button again closes it:

| Tool | What it holds |
|---|---|
| **Layout** | The figure's size, title, grid and spacing; adding, filling, copying and removing panels and changing their type; a panel's place, title and row label; a plan view's area; zoom insets' place and area; a 3D scene's region. |
| **Layers** | What the panels draw: the layers every panel of a kind shares, a panel's own, an inset's; the sections; a sounding, series or distribution panel's entries; a 3D scene's surfaces, floor, vectors, streamlines and parcels. |
| **Look** | Fonts, axes and ticks, panel labels, colorbars, legends, each kind's plot, the skew-T and hodograph, a 3D scene's camera and look, style presets, matplotlib style, your own code. |
| **Marks** | Annotations, legend entries of your own, the contour key, maximum and minimum marks. |
| **Times** | Each panel's run and time; a 3D scene's animation settings. |
| **Runs** | The figure's runs: label, colour, time zero, storm track; how runs line up; adding and removing one. |

- The **preview** is drawn at the figure's final size. **Clicking a panel picks it**: the drawer
  then shows that panel's settings.
- **Clicking a part of a panel opens its setting**: a panel's title, its x or y label, its row
  label, a panel label (letter, time, run name, height), a legend, a colorbar, or the figure's
  title or legend. The drawer opens at the place that owns it, with its section open and the
  setting outlined, as **Find** does (*Clicked the x label: x label, in Axes and ticks*). The part
  under the mouse is outlined, dashed, with a tooltip saying what it is. A panel's title and
  labels open at that panel; the figure's legend and title at **Figure**.
  A colorbar opens where its settings are: one for the figure at **Figure** (*Colorbars*), one per
  row or column at that row or column, a panel's own at the panel, and a bar panels name at the
  first of them. A shared bar says which panels it serves and whose colours it shows, with
  **Jump to** buttons for that panel's fill (its colours), *All colorbars* and the controlling
  panel's own colorbar settings ([Colorbar](figures-style.md#colorbar)). While the *Click* list
  places something, clicks place it instead.
- **Headers** above the preview's columns and beside its rows (a grid of more than one) name
  what each differs in: *80 min*, a run's label, *3 km*. **Clicking a header picks that row or
  column**: an edit made there is written to each of its panels
  ([Rows and columns](figures-panels.md#picking-a-row-or-a-column)).
- **Layer chips** above the preview list the layers all plan views (or cross-sections) share;
  clicking one opens it in Layers at *All plan views*, and **+ Layer** opens Layers there to add
  one.
- A **dot** at a panel's upper right corner marks a panel with changes of its own: shared layers
  it changes, layers of its own, look settings it sets alone. Its Layers drawer lists them, with
  **Use the shared ones**.

**Where an edit goes.** A row of buttons at the top of each drawer says where: **Figure**, **All
plan views** (one button for each kind the figure has), then the row or column picked
(**Column 2 · b, d**) or the panel picked (**Panel b**) and, when one is picked, its **Inset** or
**Layer**. The line under it says what an edit there reaches
(*Applies to all plan views*, *Applies to panel b only*). It follows what you click in the preview,
and going up to *All plan views* and back to the panel is one click each.

- A setting at **Figure** reaches every panel; at **All plan views**, every plan view; at a
  **row or column**, each of its panels (of the kind most of them are); at a **panel**, that
  panel alone.
- A setting a panel sets for itself is marked there, with **↺** to go back to what it inherits;
  a change at *All plan views* then skips it, and *All plan views* lists the panels that set some
  of their look alone. A section's header counts what is set there (*2 set here*), and **↺ Reset
  section** takes them all back.
- At the figure (and a kind's own settings at the kind), a section counts what differs from a
  new figure (*3 changed*), and its reset, or a setting's ↺, goes back to a new figure's.

**Shared layers and sections.** The layers at *All plan views* (Layers) are shared by the panels
that draw them: an edit there reaches them all. *Drawn in panels* picks which panels draw one. The
panels that changed it for themselves are listed, and **↺ All as shared** takes their changes back;
when panels of another kind draw it too (a cross-section, say), **Keep apart** gives them a copy of
their own. At a panel a shared layer is marked *shared* (*changed here* once the panel changes it):
what is set there stays there, and **↺ Use the shared settings** takes it all back. A panel can add
layers of its own too. Sections are shared by the cross-sections showing them in the same way.

**Find**, in the top bar, searches every setting of the figure by name (*colour* and *color*,
*centre* and *center* alike): picking a hit opens its tool at the panel picked (else the figure),
with its section open and the setting outlined. A setting of the Export dialog opens the dialog.

Above the preview, *Size* switches between **Fit** and **Actual size** (as large as it prints, to
judge the font sizes), *Colours* previews the picture in greyscale or as seen with a colour-vision
deficiency (the preview only, not the figure), and *Click* says what a click or drag in the
preview does: pick a panel, place an annotation, a section's A and B, a panel's area or an inset
([Style and annotations](figures-style.md#annotate)).

Under the preview, a **time slider** shows the figure at other outputs. **Keep this time** moves
the figure there, and *Saved time* comes back; it changes nothing else.

- **↶ ↷** undo and redo every change, including a new figure. Sections and lists stay folded or
  open as you left them.
- **Auto-redraw** redraws after each change; untick it and press **Redraw** to draw only when you
  ask (useful for slow figures).
- **Export** saves the figure.

## Saving

**Export**, in the top bar, opens the dialog that saves the figure:

| Control | Meaning |
|---|---|
| **Save as** | Folder and name, without extension. For one run it starts in `<figures_dir>/<parent>_<run>/` (see [Settings](../settings.md)). A figure of several runs has no folder of its own: choose one (the last one used is offered next time). |
| **Format** | PNG, PDF, SVG, EPS or TIFF. |
| **DPI** | 50 to 1200. |
| **Background** | White, black or transparent. |
| **Image size** | *Trim white space*, *Exact width, trim the height* or *Exact width and height* ([Image size](figures-export.md#image-size)). |
| **Also the script and data** | Adds a stand-alone script, the plotted arrays and the drawing code ([Export, animations and the script](figures-export.md#the-script-and-data)). |
| **Save** | The image, and the figure's settings (`_src/<name>_spec.json`) so it can be reopened. |
| **Download** | Sends the image to your browser. |

A figure whose time series are still being computed is saved when they are done; the line
under the preview says so. It saves the figure as it was when you pressed **Save**.

Saving over an existing file asks first. Figures are drawn and saved one at a time,
because matplotlib's style settings are process-wide.

## Fields and runs

A figure may show several runs. Every layer, sounding, distribution and series picks its
own run, and runs have their own storm track (the viewer's Track tool, or `storm_tracks/<run>.csv`
found automatically; see `track_dirs` and `track_patterns` in [Settings](../settings.md)).
In the **Runs** tool, a run's *Track file* lists the files in those folders, or takes a path you type.
When the file holds several storms (a WoFS member's cells, say), a *Storm* list picks the
one that run's panels follow; without one picked they follow the file's first. A run on the
viewer's track follows the viewer's storm, and the saved figure names it.
[Templates](figures-panels.md#runs) and **Apply to other runs** carry the storm's name to the
run they are applied to, so the same storm is drawn for every member
([Several storms in one file](tracking.md#several-storms-in-one-file)).
See [Figure panels](figures-panels.md#runs) for how runs are added and coloured.
