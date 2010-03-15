#! /usr/bin/env python
# LabelThoughts.py
# This file is part of Labyrinth
#
# Copyright (C) 2010 - Jorge Saldivar <jsaldivar@paraguayeduca.org>
#                      Martin Abente <mabente@paraguayeduca.org>
#
# Labyrinth is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Labyrinth is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Labyrinth; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor,
# Boston, MA  02110-1301  USA
#

import gtk
import pango
import utils
import xml.dom

from BaseThought import *
from TextThought import TextThought

class LabelThought (TextThought):
    def __init__ (self, coords, pango_context, thought_number, save, undo, loading, background_color, foreground_color, name="label_thought"):
        super (LabelThought, self).__init__(coords, pango_context, thought_number, save, undo, loading, background_color, foreground_color, name)
        self.edge = True

    def can_be_parent(self):
        return False

    def draw (self, context):
        self.recalc_edges ()
        if self.edge:
            ResizableThought.draw(self, context)
        if self.creating:
            return
        (textx, texty) = (self.min_x, self.min_y)
        if self.am_primary:
            r, g, b = utils.primary_colors["text"]
        elif (self.foreground_color):
            r, g, b = utils.gtk_to_cairo_color(self.foreground_color)
        else:
            r, g ,b = utils.gtk_to_cairo_color(utils.default_colors["text"])
        context.set_source_rgb (r, g, b)
        self.layout.set_alignment(pango.ALIGN_CENTER)
        context.move_to (textx, texty)
        context.show_layout (self.layout)
        if self.editing:
            if self.preedit:
                (strong, weak) = self.layout.get_cursor_pos (self.index + self.preedit[2])
            else:
                (strong, weak) = self.layout.get_cursor_pos (self.index)
            (startx, starty, curx,cury) = strong
            startx /= pango.SCALE
            starty /= pango.SCALE
            curx /= pango.SCALE
            cury /= pango.SCALE
            context.move_to (textx + startx, texty + starty)
            context.line_to (textx + startx, texty + starty + cury)
            context.stroke ()
        context.set_source_rgb (0,0,0)
        context.stroke ()

    def update_save (self):
        next = self.element.firstChild
        while next:
            m = next.nextSibling
            if next.nodeName == "attribute":
                self.element.removeChild (next)
                next.unlink ()
            next = m

        if self.text_element.parentNode is not None:
            self.text_element.replaceWholeText (self.text)
        text = self.extended_buffer.get_text ()
        if text:
            self.extended_buffer.update_save()
        else:
            try:
                self.element.removeChild(self.extended_buffer.element)
            except xml.dom.NotFoundErr:
                pass
        self.element.setAttribute ("cursor", str(self.index))
        self.element.setAttribute ("ul-coords", str(self.ul))
        self.element.setAttribute ("lr-coords", str(self.lr))
        self.element.setAttribute ("identity", str(self.identity))
        self.element.setAttribute ("background-color", utils.color_to_string(self.background_color))
        self.element.setAttribute ("foreground-color", utils.color_to_string(self.foreground_color))
        self.element.setAttribute ("edge", str(self.edge))
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
        it = self.attributes.get_iterator()
        while (1):
            r = it.range()
            for x in it.get_attrs():
                if x.type == pango.ATTR_WEIGHT and x.value == pango.WEIGHT_BOLD:
                    elem = doc.createElement ("attribute")
                    self.element.appendChild (elem)
                    elem.setAttribute("start", str(r[0]))
                    elem.setAttribute("end", str(r[1]))
                    elem.setAttribute("type", "bold")
                elif x.type == pango.ATTR_STYLE and x.value == pango.STYLE_ITALIC:
                    elem = doc.createElement ("attribute")
                    self.element.appendChild (elem)
                    elem.setAttribute("start", str(r[0]))
                    elem.setAttribute("end", str(r[1]))
                    elem.setAttribute("type", "italics")
                elif x.type == pango.ATTR_UNDERLINE and x.value == pango.UNDERLINE_SINGLE:
                    elem = doc.createElement ("attribute")
                    self.element.appendChild (elem)
                    elem.setAttribute("start", str(r[0]))
                    elem.setAttribute("end", str(r[1]))
                    elem.setAttribute("type", "underline")
                elif x.type == pango.ATTR_FONT_DESC:
                    elem = doc.createElement ("attribute")
                    self.element.appendChild (elem)
                    elem.setAttribute("start", str(r[0]))
                    elem.setAttribute("end", str(r[1]))
                    elem.setAttribute("type", "font")
                    elem.setAttribute("value", x.desc.to_string ())
            if not it.next():
                break

    def load (self, node, tar):
        self.index = int (node.getAttribute ("cursor"))
        self.end_index = self.index
        tmp = node.getAttribute ("ul-coords")
        self.ul = utils.parse_coords (tmp)
        tmp = node.getAttribute ("lr-coords")
        self.lr = utils.parse_coords (tmp)

        self.width = self.lr[0] - self.ul[0]
        self.height = self.lr[1] - self.ul[1]

        self.identity = int (node.getAttribute ("identity"))
        try:
            tmp = node.getAttribute ("background-color")
            self.background_color = gtk.gdk.color_parse(tmp)
            tmp = node.getAttribute ("foreground-color")
            self.foreground_color = gtk.gdk.color_parse(tmp)
        except ValueError:
            pass

        self.am_selected = node.hasAttribute ("current_root")
        self.am_primary = node.hasAttribute ("primary_root")
        
        if node.getAttribute ("edge") == "True":
            self.edge = True
        else:
            self.edge = False

        for n in node.childNodes:
            if n.nodeType == n.TEXT_NODE:
                self.text = n.data
            elif n.nodeName == "Extended":
                self.extended_buffer.load(n)
            elif n.nodeName == "attribute":
                attrType = n.getAttribute("type")
                start = int(n.getAttribute("start"))
                end = int(n.getAttribute("end"))

                if attrType == "bold":
                    attr = pango.AttrWeight(pango.WEIGHT_BOLD, start, end)
                elif attrType == "italics":
                    attr = pango.AttrStyle(pango.STYLE_ITALIC, start, end)
                elif attrType == "underline":
                    attr = pango.AttrUnderline(pango.UNDERLINE_SINGLE, start, end)
                elif attrType == "font":
                    font_name = str(n.getAttribute("value"))
                    pango_font = pango.FontDescription (font_name)
                    attr = pango.AttrFontDesc (pango_font, start, end)
                self.attributes.change(attr)
            else:
                print "Unknown: "+n.nodeName
        self.rebuild_byte_table ()
        self.recalc_edges()

    def enter(self):
        if self.editing:
            return
        self.orig_text = self.text
        self.editing = True
        self.edge = True

    def leave(self):
        if not self.editing:
            return
        ResizableThought.leave(self)
        self.editing = False
        self.end_index = self.index
        self.emit ("update_links")
        self.edge = False
        self.recalc_edges ()
