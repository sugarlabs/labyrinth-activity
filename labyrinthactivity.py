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
import time
import logging
from gettext import gettext as _
import tempfile
import xml.dom.minidom as dom

import gobject
import gtk
import pango
import pangocairo
import cairo

from sugar.activity import activity
from sugar.graphics.toolbutton import ToolButton
from sugar.graphics.radiotoolbutton import RadioToolButton
from sugar.graphics.menuitem import MenuItem
from sugar.datastore import datastore
from port.tarball import Tarball

try:
    # >= 0.86 toolbars
    from sugar.graphics.toolbarbox import ToolbarButton, ToolbarBox
    from sugar.activity.widgets import ActivityToolbarButton
    from sugar.activity.widgets import StopButton
except ImportError:
    # <= 0.84 toolbars
    pass


# labyrinth sources are shipped inside the 'src' subdirectory
sys.path.append(os.path.join(activity.get_bundle_path(), 'src'))

import UndoManager
import MMapArea
import ImageThought
import utils

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
        
        self.clipboard = gtk.Clipboard()
        
        self.copy.child.set_sensitive(False)
        self.paste.child.set_sensitive(False)

    def __undo_cb(self, button):
        self._parent._undo.undo_action(None)

    def __redo_cb(self, button):
        self._parent._undo.redo_action(None)

    def __cut_cb (self, event):
        self._parent._main_area.cut_clipboard(self.clipboard)

    def __copy_cb (self, event):
        self._parent._main_area.copy_clipboard(self.clipboard)

    def __paste_cb (self, event):
        self._parent._main_area.paste_clipboard(self.clipboard)

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

