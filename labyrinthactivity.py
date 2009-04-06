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
import logging
from gettext import gettext as _
import tarfile
import tempfile
import xml.dom.minidom as dom

import gobject
import gtk
import pango

from sugar.activity import activity
from sugar.graphics.toolbutton import ToolButton
from sugar.graphics.radiotoolbutton import RadioToolButton
from sugar.graphics.toggletoolbutton import ToggleToolButton
from sugar.graphics.menuitem import MenuItem

# labyrinth sources are shipped inside the 'src' subdirectory
sys.path.append(os.path.join(activity.get_bundle_path(), 'src'))

import UndoManager
import MMapArea
import ImageThought
import utils


class LabyrinthActivity(activity.Activity):
    def __init__(self, handle):
        activity.Activity.__init__(self, handle)

        toolbox = activity.ActivityToolbox(self)
        self.set_toolbox(toolbox)
        toolbox.show()

        edit_toolbar = activity.EditToolbar()
        toolbox.add_toolbar(_('Edit'), edit_toolbar)
        edit_toolbar.undo.child.connect('clicked', self.__undo_cb)
        edit_toolbar.redo.child.connect('clicked', self.__redo_cb)
        edit_toolbar.copy.connect('clicked', self.__copy_cb)
        menu_item = MenuItem('Cut') 
        menu_item.connect('activate', self.__cut_cb)
        menu_item.show()
        edit_toolbar.copy.get_palette().menu.append(menu_item)
        edit_toolbar.paste.connect('clicked', self.__paste_cb)
        edit_toolbar.show()

        activity_toolbar = toolbox.get_activity_toolbar()
        activity_toolbar.share.props.visible = False

        self.clipboard = gtk.Clipboard()

        self._undo = UndoManager.UndoManager (self,
                                             edit_toolbar.undo.child,
                                             edit_toolbar.redo.child)
        self._undo.block ()

        #separator = gtk.SeparatorToolItem()
        #separator.set_draw(True)
        #edit_toolbar.insert(separator, -1)
        #separator.show()

        thought_toolbar = gtk.Toolbar()
        thought_toolbar.show()
        toolbox.add_toolbar(_('Thoughts'), thought_toolbar)

        self._edit_mode = RadioToolButton(named_icon='edit-mode')
        self._edit_mode.set_tooltip(_('Edit mode'))
        self._edit_mode.set_accelerator(_('<ctrl>e'))
        self._edit_mode.set_group(None)
        self._edit_mode.connect('clicked', self.__edit_mode_cb)
        thought_toolbar.insert(self._edit_mode, -1)
        self._edit_mode.show()

        self._draw_mode = RadioToolButton(named_icon='draw-mode')
        self._draw_mode.set_group(self._edit_mode)
        self._draw_mode.set_tooltip(_('Drawing mode'))
        self._draw_mode.set_accelerator(_('<ctrl>d'))
        self._draw_mode.connect('clicked', self.__draw_mode_cb)
        thought_toolbar.insert(self._draw_mode, -1)
        self._draw_mode.show()

        # FIXME: Disabled image add mode toolbar icon while I get the
        # Object chooser working (needs bunch of custom fluff the normal
        # gtk+ file picker does not).
        self._image_mode = RadioToolButton(named_icon='add-image')
        self._image_mode.set_group(self._edit_mode)
        self._image_mode.set_tooltip(_('Image add mode'))
        self._image_mode.set_accelerator(_('<ctrl>i'))
        self._image_mode.connect('clicked', self.__image_mode_cb)
        thought_toolbar.insert(self._image_mode, -1)
        self._image_mode.show()

        view_toolbar = gtk.Toolbar()
        view_toolbar.show()
        toolbox.add_toolbar(_('View'), view_toolbar)

        self._zoom_in = ToolButton('zoom-in')
        self._zoom_in.set_tooltip(_('Zoom in'))
        self._zoom_in.connect('clicked', self.__zoom_in_cb)
        view_toolbar.insert(self._zoom_in, -1)
        self._zoom_in.show()

        self._zoom_out = ToolButton('zoom-out')
        self._zoom_out.set_tooltip(_('Zoom out'))
        self._zoom_out.connect('clicked', self.__zoom_out_cb)
        view_toolbar.insert(self._zoom_out, -1)
        self._zoom_out.show()

        self._zoom_tofit = ToolButton('zoom-best-fit')
        self._zoom_tofit.set_tooltip(_('Fit to window'))
        self._zoom_tofit.connect('clicked', self.__zoom_tofit_cb)
        view_toolbar.insert(self._zoom_tofit, -1)
        self._zoom_tofit.show()

        self._zoom_original = ToolButton('zoom-original')
        self._zoom_original.set_tooltip(_('Original size'))
        self._zoom_original.connect('clicked', self.__zoom_original_cb)
        view_toolbar.insert(self._zoom_original, -1)
        self._zoom_original.show()

        self._save_file = None
        self._mode = MMapArea.MODE_EDITING

        self._main_area = MMapArea.MMapArea (self._undo)
        self._main_area.connect ("doc_save", self.__doc_save_cb)
        self._main_area.connect ("set_focus", self.__main_area_focus_cb)
        self._main_area.connect ("button-press-event", self.__main_area_focus_cb)
        self._main_area.connect ("expose_event", self.__expose)
        self._main_area.set_mode (self._mode)
        self.set_canvas(self._main_area)
        self._main_area.show()

        tree_model = gtk.TreeStore(gobject.TYPE_STRING)
        self._main_area.initialize_model(tree_model)

        self.set_focus_child (self._main_area)
        
        self._undo.unblock()
                
    def __expose(self, widget, event):
        """Create skeleton map at start
        """
        thought_count = len(self._main_area.thoughts)
        if thought_count > 1:
            return False

        context = self._main_area.window.cairo_create()
        pango_context = self._main_area.pango_context
        layout = pango.Layout(pango_context)
        context.set_source_rgb(0.6, 0.6, 0.6)
        context.set_line_width(4.0)
        context.set_dash([10.0, 5.0], 0.0)
        geom = list(self._main_area.window.get_geometry())
        geom[3] =  geom[3] - ((self.window.get_geometry()[3] - geom[3]) / 2)
            
        if thought_count == 0:
            layout.set_alignment(pango.ALIGN_CENTER)
            layout.set_text(_('Click to add\ncentral thought'))        
            (width, height) = layout.get_pixel_size()
            context.move_to (geom[2] / 2 - (width / 2), geom[3] / 2 - (height / 2))
            context.show_layout(layout)

            round = 40
            ul = (geom[2] / 2 - (width / 2) - round,
                  geom[3] / 2 - (height / 2) - round)
            lr = (geom[2] / 2 + (width / 2) + round,
                  geom[3] / 2 + (height / 2) + round)
            context.move_to (ul[0], ul[1] + round)
            context.line_to (ul[0], lr[1] - round)
            context.curve_to (ul[0], lr[1], ul[0], lr[1], ul[0] + round, lr[1])
            context.line_to (lr[0] - round, lr[1])
            context.curve_to (lr[0], lr[1], lr[0], lr[1], lr[0], lr[1] - round)
            context.line_to (lr[0], ul[1] + round)
            context.curve_to (lr[0], ul[1], lr[0], ul[1], lr[0] - round, ul[1])
            context.line_to (ul[0] + round, ul[1])
            context.curve_to (ul[0], ul[1], ul[0], ul[1], ul[0], ul[1] + round)
            context.stroke()

        # Considering possible 2nd, or 3rd stage hints to help
        # walk someone through creating a map
        #
        #elif thought_count == 1:
        #    (x, y) = self._main_area.thoughts[0].ul
        #    (x, y) = (x - 5, y - 5)
        #    context.move_to (x, y)
        #    context.line_to (x - 95, y - 95)
        #    context.move_to (x + 2, y)
        #    context.line_to (x - 20, y)
        #    context.move_to (x, y + 2)
        #    context.line_to (x, y - 20)
        #    context.stroke()            
        #    layout.set_text (_('Type central thought'))        
        #    (width, height) = layout.get_pixel_size()
        #    context.move_to (x - 100 - (width / 2), y - 100 - height)
        #    context.show_layout(layout)
        
        return False
        
    def __centre(self):
        bounds = self.__get_thought_bounds()
        self._main_area.translation[0] = bounds['x']
        self._main_area.translation[1] = bounds['y']
        self._main_area.invalidate()
        return False

    def __zoom_in_cb(self, button):
        self._main_area.scale_fac *= 1.2
        self._main_area.invalidate()

    def __zoom_out_cb(self, button):
        self._main_area.scale_fac /= 1.2
        self._main_area.invalidate()

    def __zoom_original_cb(self, button):
        self._main_area.scale_fac = 1.0
        self._main_area.invalidate()
        
    def __zoom_tofit_cb(self, button):
        bounds = self.__get_thought_bounds()
        self._main_area.translation[0] = bounds['x']
        self._main_area.translation[1] = bounds['y']
        self._main_area.scale_fac = bounds['scale']
        self._main_area.invalidate()

    def __get_thought_bounds(self):
        if len(self._main_area.thoughts) == 0:
            self._main_area.scale_fac = 1.0
            self._main_area.translation[0] = 0
            self._main_area.translation[1] = 0
            self._main_area.invalidate()
            return {'x':0, 'y':0, 'scale':1.0}
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
        geom = self._main_area.window.get_geometry()
        overlap = (width - geom[2], height - geom[3])
        # Leave 10% space around the edge
        width_scale = float(geom[2]) / (width * 1.1)
        height_scale = float(geom[3]) / (height * 1.1)
        return {'x':(geom[2] / 2.0) - (width / 2.0 + left),
                'y':(geom[3] / 2.0) - (height / 2.0 + upper),
                'scale':min(width_scale, height_scale)}

    def __edit_mode_cb(self, button):
        self._mode = MMapArea.MODE_EDITING
        self._main_area.set_mode (self._mode)

    def __draw_mode_cb(self, button):
        self._mode = MMapArea.MODE_DRAW
        self._main_area.set_mode (self._mode)

    def __image_mode_cb(self, button):
        self._mode = MMapArea.MODE_IMAGE
        self._main_area.set_mode (self._mode)

    def __undo_cb(self, button):
        self._undo.undo_action(None)

    def __redo_cb(self, button):
        self._undo.redo_action(None)

    def __cut_cb (self, event):
        self._main_area.cut_clipboard (self.clipboard)

    def __copy_cb (self, event):
        self._main_area.copy_clipboard (self.clipboard)

    def __paste_cb (self, event):
        self._main_area.paste_clipboard (self.clipboard)

    def __main_area_focus_cb (self, arg, event, extended = False):
        self._main_area.grab_focus ()

    def read_file(self, file_path):
        tar_file = tarfile.open(file_path)
        map_name = tar_file.getnames()[0]
        tar_file.extractall(tempfile.gettempdir())
        tar_file.close()

        f = file (os.path.join(tempfile.gettempdir(), map_name), 'r')
        doc = dom.parse (f)
        top_element = doc.documentElement
        self.set_title(top_element.getAttribute ("title"))
        self._mode = int (top_element.getAttribute ("mode"))

        self._main_area.set_mode (self._mode)
        self._main_area.load_thyself (top_element, doc)
        if top_element.hasAttribute("scale_factor"):
            self._main_area.scale_fac = float (top_element.getAttribute ("scale_factor"))
        if top_element.hasAttribute("translation"):
            tmp = top_element.getAttribute("translation")
            (x,y) = utils.parse_coords(tmp)
            self._main_area.translation = [x,y]

    def write_file(self, file_path):
        logging.debug('write_file')
        self._main_area.save_thyself ()

        if self._save_file is None:
            # FIXME: Create an empty file because the Activity superclass
            # always requires one
            fd, self._save_file = tempfile.mkstemp(suffix='.map')
            del fd

        tf = tarfile.open (file_path, "w")
        tf.add (self._save_file, os.path.split(self._save_file)[1])
        for t in self._main_area.thoughts:
            if isinstance(t, ImageThought.ImageThought):
                tf.add (t.filename, 'images/' + os.path.split(t.filename)[1])
                
        tf.close()

        os.unlink(self._save_file)

    def __doc_save_cb (self, widget, doc, top_element):
        logging.debug('doc_save_cb')
        save_string = self.serialize_to_xml(doc, top_element)

        fd, self._save_file = tempfile.mkstemp(suffix='.map')
        del fd

        self.save_map(self._save_file, save_string)
        #self.emit ('file_saved', self._save_file, self)

    def serialize_to_xml(self, doc, top_element):
        top_element.setAttribute ("title", self.props.title)
        top_element.setAttribute ("mode", str(self._mode))
        top_element.setAttribute ("size", str((400, 400)))
        top_element.setAttribute ("position", str((0, 0)))
        top_element.setAttribute ("maximised", str(True))
        top_element.setAttribute ("view_type", str(0))
        top_element.setAttribute ("pane_position", str(500))
        top_element.setAttribute ("scale_factor", str(self._main_area.scale_fac))
        top_element.setAttribute ("translation", str(self._main_area.translation))
        string = doc.toxml ()
        return string.encode ("utf-8" )

    def save_map(self, filename, string):
        f = file (filename, 'w')
        f.write (string)
        f.close ()

