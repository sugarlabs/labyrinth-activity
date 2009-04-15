# BaseThought.py
# This file is part of Labyrinth
#
# Copyright (C) 2006 - Don Scorgie <DonScorgie@Blueyonder.co.uk>
#
# Labyrinth is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Labyrinth is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Labyrinth; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor,
# Boston, MA  02110-1301  USA
#

import gobject
import gtk
import utils
import pango

import TextBufferMarkup
import UndoManager

UNDO_RESIZE = 0
UNDO_DRAW = 1
UNDO_ERASE = 2

MIN_SIZE = 20

DEFAULT_WIDTH	= 100
DEFAULT_HEIGHT	= 70

class BaseThought (gobject.GObject):
	''' The basic class to derive other thoughts from. \
		Instructions for creating derivative thought types are  \
		given as comments'''
	# These are general signals.  They are available to all thoughts to
	# emit.  If you emit other signals, the chances are they'll be ignored
	# by the MMapArea.  It's you're responsiblity to catch and handle them.
	# All these signals are handled correctly by the MMapArea.
	__gsignals__ = dict (select_thought      = (gobject.SIGNAL_RUN_FIRST,
											    gobject.TYPE_NONE,
											    (gobject.TYPE_PYOBJECT,)),
						 update_view		 = (gobject.SIGNAL_RUN_LAST,
						 						gobject.TYPE_NONE,
						 						()),
						 create_link		 = (gobject.SIGNAL_RUN_FIRST,
						 						gobject.TYPE_NONE,
						 						(gobject.TYPE_PYOBJECT,)),
						 title_changed       = (gobject.SIGNAL_RUN_LAST,
						 						gobject.TYPE_NONE,
						 						(gobject.TYPE_STRING,)),
						 text_selection_changed = (gobject.SIGNAL_RUN_LAST,
						 						   gobject.TYPE_NONE,
						 						   (gobject.TYPE_INT, gobject.TYPE_INT, gobject.TYPE_STRING)),
						 change_mouse_cursor    = (gobject.SIGNAL_RUN_FIRST,
						 						   gobject.TYPE_NONE,
						 						   (gobject.TYPE_INT,)),
						 update_links			= (gobject.SIGNAL_RUN_LAST,
						 						   gobject.TYPE_NONE,
						 						   ()),
						 grab_focus				= (gobject.SIGNAL_RUN_FIRST,
						 						   gobject.TYPE_NONE,
						 						   (gobject.TYPE_BOOLEAN,)),
						 update_attrs			= (gobject.SIGNAL_RUN_FIRST,
						 						   gobject.TYPE_NONE,
						 						   (gobject.TYPE_BOOLEAN, gobject.TYPE_BOOLEAN, gobject.TYPE_BOOLEAN, pango.FontDescription)))

	# The first thing that should be called is this constructor
	# It sets some basic properties of all thoughts and should be called
	# before you start doing you're own thing with thoughts
	# save: the save document passed into the derived constructor
	# elem_type: a string representing the thought type (e.g. "image_thought")
	def __init__ (self, save, elem_type, undo, background_color, foreground_color):
		# Note: Once the thought has been successfully initialised (i.e. at the end
		# of the constructor) you MUST set all_okay to True
		# Otherwise, bad things will happen.
		self.all_okay = False
		super (BaseThought, self).__init__()
		self.ul = self.lr = None
		self.am_primary = False
		self.am_selected = False
		self.sensitive = 5
		self.editing = False
		self.identity = -1
		self.index = 0
		self.end_index = 0
		self.text = ""
		self.undo = undo
		self.background_color = background_color
		self.foreground_color = foreground_color
		self.model_iter = None
		extended_elem = save.createElement ("Extended")
		self.extended_buffer = TextBufferMarkup.ExtendedBuffer (self.undo, extended_elem, save)
		self.extended_buffer.set_text("")
		self.extended_buffer.connect ("set_focus", self.focus_buffer)
		self.extended_buffer.connect ("set_attrs", self.set_extended_attrs)
		self.element = save.createElement (elem_type)
		self.element.appendChild (extended_elem)
		self.creating = True

	# These are self-explanitory.  You probably don't want to
	# overwrite these methods, unless you have a very good reason
	def get_save_element (self):
		return self.element

	def make_primary (self):
		self.am_primary = True

	def select (self):
		self.am_selected = True

	def unselect (self):
		self.am_selected = False

	def get_max_area (self):
		if not self.ul or not self.lr:
			return 999,999,-999,-999
		return self.ul[0], self.ul[1], self.lr[0], self.lr[1]

	def okay (self):
		return self.all_okay

	def move_content_by (self, x, y):
		pass

	def move_by (self, x, y):
		pass

	def focus_buffer (self, buf):
		self.emit ("select_thought", None)
		self.emit ("grab_focus", True)

	def set_extended_attrs(self, buf, bold, underline, italics, pango_font):
		self.emit("update_attrs", bold, underline, italics, pango_font)
		
	def can_be_parent (self):
		return True
		
	# This, you may want to change.  Though, doing so will only affect
	# thoughts that are "parents"
	def find_connection (self, other):
		if not self.ul or not self.lr or not other.ul \
		or not other.lr:
			return None, None

		if utils.use_bezier_curves:
			if other.ul[0] > self.lr[0]:
				xfrom = self.lr[0]
				xto = other.ul[0]
			else:
				xfrom = self.ul[0]
				xto = other.lr[0]
		else:
			xfrom = self.ul[0]-((self.ul[0]-self.lr[0]) / 2.)
			xto = other.ul[0]-((other.ul[0]-other.lr[0]) / 2.)
			
		yfrom = self.ul[1]-((self.ul[1]-self.lr[1]) / 2.)
		yto = other.ul[1]-((other.ul[1]-other.lr[1]) / 2.)
		return (xfrom, yfrom), (xto, yto)

	# All the rest of these should be handled within you're thought
	# type, supposing you actually want to handle them.
	# You almost certianly do want to ;)
	def process_button_down (self, event, transformed):
		return False

	def process_button_release (self, event, transformed):
		return False

	def process_key_press (self, event, mode):
		return False

	def handle_motion (self, event, transformed):
		return False

	def includes (self, coords):
		pass

	def draw (self, context):
		pass

	def load (self, node, tar):
		pass

	def update_save (self):
		pass

	def save (self, tar):
		pass

	def copy_text (self, clip):
		pass

	def cut_text (self, clip):
		pass

	def paste_text (self, clip):
		pass

	def export (self, context, move_x, move_y):
		pass

	def commit_text (self, im_context, string, mode):
		pass

	def recalc_edges (self):
		pass

	def delete_surroundings(self, imcontext, offset, n_chars, mode):
		pass

	def preedit_changed (self, imcontext, mode):
		pass

	def preedit_end (self, imcontext, mode):
		pass

	def preedit_start (self, imcontext, mode):
		pass

	def retrieve_surroundings (self, imcontext, mode):
		pass
	
	def set_bold (self, active):
		pass
		
	def inside (self, inside):
		pass

	def enter (self):
		pass

	def leave (self):
		pass

