# functions.py
# This file is part of labyrinth
#
# Copyright (C) 2006 - Don Scorgie
#                    - Andreas Sliwka
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
# along with Labyrinth; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor,
# Boston, MA  02110-1301  USA
#

# This file defines various useful functions
# that can be accessed from anywhere :)

import sys
from os.path import *
import os
from array import array

# Not available on OLPC's XO, but not needed neither
#from Numeric import *

import gtk

try:
	# Sugar specific modules
	from sugar.profile import get_color
	from sugar.graphics.style import Color
except:
	pass

def color_to_string(color):
    # Needed for compatibility with pygtk < 2.12
    return '#%04x%04x%04x' % (color.red, color.green, color.blue)

__BE_VERBOSE=os.environ.get('DEBUG_LABYRINTH',0)
if __BE_VERBOSE:
	def print_debug(*data):
		sys.stderr.write("\n".join(data) + "\n")
else:
	def print_debug(*data):
		pass

# FIXME: this is a no-go, but fast and efficient
# global variables
use_bezier_curves = True
default_colors = {
	"text" : (0.0, 0.0, 0.0),
	"fg" : (0.0, 0.0, 0.0),
	"bg" : (0.0, 0.0, 0.0),
	"base" : (0.0, 0.0, 0.0)
	}

selected_colors = {
	"text" : (0.0, 0.0, 0.0),
	"fg" : (0.0, 0.0, 0.0),
	"bg" : (0.0, 0.0, 0.0),
	"border" : (0.0, 0.0, 0.0),		# bounding box
	"fill" : (0.0, 0.0, 0.0)		# bounding box
	}

default_font = None

default_font_size = '10'

try:
	# Sugar specific tweak
	xo_col = get_color()
	rf, gf, bf, af = Color(xo_col.get_fill_color()).get_rgba()
	rs, gs, bs, as_ = Color(xo_col.get_stroke_color()).get_rgba()

	# Use white or black text for best contrast
	if rf + gf + bf < 0.5:
		rt, gt, bt = 1, 1, 1
	else:
		rt, gt, bt = 0, 0, 0
	primary_colors = {
		"bg" : (rf, gf, bf),
		"fg" : (rs, gs, bs),
		"text" : (rt, gt, bt)
		}
except:
	primary_colors = {
		"bg" : (0.2, 0.6, 1.0),
		"fg" : (0, 0, 0),
		"text" : (0, 0, 0)
		}

def get_save_dir ():
	''' Returns the path to the directory to save the maps to '''
	try:
		base = os.environ ['HOME']
	except:
		base = os.environ ['USERPROFILE']
	if os.name != 'nt':
		dirname = os.path.join (base, ".gnome2", "labyrinth"+os.sep)
	else:
		dirname = os.path.join (base, ".labyrinth"+os.sep)
	if not os.access (dirname, os.W_OK):
		os.makedirs (dirname)
	return dirname

def parse_coords (string):
	if string == "None":
		return None
	local = string[1:string.find(',')]
	local_2 = string[string.find (',')+1:string.find(')')]
	coord = (float(local),	float(local_2))
	return coord

__data_dir = None

_version = None

def get_version ():
	global _version
	if not _version:
		try:
			import defs
			_version = defs.VERSION
		except:
			_version = "Uninstalled"
	return _version

def get_data_dir():
	'''returns the data dir. Tries to find it the first time its called'''
	global __data_dir
	if os.name != 'nt':

		if __data_dir is None:
			#decide wether we run under development or if the program has been installed
			path = join(dirname(__file__), '..')
			if exists(path) and isdir(path) and isfile(path+"/AUTHORS"):
				__data_dir = os.sep.join([dirname(__file__), '..' , 'data'])
			else:
				try:
					import defs
					__data_dir=defs.pkgdatadir
				except:
					__data_dir = "./data"
	else:
		if __data_dir is None:
			__data_dir = join (".","data")
	return __data_dir

def get_data_file_name (file_name):
	''' takes a string and either returns it with the data directory prepended.'''
	return get_data_dir() + os.sep + file_name

def get_data_file (file_name):
	''' takes a string and either returns a data file of that name or raises an exception if it cant find it '''
	return open(get_data_file_name(file_name))

