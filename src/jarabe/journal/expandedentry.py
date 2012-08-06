# Copyright (C) 2007, One Laptop Per Child
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

import logging
from gettext import gettext as _
import StringIO
import time
import os

import cairo
import gobject
import glib
import gtk
import simplejson

from sugar.graphics import style
from sugar.graphics.xocolor import XoColor
from sugar.util import format_size

from jarabe.journal.keepicon import KeepIcon
from jarabe.journal.palettes import ObjectPalette, BuddyPalette
from jarabe.journal import misc
from jarabe.journal import model
from jarabe.view.eventicon import EventIcon


class Separator(gtk.VBox):
    def __init__(self, orientation):
        gtk.VBox.__init__(self,
                background_color=style.COLOR_PANEL_GREY.get_gdk_color())


class BuddyList(gtk.Alignment):
    def __init__(self, buddies):
        gtk.Alignment.__init__(self, 0, 0, 0, 0)

        hbox = gtk.HBox()
        for buddy in buddies:
            nick_, color = buddy
            icon = EventIcon(icon_name='computer-xo',
                             xo_color=XoColor(color),
                             pixel_size=style.STANDARD_ICON_SIZE)
            icon.set_palette(BuddyPalette(buddy))
            hbox.pack_start(icon)
        self.add(hbox)


