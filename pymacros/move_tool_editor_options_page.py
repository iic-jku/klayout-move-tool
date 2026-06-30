# --------------------------------------------------------------------------------
# SPDX-FileCopyrightText: 2025 Martin Jan Köhler
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

import traceback

import pya

from klayout_plugin_utils.editor_options import EditorOptions, EditGridKind, AngleMode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_get(dispatcher, key, default):
    """get_config returns '' for unknown keys; guard and convert."""
    try:
        raw = dispatcher.get_config(key)
        if raw == "" or raw is None:
            return default
        return raw
    except Exception:
        return default


def _to_bool(v, default=False):
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s in ("true", "1", "yes") if s else default


def _to_float(v, default=0.0):
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def _to_int(v, default=0):
    try:
        return int(v)
    except (ValueError, TypeError):
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
        # title, sort-index
        super().__init__(title, page_index)

        # ------------------------------------------------------------------ #
        # Build the widget tree                                                #
        # ------------------------------------------------------------------ #
        outer_layout = pya.QVBoxLayout(self)
        outer_layout.setContentsMargins(4, 4, 4, 4)
        outer_layout.setSpacing(4)

        # ── Snapping group ─────────────────────────────────────────────────
        snap_group = pya.QGroupBox("Snapping", self)
        snap_layout = pya.QFormLayout(snap_group)
        snap_layout.setContentsMargins(6, 6, 6, 6)
        snap_layout.setSpacing(4)
        snap_layout.setFieldGrowthPolicy(
            pya.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        snap_layout.setLabelAlignment(pya.Qt.AlignmentFlag.AlignRight)

        # Grid mode (combobox)
        self._grid_mode = pya.QComboBox(snap_group)
        self._grid_mode.addItem("No grid")            # index 0
        self._grid_mode.addItem("Global grid")    # index 1
        self._grid_mode.addItem("Other grid")    # index 2
        snap_layout.addRow("Editor grid:", self._grid_mode)

        # Custom grid value
        self._grid_val = pya.QDoubleSpinBox(snap_group)
        self._grid_val.setDecimals(3)
        self._grid_val.setRange(0.0001, 10000.0)
        self._grid_val.setSingleStep(0.005)
        self._grid_val.setSuffix(" µm")
        self._grid_val.setMinimumWidth(110)
        snap_layout.addRow("Grid value:", self._grid_val)

        # Snap-to-objects
        self._snap_objects = pya.QCheckBox("Snap to other objects", snap_group)
        snap_layout.addRow("Objects:", self._snap_objects)

        outer_layout.addWidget(snap_group)

        # ── Connection angle constraint ────────────────────────────────────
        angle_group = pya.QGroupBox("Angle Constraints", self)
        angle_layout = pya.QFormLayout(angle_group)
        angle_layout.setContentsMargins(6, 6, 6, 6)
        angle_layout.setSpacing(4)
        angle_layout.setFieldGrowthPolicy(
            pya.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        angle_layout.setLabelAlignment(pya.Qt.AlignmentFlag.AlignRight)

        self._angle_mode = pya.QComboBox(angle_group)
        self._angle_mode.addItem("Any angle")     # index 0
        self._angle_mode.addItem("Diagonal")      # index 1
        self._angle_mode.addItem("Manhattan")      # index 2
        angle_layout.addRow("Connections:", self._angle_mode)

        self._move_mode = pya.QComboBox(angle_group)
        self._move_mode.addItem("Any direction")   # index 0
        self._move_mode.addItem("Diagonal")        # index 1
        self._move_mode.addItem("Manhattan")        # index 2
        angle_layout.addRow("Movement:", self._move_mode)

        outer_layout.addWidget(angle_group)
        
        outer_layout.addStretch(1)

        # ------------------------------------------------------------------ #
        # Wire signals → edited()                                              #
        # ------------------------------------------------------------------ #
        self._grid_mode.currentIndexChanged(self._on_grid_mode_changed)
        self._grid_val.editingFinished(self._on_edited)
        self._snap_objects.stateChanged(self._on_edited)
        self._angle_mode.currentIndexChanged(self._on_edited)
        self._move_mode.currentIndexChanged(self._on_edited)

        # Initial enable state
        self._update_grid_enable()

    @property
    def editor_options(self) -> EditorOptions:
        lv = pya.LayoutView.current()
        if lv is None:
            return

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
        mode = self._grid_mode.currentIndex
        custom = (mode == 2)
        self._grid_val.setEnabled(custom)
        # When not custom, show the effective value (global grid or 0 for off)
        if mode == 0:
            self._grid_val.setValue(0.0)
            self._grid_val.setSpecialValueText("(none)")
            self._grid_val.setMinimum(0.0)
        elif mode == 1:
            self._grid_val.setMinimum(0.0)
            eo = self.editor_options
            self._grid_val.setValue(eo.global_grid)
            self._grid_val.setSpecialValueText("")
        else:
            self._grid_val.setMinimum(0.0001)
            self._grid_val.setSpecialValueText("")

    # ------------------------------------------------------------------ #
    # EditorOptionsPage virtual methods                                    #
    # ------------------------------------------------------------------ #

    def _setup(self, dispatcher):
        """Transfer configuration → widgets."""

        eo = self.editor_options
        if eo.edit_grid_kind == EditGridKind.NONE:
            self._grid_mode.currentIndex = 0
        elif eo.edit_grid_kind == EditGridKind.GLOBAL:
            self._grid_mode.currentIndex = 1
        elif eo.edit_grid_kind == EditGridKind.OTHER:
            self._grid_mode.currentIndex = 2
        else:
            raise NotImplementedError(f"Unexpected EditGridKind enum case: {eo.edit_grid_kind}")

        # Set the custom value; _update_grid_enable will override display
        # for off/global modes
        self._grid_val.setValue(eo.edit_grid_value or 0.005)

        self._snap_objects.setChecked(eo.edit_snap_objects_to_grid)

        conn_angle_mode_index = 0
        if eo.edit_connect_angle_mode == AngleMode.ANY_ANGLE:
            conn_angle_mode_index = 0
        elif eo.edit_connect_angle_mode == AngleMode.DIAGONAL:
            conn_angle_mode_index = 1
        elif eo.edit_connect_angle_mode == AngleMode.MANHATTAN:
            conn_angle_mode_index = 2
        self._angle_mode.currentIndex = min(conn_angle_mode_index, 2)

        move_angle_mode_idx = 0
        if eo.edit_move_angle_mode == AngleMode.ANY_ANGLE:
            move_angle_mode_idx = 0
        elif eo.edit_move_angle_mode == AngleMode.DIAGONAL:
            move_angle_mode_idx = 1
        elif eo.edit_move_angle_mode == AngleMode.MANHATTAN:
            move_angle_mode_idx = 2
        self._move_mode.currentIndex = min(move_angle_mode_idx, 2)

        self._update_grid_enable()

    def _apply(self, dispatcher):
        """Transfer widgets → configuration."""

        lv = pya.LayoutView.current()
        if lv is None:
            return

        eo = EditorOptions(lv)
    
        grid_idx = self._grid_mode.currentIndex
        if grid_idx == 0:
            eo.set_edit_grid_kind(EditGridKind.NONE)
        elif grid_idx == 1:
            eo.set_edit_grid_kind(EditGridKind.GLOBAL)
        elif grid_idx == 2:
            eo.set_edit_grid_kind(EditGridKind.OTHER)
            gv = self._grid_val.value
            eo.set_edit_grid_value(gv)

        eo.set_edit_snap_objects_to_grid(self._snap_objects.isChecked())

        angle_dict = {
            0: AngleMode.ANY_ANGLE,
            1: AngleMode.DIAGONAL,
            2: AngleMode.MANHATTAN,
        }
        
        connect_angle_mode = angle_dict.get(self._angle_mode.currentIndex, AngleMode.ANY_ANGLE)
        move_angle_mode = angle_dict.get(self._move_mode.currentIndex, AngleMode.ANY_ANGLE)
        eo.set_edit_connect_angle_mode(connect_angle_mode)
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
