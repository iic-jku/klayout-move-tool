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

from __future__ import annotations
from abc import abstractmethod
from dataclasses import dataclass
from functools import cached_property
from typing import *
import os 
import sys

import pya

from utils.debugging import debug, Debugging
from utils.editor_options import EditorOptions
from utils.str_enum_compat import StrEnum


class MoveQuicklyToolState(StrEnum):
    INACTIVE = "inactive"
    SELECTING = "selecting"               # wait for click to happen to get moving
    DRAG_SELECTING = "drag_selecting"     # user draws a (additional) selection rectangle (shift = additional)
    MOVING = "moving"


@dataclass
class SelectableObject:
    path: List[pya.InstElement]
    bbox: pya.Box


@dataclass
class ShapeOfInstance(SelectableObject):
    shape: pya.Shape
 
    
@dataclass
class Instance(SelectableObject):
    instance: pya.Instance


@dataclass
class MoveQuicklyToolSelection:
    objects: List[Instance | ShapeOfInstance]

    def is_single_selection(self) -> bool:
        return len(self.objects) == 1
        
    def is_multi_selection(self) -> bool:
        return len(self.objects) >= 2
        
    @cached_property
    def bbox(self) -> pya.Box:
        r = pya.Region()
        for o in self.objects:
            r.insert(o.bbox)
        return r.bbox()
    
    @cached_property
    def position(self) -> pya.Point:
        return pya.Point(self.bbox.left, self.bbox.bottom)

    def all_instances(self) -> List[Instance]:
        return [o for o in self.objects if isinstance(o, Instance)]

    def all_shapes_of_instance(self) -> List[ShapeOfInstance]:
        return [o for o in self.objects if isinstance(o, ShapeOfInstance)]
        
    def as_transformees(self) -> List[pya.Instance | pya.Shape]:
        tl = []
        tl += [o.instance for o in self.objects if isinstance(o, Instance)]
        for o in self.objects:
            if not isinstance(o, ShapeOfInstance):
                continue
            if len(o.path) == 0:
                tl += [o.shape]  # directly move this shape
            else:  # the shape belongs to a subcell, never move the shape alone, always the whole cell
                tl += [o.path[0].inst()]
        return tl


@dataclass
class MoveOperation:
    @abstractmethod
    def effective_delta(self) -> pya.DVector:
        raise NotImplementedError()


@dataclass
class MouseMoveOperation(MoveOperation):
    original_position: pya.DPoint
    snapped_position: pya.DPoint
    from_cursor: pya.DPoint                # original cursor
    to_cursor: pya.DPoint                  # original cursor
    snapped_cursor_delta: pya.DVector      # snap-to-grid cursor delta
    
    def effective_delta(self) -> pya.DVector:
        # NOTE: because of snap-to-grid, we might have to correct the original position of the selection
        delta = self.snapped_position - self.original_position + self.snapped_cursor_delta
        return delta


@dataclass
class TextMoveOperation(MoveOperation):
    original_position: pya.DPoint

    x: float
    y: float
    dx: float
    dy: float
    
    def effective_delta(self) -> pya.DVector:
        delta = pya.DPoint(self.x, self.y) - self.original_position + pya.DVector(self.dx, self.dy)
        return delta


class MoveQuicklyToolSetupDock(pya.QDockWidget):
    def __init__(self, host: MoveQuicklyToolPlugin):
        super().__init__()
        self.setupWidget = MoveQuicklyToolSetupWidget(host)
        self.setWidget(self.setupWidget)
        self.setWindowTitle("Move Quickly Tool")

    def updateState(self, state: MoveQuicklyToolState):
        self.setupWidget.updateState(state)
        
    def updateSelection(self, selection: Optional[MoveQuicklyToolSelection]):
        self.setupWidget.updateSelection(selection)

    def updatePositionValues(self, x: float, y: float, dx: float, dy: float):
        self.setupWidget.updatePositionValues(x, y, dx, dy)

    def navigateToNextTextField(self):
        self.setupWidget.navigateToNextTextField()
        
        
