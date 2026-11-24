"""The figure editor, on the figure document (spec/doc.py): the document, undo, drawing and the
preview (frame.py), and the edits (docedit.py).  Its page is figures/ui's frame: the tools'
drawers, and the level switch saying what an edit reaches (a panel alone, all panels of a
kind, the figure)."""

from .frame import FigureShell

__all__ = ["FigureShell"]
