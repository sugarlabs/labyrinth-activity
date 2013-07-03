#!/usr/bin/python
# coding=UTF-8

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

import sys
import os
import shutil
import time
from gettext import gettext as _
import xml.dom.minidom as dom

import gtk
import gio
import pango
import pangocairo
import cairo

from sugar.activity import activity
from sugar.graphics.toolbutton import ToolButton
from sugar.graphics.radiotoolbutton import RadioToolButton
from sugar.graphics.colorbutton import ColorToolButton
from sugar.graphics.menuitem import MenuItem
from sugar.graphics.icon import Icon
from sugar.datastore import datastore
from sugar.graphics import style
from port.tarball import Tarball
from sugar import env

try:
    from sugar.graphics.toolbarbox import ToolbarBox
    HASTOOLBARBOX = True
except ImportError:
    HASTOOLBARBOX = False
    pass

if HASTOOLBARBOX:
    from sugar.graphics.toolbarbox import ToolbarButton
    from sugar.activity.widgets import ActivityToolbarButton
    from sugar.activity.widgets import StopButton

# labyrinth sources are shipped inside the 'src' subdirectory
sys.path.append(os.path.join(activity.get_bundle_path(), 'src'))

import UndoManager
import MMapArea
import utils

EMPTY = -800

DEFAULT_FONTS = ['Sans', 'Serif', 'Monospace']
USER_FONTS_FILE_PATH = env.get_profile_path('fonts')
GLOBAL_FONTS_FILE_PATH = '/etc/sugar_fonts'


def stop_editing(main_area):
    if len(main_area.selected) == 1:
        if hasattr(main_area.selected[0], 'textview'):
            main_area.selected[0].remove_textview()


class MyMenuItem(MenuItem):

    def __init__(self, text_label=None, icon_name=None, text_maxlen=60,
                 xo_color=None, file_name=None, image=None):
        super(MenuItem, self).__init__()
        self._accelerator = None
        self.props.submenu = None

        label = gtk.AccelLabel(text_label)
        label.set_alignment(0.0, 0.5)
        label.set_accel_widget(self)
        if text_maxlen > 0:
            label.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
            label.set_max_width_chars(text_maxlen)
        self.add(label)
        label.show()

        if image is not None:
            self.set_image(image)
            image.show()

        elif icon_name is not None:
            icon = Icon(icon_name=icon_name,
                        icon_size=gtk.ICON_SIZE_SMALL_TOOLBAR)
            if xo_color is not None:
                icon.props.xo_color = xo_color
            self.set_image(icon)
            icon.show()

        elif file_name is not None:
            icon = Icon(file=file_name, icon_size=gtk.ICON_SIZE_SMALL_TOOLBAR)
            if xo_color is not None:
                icon.props.xo_color = xo_color
            self.set_image(icon)
            icon.show()


class FontImage(gtk.Image):

    _FONT_ICON = \
'<?xml version="1.0" encoding="UTF-8" standalone="no"?>\
<svg\
   version="1.1"\
   width="27.5"\
   height="27.5"\
   viewBox="0 0 27.5 27.5">\
<text\
     x="5"\
     y="21"\
     style="font-size:25px;fill:#ffffff;stroke:none"><tspan\
       x="5"\
       y="21"\
       style="font-family:%s">F</tspan></text>\
</svg>'

    def __init__(self, font_name):
        super(gtk.Image, self).__init__()

        pl = gtk.gdk.PixbufLoader('svg')
        pl.write(self._FONT_ICON % (font_name))
        pl.close()
        pixbuf = pl.get_pixbuf()
        self.set_from_pixbuf(pixbuf)
        self.show()


class EditToolbar(activity.EditToolbar):
    def __init__(self, _parent):
        activity.EditToolbar.__init__(self)

        self._parent = _parent

        self.undo.connect('clicked', self.__undo_cb)
        self.redo.connect('clicked', self.__redo_cb)
        self.copy.connect('clicked', self.__copy_cb)
        self.paste.connect('clicked', self.__paste_cb)

        menu_item = MenuItem(_('Cut'))
        menu_item.connect('activate', self.__cut_cb)
        menu_item.show()
        self.copy.get_palette().menu.append(menu_item)

        self.insert(gtk.SeparatorToolItem(), -1)

        self.erase_button = ToolButton('edit-delete')
        self.erase_button.set_tooltip(_('Erase selected thought(s)'))
        self.erase_button.connect('clicked', self.__delete_cb)
        self.insert(self.erase_button, -1)

        self.show_all()
        self.clipboard = gtk.Clipboard()

        self.copy.child.set_sensitive(False)
        self.paste.child.set_sensitive(False)
        self.erase_button.set_sensitive(False)

    def __undo_cb(self, button):
        self._parent._undo.undo_action(None)

    def __redo_cb(self, button):
        self._parent._undo.redo_action(None)

    def __cut_cb(self, event):
        self._parent._main_area.cut_clipboard(self.clipboard)

    def __copy_cb(self, event):
        self._parent._main_area.copy_clipboard(self.clipboard)

    def __paste_cb(self, event):
        self._parent._main_area.paste_clipboard(self.clipboard)

    def __delete_cb(self, widget):
        self._stop_moving()
        self.stop_dragging()
        self._parent._main_area.delete_selected_elements()

    def stop_dragging(self):
        if self._parent._main_area.is_dragging():
            self._parent._main_area.drag_menu_cb(self._sw, False)

    def _stop_moving(self):
        self._parent._main_area.move_mode = False