RESIZE_NONE 	= 0
RESIZE_LEFT 	= 1
RESIZE_RIGHT 	= 2
RESIZE_TOP 		= 4
RESIZE_BOTTOM 	= 8

CURSOR = {}

CURSOR[RESIZE_LEFT] 				= gtk.gdk.LEFT_SIDE;
CURSOR[RESIZE_RIGHT]				= gtk.gdk.RIGHT_SIDE;
CURSOR[RESIZE_TOP]					= gtk.gdk.TOP_SIDE;
CURSOR[RESIZE_BOTTOM]				= gtk.gdk.BOTTOM_SIDE;
CURSOR[RESIZE_LEFT|RESIZE_TOP]		= gtk.gdk.TOP_LEFT_CORNER;
CURSOR[RESIZE_LEFT|RESIZE_BOTTOM]	= gtk.gdk.BOTTOM_LEFT_CORNER;
CURSOR[RESIZE_RIGHT|RESIZE_TOP]		= gtk.gdk.TOP_RIGHT_CORNER;
CURSOR[RESIZE_RIGHT|RESIZE_BOTTOM]	= gtk.gdk.BOTTOM_RIGHT_CORNER;

class ResizableThought (BaseThought):
	''' A resizable thought base class.  This allows the sides and corners \
	    of the thought to be dragged around.  It only provides the very basic \
	    functionality.  Other stuff must be done within the derived classes'''

	# Possible types of resizing - where the user selected to resize

	def __init__ (self, coords, save, elem_type, undo, background_color, foreground_color):
		super (ResizableThought, self).__init__(save, elem_type, undo, background_color, foreground_color)
		self.resizing = RESIZE_NONE
		self.button_down = False
		self.orig_size = None

		if coords:
			margin = utils.margin_required (utils.STYLE_NORMAL)
			self.ul = (coords[0]-margin[0], coords[1]-margin[1])
			self.lr = (coords[0]+margin[2], coords[1]+margin[3])
			self.width = 1
			self.height = 1

		self.min_x = self.max_x = None
		self.min_y = self.max_y = None


	def move_content_by (self, x, y):
		if self.min_x != None: self.min_x += x
		if self.min_y != None: self.min_y += y
		if self.max_x != None: self.max_x += x
		if self.max_y != None: self.max_y += y

	def move_by (self, x, y):
		self.move_content_by(x, y)
		self.ul = (self.ul[0]+x, self.ul[1]+y)
		self.recalc_edges ()
		self.emit ("update_links")
		self.emit ("update_view")

	def inside (self, inside):
		self.emit ("change_mouse_cursor", gtk.gdk.LEFT_PTR)

	def includes (self, coords):
		if not self.ul or not self.lr or not coords:
			return False

		if self.button_down:
			resizing = self.resizing
			inside = True
		else:
			inside = (coords[0] < self.lr[0] + self.sensitive) and \
					 (coords[0] > self.ul[0] - self.sensitive) and \
					 (coords[1] < self.lr[1] + self.sensitive) and \
					 (coords[1] > self.ul[1] - self.sensitive)
			resizing = RESIZE_NONE

			if inside:
				# 2 cases: 1. The click was within the main area
				#		   2. The click was near the border
				# In the first case, we handle as normal
				# In the second case, we want to intercept all the fun thats
				# going to happen so we can resize the thought

				if abs (coords[0] - self.ul[0]) <= self.sensitive:
					if coords[1] <= self.lr[1] and coords[1] >= self.ul[1]:
						resizing = resizing | RESIZE_LEFT
				elif abs (coords[0] - self.lr[0]) <= self.sensitive:
					if coords[1] <= self.lr[1] and coords[1] >= self.ul[1]:
						resizing = resizing | RESIZE_RIGHT

				if abs (coords[1] - self.ul[1]) <= self.sensitive and \
						(coords[0] <= self.lr[0] and coords[0] >= self.ul[0]):
					resizing = resizing | RESIZE_TOP
				elif abs (coords[1] - self.lr[1]) <= self.sensitive and \
						(coords[0] <= self.lr[0] and coords[0] >= self.ul[0]):
					resizing = resizing | RESIZE_BOTTOM

		if resizing == RESIZE_NONE:
			self.inside(inside)
		else:
			self.emit ("change_mouse_cursor", CURSOR[resizing])

		self.resizing = resizing
		return inside

	def process_button_down(self, event, coords):
		self.orig_size = None

		if self.resizing:
			self.button_down = True
			self.orig_size = (self.ul, self.width, self.height)
			return True

		return False

	def process_button_release(self, event, coords):
		self.resizing = RESIZE_NONE
		self.button_down = False

		if self.width < MIN_SIZE or self.height < MIN_SIZE:
			self.width = max(MIN_SIZE, self.width)
			self.height = max(MIN_SIZE, self.height)
			self.recalc_edges()

		return True

	def handle_motion (self, event, coords):
		if not self.resizing or not self.button_down:
			return False

		resizing = False

		if self.resizing & RESIZE_LEFT:
			if self.min_x is None or coords[0] < self.lr[0]-(self.max_x-self.min_x):
				if self.min_x and coords[0] > self.min_x:
					self.move_content_by(coords[0] - self.min_x, 0)
				self.ul = (coords[0], self.ul[1])
				resizing = True;
		elif self.resizing & RESIZE_RIGHT:
			if self.max_x is None or coords[0] > self.ul[0]+(self.max_x-self.min_x):
				if self.max_x and coords[0] < self.max_x:
					self.move_content_by(coords[0] - self.max_x, 0)
				self.lr = (coords[0], self.lr[1])
				resizing = True;
		if self.resizing & RESIZE_TOP:
			if self.min_y is None or coords[1] < self.lr[1]-(self.max_y-self.min_y):
				if self.min_y and coords[1] > self.min_y:
					self.move_content_by(0, coords[1] - self.min_y)
				self.ul = (self.ul[0], coords[1])
				resizing = True;
		elif self.resizing & RESIZE_BOTTOM:
			if self.max_y is None or coords[1] > self.ul[1]+(self.max_y-self.min_y):
				if self.max_y and coords[1] < self.max_y:
					self.move_content_by(0, coords[1] - self.max_y)
				self.lr = (self.lr[0], coords[1])
				resizing = True;

		if not resizing:
			return False

		if self.ul[0] > self.lr[0]:
			# horizontal mirroring
			tmp = self.ul[0]
			self.ul = (self.lr[0], self.ul[1])
			self.lr = (tmp, self.lr[1])
			self.resizing = (~self.resizing & 0x3) | (self.resizing & (0x3<<2))

		if self.ul[1] > self.lr[1]:
			# vertical mirroring
			tmp = self.ul[1]
			self.ul = (self.ul[0], self.lr[1])
			self.lr = (self.lr[0], tmp)
			self.resizing = (~self.resizing & (0x3<<2)) | (self.resizing & 0x3)

		self.width = self.lr[0] - self.ul[0]
		self.height = self.lr[1] - self.ul[1]

		return True

	def leave (self):
		self.editing = False
		self.emit('change_mouse_cursor', gtk.gdk.LEFT_PTR)

	def undo_resize (self, action, mode):
		self.undo.block ()
		if mode == UndoManager.UNDO:
			choose = 0
		else:
			choose = 1
		self.ul = action.args[choose][0]
		self.width = action.args[choose][1]
		self.height = action.args[choose][2]
		self.pic = self.orig_pic.scale_simple (int(self.width), int(self.height), gtk.gdk.INTERP_HYPER)
		self.recalc_edges ()
		self.emit ("update_links")
		self.emit ("update_view")
		self.undo.unblock ()

	def draw (self, context):
		if len (self.extended_buffer.get_text()) == 0:
			utils.draw_thought_outline (context, self.ul, self.lr,
					self.background_color, self.am_selected, self.am_primary,
					utils.STYLE_NORMAL)
		else:
			utils.draw_thought_outline (context, self.ul, self.lr,
					self.background_color, self.am_selected, self.am_primary,
					utils.STYLE_EXTENDED_CONTENT)
