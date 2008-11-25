import sys
import os
import logging
from gettext import gettext as _
import tarfile
import tempfile
import xml.dom.minidom as dom

import gobject
import gtk

from sugar.activity import activity
from sugar.graphics.toolbutton import ToolButton

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
        edit_toolbar.show()

        self._undo = UndoManager.UndoManager (self,
                                             edit_toolbar.undo.child,
                                             edit_toolbar.redo.child)
        self._undo.block ()

        """
        self._add_text_thought = ToolButton('go-next-paired')
        self._add_text_thought.set_tooltip(_('Add idea as text'))
        self._add_text_thought.connect('clicked', self.__add_text_thought_cb)
        edit_toolbar.insert(self._add_text_thought, -1)
        self._add_text_thought.show()
        """

        self._save_file = None
        self._mode = MMapArea.MODE_EDITING

        self._main_area = MMapArea.MMapArea (self._undo)
        self._main_area.connect ("doc_save", self.__doc_save_cb)
        self._main_area.connect ("set_focus", self.__main_area_focus_cb)
        self._main_area.connect ("button-press-event", self.__main_area_focus_cb)
        self.set_canvas(self._main_area)
        self._main_area.show()

        tree_model = gtk.TreeStore(gobject.TYPE_STRING)
        self._main_area.initialize_model(tree_model)

        self.set_focus_child (self._main_area)

        self._undo.unblock()

    def __add_text_thought_cb(self, button):
        coords = (100, 100)
        thought = self._main_area.create_new_thought(coords, MMapArea.TYPE_TEXT)
        self._main_area.begin_editing(thought)

    def __undo_cb(self, button):
        self._undo.undo_action(None)

    def __redo_cb(self, button):
        self._undo.redo_action(None)

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