class ViewToolbar(gtk.Toolbar):
    def __init__(self, main_area):
        gtk.Toolbar.__init__(self)

        self._main_area = main_area

        tool = ToolButton('zoom-best-fit')
        tool.set_tooltip(_('Fit to window'))
        tool.set_accelerator(_('<ctrl>9'))
        tool.connect('clicked', self.__zoom_tofit_cb)
        self.insert(tool, -1)

        tool = ToolButton('zoom-original')
        tool.set_tooltip(_('Original size'))
        tool.set_accelerator(_('<ctrl>0'))
        tool.connect('clicked', self.__zoom_original_cb)
        self.insert(tool, -1)

        tool = ToolButton('zoom-out')
        tool.set_tooltip(_('Zoom out'))
        tool.set_accelerator(_('<ctrl>minus'))
        tool.connect('clicked', self.__zoom_out_cb)
        self.insert(tool, -1)

        tool = ToolButton('zoom-in')
        tool.set_tooltip(_('Zoom in'))
        tool.set_accelerator(_('<ctrl>equal'))
        tool.connect('clicked', self.__zoom_in_cb)
        self.insert(tool, -1)

        self.show_all()

    def __zoom_in_cb(self, button):
        stop_editing(self._main_area)
        self._main_area.scale_fac *= 1.2
        hadj = self._main_area.sw.get_hadjustment()
        hadj.set_upper(hadj.get_upper() * 1.2)
        vadj = self._main_area.sw.get_vadjustment()
        vadj.set_upper(vadj.get_upper() * 1.2)
        self._main_area.invalidate()

    def __zoom_out_cb(self, button):
        stop_editing(self._main_area)
        self._main_area.scale_fac /= 1.2
        hadj = self._main_area.sw.get_hadjustment()
        hadj.set_upper(hadj.get_upper() / 1.2)
        vadj = self._main_area.sw.get_vadjustment()
        vadj.set_upper(vadj.get_upper() / 1.2)
        self._main_area.invalidate()

    def __zoom_original_cb(self, button):
        stop_editing(self._main_area)
        self._main_area.scale_fac = 1.0
        self._main_area.translation[0] = 0
        self._main_area.translation[1] = 0
        hadj = self._main_area.sw.get_hadjustment()
        hadj.set_lower(0)
        hadj.set_upper(max(gtk.gdk.screen_width(), gtk.gdk.screen_height()))
        vadj = self._main_area.sw.get_vadjustment()
        vadj.set_lower(0)
        vadj.set_upper(max(gtk.gdk.screen_width(), gtk.gdk.screen_height()))
        self._main_area.invalidate()

    def __zoom_tofit_cb(self, button):
        stop_editing(self._main_area)
        bounds = self.__get_thought_bounds()
        self._main_area.translation[0] = bounds['x']
        self._main_area.translation[1] = bounds['y']
        self._main_area.scale_fac = bounds['scale']
        hadj = self._main_area.sw.get_hadjustment()
        hadj.set_lower(0)
        hadj.set_upper(max(gtk.gdk.screen_width(),
                           gtk.gdk.screen_height()) * bounds['scale'])
        vadj = self._main_area.sw.get_vadjustment()
        vadj.set_lower(0)
        vadj.set_upper(max(gtk.gdk.screen_width(),
                           gtk.gdk.screen_height()) * bounds['scale'])
        self._main_area.invalidate()

    def __get_thought_bounds(self):
        if len(self._main_area.thoughts) == 0:
            self._main_area.scale_fac = 1.0
            self._main_area.translation[0] = 0
            self._main_area.translation[1] = 0
            self._main_area.invalidate()
            return {'x': 0, 'y': 0, 'scale': 1.0}
        # Find thoughts extent
        left = right = upper = lower = None
        for t in self._main_area.thoughts:
            if right == None or t.lr[0] > right:
                right = t.lr[0]
            if lower == None or t.lr[1] > lower:
                lower = t.lr[1]
            if left == None or  t.ul[0] < left:
                left = t.ul[0]
            if upper == None or t.ul[1] < upper:
                upper = t.ul[1]
        width = right - left
        height = lower - upper
        '''
        screen_width = self._main_area.window.get_geometry()[2]
        screen_height = self._main_area.window.get_geometry()[3]
        '''
        screen_width = gtk.gdk.screen_width()
        screen_height = gtk.gdk.screen_height() - style.GRID_CELL_SIZE
        overlap = (width - screen_width, height - screen_height)
        width_scale = float(screen_width) / (width * 1.1)
        height_scale = float(screen_height) / (height * 1.1)
        return {'x': (screen_width / 2.0) - (width / 2.0 + left),
                'y': (screen_height / 2.0) - (height / 2.0 + upper) + \
                    style.GRID_CELL_SIZE,
                'scale': min(width_scale, height_scale)}