def strip_path_from_file_name(f):
	''' Removes the path including all leading and trailing slashes from a filename. '''
	return f.split('/')[-1]

# Drawing functions

# These are thought outline styles.
# Currently, there is only 1 - STYLE_NORMAL, which is the slightly rounded corners
# - The normal thought type
STYLE_NORMAL = 0
STYLE_EXTENDED_CONTENT = 1

def draw_thought_outline (context, ul, lr, background_color, am_root = False, am_primary = False, style=STYLE_NORMAL):
	draw_thought_extended(context, ul, lr, am_root, am_primary, background_color, style == STYLE_EXTENDED_CONTENT)

# This is used to find the required margin from the (real) ul / lr coords to the edge of the
# box area.  Makes selection of thoughts less erratic
def margin_required (style = STYLE_NORMAL):
	if style == STYLE_NORMAL:
		return margin_thought_classic ()
	else:
		print "Error: Unknown thought margine style: "+str(style)

# Classic thought style drawing code
def margin_thought_classic ():
	return (5, 5, 5, 5)

def gtk_to_cairo_color(color):
	return (color.red / 65535.0, color.green / 65535.0, color.blue / 65535.0)

def draw_thought_extended (context, ul, lr, am_root, am_primary, background_color, fatborder=False, dashborder=False):
	radius = min(15, lr[0]-ul[0], lr[1]-ul[1])

	context.move_to (ul[0], ul[1]+radius)
	context.line_to (ul[0], lr[1]-radius)
	context.curve_to (ul[0], lr[1], ul[0], lr[1], ul[0]+radius, lr[1])
	context.line_to (lr[0]-radius, lr[1])
	context.curve_to (lr[0], lr[1], lr[0], lr[1], lr[0], lr[1]-radius)
	context.line_to (lr[0], ul[1]+radius)
	context.curve_to (lr[0], ul[1], lr[0], ul[1], lr[0]-radius, ul[1])
	context.line_to (ul[0]+radius, ul[1])
	context.curve_to (ul[0], ul[1], ul[0], ul[1], ul[0], ul[1]+radius)
	if am_root:
		r,g,b = selected_colors["bg"]
	elif am_primary:
		r,g,b = primary_colors["bg"]
	else:
		r,g,b = gtk_to_cairo_color(background_color)
	context.set_source_rgb (r, g, b)
	context.fill_preserve ()
	if am_primary:
		r,g,b = primary_colors["fg"]
		context.set_source_rgb (r,g,b)
		fatborder = True
	else:
		context.set_source_rgb (0,0,0)
	if dashborder:
		context.set_dash([4.0], 0.0)
	if fatborder:
		orig_line_width = context.get_line_width ()
		context.set_line_width (5.0)
		context.stroke ()
		context.set_line_width (orig_line_width)
	else:
		context.stroke ()
		
	if dashborder:
		context.set_dash([], 0.0)	
		
# Export outline stuff
def export_thought_outline (context, ul, lr, background_color, am_root = False, am_primary = False, style=STYLE_NORMAL, move=(0,0)):
	real_ul = (ul[0]+move[0], ul[1]+move[1])
	real_lr = (lr[0]+move[0], lr[1]+move[1])
	draw_thought_extended (context, real_ul, real_lr, False, am_primary, background_color, style == STYLE_EXTENDED_CONTENT)

def pixbuf_to_cairo (pixel_array):
	imgW, imgH = len(pixel_array[0]), len(pixel_array)
	data = array('B', [0] * imgW * imgH * 4)
	for y in range(imgH):
		for x in range(imgW):
			# cairo.FORMAT_ARGB32 uses pre-multiplied alpha
			try:
				alpha = pixel_array[y][x][3]
			except:
				alpha = 255
			alpha_mul = float(alpha) / 255

			offset = (x + (y * imgW)) * 4
			data[offset] = int(int(pixel_array[y][x][2]) * alpha_mul) # B
			data[offset+1] = int(int(pixel_array[y][x][1]) * alpha_mul) # G
			data[offset+2] = int(int(pixel_array[y][x][0]) * alpha_mul) # R
			data[offset+3] = alpha # A

	return data
