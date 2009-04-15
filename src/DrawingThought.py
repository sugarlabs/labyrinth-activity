# DrawingThought.py
# This file is part of Labyrinth
#
# Copyright (C) 2006 - Don Scorgie <Don@Scorgieorg>
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

import gtk
import xml.dom.minidom as dom
import xml.dom
import gettext
_ = gettext.gettext
import math
import logging
import cairo

from BaseThought import *
import utils
import UndoManager

STYLE_CONTINUE=0
STYLE_END=1
STYLE_BEGIN=2
ndraw =0
SMOOTH = 5

class DrawingThought (ResizableThought):
	class DrawingPoint (object):
		def __init__ (self, coords, style=STYLE_CONTINUE, color = gtk.gdk.Color(0,0,0), width = 2):
			self.x, self.y = coords
			self.style = style
			if color == None:
				color = gtk.gdk.Color(0,0,0)
			self.color = color
			self.width = 1
		def move_by (self, x, y):
			self.x += x
			self.y += y

	def __init__ (self, coords, pango_context, thought_number, save, undo, loading, background_color, foreground_color):
		global ndraw
		super (DrawingThought, self).__init__(coords, save, "drawing_thought", undo, background_color, foreground_color)
		ndraw+=1
		self.identity = thought_number
		self.points = []
		self.text = _("Drawing #%d" % ndraw)
		self.drawing = 0
		self.all_okay = True
		self.coords_smooth = []

	def draw (self, context):
		ResizableThought.draw(self, context)

		cwidth = context.get_line_width ()
		context.set_line_width (2)
		context.set_line_join(cairo.LINE_JOIN_BEVEL)
		context.set_line_cap(cairo.LINE_CAP_ROUND)
		if len (self.points) > 0:
			for p in self.points:
				if p.style == STYLE_BEGIN:
					context.move_to (p.x, p.y)
					r,g,b = utils.gtk_to_cairo_color(self.foreground_color)
					context.set_source_rgb (r, g, b)
				elif p.style == STYLE_END:
					context.line_to (p.x, p.y)
					context.stroke()
				else:
					context.line_to (p.x, p.y)

		context.set_line_width (cwidth)
		context.stroke ()
		return

	def recalc_edges (self):
		self.lr = (self.ul[0]+self.width, self.ul[1]+self.height)

	def undo_drawing (self, action, mode):
		self.undo.block ()
		if mode == UndoManager.UNDO:
			choose = 1
			for p in action.args[0]:
				self.points.remove (p)
		else:
			choose = 2
			for p in action.args[0]:
				self.points.append (p)

		self.ul = action.args[choose][0]
		self.width = action.args[choose][1]
		self.height = action.args[choose][2]
		self.recalc_edges ()
		self.emit ("update_links")
		self.emit ("update_view")
		self.undo.unblock ()

	def process_button_down (self, event, coords):
		if ResizableThought.process_button_down(self, event, coords):
			return True

		if event.button == 1:
			self.button_down = True
			self.drawing = 2
			if not event.state & gtk.gdk.SHIFT_MASK:
				self.drawing = 1
			self.orig_size = (self.ul, self.width, self.height)
			self.ins_points = []
			self.del_points = []
			return True

		return False

	def process_button_release (self, event, transformed):
		if len(self.points) > 0:
			self.points[-1].style=STYLE_END

		if self.orig_size:
			if self.drawing == 0:
				# correct sizes after creation
				if self.creating:
					orig_size = self.width >= MIN_SIZE or self.height >= MIN_SIZE
					self.width = orig_size and max(MIN_SIZE, self.width) or DEFAULT_WIDTH
					self.height = orig_size and max(MIN_SIZE, self.height) or DEFAULT_HEIGHT
					self.recalc_edges()
					self.creating = False
				else:
					self.undo.add_undo (UndoManager.UndoAction (self, UNDO_RESIZE, \
							self.undo_resize, self.orig_size, (self.ul, self.width, self.height)))

			elif self.drawing == 1:
				self.undo.add_undo (UndoManager.UndoAction (self, UNDO_DRAW, \
						self.undo_drawing, self.ins_points, self.orig_size, \
						(self.ul, self.width, self.height)))

			elif self.drawing == 2:
				self.undo.add_undo (UndoManager.UndoAction (self, UNDO_ERASE, \
						self.undo_erase, self.ins_points))

		self.drawing = 0
		return ResizableThought.process_button_release(self, event, transformed)

	def leave(self):
		ResizableThought.leave(self)
		self.drawing = 0

	def undo_erase (self, action, mode):
		self.undo.block ()
		action.args[0].reverse ()
		if mode == UndoManager.UNDO:
			for x in action.args[0]:
				if x[0] == 0:
					self.points.remove (x[2])
				else:
					self.points.insert (x[1],x[2])
		else:
			for x in action.args[0]:
				if x[0] == 0:
					self.points.insert (x[1], x[2])
				else:
					self.points.remove (x[2])
		self.undo.unblock ()
		self.emit ("update_view")

	def handle_motion (self, event, coords):
		if ResizableThought.handle_motion(self, event, coords):
			return True

		if not self.editing:
			return False

		# Smooth drawing and reduce number of points
		self.coords_smooth.append(coords)
		if len(self.coords_smooth) < SMOOTH:
			return False
		else:
			coords = (float(sum([i[0] for i in self.coords_smooth])) / SMOOTH,
                      float(sum([i[1] for i in self.coords_smooth])) / SMOOTH)
			self.coords_smooth = []

		if self.drawing == 1:
			if coords[0] < self.ul[0]+5:
				self.ul = (coords[0]-5, self.ul[1])
			elif coords[0] > self.lr[0]-5:
				self.lr = (coords[0]+5, self.lr[1])
			if coords[1] < self.ul[1]+5:
				self.ul = (self.ul[0], coords[1]-5)
			elif coords[1] > self.lr[1]-5:
				self.lr = (self.lr[0], coords[1]+5)

			if self.min_x is None or coords[0] < self.min_x:
				self.min_x = coords[0]-10
			elif self.max_x is None or coords[0] > self.max_x:
				self.max_x = coords[0]+5
			if self.min_y is None or coords[1] < self.min_y:
				self.min_y = coords[1]-10
			elif self.max_y is None or coords[1] > self.max_y:
				self.max_y = coords[1]+5
			self.width = self.lr[0] - self.ul[0]
			self.height = self.lr[1] - self.ul[1]
			if len(self.points) == 0 or self.points[-1].style == STYLE_END:
				p = self.DrawingPoint (coords, STYLE_BEGIN, self.foreground_color)
			else:
				p = self.DrawingPoint (coords, STYLE_CONTINUE)
			self.points.append (p)
			self.ins_points.append (p)
			return True

		elif self.drawing == 2 and len (self.points) > 0:
			out = self.points[0]
			loc = []
			handle = []
			ins_point = -1

			for x in self.points:
				ins_point += 1
				dist = (x.x - coords[0])**2 + (x.y - coords[1])**2

				if dist < 16:
					if x == self.points[0]:
						out = None
					loc.append ((ins_point, x, dist))
				else:
					if len(loc) != 0:
						handle.append ((loc, out, x))
						loc = []
					elif x.style != STYLE_BEGIN:
						x1 = x.x - out.x
						y1 = x.y - out.y
						d_rsqr = x1**2 + y1 **2
						d = ((out.x-coords[0])*(x.y-coords[1]) - (x.x-coords[0])*(out.y-coords[1]))
						det = (d_rsqr*16) - d**2
						if det > 0:
							xt = -99999
							yt = -99999
							xalt = -99999
							yalt = -99999
							if y1 < 0:
								sgn = -1
							else:
								sgn = 1
							xt = (((d*y1) + sgn*x1 * math.sqrt (det)) / d_rsqr) +coords[0]
							xalt = (((d*y1) - sgn*x1 * math.sqrt (det)) / d_rsqr) +coords[0]
							yt = (((-d*x1) + abs(y1)*math.sqrt(det)) / d_rsqr) + coords[1]
							yalt = (((-d*x1) - abs(y1)*math.sqrt(det)) / d_rsqr) +coords[1]
							x1_inside = (xt > x.x and xt < out.x) or (xt > out.x and xt < x.x)
							x2_inside = (xalt > x.x and xalt < out.x) or (xalt > out.x and xalt < x.x)
							y1_inside = (yt > x.y and yt < out.y) or (yt > out.y and yt < x.y)
							y2_inside = (yalt > x.y and yalt < out.y) or (yalt > out.y and yalt < x.y)


							if (x1_inside and x2_inside and y1_inside and y2_inside):
							   	if abs (xalt - x.x) < abs (xt - x.x):
							   		handle.append ((None, out, x, ins_point, xt, xalt, yt, yalt))
							   	else:
							   		handle.append ((None, out, x, ins_point, xalt, xt, yalt, yt))
							elif x.x == out.x and y1_inside and y2_inside:
							   	if abs (yalt - x.y) < abs (yt - x.y):
							   		handle.append ((None, out, x, ins_point, xt, xalt, yt, yalt))
							   	else:
							   		handle.append ((None, out, x, ins_point, xalt, xt, yalt, yt))
							elif x.y == out.y and x1_inside and x2_inside:
								if abs (xalt - x.x) < abs (xt - x.x):
								   	handle.append ((None, out, x, ins_point, xt, xalt, yt, yalt))
								else:
								   	handle.append ((None, out, x, ins_point, xalt, xt, yalt, yt))

					out = x
			if loc:
				handle.append ((loc, out, None))
			appends = []
			dels = []
			for l in handle:
				inside = l[0]
				prev = l[1]
				next = l[2]
				if not inside:
					ins = l[3]
					x1 = l[4]
					x2 = l[5]
					y1 = l[6]
					y2 = l[7]
					p1 = self.DrawingPoint ((x1,y1), STYLE_END)
					p2 = self.DrawingPoint ((x2,y2), STYLE_BEGIN)
					appends.append ((p1, ins))
					appends.append ((p2, ins))
				else:
					first = inside[0][1]
					last = inside[-1][1]
					done_ins = 0
					if last.style != STYLE_END:
						end_dist = math.sqrt (inside[-1][2]) - 4
						alpha = math.atan2 ((last.y-next.y), (last.x-next.x))
						new_x = end_dist * math.cos(alpha) + last.x
						new_y = end_dist * math.sin(alpha) + last.y
						p = self.DrawingPoint ((new_x, new_y), STYLE_BEGIN)
						appends.append ((p, inside[-1][0]))
						done_ins = 1
					if first.style != STYLE_BEGIN:
						start_dist = math.sqrt (inside[0][2]) - 4
						alpha = math.atan2 ((first.y-prev.y),(first.x-prev.x))
						new_x = start_dist * math.cos (alpha) + first.x
						new_y = start_dist * math.sin (alpha) + first.y
						p = self.DrawingPoint ((new_x, new_y), STYLE_END)
						appends.append ((p, inside[0][0]-done_ins))
					for i in inside:
						dels.append (i[1])
			inserts = 0
			for x in appends:
				self.points.insert (x[1]+inserts, x[0])
				self.ins_points.append ((0, x[1]+inserts, x[0]))
				inserts+=1
			for x in dels:
				self.ins_points.append ((1, self.points.index (x), x))
				self.points.remove (x)

			return True

		return False

	def move_content_by(self, x, y):
		map(lambda p : p.move_by(x,y), self.points)
		ResizableThought.move_content_by(self, x, y)

	def update_save (self):
		next = self.element.firstChild
		while next:
			m = next.nextSibling
			if next.nodeName == "point":
				self.element.removeChild (next)
				next.unlink ()
			next = m		
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
		self.element.setAttribute ("foreground-color", self.foreground_color.to_string())
		self.element.setAttribute ("min_x", str(self.min_x))
		self.element.setAttribute ("min_y", str(self.min_y))
		self.element.setAttribute ("max_x", str(self.max_x))
		self.element.setAttribute ("max_y", str(self.max_y))

		if self.am_selected:
				self.element.setAttribute ("current_root", "true")
		else:
			try:
				self.element.removeAttribute ("current_root")
			except xml.dom.NotFoundErr:
				pass
		if self.am_primary:
			self.element.setAttribute ("primary_root", "true");
		else:
			try:
				self.element.removeAttribute ("primary_root")
			except xml.dom.NotFoundErr:
				pass
		doc = self.element.ownerDocument
		for p in self.points:
			elem = doc.createElement ("point")
			self.element.appendChild (elem)
			elem.setAttribute ("coords", str((p.x,p.y)))
			elem.setAttribute ("type", str(p.style))
			elem.setAttribute ("color", p.color.to_string())
		return

	def load (self, node, tar):
		tmp = node.getAttribute ("ul-coords")
		self.ul = utils.parse_coords (tmp)
		tmp = node.getAttribute ("lr-coords")
		self.lr = utils.parse_coords (tmp)
		self.identity = int (node.getAttribute ("identity"))
		try:
			tmp = node.getAttribute ("background-color")
			self.background_color = gtk.gdk.color_parse(tmp)
			tmp = node.getAttribute ("foreground-color")
			self.foreground_color = gtk.gdk.color_parse(tmp)
		except ValueError:
			pass

		def get_min_max(node, name):
			attr = node.getAttribute(name)
			if attr == 'None':
				return None
			else:
				return float(attr)

		self.min_x = get_min_max(node, 'min_x')
		self.min_y = get_min_max(node, 'min_y')
		self.max_x = get_min_max(node, 'max_x')
		self.max_y = get_min_max(node, 'max_y')

		self.width = self.lr[0] - self.ul[0]
		self.height = self.lr[1] - self.ul[1]

		self.am_selected = node.hasAttribute ("current_root")
		self.am_primary = node.hasAttribute ("primary_root")

		for n in node.childNodes:
			if n.nodeName == "Extended":
				self.extended_buffer.load(n)
			elif n.nodeName == "point":
				style = int (n.getAttribute ("type"))
				tmp = n.getAttribute ("coords")
				c = utils.parse_coords (tmp)
				col = None
				try:
					tmp = n.getAttribute ("color")
					col = gtk.gdk.color_parse (tmp)
				except ValueError:
					pass
				self.points.append (self.DrawingPoint (c, style, col))
			else:
				print "Unknown node type: "+str(n.nodeName)

	def export (self, context, move_x, move_y):
		utils.export_thought_outline (context, self.ul, self.lr, self.background_color, self.am_selected, self.am_primary, utils.STYLE_NORMAL,
									  (move_x, move_y))
		cwidth = context.get_line_width ()
		context.set_line_width (1)
		if len (self.points) > 0:
			for p in self.points:
				if p.style == STYLE_BEGIN:
					context.move_to (p.x+move_x, p.y+move_y)
				else:
					context.line_to (p.x+move_x,p.y+move_y)

		context.set_line_width (cwidth)
		r,g,b = utils.gtk_to_cairo_color(self.foreground_color)
		context.set_source_rgb (r, g, b)
		context.stroke ()
		return

	def inside(self, inside):
		if self.editing:
			self.emit ("change_mouse_cursor", gtk.gdk.PENCIL)
		else:
			ResizableThought.inside(self, inside)

	def enter (self):
		self.editing = True
