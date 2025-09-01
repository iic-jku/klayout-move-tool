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

import pya
from utils.debugging import debug, Debugging
from utils.str_enum_compat import StrEnum


class AngleMode(StrEnum):
    ANY_ANGLE = 'any'
    DIAGONAL = 'diagonal'
    MANHATTAN = 'ortho'
    

class EditorOptions:
    def __init__(self, view: pya.LayoutView):
        self.view = view
        
        self._edit_connect_angle_mode = AngleMode(view.get_config('edit-connect-angle-mode'))
        self._edit_move_angle_mode = AngleMode(view.get_config('edit-move-angle-mode'))

    def plugin_configure(self, name: str, value: str):
        if name == 'edit-connect-angle-mode':
            self._edit_connect_angle_mode = AngleMode(value)
        elif name == 'edit-move-angle-mode':
            self._edit_move_angle_mode = AngleMode(value)
        if Debugging.DEBUG:
            debug(f"Plugin reconfigured: EditorOptions are now {self.__dict__}")

    @property
    def edit_move_angle_mode(self) -> AngleMode:
        return self._edit_move_angle_mode

    @property
    def edit_connect_angle_mode(self) -> AngleMode:
        return self._edit_connect_angle_mode

    @classmethod
    def show_editor_options(cls):
        # NOTE: if we directly call the Editor Options menu action
        #       the GUI immediately will switch back to the Librariew view
        #       so we enqueue it into the event loop

        mw = pya.Application.instance().main_window()
    
        def on_timeout():
            mw.call_menu('cm_edit_options')
            if getattr(cls, "_defer_timer", None):
                try:
                    cls._defer_timer._destroy()
                except RuntimeError:
                    pass  # already deleted by Qt
                cls._defer_timer = None
        
        cls._defer_timer = pya.QTimer(mw)
        cls._defer_timer.setSingleShot(True)
        cls._defer_timer.timeout = on_timeout
        cls._defer_timer.start(0)