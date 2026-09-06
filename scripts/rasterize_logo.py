#!/usr/bin/env python3
"""Render a supplied SVG with Ubuntu's system librsvg, preserving its colours."""
import sys
import cairo
import gi

gi.require_version("Rsvg", "2.0")
from gi.repository import Rsvg

handle = Rsvg.Handle.new_from_file(sys.argv[1])
surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 900, 300)
context = cairo.Context(surface)
viewport = Rsvg.Rectangle()
viewport.x, viewport.y, viewport.width, viewport.height = 0, 0, 900, 300
handle.render_document(context, viewport)
surface.write_to_png(sys.stdout.buffer)
