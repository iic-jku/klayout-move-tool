# --------------------------------------------------------------------------------
# SPDX-FileCopyrightText: 2025-2026 Martin Jan Köhler
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
# SPDX-License-Identifier: GPL-3.0-or-later
#--------------------------------------------------------------------------------

"""
A pya.EditorOptionsPage that replicates KLayout's built-in "Basic Editor Options"
panel (Edit > Editor Options, or F3) **without** any hierarchy-related controls
(i.e. no "Edit in place", "Descend into", "Top-level context" items).

Covers the three standard groups:
  • Snapping   – grid mode / grid value(s), snap-to-objects
  • Connection angle constraint
  • Movement direction constraint

Requires KLayout ≥ 0.30.4 (EditorOptionsPage introduced there).
"""

import os
import traceback
from typing import *

import pya

from klayout_plugin_utils.editor_options import EditorOptions, EditGridKind, AngleMode

# ---------------------------------------------------------------------------

path_containing_this_script = os.path.realpath(os.path.dirname(__file__))

# as we had crashes when connecting UI signals to the MoveToolEditorOptionsPage,
# we keep the pages alive here
_live_pages = {}
_next_page_id = 0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_safe_callback(page_id, method_name):
    """Closure captures only an int and a string — no Python objects."""
    def callback(*args):
        obj = _live_pages.get(page_id)
        if obj is not None:
            getattr(obj, method_name)(*args)
    return callback


def _to_float(v, default=0.0):
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        v = v.strip()
        if v.replace('.', '', 1).replace('-', '', 1).replace('+', '', 1).isdigit():
            return float(v)
    return default
    

# ---------------------------------------------------------------------------
# Main page class
# ---------------------------------------------------------------------------