class TextAttributesToolbar(gtk.Toolbar):
    def __init__(self, main_area):
        gtk.Toolbar.__init__(self)

        self._main_area = main_area
        self._font_list = ['ABC123', 'Sans', 'Serif', 'Monospace', 'Symbol']
        self._font_sizes = ['8', '9', '10', '11', '12', '14', '16', '20',
                            '22', '24', '26', '28', '36', '48', '72']

        self.font_button =  ToolButton('font-text')
        self.font_button.set_tooltip(_('Select font'))
        self.font_button.connect('clicked', self.__font_selection_cb)
        self.insert(self.font_button, -1)
        self._setup_font_palette()

        self.insert(gtk.SeparatorToolItem(), -1)

        self.font_size_up = ToolButton('resize+')
        self.font_size_up.set_tooltip(_('Bigger'))
        self.font_size_up.connect('clicked', self.__font_sizes_cb, True)
        self.insert(self.font_size_up, -1)

        if len(self._main_area.selected) > 0:
            font_size = self._main_area.font_size
        else:
            font_size = utils.default_font_size
        self.size_label = gtk.Label(str(font_size))
        self.size_label.show()
        toolitem = gtk.ToolItem()
        toolitem.add(self.size_label)
        toolitem.show()
        self.insert(toolitem, -1)

        self.font_size_down = ToolButton('resize-')
        self.font_size_down.set_tooltip(_('Smaller'))
        self.font_size_down.connect('clicked', self.__font_sizes_cb, False)
        self.insert(self.font_size_down, -1)

        self.insert(gtk.SeparatorToolItem(), -1)

        self.bold = ToolButton('bold-text')
        self.bold.set_tooltip(_('Bold'))
        self.bold.connect('clicked', self.__bold_cb)
        self.insert(self.bold, -1)

        self.italics = ToolButton('italics-text')
        self.italics.set_tooltip(_('Italics'))
        self.italics.connect('clicked', self.__italics_cb)
        self.insert(self.italics, -1)

        self.underline = ToolButton('underline-text')
        self.underline.set_tooltip(_('Underline'))
        self.underline.connect('clicked', self.__underline_cb)
        self.insert(self.underline, -1)

        foreground_color = ColorToolButton()
        foreground_color.set_title(_('Set font color'))
        foreground_color.connect('color-set', self.__foreground_color_cb)
        self.insert(foreground_color, -1)

        bakground_color = ColorToolButton()
        bakground_color.set_title(_('Set background color'))
        bakground_color.connect('color-set', self.__background_color_cb)
        bakground_color.set_color(gtk.gdk.Color(65535, 65535, 65535))
        self.insert(bakground_color, -1)

        self.show_all()

    def __font_selection_cb(self, widget):
        if self._font_palette:
            if not self._font_palette.is_up():
                self._font_palette.popup(immediate=True,
                                    state=self._font_palette.SECONDARY)
            else:
                self._font_palette.popdown(immediate=True)
            return

    def _init_font_list(self):
        self._font_white_list = []
        self._font_white_list.extend(DEFAULT_FONTS)

        # check if there are a user configuration file
        if not os.path.exists(USER_FONTS_FILE_PATH):
            # verify if exists a file in /etc
            if os.path.exists(GLOBAL_FONTS_FILE_PATH):
                shutil.copy(GLOBAL_FONTS_FILE_PATH, USER_FONTS_FILE_PATH)

        if os.path.exists(USER_FONTS_FILE_PATH):
            # get the font names in the file to the white list
            fonts_file = open(USER_FONTS_FILE_PATH)
            # get the font names in the file to the white list
            for line in fonts_file:
                self._font_white_list.append(line.strip())
            # monitor changes in the file
            gio_fonts_file = gio.File(USER_FONTS_FILE_PATH)
            self.monitor = gio_fonts_file.monitor_file()
            self.monitor.set_rate_limit(5000)
            self.monitor.connect('changed', self._reload_fonts)

    def _reload_fonts(self, monitor, gio_file, other_file, event):
        if event != gio.FILE_MONITOR_EVENT_CHANGES_DONE_HINT:
            return
        self._font_white_list = []
        self._font_white_list.extend(DEFAULT_FONTS)
        fonts_file = open(USER_FONTS_FILE_PATH)
        for line in fonts_file:
            self._font_white_list.append(line.strip())
        # update the menu
        for child in self._font_palette.menu.get_children():
            self._font_palette.menu.remove(child)
            child = None
        context = self.get_pango_context()
        tmp_list = []
        for family in context.list_families():
            name = family.get_name()
            if name in self._font_white_list:
                tmp_list.append(name)
        for font in sorted(tmp_list):
            menu_item = MyMenuItem(image=FontImage(font.replace(' ', '-')),
                                   text_label=font)
            menu_item.connect('activate', self.__font_selected_cb, font)
            self._font_palette.menu.append(menu_item)
            menu_item.show()

        return False

    def _setup_font_palette(self):
        self._init_font_list()
        context = self._main_area.pango_context
        for family in context.list_families():
            name = pango.FontDescription(family.get_name()).to_string()
            if name not in self._font_list and \
                    name in self._font_white_list:
                self._font_list.append(name)

        self._font_palette = self.font_button.get_palette()
        for font in sorted(self._font_list):
            menu_item = MyMenuItem(image=FontImage(font.replace(' ', '-')),
                                   text_label=font)
            menu_item.connect('activate', self.__font_selected_cb, font)
            self._font_palette.menu.append(menu_item)
            menu_item.show()

    def __font_selected_cb(self, widget, font_name):
        if not hasattr(self._main_area, 'font_name'):
            return
        if len(self._main_area.selected) > 0:
            font_size = self._main_area.font_size
        else:
            font_size = utils.default_font_size
        self._main_area.set_font(font_name, font_size)
        self._main_area.font_name = font_name
        self._main_area.font_size = font_size

    def __attribute_values(self):
        attributes = {"bold": True, "italics": True, "underline": True,
                      "font": ""}
        it = self._main_area.selected[0].attributes.get_iterator()
        start_index = self._main_area.selected[0].index
        end_index = self._main_area.selected[0].end_index
        while(1):
            found = False
            r = it.range()
            if start_index == end_index:
                if r[0] <= start_index and r[1] > start_index:
                    found = True
            elif start_index < end_index:
                if r[0] > end_index:
                    break
                if start_index == end_index and \
                    r[0] < start_index and \
                    r[1] > start_index:
                    found = True
                elif start_index != end_index and r[0] <= start_index and \
                   r[1] >= end_index:
                    found = True
            else:
                if r[0] > start_index:
                    break
                if start_index == end_index and \
                    r[0] < start_index and \
                    r[1] > start_index:
                    found = True
                elif start_index != end_index and r[0] <= end_index and \
                   r[1] >= start_index:
                    found = True

            if found:
                attr = it.get_attrs()
                for x in attr:
                    if x.type == pango.ATTR_WEIGHT and \
                       x.value == pango.WEIGHT_BOLD:
                        attributes["bold"] = False
                    elif x.type == pango.ATTR_STYLE and \
                         x.value == pango.STYLE_ITALIC:
                        attributes["italics"] = False
                    elif x.type == pango.ATTR_UNDERLINE and \
                         x.value == pango.UNDERLINE_SINGLE:
                        attributes["underline"] = False
                    elif x.type == pango.ATTR_FONT_DESC:
                        attributes["font"] = x.desc
            if it.next() == False:
                break

        return attributes

    def __font_sizes_cb(self, button, increase):
        if not hasattr(self._main_area, 'font_size'):
            return
        if len(self._main_area.selected) < 1:
            return
        font_size = self._main_area.font_size
        if font_size in self._font_sizes:
            i = self._font_sizes.index(font_size)
            if increase:
                if i < len(self._font_sizes) - 2:
                    i += 1
            else:
                if i > 0:
                    i -= 1
        else:
            i = self._font_sizes.index(utils.default_font_size)

        font_size = self._font_sizes[i]
        self.size_label.set_text(str(font_size))
        self.font_size_down.set_sensitive(i != 0)
        self.font_size_up.set_sensitive(i < len(self._font_sizes) - 2)
        self._main_area.set_font(self._main_area.font_name, font_size)

    def __bold_cb(self, button):
        if len(self._main_area.selected) < 1:
            return
        value = self.__attribute_values()["bold"]
        self._main_area.set_bold(value)

    def __italics_cb(self, button):
        if len(self._main_area.selected) < 1:
            return
        value = self.__attribute_values()["italics"]
        self._main_area.set_italics(value)

    def __underline_cb(self, button):
        if len(self._main_area.selected) < 1:
            return
        value = self.__attribute_values()["underline"]
        self._main_area.set_underline(value)

    def __foreground_color_cb(self, button):
        color = button.get_color()
        self._main_area.set_foreground_color(color)

    def __background_color_cb(self, button):
        color = button.get_color()
        self._parent._main_area.set_background_color(color)

    def change_active_font(self):
        # TODO: update the toolbar
        return