class MoveQuicklyToolSetupWidget(pya.QWidget):
    def __init__(self, host: MoveQuicklyToolPlugin):
        super().__init__()
        self.host = host
        self.selection_label = pya.QLabel('<span style="text-decoration: underline;">Selection:</span>')
        self.selection_value = pya.QLabel('None')
        
        self.x_label = pya.QLabel('<span style="text-decoration: underline;">X:</span>')
        self.x_value = pya.QDoubleSpinBox()
        self.x_unit = pya.QLabel('µm')
        
        self.y_label = pya.QLabel('<span style="text-decoration: underline;">Y:</span>')
        self.y_value = pya.QDoubleSpinBox()
        self.y_unit = pya.QLabel('µm')
        
        self.dx_label = pya.QLabel('<span style="text-decoration: underline;">dX:</span>')
        self.dx_value = pya.QDoubleSpinBox()
        self.dx_unit = pya.QLabel('µm')

        self.dy_label = pya.QLabel('<span style="text-decoration: underline;">dY:</span>')
        self.dy_value = pya.QDoubleSpinBox()
        self.dy_unit = pya.QLabel('µm')
        
        spin_box_size_policy = pya.QSizePolicy(pya.QSizePolicy.Expanding, pya.QSizePolicy.Expanding)
        for sb in (self.x_value, self.y_value, self.dx_value, self.dy_value):
            sb.setSingleStep(0.01)
            sb.setDecimals(3)
            sb.setMinimum(-float('inf'))
            sb.setMaximum(float('inf'))
            sb.setSizePolicy(spin_box_size_policy)
        
        self.spacerItem = pya.QSpacerItem(0, 20, pya.QSizePolicy.Minimum, pya.QSizePolicy.Fixed)
        self.cancelInfoLabel = pya.QLabel('<span style="color: grey;"><span style="text-decoration: underline;">Hint:</span> Esc to cancel</span>')
        
        self.layout = pya.QGridLayout()
        self.layout.setSpacing(5)
        self.layout.setVerticalSpacing(5)
        self.layout.addWidget(self.selection_label,     0, 0)
        self.layout.addWidget(self.selection_value,     0, 1)
        self.layout.addWidget(self.x_label,             1, 0)
        self.layout.addWidget(self.x_value,             1, 1)
        self.layout.addWidget(self.x_unit,              1, 2)
        self.layout.addWidget(self.y_label,             2, 0)
        self.layout.addWidget(self.y_value,             2, 1)
        self.layout.addWidget(self.y_unit,              2, 2)
        self.layout.addWidget(self.dx_label,            3, 0)
        self.layout.addWidget(self.dx_value,            3, 1)
        self.layout.addWidget(self.dx_unit,             3, 2)
        self.layout.addWidget(self.dy_label,            4, 0)
        self.layout.addWidget(self.dy_value,            4, 1)
        self.layout.addWidget(self.dy_unit,             4, 2)
        self.layout.addItem(self.spacerItem)
        self.layout.addWidget(self.cancelInfoLabel,     5, 0, 1, 3)
        self.layout.setRowStretch(6, 3)
        self.setLayout(self.layout)
        
    def hideEvent(self, event):
        event.accept()

    def updateState(self, state: MoveQuicklyToolState):
        return

    def format_selection(self, selection: Optional[MoveQuicklyToolSelection]) -> str:
        if selection is None or \
           len(selection.objects) == 0:
            return "None"
        def format_objects(singular: str, objects: List[Instance | ShapeOfInstance]):
            if objects is not None:
                n = len(objects)
                match n:
                    case 0: return ''
                    case 1: return f"1 {singular}"
                    case _: return f"{n} {singular}s"
            return ''
        
        instances = format_objects("instance", selection.all_instances())
        shapes = format_objects("shape", selection.all_shapes_of_instance())
        if instances == '':
            return shapes
        elif shapes == '':
            return instances
        else:
            return f"{instances}, {shapes}"

    def updateSelection(self, selection: Optional[MoveQuicklyToolSelection]):
        txt = self.format_selection(selection)
        self.selection_value.setText(txt)
        
        enabled = selection is not None
        self.x_value.setEnabled(enabled)
        self.y_value.setEnabled(enabled)
        self.dx_value.setEnabled(enabled)
        self.dy_value.setEnabled(enabled)
        
        if enabled:
            dpos: pya.DPoint = selection.position.to_dtype(self.host.dbu)
            if dpos is None:
                self.x_value.setValue(0.0)
                self.y_value.setValue(0.0)
            else:
                self.x_value.setValue(dpos.x)
                self.y_value.setValue(dpos.y)
        else:
            self.x_value.clearFocus()
            self.y_value.clearFocus()
            self.dx_value.clearFocus()
            self.dy_value.clearFocus()
            
            self.x_value.setValue(0.0)
            self.y_value.setValue(0.0)
        self.dx_value.setValue(0.0)
        self.dy_value.setValue(0.0)

    def updatePositionValues(self, x: float, y: float, dx: float, dy: float):
        self.x_value.setValue(x)
        self.y_value.setValue(y)
        self.dx_value.setValue(dx)
        self.dy_value.setValue(dy)

    def navigateToNextTextField(self):
        self.focusNextPrevChild(next=True)

    def focusNextPrevChild(self, next: bool) -> bool:
        if next:
            if self.x_value.hasFocus():
                self.y_value.setFocus()
                self.y_value.selectAll()
            elif self.y_value.hasFocus():
                self.dx_value.setFocus()
                self.dx_value.selectAll()
            elif self.dx_value.hasFocus():
                self.dy_value.setFocus()
                self.dy_value.selectAll()
            else:
                self.x_value.setFocus()
                self.x_value.selectAll()
        else:
            if self.x_value.hasFocus():
                self.dy_value.setFocus()
                self.dy_value.selectAll()
            elif self.dy_value.hasFocus():
                self.dx_value.setFocus()
                self.dx_value.selectAll()
            elif self.dx_value.hasFocus():
                self.y_value.setFocus()
                self.y_value.selectAll()
            else:
                self.x_value.setFocus()        
                self.x_value.selectAll()
        return True

    def keyPressEvent(self, event: pya.QKeyEvent):
        if Debugging.DEBUG:
            debug(f"SetupDock.key_event: key={event.key()}, buttons={event.modifiers}")
        match event.key():
            case pya.KeyCode.Enter | pya.KeyCode.Return:
                if Debugging.DEBUG:
                    debug("keyPressEvent: enter!")
                    
                orig_pos = self.host.selection.position.to_dtype(self.host.dbu)
                op = TextMoveOperation(orig_pos,
                                       self.x_value.value, self.y_value.value,
                                       self.dx_value.value, self.dy_value.value)
                self.host.commit_move(op)
                event.accept()
                return
        super().keyPressEvent(event)
        