class LabyrinthActivity(activity.Activity):
    def __init__(self, handle):
        activity.Activity.__init__(self, handle)

        try:
            # Use new >= 0.86 toolbar design
            self.max_participants = 1
            toolbar_box = ToolbarBox()
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

            self.edit_toolbar = ToolbarButton()
            self.edit_toolbar.props.page = EditToolbar(self)
            self.edit_toolbar.props.icon_name = 'toolbar-edit'
            self.edit_toolbar.props.label = _('Edit'),
            toolbar_box.toolbar.insert(self.edit_toolbar, -1)

            self._undo = UndoManager.UndoManager (self,
                                         self.edit_toolbar.props.page.undo.child,
                                         self.edit_toolbar.props.page.redo.child)
                    
            self.__build_main_canvas_area()

            tool = ToolbarButton()
            tool.props.page = ViewToolbar(self._main_area)
            tool.props.icon_name = 'toolbar-view'
            tool.props.label = _('View'),
            toolbar_box.toolbar.insert(tool, -1)

            separator = gtk.SeparatorToolItem()
            toolbar_box.toolbar.insert(separator, -1)

            separator = gtk.SeparatorToolItem()
            separator.props.draw = False
            separator.set_expand(True)
            separator.show()
            toolbar_box.toolbar.insert(separator, -1)
            
            target_toolbar = toolbar_box.toolbar
            tool_offset = 4

            tool = StopButton(self)
            toolbar_box.toolbar.insert(tool, -1)

            toolbar_box.show_all()
            self.set_toolbar_box(toolbar_box)
        
        except NameError:
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

            target_toolbar = self.edit_toolbar
            tool_offset = 0

            self._undo = UndoManager.UndoManager (self,
                                                 self.edit_toolbar.undo.child,
                                                 self.edit_toolbar.redo.child)

            self.__build_main_canvas_area()

            view_toolbar = ViewToolbar(self._main_area)
            toolbox.add_toolbar(_('View'), view_toolbar)

            activity_toolbar = toolbox.get_activity_toolbar()
            activity_toolbar.share.props.visible = False
            toolbox.set_current_toolbar(1)

        self.mods = [None] * 6

        self.mods[0] = RadioToolButton(named_icon='select-mode')
        self.mods[0].set_tooltip(_('Edit mode'))
        self.mods[0].set_accelerator(_('<ctrl>e'))
        self.mods[0].set_group(None)
        self.mods[0].connect('clicked', self.__mode_cb, MMapArea.MODE_NULL)
        target_toolbar.insert(self.mods[0], tool_offset)

        self.mods[1] = RadioToolButton(named_icon='text-mode')
        self.mods[1].set_tooltip(_('Text mode'))
        self.mods[1].set_accelerator(_('<ctrl>t'))
        self.mods[1].set_group(self.mods[0])
        self.mods[1].connect('clicked', self.__mode_cb, MMapArea.MODE_TEXT)
        target_toolbar.insert(self.mods[1], tool_offset + 1)

        self.mods[2] = RadioToolButton(named_icon='draw-mode')
        self.mods[2].set_group(self.mods[0])
        self.mods[2].set_tooltip(_('Drawing mode'))
        self.mods[2].set_accelerator(_('<ctrl>d'))
        self.mods[2].connect('clicked', self.__mode_cb, MMapArea.MODE_DRAW)
        target_toolbar.insert(self.mods[2], tool_offset + 2)

        self.mods[3] = RadioToolButton(named_icon='image-mode')
        self.mods[3].set_group(self.mods[0])
        self.mods[3].set_tooltip(_('Image add mode'))
        self.mods[3].set_accelerator(_('<ctrl>i'))
        self.mods[3].connect('clicked', self.__mode_cb, MMapArea.MODE_IMAGE)
        target_toolbar.insert(self.mods[3], tool_offset + 3)

        self.mods[5] = RadioToolButton(named_icon='label-mode')
        self.mods[5].set_tooltip(_('Label mode'))
        self.mods[5].set_accelerator(_('<ctrl>a'))
        self.mods[5].set_group(self.mods[0])
        self.mods[5].connect('clicked', self.__mode_cb, MMapArea.MODE_LABEL)
        target_toolbar.insert(self.mods[5], tool_offset + 4)

        separator = gtk.SeparatorToolItem()
        target_toolbar.insert(separator, tool_offset + 5)

        tool = ToolButton('link')
        tool.set_tooltip(_('Link/unlink two selected thoughts'))
        tool.set_accelerator(_('<ctrl>l'))
        tool.connect('clicked', self.__link_cb)
        target_toolbar.insert(tool, tool_offset + 6)

        tool = ToolButton('edit-delete')
        tool.set_tooltip(_('Erase selected thought(s)'))
        tool.connect('clicked', self.__delete_cb)
        target_toolbar.insert(tool, tool_offset + 7)

        self.show_all()
        self._mode = MMapArea.MODE_TEXT
        self._main_area.set_mode(self._mode)
        self.mods[MMapArea.MODE_TEXT].set_active(True)        
        self.set_focus_child(self._main_area)        

    def __build_main_canvas_area(self):
        self._undo.block ()
        self._main_area = MMapArea.MMapArea (self._undo)
        self._main_area.connect ("set_focus", self.__main_area_focus_cb)
        self._main_area.connect ("button-press-event", self.__main_area_focus_cb)
        self._main_area.connect ("expose_event", self.__expose)
        self._main_area.connect ("text_selection_changed", self.__text_selection_cb)
        self._main_area.connect ("thought_selection_changed", self.__thought_selected_cb)
        self.set_canvas(self._main_area)
        self._undo.unblock()

    def __text_selection_cb(self, thought, start, end, text):
        """Update state of copy button based on text selection
        """
        if start != end:
            self.__change_copy_state(True)
        else:
            self.__change_copy_state(False)
            
        if self._mode == MMapArea.MODE_TEXT and len(self._main_area.selected) and \
				   self._main_area.selected[0].editing:
            self.__change_paste_state(True)
        else:
            self.__change_paste_state(False)
    
    # TODO: implement copy/paste for a whole thought or thoughts
    def __thought_selected_cb(self, arg, background_color, foreground_color):
        """Disable copy button if whole thought object is selected
        """
        self.__change_copy_state(False)
        self.__change_paste_state(False)

    def __change_copy_state(self, state):
        try:
            self.edit_toolbar.props.page.copy.child.set_sensitive(state)
        except AttributeError:
            self.edit_toolbar.copy.child.set_sensitive(state)

    def __change_paste_state(self, state):
        try:
            self.edit_toolbar.props.page.paste.child.set_sensitive(state)
        except AttributeError:
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
        geom[3] =  geom[3] - ((self.window.get_geometry()[3] - geom[3]) / 2)

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
        
        return False
        
    def __centre(self):
        bounds = self.__get_thought_bounds()
        self._main_area.translation[0] = bounds['x']
        self._main_area.translation[1] = bounds['y']
        self._main_area.invalidate()
        return False

    def __mode_cb(self, button, mode):
        self._mode = mode
        self._main_area.set_mode (self._mode)

    def __export_pdf_cb (self, event):
        maxx, maxy = self._main_area.get_max_area()
        true_width = int(maxx)
        true_height = int(maxy)
        
        # Create the new journal entry
        fileObject = datastore.create()
        act_meta = self.metadata
        fileObject.metadata['title'] = act_meta['title'] + ' (PDF)'
        fileObject.metadata['title_set_by_user'] = act_meta['title_set_by_user']
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

    def __export_png_cb (self, event):
        x, y, w, h, bitdepth = self._main_area.window.get_geometry()
        cmap = self._main_area.window.get_colormap()
        maxx, maxy = self._main_area.get_max_area()
        true_width = int(maxx)
        true_height = int(maxy)
        
        # Create the new journal entry
        fileObject = datastore.create()
        act_meta = self.metadata
        fileObject.metadata['title'] = act_meta['title'] + ' (PNG)'
        fileObject.metadata['title_set_by_user'] = act_meta['title_set_by_user']
        fileObject.metadata['mime_type'] = 'image/png'
        
        fileObject.metadata['icon-color'] = act_meta['icon-color']
        fileObject.file_path = os.path.join(self.get_activity_root(),
                                            'instance', '%i' % time.time())
        filename = fileObject.file_path
        pixmap = gtk.gdk.Pixmap(None, true_width, true_height, bitdepth)
        pixmap.set_colormap(cmap)
        self._main_area.export(pixmap.cairo_create(), true_width, true_height, False)
        pb = gtk.gdk.Pixbuf.get_from_drawable(
                                          gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB,
                                                         True,
                                                         8,
                                                         true_width,
                                                         true_height),
                                          pixmap,
                                          gtk.gdk.colormap_get_system(),
                                          0, 0, 0, 0,
                                          true_width,
                                          true_height)
        pb.save(filename, 'png')
        datastore.write(fileObject, transfer_ownership=True)
        fileObject.destroy()
        del fileObject

    def __main_area_focus_cb (self, arg, event, extended = False):
        self._main_area.grab_focus ()

    def read_file(self, file_path):
        tar = Tarball(file_path)

        doc = dom.parseString (tar.read(tar.getnames()[0]))
        top_element = doc.documentElement

        self.set_title(top_element.getAttribute ("title"))
        self._mode = int (top_element.getAttribute ("mode"))

        self._main_area.set_mode (self._mode)
        self._main_area.load_thyself (top_element, doc, tar)
        if top_element.hasAttribute("scale_factor"):
            self._main_area.scale_fac = float (top_element.getAttribute ("scale_factor"))
        if top_element.hasAttribute("translation"):
            tmp = top_element.getAttribute("translation")
            (x,y) = utils.parse_coords(tmp)
            self._main_area.translation = [x,y]

        self.mods[self._mode].set_active(True)

        tar.close()

    def write_file(self, file_path):
        logging.debug('write_file')

        tar = Tarball(file_path, 'w')

        self._main_area.update_save()
        manifest = self.serialize_to_xml(self._main_area.save,
                self._main_area.element)
        tar.write('MANIFEST', manifest)
        self._main_area.save_thyself(tar)

        tar.close()

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

    def __link_cb(self, widget):
        self._main_area.link_menu_cb()

    def __delete_cb(self, widget):
        self._main_area.delete_selected_elements ()