class ThoughtsToolbar(gtk.Toolbar):

    def __init__(self, parent):
        gtk.Toolbar.__init__(self)
        self._parent = parent

        text_mode_btn = RadioToolButton(named_icon='text-mode')
        text_mode_btn.set_tooltip(_('Text mode'))
        text_mode_btn.set_accelerator(_('<ctrl>t'))
        text_mode_btn.set_group(None)
        text_mode_btn.connect('clicked', self._parent.mode_cb,
                              MMapArea.MODE_TEXT)
        self._parent.btn_group = text_mode_btn
        self.insert(text_mode_btn, -1)

        image_mode_btn = RadioToolButton(named_icon='image-mode')
        image_mode_btn.set_group(text_mode_btn)
        image_mode_btn.set_tooltip(_('Image add mode'))
        image_mode_btn.set_accelerator(_('<ctrl>i'))
        image_mode_btn.connect('clicked', self._parent.mode_cb,
                               MMapArea.MODE_IMAGE)
        self.insert(image_mode_btn, -1)

        draw_mode_btn = RadioToolButton(named_icon='draw-mode')
        draw_mode_btn.set_group(text_mode_btn)
        draw_mode_btn.set_tooltip(_('Drawing mode'))
        draw_mode_btn.set_accelerator(_('<ctrl>d'))
        draw_mode_btn.connect('clicked', self._parent.mode_cb,
                              MMapArea.MODE_DRAW)
        self.insert(draw_mode_btn, -1)

        label_mode_btn = RadioToolButton(named_icon='label-mode')
        label_mode_btn.set_tooltip(_('Label mode'))
        label_mode_btn.set_accelerator(_('<ctrl>a'))
        label_mode_btn.set_group(text_mode_btn)
        label_mode_btn.connect('clicked', self._parent.mode_cb,
                               MMapArea.MODE_LABEL)
        self.insert(label_mode_btn, -1)

        self.show_all()