class MoveToolEditorOptionsPage(pya.EditorOptionsPage):
    """
    Editor Options page that mirrors KLayout's "Basic Editor Options" without
    hierarchy controls.
    """

    def __init__(self, 
                 title: str, 
                 page_index: int):
        """
        Tab ordering – place right after the built-in Basic page (index 0).
        Use a high index (e.g. 100) to append at the end instead.
        """
        
        global _next_page_id
        
        super().__init__(title, page_index)

        # Clean up destroyed pages
        dead_ids = [pid for pid, page in _live_pages.items() if page._destroyed()]
        for pid in dead_ids:
            del _live_pages[pid]
        
        self._page_id = _next_page_id
        _next_page_id += 1
        _live_pages[self._page_id] = self
                
        loader = pya.QUiLoader()
        ui_path = os.path.join(path_containing_this_script, "MoveToolEditorOptions.ui")
        ui_file = pya.QFile(ui_path)
        try:
            ui_file.open(pya.QFile.ReadOnly)
            self.page = loader.load(ui_file, self)
        finally:
            ui_file.close()

        outer_layout = pya.QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self.page)

        # ------------------------------------------------------------------ #
        # Wire signals → edited()                                              #
        # ------------------------------------------------------------------ #
        
        pid = self._page_id
        self.page.grid_cb.currentIndexChanged(_make_safe_callback(pid, '_on_grid_mode_changed'))
        self.page.edit_grid_le.editingFinished(_make_safe_callback(pid, '_on_edited'))
        self.page.snap_objects_cbx.stateChanged(_make_safe_callback(pid, '_on_edited'))
        self.page.snap_objects_to_grid_cbx.stateChanged(_make_safe_callback(pid, '_on_edited'))
        self.page.move_angle_cb.currentIndexChanged(_make_safe_callback(pid, '_on_edited'))

        # Initial enable state
        self._update_grid_enable()

    @property
    def editor_options(self) -> Optional[EditorOptions]:
        lv = pya.LayoutView.current()
        if lv is None:
            return None

        eo = EditorOptions(lv)
        return eo

    # ------------------------------------------------------------------ #
    # Internal slot helpers                                                #
    # ------------------------------------------------------------------ #

    def _on_edited(self, *_):
        try:
            self.edited()   # signal KLayout to call apply()
        except Exception as e:
            traceback.print_exc()

    def _on_grid_mode_changed(self, *_):
        try:
            self._update_grid_enable()
            self.edited()
        except Exception as e:
            traceback.print_exc()

    def _update_grid_enable(self):
        mode = self.grid_cb.currentIndex
        custom = (mode == 2)
        self.edit_grid_le.setEnabled(custom)
        # When not custom, show the effective value (global grid or 0 for off)
        if mode == 0:
            self.edit_grid_le.setText('')
            self.edit_grid_le.setPlaceholderText('(none)')
        elif mode == 1:
            eo = self.editor_options
            if eo is None:
                return
            self.edit_grid_le.setText(f"{eo.global_grid:.3f}")
            self.edit_grid_le.setPlaceholderText('')
        else:
            self.edit_grid_le.setPlaceholderText('')

    # ------------------------------------------------------------------ #
    # EditorOptionsPage virtual methods                                    #
    # ------------------------------------------------------------------ #

    def _setup(self, dispatcher):
        """Transfer configuration → widgets."""

        eo = self.editor_options
        if eo is None:
            return
        if eo.edit_grid_kind == EditGridKind.NONE:
            self.grid_cb.currentIndex = 0
        elif eo.edit_grid_kind == EditGridKind.GLOBAL:
            self.grid_cb.currentIndex = 1
        elif eo.edit_grid_kind == EditGridKind.OTHER:
            self.grid_cb.currentIndex = 2
        else:
            raise NotImplementedError(f"Unexpected EditGridKind enum case: {eo.edit_grid_kind}")

        # Set the custom value; _update_grid_enable will override display
        # for off/global modes
        self.edit_grid_le.setText(f"{_to_float(eo.edit_grid_value, 0.005):.3f}")

        self.snap_objects_cbx.setChecked(eo.edit_snap_to_objects)
        self.snap_objects_to_grid_cbx.setChecked(eo.edit_snap_objects_to_grid)

        move_angle_mode_idx = 0
        if eo.edit_move_angle_mode == AngleMode.ANY_ANGLE:
            move_angle_mode_idx = 0
        elif eo.edit_move_angle_mode == AngleMode.DIAGONAL:
            move_angle_mode_idx = 1
        elif eo.edit_move_angle_mode == AngleMode.MANHATTAN:
            move_angle_mode_idx = 2
        self.move_angle_cb.currentIndex = min(move_angle_mode_idx, 2)

        self._update_grid_enable()

    def _apply(self, dispatcher):
        """Transfer widgets → configuration."""

        lv = pya.LayoutView.current()
        if lv is None:
            return

        eo = EditorOptions(lv)
    
        grid_idx = self.grid_cb.currentIndex
        if grid_idx == 0:
            eo.set_edit_grid_kind(EditGridKind.NONE)
        elif grid_idx == 1:
            eo.set_edit_grid_kind(EditGridKind.GLOBAL)
        elif grid_idx == 2:
            eo.set_edit_grid_kind(EditGridKind.OTHER)
            gv = _to_float(self.edit_grid_le.text, 0.005)
            eo.set_edit_grid_value(gv)

        eo.set_edit_snap_to_objects(self.snap_objects_cbx.isChecked())
        eo.set_edit_snap_objects_to_grid(self.snap_objects_to_grid_cbx.isChecked())
        
        angle_dict = {
            0: AngleMode.ANY_ANGLE,
            1: AngleMode.DIAGONAL,
            2: AngleMode.MANHATTAN,
        }
        
        move_angle_mode = angle_dict.get(self.move_angle_cb.currentIndex, AngleMode.ANY_ANGLE)
        eo.set_edit_move_angle_mode(move_angle_mode)

        eo.save()

    def setup(self, dispatcher):
        """Transfer configuration → widgets."""
        try:
            self._setup(dispatcher)
        except Exception as e:
            traceback.print_exc()

    def apply(self, dispatcher):
        """Transfer widgets → configuration."""
        try:
            self._apply(dispatcher)
        except Exception as e:
            traceback.print_exc()
