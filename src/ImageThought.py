# ImageThought.py
# This file is part of labyrinth
#
# Copyright (C) 2006 - Don Scorgie <Don@Scorgie.org>
#
# labyrinth is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# labyrinth is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with labyrinth; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor,
# Boston, MA  02110-1301  USA
#

import gtk
import xml.dom.minidom as dom
import xml.dom
import gettext
_ = gettext.gettext
import cairo
import os
import logging
import tempfile
import cStringIO

from sugar import mime

from BaseThought import *
import utils
import UndoManager

from sugar.activity.activity import get_activity_root
from sugar.graphics.objectchooser import ObjectChooser

class ImageThought (ResizableThought):
	def __init__ (self, coords, pango_context, thought_number, save, undo, loading, background_color, foreground_color):
		super (ImageThought, self).__init__(coords, save, "image_thought", undo, background_color, foreground_color)

		self.identity = thought_number
		self.pic = None
		self.orig_pic = None
		self.pic_location = coords
		self.button_press = False
		self.all_okay = True
		self.object_chooser_active = False

	# FIXME: Work in progress, needs at least activity self to create
	# tmp files/links in the right places and reference the window.
	def journal_open_image (self):
		self.object_chooser_active = True
		if hasattr(mime, 'GENERIC_TYPE_IMAGE'):
			chooser = ObjectChooser(_('Choose image'),
					what_filter=mime.GENERIC_TYPE_IMAGE)
		else:
			chooser = ObjectChooser(_('Choose image'))

		try:
			result = chooser.run()
			if result == gtk.RESPONSE_ACCEPT and chooser.get_selected_object():
				jobject = chooser.get_selected_object()
			else:
				return False

			if jobject and jobject.file_path:
				logging.debug("journal_open_image: fname=%s" % jobject.file_path)
				try:
					self.orig_pic = gtk.gdk.pixbuf_new_from_file (jobject.file_path)
					self.filename = os.path.join('images', os.path.basename(jobject.file_path))
				except Exception, e:
					logging.error("journal_open_image: %s" % e)
					return False
			else:
				return False
		finally:
			chooser.destroy()
			del chooser
		self.object_chooser_active = False

		self.text = self.filename[0:self.filename.rfind('.')]
		self.recalc_edges(True)

		return True

	def draw (self, context):
		ResizableThought.draw(self, context)
		if self.pic:
			context.set_source_pixbuf (self.pic, self.pic_location[0], self.pic_location[1])
			context.rectangle (self.pic_location[0], self.pic_location[1], self.width, self.height)
			context.fill ()
		context.set_source_rgb (0,0,0)

	def export (self, context, move_x, move_y):
		utils.export_thought_outline (context, self.ul, self.lr, self.background_color, self.am_selected, self.am_primary, utils.STYLE_NORMAL,
									  (move_x, move_y))
		if self.pic:
			raw_pixels = self.pic.get_pixels_array()
			if hasattr(context, "set_source_pixbuf"):
				context.set_source_pixbuf (self.pic, self.pic_location[0]+move_x, self.pic_location[1]+move_y)
			elif hasattr(context, "set_source_surface"):
				pixel_array = utils.pixbuf_to_cairo (raw_pixels)
				image_surface = cairo.ImageSurface.create_for_data(pixel_array, cairo.FORMAT_ARGB32, len(raw_pixels[0]), len(raw_pixels), -1)
				context.set_source_surface (image_surface, self.pic_location[0]+move_x, self.pic_location[1]+move_y)
                
			context.rectangle (self.pic_location[0]+move_x, self.pic_location[1]+move_y, len(raw_pixels[0]), len(raw_pixels))
			context.fill ()
		context.set_source_rgb (0,0,0)

	def recalc_edges (self, force=False, scale=gtk.gdk.INTERP_HYPER):
		self.lr = (self.ul[0]+self.width, self.ul[1]+self.height)

		margin = utils.margin_required (utils.STYLE_NORMAL)
		self.pic_location = (self.ul[0]+margin[0], self.ul[1]+margin[1])

		pic_w = max(MIN_SIZE, self.width - margin[0] - margin[2])
		pic_h = max(MIN_SIZE, self.height - margin[1] - margin[3])

		if self.orig_pic and (force or not self.pic or self.pic.get_width() != pic_w
				or self.pic.get_height() != pic_h):
                        self.pic = self.orig_pic.scale_simple(int(pic_w),
							      int(pic_h), scale)


	def process_button_down (self, event, coords):
		if ResizableThought.process_button_down(self, event, coords):
			return True

		return False

	def process_button_release (self, event, transformed):
		if self.button_down:
			if self.creating:
				if not self.journal_open_image():
					return False
				if self.width >= MIN_SIZE or self.height >= MIN_SIZE:
					self.width = max(MIN_SIZE, self.width)
					self.height = max(MIN_SIZE, self.height)
				else:
					self.width = self.orig_pic.get_width()
					self.height = self.orig_pic.get_height()
				self.creating = False
			else:
				self.undo.add_undo (UndoManager.UndoAction (self, UNDO_RESIZE, \
						self.undo_resize, self.orig_size, (self.ul, self.width, self.height)))

			self.recalc_edges(True)

		return ResizableThought.process_button_release(self, event, transformed)

	def handle_motion (self, event, coords):
		if self.object_chooser_active:
			return False
		if ResizableThought.handle_motion(self, event, coords):
			self.recalc_edges(False, gtk.gdk.INTERP_NEAREST)
			return True

		return False

	def update_save (self):
		text = self.extended_buffer.get_text ()
		if text:
			self.extended_buffer.update_save()
		else:
			try:
				self.element.removeChild(self.extended_buffer.element)
			except xml.dom.NotFoundErr:
				pass
		self.element.setAttribute ("ul-coords", str(self.ul))
		self.element.setAttribute ("lr-coords", str(self.lr))
		self.element.setAttribute ("identity", str(self.identity))
		self.element.setAttribute ("background-color", self.background_color.to_string())
		self.element.setAttribute ("file", str(self.filename))
		self.element.setAttribute ("image_width", str(self.width))
		self.element.setAttribute ("image_height", str(self.height))
		if self.am_selected:
				self.element.setAttribute ("current_root", "true")
		else:
			try:
				self.element.removeAttribute ("current_root")
			except xml.dom.NotFoundErr:
				pass
		if self.am_primary:
			self.element.setAttribute ("primary_root", "true")
		else:
			try:
				self.element.removeAttribute ("primary_root")
			except xml.dom.NotFoundErr:
				pass

	def save (self, tar):
		if not [i for i in tar.getnames() if i == self.filename]:
			tar.write(self.filename, self.orig_pic)

	def load (self, node, tar):
		tmp = node.getAttribute ("ul-coords")
		self.ul = utils.parse_coords (tmp)
		tmp = node.getAttribute ("lr-coords")
		self.lr = utils.parse_coords (tmp)
		self.filename = os.path.join('images', 
				os.path.basename(node.getAttribute ("file")))
		self.identity = int (node.getAttribute ("identity"))
		try:
			tmp = node.getAttribute ("background-color")
			self.background_color = gtk.gdk.color_parse(tmp)
		except ValueError:
			pass
		self.width = float(node.getAttribute ("image_width"))
		self.height = float(node.getAttribute ("image_height"))
		self.am_selected = node.hasAttribute ("current_root")
		self.am_primary = node.hasAttribute ("primary_root")

		for n in node.childNodes:
			if n.nodeName == "Extended":
				self.extended_buffer.load(n)
			else:
				print "Unknown: "+n.nodeName
		margin = utils.margin_required (utils.STYLE_NORMAL)
		self.pic_location = (self.ul[0]+margin[0], self.ul[1]+margin[1])
		self.orig_pic = tar.read_pixbuf(self.filename)
		self.lr = (self.pic_location[0]+self.width+margin[2], self.pic_location[1]+self.height+margin[3])
		self.recalc_edges()
	
	def enter (self):
		self.editing = True