class MoveQuicklyToolPlugin(pya.Plugin):
    def __init__(self, view: pya.LayoutView):
        super().__init__()
        self.setupDock      = None
        self.view            = view

        self._state = MoveQuicklyToolState.INACTIVE

        self._selection: Optional[MoveQuicklyToolSelection] = None
        self.move_preview_markers = []
        self.drag_selection_markers = []
        
        self.editor_options = None
        
        self.is_dragging = False
        self.drag_selection_from_dpoint = None
        self.drag_selection_to_dpoint = None
        self.move_from_dpoint = None
        self.move_to_dpoint = None
        self.move_operation = None

    @property
    def cell_view(self) -> pya.CellView:
        return self.view.active_cellview()

    @property
    def layout(self) -> pya.Layout:
        return self.cell_view.layout()
        
    @property
    def dbu(self) -> float:
        return self.layout.dbu

    @property
    def state(self) -> MoveQuicklyToolState:
        return self._state

    @state.setter
    def state(self, state: MoveQuicklyToolState):
        if Debugging.DEBUG:
            debug(f"Transitioning from {self._state.value} to {state.value}")
        self._state = state
        if not(self.setupDock):
            pass
        else:
            self.setupDock.updateState(state)
            
    @property
    def selection(self) -> MoveQuicklyToolSelection:
        return self._selection

    @selection.setter
    def selection(self, selection: Optional[MoveQuicklyToolSelection]):
        # # Hotspot, don't log this
        # if Debugging.DEBUG:
        #     debug(f"setting selection to {selection}")
        self._selection = selection
        if not(self.setupDock):
            pass
        else:
            self.setupDock.updateSelection(selection)

    def selected_objects(self) -> Optional[MoveQuicklyToolSelection]:
        so = []
        for o in self.view.each_object_selected():
            if len(o.path) == 0:  # a shape within the same cell has to be aligned
                if o.shape is not None:
                    bbox = o.shape.bbox().transformed(o.source_trans())
                    so += [ShapeOfInstance(shape=o.shape, path=o.path, bbox=bbox)]
            else:  # the instance/shape is within subcells, we want to move only the top-most instance!
                inst = o.path[0].inst()
                bbox = inst.bbox()
                so += [Instance(instance=inst, path=o.path[0:1], bbox=bbox)]
        if len(so) == 0:
            return None
        return MoveQuicklyToolSelection(objects=so)

    def _visible_left_dock_widgets(self) -> List[pya.QDockWidget]:
        widgets = []
        mw = pya.MainWindow.instance()
        for ch in mw.findChildren():
            if 'QDockWidget' not in ch.__class__.__name__:
                continue
            if mw.dockWidgetArea(ch) == pya.Qt.LeftDockWidgetArea and ch.isVisible():
                widgets.append(ch)
        return widgets
        
    @staticmethod
    def is_left_dock_visible(visible_left_dock_widgets: List[pya.QDockWidget]) -> bool:
        for w in visible_left_dock_widgets:
            if Debugging.DEBUG:
                debug(f"MoveQuicklyToolPlugin.is_left_dock_visible, "
                      f"at least one dock is visible in the left sidebar.")
            return True
        if Debugging.DEBUG:
            debug(f"MoveQuicklyToolPlugin.is_left_dock_visible, "
                  f"no docks are visible in the left sidebar.")
        return False
    
    def activated(self):
        view_is_visible = self.view.widget().isVisible()
        if Debugging.DEBUG:
            debug(f"MoveQuicklyToolPlugin.activated, "
                  f"for cell view {self.cell_view.cell_name}, "
                  f"is visible: {view_is_visible}")
            debug(f"viewport trans: {self.view.viewport_trans()}")
        if not view_is_visible:
            return

        if not(self.setupDock):
            mw = pya.Application.instance().main_window()
            self.setupDock = MoveQuicklyToolSetupDock(host=self)
            mw.addDockWidget(pya.Qt_DockWidgetArea.RightDockWidgetArea, self.setupDock)
        self.setupDock.show()

        self.editor_options = EditorOptions(view=self.view)
        
        # NOTE: only show the editor options if anything is shown in the left sidebar, but
        #       not if the user has deliberatly hidden it and it would "waste" horizontal screen space
        visible_left_dock_widgets = self._visible_left_dock_widgets()
        if self.is_left_dock_visible(visible_left_dock_widgets):
            debug(f"MoveQuicklyToolPlugin.activated: show editor options dock widget")
            EditorOptions.show_editor_options()
        self._state = MoveQuicklyToolState.SELECTING
        self.selection = self.selected_objects()
            
    def deactivated(self):
        if Debugging.DEBUG:
            debug("MoveQuicklyToolPlugin.deactivated")
        
        self._clear_all_markers()
        self.selection = None
        self.is_dragging = False

        self._state = MoveQuicklyToolState.INACTIVE
        
        self.editor_options = None
        
        self.ungrab_mouse()
        if self.setupDock:
            self.setupDock.hide()

    def deactivate(self):
        if Debugging.DEBUG:
            debug("MoveQuicklyToolPlugin.deactivate")
        esc_key  = 16777216 
        keyPress = pya.QKeyEvent(pya.QKeyEvent.KeyPress, esc_key, pya.Qt.NoModifier)
        pya.QApplication.sendEvent(self.view.widget(), keyPress)        

    def configure(self, name: str, value: str) -> bool:
        if Debugging.DEBUG:
            debug(f"MoveQuicklyToolPlugin.configure, name={name}, value={value}")
        if self.editor_options is not None:
            self.editor_options.plugin_configure(name, value)
        return False

    def _clear_move_preview_markers(self):
        for marker in self.move_preview_markers:
            marker._destroy()
        self.move_preview_markers = []
        
    def _clear_drag_selection_markers(self):
        for marker in self.drag_selection_markers:
            marker._destroy()
        self.drag_selection_markers = []

    def _clear_all_markers(self):
        self._clear_move_preview_markers()
        self._clear_drag_selection_markers()
        
    def viewport_adjust(self, v: int) -> int:
        trans = pya.CplxTrans(self.view.viewport_trans(), self.dbu)
        return v / trans.mag
        
    def update_move_preview_markers(self):
        self._clear_move_preview_markers()
        
        if self.selection is None:
            return
        
        match self.state:
            case MoveQuicklyToolState.INACTIVE | MoveQuicklyToolState.SELECTING | MoveQuicklyToolState.DRAG_SELECTING:
                return
            case MoveQuicklyToolState.MOVING:
                delta = self.move_operation.effective_delta()
                preview_box = self.selection.bbox.to_dtype(self.dbu).moved(delta)
                
                marker = pya.Marker(self.view)
                marker.line_style     = 0
                marker.line_width     = 2
                marker.vertex_size    = 0 
                marker.dither_pattern = 1
                marker.set(preview_box)
                
                self.move_preview_markers += [marker]
        
    def update_drag_selection_markers(self):
        self._clear_drag_selection_markers()
        
        match self.state:
            case MoveQuicklyToolState.INACTIVE | MoveQuicklyToolState.SELECTING | MoveQuicklyToolState.MOVING:
                return
            case MoveQuicklyToolState.DRAG_SELECTING:
                selection_box = pya.DBox(self.drag_selection_from_dpoint, self.drag_selection_to_dpoint)

                marker = pya.Marker(self.view)
                marker.line_style     = 2
                marker.line_width     = 2
                marker.vertex_size    = 0 
                marker.dither_pattern = 1
                marker.set(selection_box)
                self.drag_selection_markers += [marker]
        
    def select_object_at(self, dpoint: pya.DPoint, buttons: int):
        if buttons & pya.ButtonState.ShiftKey:
            selection_mode = pya.LayoutView.SelectionMode.Add
        else:
            selection_mode = pya.LayoutView.SelectionMode.Replace
        self.view.select_from(dpoint, selection_mode)
        self.selection = self.selected_objects()
       
    def visible_layer_indexes(self) -> List[int]:
        idxs = []
        for lref in self.view.each_layer():
            if lref.visible and lref.valid:
                if lref.layer_index() == -1:  # hidden by the user
                    continue
                # # Hotspot, don't log this
                # if Debugging.DEBUG:
                #     debug(f"layer is visible, name={lref.name}, idx={lref.layer_index()}, "
                #           f"marked={lref.marked} cellview={lref.cellview()}, "
                #           f"source={lref.source}")
                idxs.append(lref.layer_index())
        return idxs
    
    def select_objects(self, search_box: pya.DBox, selection_mode: pya.LayoutView.SelectionMode):
        search_box = search_box.to_itype(self.dbu)
        visible_layer_indexes = self.visible_layer_indexes()
        for top_cell in self.layout.top_cells():
            if self.cell_view.is_cell_hidden(top_cell):
                continue
            if self.view.max_hier_levels >= 1:
                iter = top_cell.begin_instances_rec_overlapping(search_box)
                iter.min_depth = max(self.view.min_hier_levels-1, 0)
                iter.max_depth = max(self.view.max_hier_levels-1, 0)
                while not iter.at_end():
                    inst = iter.current_inst_element().inst()
                    hidden = self.view.is_cell_hidden(inst.cell.cell_index(), self.view.active_cellview_index)
                    if not hidden:
                        self.view.select_from(inst.bbox().to_dtype(self.dbu), selection_mode)
                    iter.next()
            if self.view.max_hier_levels >= 1:
                for lyr in visible_layer_indexes:
                    iter = top_cell.begin_shapes_rec_overlapping(lyr, search_box)
                    iter.min_depth = max(self.view.min_hier_levels-1, 0)
                    iter.max_depth = max(self.view.max_hier_levels-1, 0)
                    while not iter.at_end():
                        sh = iter.shape()
                        self.view.select_from(sh.bbox().to_dtype(self.dbu), selection_mode)
                        iter.next()
        
    def mouse_moved_event(self, dpoint: pya.DPoint, buttons: int, prio: bool):
        if prio:
            # # Hotspot, don't log this
            # if Debugging.DEBUG:
            #     debug(f"mouse moved event, p={dpoint}, buttons={buttons}, prio={prio}")
            
            # NOTE: dragging will change the selection
            #       clicking (select object) and moving without dragging will show the move preview
            
            if buttons & pya.ButtonState.LeftButton:  # drag selection
                match self.state:
                    case MoveQuicklyToolState.INACTIVE | MoveQuicklyToolState.SELECTING | MoveQuicklyToolState.MOVING:
                        self.state = MoveQuicklyToolState.DRAG_SELECTING
                        # NOTE: the from point is directly recorded via mouse_button_pressed_event, because some drag events could be skipped!
                        self.drag_selection_to_dpoint = dpoint
                    case MoveQuicklyToolState.DRAG_SELECTING:
                        self.drag_selection_to_dpoint = dpoint
                
                if self.drag_selection_from_dpoint is None:
                    return False
                
                self.select_objects(pya.DBox(self.drag_selection_from_dpoint, self.drag_selection_to_dpoint), pya.LayoutView.SelectionMode.Add)
                self.selection = self.selected_objects()
                
                self.update_drag_selection_markers()
                return True
            elif buttons & pya.ButtonState.ShiftKey:
                state = MoveQuicklyToolState.SELECTING
                self._clear_move_preview_markers()
                return True
            else:
                # # Hotspot, don't log this
                # if Debugging.DEBUG:
                #     debug(f"mouse drag event, p={dpoint}, buttons={buttons}, prio={prio}")
                if self.state == MoveQuicklyToolState.MOVING:
                    snapped_from_cursor = self.editor_options.snap_to_grid_if_necessary(self.move_from_dpoint)
                    snapped_to_cursor = self.editor_options.snap_to_grid_if_necessary(dpoint)
                    constrained_to_cursor = self.editor_options.constrain_angle(origin=snapped_from_cursor, destination=snapped_to_cursor)
                    
                    delta = constrained_to_cursor - snapped_from_cursor
                    
                    orig_pos = self.selection.position.to_dtype(self.dbu)
                    pos = self.editor_options.snap_to_grid_if_necessary(orig_pos)
                    
                    self.move_operation = MouseMoveOperation(original_position=orig_pos, 
                                                             snapped_position=pos, 
                                                             from_cursor=self.move_from_dpoint,
                                                             to_cursor=dpoint,
                                                             snapped_cursor_delta=delta)
                    self.setupDock.updatePositionValues(pos.x + delta.x,
                                                        pos.y + delta.y,
                                                        delta.x, 
                                                        delta.y)
                    self.update_move_preview_markers()
                    
                    return True
        return False

    def mouse_button_pressed_event(self, dpoint: pya.DPoint, buttons: int, prio: bool) -> bool:
        # NOTE: directly record drag selection origin, because some drag events could be skipped!
        self.drag_selection_from_dpoint = dpoint
        return False

    def mouse_button_released_event(self, dpoint: pya.DPoint, buttons: int, prio: bool) -> bool:
        if Debugging.DEBUG:
            debug(f"mouse button released event, p={dpoint}, buttons={buttons}, prio={prio}")
        
        if self.is_dragging:
            self.is_dragging = False
            self.drag_selection_from_dpoint = None
            self.drag_selection_to_dpoint = None
            return True

        match self.state:
            case MoveQuicklyToolState.INACTIVE:
                pass
            case MoveQuicklyToolState.SELECTING:
                if self.selection is not None and not buttons & pya.ButtonState.ShiftKey:
                    self.state = MoveQuicklyToolState.MOVING
                    self.move_from_dpoint = dpoint
                    return True                        
            case MoveQuicklyToolState.DRAG_SELECTING:
                self._clear_drag_selection_markers()
                self.drag_selection_from_dpoint = None
                self.drag_selection_to_dpoint = None
                self.state = MoveQuicklyToolState.SELECTING
                return True
                
            case MoveQuicklyToolState.MOVING:
                pass
                
        return False

    def mouse_click_event(self, dpoint: pya.DPoint, buttons: int, prio: bool) -> bool:
        if prio:
            if buttons & pya.ButtonState.LeftButton:
                match self.state:
                    case MoveQuicklyToolState.INACTIVE:
                        pass
                    case MoveQuicklyToolState.SELECTING:
                        if self.selection is None or buttons & pya.ButtonState.ShiftKey:
                            self._clear_all_markers()
                            self.select_object_at(dpoint, buttons)
                            
                        if self.selection is not None and not buttons & pya.ButtonState.ShiftKey:
                            self.state = MoveQuicklyToolState.MOVING
                            self.move_from_dpoint = dpoint
                        if Debugging.DEBUG:
                            debug(f"State {MoveQuicklyToolState.SELECTING} → self.state: selection={self.selection}, move_from_dpoint={self.move_from_dpoint}")
                        return True                        
                    case MoveQuicklyToolState.DRAG_SELECTING:
                        pass
                    case MoveQuicklyToolState.MOVING:
                        if buttons & pya.ButtonState.ShiftKey:
                            self.select_object_at(dpoint, buttons)
                            self._clear_all_markers()
                            self.state = MoveQuicklyToolState.SELECTING
                        elif self.selection is not None:
                            self.commit_move(self.move_operation)
                        return True                        
            elif buttons in [pya.ButtonState.RightButton, pya.ButtonState.RightButton]:
                self._clear_all_markers()
                self.view.clear_selection()
                self.selection = None
                self.state = MoveQuicklyToolState.SELECTING
                return True
                
        return False
        
    def key_event(self, key: int, buttons: int):
        if Debugging.DEBUG:
            debug(f"key_event: key={key}, buttons={buttons}")
        
        if buttons & pya.ButtonState.ShiftKey and \
           self.state == MoveQuicklyToolState.MOVING:
            if Debugging.DEBUG:
                debug("key_event: shift cancels moving!")
            self.state = MoveQuicklyToolState.SELECTING
            self._clear_move_preview_markers()
            return True
                
        match key:
            case pya.KeyCode.Tab:
                if Debugging.DEBUG:
                    debug("key_event: tab!")
                if self.selection is not None:
                    orig_pos = self.selection.position.to_dtype(self.dbu)
                    self.setupDock.updatePositionValues(orig_pos.x,
                                                        orig_pos.y,
                                                        0.0, 0.0)
                    self._clear_move_preview_markers()
                    self.setupDock.navigateToNextTextField()
                    return True
                
            case pya.KeyCode.Enter | pya.KeyCode.Return:
                if Debugging.DEBUG:
                    debug("key_event: enter!")
                if self.selection is not None:
                    self.commit_move()
                    return True
                    
        return False
        
    def commit_move(self, operation: MoveOperation):
        self._clear_all_markers()
        if self.selection is None:
            self.state = MoveQuicklyToolState.SELECTING
            return
            
        delta = operation.effective_delta()

        if Debugging.DEBUG:
            debug(f"commit_move: operation={operation}")
            
        self.view.transaction("move quickly")
        try:
            trans = pya.DTrans(delta.x, delta.y)
            for t in self.selection.as_transformees():
                t.transform(trans)
        finally:
            self.view.commit()
            self.selection = None
            # reset move tool selection, but keep selection of the LayoutView
            # NOTE: do not deactivate, stay in M-mode!
            self.state = MoveQuicklyToolState.SELECTING


class MoveQuicklyToolPluginFactory(pya.PluginFactory):
    def __init__(self):
        super().__init__()
        self.register(-1000, "Move Quickly Tool", "Move Quickly (M)", ':move_24px')
  
    def create_plugin(self, manager, root, view):
        return MoveQuicklyToolPlugin(view)