class ExpandedEntry(gtk.EventBox):
    def __init__(self):
        gtk.EventBox.__init__(self)
        self._vbox = gtk.VBox()
        self.add(self._vbox)

        self._metadata = None
        self._update_title_sid = None

        self.modify_bg(gtk.STATE_NORMAL, style.COLOR_WHITE.get_gdk_color())

        # Create a header
        header = gtk.HBox()
        self._vbox.pack_start(header, False, False, style.DEFAULT_SPACING * 2)

        # Create a two-column body
        body_box = gtk.EventBox()
        body_box.set_border_width(style.DEFAULT_SPACING)
        body_box.modify_bg(gtk.STATE_NORMAL, style.COLOR_WHITE.get_gdk_color())
        self._vbox.pack_start(body_box)
        body = gtk.HBox()
        body_box.add(body)

        first_column = gtk.VBox()
        body.pack_start(first_column, False, False, style.DEFAULT_SPACING)

        second_column = gtk.VBox()
        body.pack_start(second_column)

        # Header
        self._keep_icon = self._create_keep_icon()
        header.pack_start(self._keep_icon, False, False, style.DEFAULT_SPACING)

        self._icon = None
        self._icon_box = gtk.HBox()
        header.pack_start(self._icon_box, False, False, style.DEFAULT_SPACING)

        self._title = self._create_title()
        header.pack_start(self._title)

        # TODO: create a version list popup instead of a date label
        self._date = self._create_date()
        header.pack_start(self._date, False, False, style.DEFAULT_SPACING)

        if gtk.widget_get_default_direction() == gtk.TEXT_DIR_RTL:
            header.reverse()

        # First body column
        self._preview_box = gtk.Frame()
        first_column.pack_start(self._preview_box, expand=False)

        self._technical_box = gtk.VBox()
        first_column.pack_start(self._technical_box)

        # Second body column
        description_box, self._description = self._create_description()
        second_column.pack_start(description_box, True, True,
                                 style.DEFAULT_SPACING)

        tags_box, self._tags = self._create_tags()
        second_column.pack_start(tags_box, True, True,
                                 style.DEFAULT_SPACING)

        self._buddy_list = gtk.VBox()
        second_column.pack_start(self._buddy_list)

        self.show_all()

    def set_metadata(self, metadata):
        if self._metadata == metadata:
            return
        self._metadata = metadata

        self._keep_icon.set_active(int(metadata.get('keep', 0)) == 1)

        self._icon = self._create_icon()
        self._icon_box.foreach(self._icon_box.remove)
        self._icon_box.pack_start(self._icon, False, False)

        self._date.set_text(misc.get_date(metadata))

        self._title.set_text(metadata.get('title', _('Untitled')))

        if self._preview_box.get_child():
            self._preview_box.remove(self._preview_box.get_child())
        self._preview_box.add(self._create_preview())

        self._technical_box.foreach(self._technical_box.remove)
        self._technical_box.pack_start(self._create_technical(),
                                       False, False, style.DEFAULT_SPACING)

        self._buddy_list.foreach(self._buddy_list.remove)
        self._buddy_list.pack_start(self._create_buddy_list(), False, False,
                                    style.DEFAULT_SPACING)

        description = metadata.get('description', '')
        self._description.get_buffer().set_text(description)
        tags = metadata.get('tags', '')
        self._tags.get_buffer().set_text(tags)

    def _create_keep_icon(self):
        keep_icon = KeepIcon()
        keep_icon.connect('toggled', self._keep_icon_toggled_cb)
        return keep_icon

    def _create_icon(self):
        icon = EventIcon(file_name=misc.get_icon_name(self._metadata))
        icon.connect_after('button-release-event',
                           self._icon_button_release_event_cb)

        if misc.is_activity_bundle(self._metadata):
            xo_color = XoColor('%s,%s' % (style.COLOR_BUTTON_GREY.get_svg(),
                                          style.COLOR_TRANSPARENT.get_svg()))
        else:
            xo_color = misc.get_icon_color(self._metadata)
        icon.props.xo_color = xo_color

        icon.set_palette(ObjectPalette(self._metadata))

        return icon

    def _create_title(self):
        entry = gtk.Entry()
        entry.connect('focus-out-event', self._title_focus_out_event_cb)

        bg_color = style.COLOR_WHITE.get_gdk_color()
        entry.modify_bg(gtk.STATE_INSENSITIVE, bg_color)
        entry.modify_base(gtk.STATE_INSENSITIVE, bg_color)

        return entry

    def _create_date(self):
        date = gtk.Label()
        return date

    def _create_preview(self):
        width = style.zoom(320)
        height = style.zoom(240)
        box = gtk.EventBox()
        box.modify_bg(gtk.STATE_NORMAL, style.COLOR_WHITE.get_gdk_color())

        if len(self._metadata.get('preview', '')) > 4:
            if self._metadata['preview'][1:4] == 'PNG':
                preview_data = self._metadata['preview']
            else:
                # TODO: We are close to be able to drop this.
                import base64
                preview_data = base64.b64decode(
                        self._metadata['preview'])

            png_file = StringIO.StringIO(preview_data)
            try:
                # Load image and scale to dimensions
                surface = cairo.ImageSurface.create_from_png(png_file)
                png_width = surface.get_width()
                png_height = surface.get_height()
                pixmap = gtk.gdk.Pixmap(None, png_width, png_height, 24)
                cr = pixmap.cairo_create()
                cr.set_source_surface(surface, 0, 0)
                cr.scale(width / png_width, height / png_height)
                cr.paint()

                im = gtk.image_new_from_pixmap(pixmap, None)
                has_preview = True
            except Exception:
                logging.exception('Error while loading the preview')
                has_preview = False
        else:
            has_preview = False

        if has_preview:
            box.add(im)
        else:
            label = gtk.Label()
            label.set_text(_('No preview'))
            label.set_size_request(width, height)
            box.add(label)

        box.connect_after('button-release-event',
                          self._preview_box_button_release_event_cb)
        return box

    def _create_technical(self):
        vbox = gtk.VBox()
        vbox.props.spacing = style.DEFAULT_SPACING

        label = \
            _('Kind: %s') % (self._metadata.get('mime_type') or \
                                 _('Unknown'),) + '\n' + \
            _('Date: %s') % (self._format_date(),) + '\n' + \
            _('Size: %s') % (format_size(int(self._metadata.get(
                        'filesize',
                        model.get_file_size(self._metadata['uid'])))))

        text = gtk.Label()
        text.set_markup('<span foreground="%s">%s</span>' % (
                style.COLOR_BUTTON_GREY.get_html(), label))
        halign = gtk.Alignment(0, 0, 0, 0)
        halign.add(text)
        vbox.pack_start(halign, False, False, 0)

        return vbox

    def _format_date(self):
        if 'timestamp' in self._metadata:
            try:
                timestamp = float(self._metadata['timestamp'])
            except (ValueError, TypeError):
                logging.warning('Invalid timestamp for %r: %r',
                                self._metadata['uid'],
                                self._metadata['timestamp'])
            else:
                return time.strftime('%x', time.localtime(timestamp))
        return _('No date')

    def _create_buddy_list(self):

        vbox = gtk.VBox()
        vbox.props.spacing = style.DEFAULT_SPACING

        text = gtk.Label()
        text.set_markup('<span foreground="%s">%s</span>' % (
                style.COLOR_BUTTON_GREY.get_html(), _('Participants:')))
        halign = gtk.Alignment(0, 0, 0, 0)
        halign.add(text)
        vbox.pack_start(halign, False, False, 0)

        if self._metadata.get('buddies'):
            buddies = simplejson.loads(self._metadata['buddies']).values()
            vbox.pack_start(BuddyList(buddies), False, False, 0)
            return vbox
        else:
            return vbox

    def _create_scrollable(self, label):
        vbox = gtk.VBox()
        vbox.props.spacing = style.DEFAULT_SPACING

        text = gtk.Label()
        text.set_markup('<span foreground="%s">%s</span>' % (
                style.COLOR_BUTTON_GREY.get_html(), label))

        halign = gtk.Alignment(0, 0, 0, 0)
        halign.add(text)
        vbox.pack_start(halign, False, False, 0)

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled_window.set_border_width(style.LINE_WIDTH)
        text_buffer = gtk.TextBuffer()
        text_view = gtk.TextView(text_buffer)
        text_view.set_left_margin(style.DEFAULT_PADDING)
        text_view.set_wrap_mode(gtk.WRAP_WORD_CHAR)
        scrolled_window.add_with_viewport(text_view)
        vbox.pack_start(scrolled_window)

        # text_view.text_view_widget.connect('focus-out-event',
        #                  self._description_focus_out_event_cb)

        return vbox, text_view

    def _create_description(self):
        return self._create_scrollable(_('Description:'))

    def _create_tags(self):
        return self._create_scrollable(_('Tags:'))

    def _title_notify_text_cb(self, entry, pspec):
        if not self._update_title_sid:
            self._update_title_sid = gobject.timeout_add_seconds(1,
                                                         self._update_title_cb)

    def _title_focus_out_event_cb(self, entry, event):
        self._update_entry()

    def _description_focus_out_event_cb(self, text_view, event):
        self._update_entry()

    def _tags_focus_out_event_cb(self, text_view, event):
        self._update_entry()

    def _update_entry(self, needs_update=False):
        if not model.is_editable(self._metadata):
            return

        old_title = self._metadata.get('title', None)
        new_title = self._title.get_text()
        if old_title != new_title:
            label = glib.markup_escape_text(new_title)
            self._icon.palette.props.primary_text = label
            self._metadata['title'] = new_title
            self._metadata['title_set_by_user'] = '1'
            needs_update = True

        bounds = self._tags.get_buffer().get_bounds()
        old_tags = self._metadata.get('tags', None)
        new_tags = self._tags.get_buffer().get_text(bounds[0], bounds[1])

        if old_tags != new_tags:
            self._metadata['tags'] = new_tags
            needs_update = True

        bounds = self._description.get_buffer().get_bounds()
        old_description = self._metadata.get('description', None)
        new_description = self._description.get_buffer().get_text(
            bounds[0], bounds[1])
        if old_description != new_description:
            self._metadata['description'] = new_description
            needs_update = True

        if needs_update:
            if self._metadata.get('mountpoint', '/') == '/':
                model.write(self._metadata, update_mtime=False)
            else:
                old_file_path = os.path.join(self._metadata['mountpoint'],
                        model.get_file_name(old_title,
                        self._metadata['mime_type']))
                model.write(self._metadata, file_path=old_file_path,
                        update_mtime=False)

        self._update_title_sid = None

    def _keep_icon_toggled_cb(self, keep_icon):
        if keep_icon.get_active():
            self._metadata['keep'] = 1
        else:
            self._metadata['keep'] = 0
        self._update_entry(needs_update=True)

    def _icon_button_release_event_cb(self, button, event):
        logging.debug('_icon_button_release_event_cb')
        misc.resume(self._metadata)
        return True

    def _preview_box_button_release_event_cb(self, button, event):
        logging.debug('_preview_box_button_release_event_cb')
        misc.resume(self._metadata)
        return True