class ActionButtons():
    ''' This class manages the action buttons that move among toolsbars '''

    def __init__(self, parent):
        self._main_toolbar = parent.get_toolbar_box().toolbar
        self._main_area = parent._main_area
        self._erase_button = parent.edit_toolbar.erase_button
        self._sw = parent._sw

        if HASTOOLBARBOX:
            target_toolbar = self._main_toolbar
        else:
            target_toolbar = self.parent.edit_toolbar

        self._mods = RadioToolButton(named_icon='select-mode')
        self._mods.set_tooltip(_('Select thoughts'))
        self._mods.set_group(parent.btn_group)
        self._mods.set_accelerator(_('<ctrl>e'))
        self._mods.connect('clicked', parent.mode_cb, MMapArea.MODE_NULL)
        target_toolbar.insert(self._mods, -1)

        self._link_button = RadioToolButton(named_icon='link')
        self._link_button.set_tooltip(_('Link/unlink two selected thoughts'))
        self._link_button.set_group(parent.btn_group)
        self._link_button.set_accelerator(_('<ctrl>l'))
        self._link_button.connect('clicked', self.__link_cb)
        target_toolbar.insert(self._link_button, -1)

        self.move_button = RadioToolButton(named_icon='move')
        self.move_button.set_tooltip(_('Move selected thoughs'))
        self.move_button.set_group(parent.btn_group)
        self.move_button.set_accelerator(_('<ctrl>m'))
        self.move_button.connect('clicked', self.__move_cb)
        target_toolbar.insert(self.move_button, -1)

        self.drag_button = RadioToolButton(named_icon='drag')
        self.drag_button.set_tooltip(_('Scroll the screen'))
        self.drag_button.set_group(parent.btn_group)
        self.drag_button.connect('clicked', self.__drag_cb)
        target_toolbar.insert(self.drag_button, -1)

        if HASTOOLBARBOX:
            self._separator_2 = gtk.SeparatorToolItem()
            self._separator_2.props.draw = False
            #self._separator_2.set_size_request(0, -1)
            self._separator_2.set_expand(True)
            self._separator_2.show()
            target_toolbar.insert(self._separator_2, -1)

            self._stop_button = StopButton(parent)
            target_toolbar.insert(self._stop_button, -1)

    def stop_dragging(self):
        if self._main_area.is_dragging():
            self._main_area.drag_menu_cb(self._sw, False)

    def _stop_moving(self):
        self._main_area.move_mode = False

    def __link_cb(self, widget):
        self._stop_moving()
        self.stop_dragging()
        self._main_area.link_menu_cb()

    def __move_cb(self, widget):
        self.stop_dragging()
        if self._main_area.move_mode:
            self._main_area.stop_moving()
        else:
            self._main_area.start_moving(self.move_button)
        self._erase_button.set_sensitive(False)

    def __drag_cb(self, widget):
        # If we were moving, stop
        self._stop_moving()
        if not self._main_area.is_dragging():
            self._main_area.drag_menu_cb(self._sw, True)
        else:
            self.stop_dragging()
        self._erase_button.set_sensitive(False)

    def reconfigure(self):
        ''' If screen width has changed, we may need to reconfigure
        the toolbars '''
        if not HASTOOLBARBOX:
            return

        if hasattr(self, '_separator_2'):
            if gtk.gdk.screen_width() / 13 > style.GRID_CELL_SIZE:
                if self._separator_2.get_parent() is None:
                    self._main_toolbar.remove(self._stop_button)
                    self._main_toolbar.insert(self._separator_2, -1)
                    self._main_toolbar.insert(self._stop_button, -1)
            else:
                self._main_toolbar.remove(self._separator_2)


