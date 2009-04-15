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

import os
import time
import tarfile
import cStringIO
import tempfile
import gtk

class TarballError(Exception):
    """Base Tarball exception."""
    pass

class BadDataTypeError(TarballError):
    """Exception for unsupported data type in read/write methods."""
    pass

class Tarball:
    def __init__(self, name=None, mode='r', mtime=None):
        self.__tar = tarfile.TarFile(name=name, mode=mode)

        if mtime:
            self.mtime = mtime
        else:
            self.mtime = time.time()

    def close(self):
        self.__tar.close()

    def getnames(self):
        return self.__tar.getnames()

    def read(self, arcname):
        fo = self.__tar.extractfile(arcname.encode('utf8'))
        if not fo:
            return None
        out = fo.read()
        fo.close()
        return out

    def read_pixbuf(self, arcname):
        data = self.read(arcname)
        fd, path = tempfile.mkstemp()

        f = os.fdopen(fd, 'w')
        f.write(data)
        f.close()

        out = gtk.gdk.pixbuf_new_from_file(path)
        os.unlink(path)

        return out

    def write(self, arcname, data, mode=0644):
        io = tarfile.TarInfo(arcname.encode('utf8'))
        io.mode = mode
        io.mtime = self.mtime

        if isinstance(data, str):
            self.__write_str(io, data)
        elif isinstance(data, gtk.gdk.Pixbuf):
            self.__write_pixbuf(io, data)
        else:
            raise BadDataTypeError()

    def __write_str(self, io, data):
        io.size = len(data)
        self.__tar.addfile(io, cStringIO.StringIO(data))
        
    def __write_pixbuf(self, io, data):
        def push(data, buffer):
            buffer.write(data)

        buffer = cStringIO.StringIO()
        data.save_to_callback(push, 'png', user_data=buffer)

        io.size = buffer.tell()
        buffer.seek(0)
        self.__tar.addfile(io, buffer)
