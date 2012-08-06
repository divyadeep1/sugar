# Copyright (C) 2007, Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import gobject

from sugar.graphics import style
from sugar.graphics import animator

from jarabe.model.buddy import get_owner_instance
from jarabe.view.buddyicon import BuddyIcon


class _Animation(animator.Animation):
    def __init__(self, icon, start_size, end_size):
        animator.Animation.__init__(self, 0.0, 1.0)

        self._icon = icon
        self.start_size = start_size
        self.end_size = end_size

    def next_frame(self, current):
        d = (self.end_size - self.start_size) * current
        self._icon.props.pixel_size = int(self.start_size + d)


class TransitionBox(BuddyIcon):
    __gtype_name__ = 'SugarTransitionBox'

    __gsignals__ = {
        'completed': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ([])),
    }

    def __init__(self):
        BuddyIcon.__init__(self, buddy=get_owner_instance(),
                           pixel_size=style.XLARGE_ICON_SIZE)

        self._animator = animator.Animator(0.3)
        self._animator.connect('completed', self._animation_completed_cb)

    def _animation_completed_cb(self, anim):
        self.emit('completed')

    def start_transition(self, start_size, end_size):
        self._animator.remove_all()
        self._animator.add(_Animation(self, start_size, end_size))
        self._animator.start()