class LabyrinthActivity(activity.Activity):
    def __init__(self, handle):
        activity.Activity.__init__(self, handle)

        if HASTOOLBARBOX:
            self.max_participants = 1
            toolbar_box = ToolbarBox()
            self.set_toolbar_box(toolbar_box)
            activity_button = ActivityToolbarButton(self)
            toolbar_box.toolbar.insert(activity_button, 0)

            separator = gtk.SeparatorToolItem()
            separator.props.draw = True
            activity_button.props.page.insert(separator, -1)
            separator.show()

            tool = ToolButton('pdf-export')
            tool.set_tooltip(_('Portable Document Format (PDF)'))
            tool.connect('clicked', self.__export_pdf_cb)
            activity_button.props.page.insert(tool, -1)
            tool.show()

            tool = ToolButton('png-export')
            tool.set_tooltip(_('Portable Network Graphic (PNG)'))
            tool.connect('clicked', self.__export_png_cb)
            activity_button.props.page.insert(tool, -1)
            tool.show()

            tool = ToolbarButton()
            self.edit_toolbar = EditToolbar(self)
            tool.props.page = self.edit_toolbar
            tool.props.icon_name = 'toolbar-edit'
            tool.props.label = _('Edit'),
            toolbar_box.toolbar.insert(tool, -1)

            self._undo = UndoManager.UndoManager(self,
                                                 self.edit_toolbar.undo.child,
                                                 self.edit_toolbar.redo.child)

            self.__build_main_canvas_area()

            tool = ToolbarButton()
            tool.props.page = ViewToolbar(self._main_area)
            tool.props.icon_name = 'toolbar-view'
            tool.props.label = _('View'),
            toolbar_box.toolbar.insert(tool, -1)

            tool = ToolbarButton()
            self.text_format_toolbar = TextAttributesToolbar(self._main_area)
            tool.props.page = self.text_format_toolbar
            tool.props.icon_name = 'toolbar-text'
            tool.props.label = _('Text')
            toolbar_box.toolbar.insert(tool, -1)
            # self._main_area.set_text_attributes(self.text_format_toolbar)

            self.thought_toolbar = ToolbarButton()
            self.thought_toolbar.props.page = ThoughtsToolbar(self)
            self.thought_toolbar.props.icon_name = 'thought'
            self.thought_toolbar.props.label = _('Thought Type')
            toolbar_box.toolbar.insert(self.thought_toolbar, -1)

            self.action_buttons = ActionButtons(self)

            toolbar_box.show_all()

        else:
            # Use old <= 0.84 toolbar design
            toolbox = activity.ActivityToolbox(self)
            self.set_toolbox(toolbox)

            activity_toolbar = toolbox.get_activity_toolbar()
            keep_palette = activity_toolbar.keep.get_palette()

            menu_item = MenuItem(_('Portable Document Format (PDF)'))
            menu_item.connect('activate', self.__export_pdf_cb)
            keep_palette.menu.append(menu_item)
            menu_item.show()

            menu_item = MenuItem(_('Portable Network Graphic (PNG)'))
            menu_item.connect('activate', self.__export_png_cb)
            keep_palette.menu.append(menu_item)
            menu_item.show()

            self.edit_toolbar = EditToolbar(self)
            toolbox.add_toolbar(_('Edit'), self.edit_toolbar)
            separator = gtk.SeparatorToolItem()
            self.edit_toolbar.insert(separator, 0)
            self.edit_toolbar.show()

            self._undo = UndoManager.UndoManager(self,
                                                 self.edit_toolbar.undo.child,
                                                 self.edit_toolbar.redo.child)

            self.__build_main_canvas_area()

            view_toolbar = ViewToolbar(self._main_area)
            toolbox.add_toolbar(_('View'), view_toolbar)

            activity_toolbar = toolbox.get_activity_toolbar()
            activity_toolbar.share.props.visible = False
            toolbox.set_current_toolbar(1)

        self.show_all()

        self.__configure_cb(None)

        self._mode = MMapArea.MODE_TEXT
        self._main_area.set_mode(self._mode)
        self.set_focus_child(self._main_area)

    def __build_main_canvas_area(self):
        self.fixed = gtk.Fixed()
        self.fixed.show()
        self.set_canvas(self.fixed)

        self._vbox = gtk.VBox()
        self._vbox.set_size_request(
            gtk.gdk.screen_width(),
            gtk.gdk.screen_height() - style.GRID_CELL_SIZE)

        self._main_area = MMapArea.MMapArea(self._undo)

        self._undo.block()

        self._main_area.set_size_request(
            max(gtk.gdk.screen_width(), gtk.gdk.screen_height()),
            max(gtk.gdk.screen_width(), gtk.gdk.screen_height()))
        self._main_area.show()
        self._main_area.connect("set_focus", self.__main_area_focus_cb)
        self._main_area.connect("button-press-event",
                                self.__main_area_focus_cb)
        self._main_area.connect("expose_event", self.__expose)
        self._main_area.connect("text_selection_changed",
                                self.__text_selection_cb)
        self._main_area.connect("thought_selection_changed",
                                self.__thought_selected_cb)
        gtk.gdk.screen_get_default().connect('size-changed',
                                             self.__configure_cb)

        self._sw = gtk.ScrolledWindow()
        self._sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self._sw.add_with_viewport(self._main_area)
        self._vbox.pack_end(self._sw, True, True)
        self._sw.show()
        self._main_area.show()
        self._vbox.show()
        self.fixed.put(self._vbox, 0, 0)

        self.hadj = self._sw.get_hadjustment()
        self.hadj.connect("value_changed", self._hadj_adjusted_cb,
                              self.hadj)

        self.vadj = self._sw.get_vadjustment()
        self.vadj.connect("value_changed", self._vadj_adjusted_cb,
                              self.vadj)

        self._main_area.drag_menu_cb(self._sw, True)
        self._main_area.drag_menu_cb(self._sw, False)
        self._undo.unblock()

    def _hadj_adjusted_cb(self, adj, data=None):
        self._main_area.hadj = adj.value
        stop_editing(self._main_area)

    def _vadj_adjusted_cb(self, adj, data=None):
        self._main_area.vadj = adj.value
        stop_editing(self._main_area)

    def __configure_cb(self, event):
        ''' Screen size has changed '''
        self._vbox.set_size_request(
            gtk.gdk.screen_width(),
            gtk.gdk.screen_height() - style.GRID_CELL_SIZE)

        self._vbox.show()

        self.action_buttons.reconfigure()
        self.show_all()

    def __text_selection_cb(self, thought, start, end, text):
        """Update state of edit buttons based on text selection
        """
        self.__change_erase_state(True)
        if start != end:
            self.__change_copy_state(True)
            self.text_format_toolbar.change_active_font()
        else:
            self.__change_copy_state(False)

        if self._mode == (MMapArea.MODE_TEXT and
                          len(self._main_area.selected)):
                          # With textview, we are always editing
                          # and self._main_area.selected[0].editing):
            self.__change_paste_state(True)
        else:
            self.__change_paste_state(False)

    # TODO: implement copy/paste for a whole thought or thoughts
    def __thought_selected_cb(self, arg, background_color, foreground_color):
        """Disable copy button if whole thought object is selected
        """
        self.__change_erase_state(True)
        self.__change_copy_state(False)
        self.__change_paste_state(False)

    def __change_erase_state(self, state):
        self.edit_toolbar.erase_button.set_sensitive(state)

    def __change_copy_state(self, state):
        self.edit_toolbar.copy.child.set_sensitive(state)

    def __change_paste_state(self, state):
        self.edit_toolbar.paste.child.set_sensitive(state)

    def __expose(self, widget, event):
        """Create canvas hint message at start
        """
        thought_count = len(self._main_area.thoughts)
        if thought_count > 0:
            return False

        context = self._main_area.window.cairo_create()
        pango_context = self._main_area.pango_context
        layout = pango.Layout(pango_context)
        context.set_source_rgb(0.6, 0.6, 0.6)
        context.set_line_width(4.0)
        context.set_dash([10.0, 5.0], 0.0)
        geom = list(self._main_area.window.get_geometry())
        geom[3] = geom[3] - ((self.window.get_geometry()[3] - geom[3]) / 2)

        # Make sure initial thought is "above the fold"
        if geom[2] < geom[3]:
            xf = 2
            yf = 4
        else:
            xf = 4
            yf = 2

        layout.set_alignment(pango.ALIGN_CENTER)
        layout.set_text(_('Click to add\ncentral thought'))
        width, height = layout.get_pixel_size()
        context.move_to(geom[2] / xf - (width / 2), geom[3] / yf - (height / 2))
        context.show_layout(layout)

        round = 40
        ul = (geom[2] / xf - (width / 2) - round,
              geom[3] / yf - (height / 2) - round)
        lr = (geom[2] / xf + (width / 2) + round,
              geom[3] / yf + (height / 2) + round)
        context.move_to(ul[0], ul[1] + round)
        context.line_to(ul[0], lr[1] - round)
        context.curve_to(ul[0], lr[1], ul[0], lr[1], ul[0] + round, lr[1])
        context.line_to(lr[0] - round, lr[1])
        context.curve_to(lr[0], lr[1], lr[0], lr[1], lr[0], lr[1] - round)
        context.line_to(lr[0], ul[1] + round)
        context.curve_to(lr[0], ul[1], lr[0], ul[1], lr[0] - round, ul[1])
        context.line_to(ul[0] + round, ul[1])
        context.curve_to(ul[0], ul[1], ul[0], ul[1], ul[0], ul[1] + round)
        context.stroke()

        return False

    def __centre(self):
        bounds = self.__get_thought_bounds()
        self._main_area.translation[0] = bounds['x']
        self._main_area.translation[1] = bounds['y']
        self._main_area.invalidate()
        return False

    def mode_cb(self, button, mode):
        self.action_buttons.stop_dragging()
        if self._mode == MMapArea.MODE_TEXT:
            if len(self._main_area.selected) > 0:
                self._main_area.selected[0].leave()
        self._mode = mode
        self._main_area.set_mode(self._mode)
        # self.edit_toolbar.erase_button.set_sensitive(True)

    def __export_pdf_cb(self, event):
        maxx, maxy = self._main_area.get_max_area()
        true_width = int(maxx)
        true_height = int(maxy)

        # Create the new journal entry
        fileObject = datastore.create()
        act_meta = self.metadata
        fileObject.metadata['title'] = act_meta['title'] + ' (PDF)'
        fileObject.metadata['title_set_by_user'] = \
            act_meta['title_set_by_user']
        fileObject.metadata['mime_type'] = 'application/pdf'

        # TODO: add text thoughts into fulltext metadata
        # fileObject.metadata['fulltext'] = ...

        fileObject.metadata['icon-color'] = act_meta['icon-color']
        fileObject.file_path = os.path.join(self.get_activity_root(),
                                            'instance', '%i' % time.time())
        filename = fileObject.file_path
        surface = cairo.PDFSurface(filename, true_width, true_height)
        cairo_context = cairo.Context(surface)
        context = pangocairo.CairoContext(cairo_context)
        self._main_area.export(context, true_width, true_height, False)
        surface.finish()
        datastore.write(fileObject, transfer_ownership=True)
        fileObject.destroy()
        del fileObject

    def __export_png_cb(self, event):
        x, y, w, h, bitdepth = self._main_area.window.get_geometry()
        cmap = self._main_area.window.get_colormap()
        maxx, maxy = self._main_area.get_max_area()
        true_width = int(maxx)
        true_height = int(maxy)

        # Create the new journal entry
        fileObject = datastore.create()
        act_meta = self.metadata
        fileObject.metadata['title'] = act_meta['title'] + ' (PNG)'
        fileObject.metadata['title_set_by_user'] = \
            act_meta['title_set_by_user']
        fileObject.metadata['mime_type'] = 'image/png'

        fileObject.metadata['icon-color'] = act_meta['icon-color']
        fileObject.file_path = os.path.join(self.get_activity_root(),
                                            'instance', '%i' % time.time())
        filename = fileObject.file_path
        pixmap = gtk.gdk.Pixmap(None, true_width, true_height, bitdepth)
        pixmap.set_colormap(cmap)
        self._main_area.export(pixmap.cairo_create(), true_width, true_height,
                               False)

        pb = gtk.gdk.Pixbuf.get_from_drawable(
            gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, True, 8, true_width,
                           true_height),
            pixmap, gtk.gdk.colormap_get_system(), 0, 0, 0, 0, true_width,
            true_height)

        pb.save(filename, 'png')
        datastore.write(fileObject, transfer_ownership=True)
        fileObject.destroy()
        del fileObject

    def __main_area_focus_cb(self, arg, event, extended=False):
        # Don't steal focus from textview
        # self._main_area.grab_focus()
        pass

    def read_file(self, file_path):
        tar = Tarball(file_path)

        doc = dom.parseString(tar.read(tar.getnames()[0]))
        top_element = doc.documentElement

        self.set_title(top_element.getAttribute("title"))
        self._mode = int(top_element.getAttribute("mode"))

        self._main_area.set_mode(self._mode)
        self._main_area.load_thyself(top_element, doc, tar)

        if top_element.hasAttribute("scale_factor"):
            fac = float(top_element.getAttribute("scale_factor"))
            self._main_area.scale_fac = fac

        if top_element.hasAttribute("translation"):
            tmp = top_element.getAttribute("translation")
            x, y = utils.parse_coords(tmp)
            self._main_area.translation = [x, y]

        tar.close()

    def write_file(self, file_path):
        tar = Tarball(file_path, 'w')

        self._main_area.update_save()
        manifest = self.serialize_to_xml(self._main_area.save,
                self._main_area.element)
        tar.write('MANIFEST', manifest)
        self._main_area.save_thyself(tar)

        tar.close()

    def serialize_to_xml(self, doc, top_element):
        top_element.setAttribute("title", self.props.title)
        top_element.setAttribute("mode", str(self._mode))
        top_element.setAttribute("size", str((400, 400)))
        top_element.setAttribute("position", str((0, 0)))
        top_element.setAttribute("maximised", str(True))
        top_element.setAttribute("view_type", str(0))
        top_element.setAttribute("pane_position", str(500))
        top_element.setAttribute("scale_factor",
                                 str(self._main_area.scale_fac))
        top_element.setAttribute("translation",
                                 str(self._main_area.translation))
        string = doc.toxml()
        return string.encode("utf-8")
