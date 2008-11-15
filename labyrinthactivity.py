import sys
import os
import logging
from gettext import gettext as _
import tarfile
import sha
import xml.dom.minidom as dom

import gobject
import gtk

from sugar.activity import activity
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

        self._edit_toolbar = activity.EditToolbar()
        toolbox.add_toolbar(_('Edit'), self._edit_toolbar)
        self._edit_toolbar.show()

        self.undo = UndoManager.UndoManager (self,
                                             self._edit_toolbar.undo.child,
                                             self._edit_toolbar.redo.child)
        self.undo.block ()

        self.save_file = None
        self.mode = MMapArea.MODE_EDITING

        self.MainArea = MMapArea.MMapArea (self.undo)
        self.MainArea.connect ("doc_save", self.doc_save_cb)
        self.MainArea.connect ("set_focus", self.main_area_focus_cb)
        self.MainArea.connect ("button-press-event", self.main_area_focus_cb)
        self.set_canvas(self.MainArea)
        self.MainArea.show()

        self.tree_model = gtk.TreeStore(gobject.TYPE_STRING)
        self.MainArea.initialize_model(self.tree_model)

        self.set_focus_child (self.MainArea)

    def main_area_focus_cb (self, arg, event, extended = False):
        self.MainArea.grab_focus ()

    def read_file(self, file_path):
        tf = tarfile.open(file_path)
        mapname = utils.get_save_dir() + tf.getnames()[0]
        tf.extractall(utils.get_save_dir())
        tf.close()

        f = file (mapname, 'r')
        doc = dom.parse (f)
        top_element = doc.documentElement
        self.set_title(top_element.getAttribute ("title"))
        self.mode = int (top_element.getAttribute ("mode"))

        self.MainArea.set_mode (self.mode)
        self.MainArea.load_thyself (top_element, doc)
        if top_element.hasAttribute("scale_factor"):
            self.MainArea.scale_fac = float (top_element.getAttribute ("scale_factor"))
        if top_element.hasAttribute("translation"):
            tmp = top_element.getAttribute("translation")
            (x,y) = utils.parse_coords(tmp)
            self.MainArea.translation = [x,y]

    def write_file(self, file_path):
        logging.debug('write_file')
        self.MainArea.save_thyself ()
        tf = tarfile.open (file_path, "w")
        tf.add (self.save_file, utils.strip_path_from_file_name(self.save_file))
        for t in self.MainArea.thoughts:
            if isinstance(t, ImageThought.ImageThought):
                tf.add (t.filename, 'images/' + utils.strip_path_from_file_name(t.filename))
                
        tf.close()

    def doc_save_cb (self, widget, doc, top_element):
        logging.debug('doc_save_cb')
        save_string = self.serialize_to_xml(doc, top_element)
        if not self.save_file:
            sham = sha.new (save_string)
            save_loc = utils.get_save_dir ()
            self.save_file = save_loc+sham.hexdigest()+".map"
            counter = 1
            while os.path.exists(self.save_file):
            
                print "Warning: Duplicate File.  Saving to alternative"
                self.save_file = save_loc + "Dup"+str(counter)+sham.hexdigest()+".map"
                counter += 1

        self.save_map(self.save_file, save_string)
        #self.emit ('file_saved', self.save_file, self)

    def serialize_to_xml(self, doc, top_element):
        top_element.setAttribute ("title", self.props.title)
        top_element.setAttribute ("mode", str(self.mode))
        top_element.setAttribute ("size", str((400, 400)))
        top_element.setAttribute ("position", str((0, 0)))
        top_element.setAttribute ("maximised", str(True))
        top_element.setAttribute ("view_type", str(0))
        top_element.setAttribute ("pane_position", str(500))
        top_element.setAttribute ("scale_factor", str(self.MainArea.scale_fac))
        top_element.setAttribute ("translation", str(self.MainArea.translation))
        string = doc.toxml ()
        return string.encode ("utf-8" )

    def save_map(self, filename, string):
        f = file (filename, 'w')
        f.write (string)
        f.close ()

