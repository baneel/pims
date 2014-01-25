import os
import numpy as np
import collections

from abc import ABCMeta, abstractmethod, abstractproperty


class FramesStream:
    """
    A base class for wrapping input data which knows how to
    advance to the next frame, but does not have random access.

    The length does not need to be finite.

    Does not support slicing.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def __iter__(self):
        pass

    @abstractproperty
    def pixel_type(self):
        """Returns a numpy.dtype for the data type of the pixel values"""
        pass

    @abstractproperty
    def frame_shape(self):
        """Returns the shape of a single frame as a tuple ex (10, 12)"""
        pass


class FramesSequence(FramesStream):
    """Baseclass for wrapping data buckets that have random access.

    Support random access.

    Supports standard slicing and fancy slicing, but returns a
    generator.

    Must be finite length.

    """
    def __getitem__(self, key):
        """for data access"""
        if isinstance(key, slice):
            # if input is a slice, return a generator
            return (self.get_frame(_k) for _k
                    in xrange(*key.indices(len(self))))
        elif isinstance(key, collections.Iterable):
            # if the input is an iterable, doing 'fancy' indexing

            if isinstance(key, np.ndarray) and key.dtype == np.bool:
                # if we have a bool array, do the right thing
                return (self.get_frame(_k) for _k in np.arange(len(self))[key])
            # else, return a generator looping over the keys
            return (self.get_frame(_k) for _k in key)
        else:
            # else, fall back to `get_frame`
            return self.get_frame(key)

    def __iter__(self):
        return self[:]

    @abstractmethod
    def __len__(self):
        """
        It is obligatory that sub-classes define a length.
        """
        pass

    @abstractmethod
    def get_frame(self, ind):
        """
        Sub classes must over-ride this function for how to get a given
        frame out of the file.  Any data-type specific internal-state
        nonsense should be dealt with in this function.
        """
        pass


class BaseFrames(FramesSequence):
    "Base class for iterable objects that return images as numpy arrays."

    def __init__(self, filename, gray=True, invert=True):
        self.filename = filename
        self.gray = gray
        self.invert = invert
        self.capture = self._open(self.filename)
        self.cursor = 0
        self.endpoint = None
        # Subclass will specify self.count and self.shape.

    def __repr__(self):
        return """<Frames>
Source File: %s
Frame Dimensions: %d x %d
Cursor at Frame %d of %d""" % (self.filename, self.shape[0], self.shape[1],
                               self.cursor, self.count)

    def __iter__(self):
        return self

    @property
    def endpoint(self):
        return self._endpoint

    @endpoint.setter
    def endpoint(self, val):
        self._endpoint = val

    def seek_forward(self, val):
        for _ in range(val):
            self.next()

    def rewind(self):
        """Reopen the video file to start at the beginning. ('Seeking'
        capabilities in the underlying OpenCV library are not reliable.)"""
        self.capture = self._open(self.filename)
        self.cursor = 0

    def next(self):
        if self.endpoint is not None and self.cursor > self.endpoint:
            raise StopIteration
        return_code, frame = self.capture.read()
        if not return_code:
            # A failsafe: the frame count is not always accurate.
            raise StopIteration
        frame = self._process(frame)
        self.cursor += 1
        return frame

    def _process(self, frame):
        """Subclasses can override this with faster ways, but this
        pure numpy implementation is general."""
        if self.gray:
            if len(frame.shape) == 2:
                pass  # already gray
            elif len(frame.shape) == 3:
                frame = np.mean(frame, axis=2).astype(frame.dtype)
            else:
                raise ValueError("Frames are not 2- or 3-dimensional " +
                                 "arrays. What now?")
        if self.invert:
            frame ^= np.iinfo(frame.dtype).max
        return frame

    def get_frame(self, val):
        if val > self.cursor:
            self.seek_forward(val - self.cursor)
            return self.next()
        elif self.cursor == val:
            return self.next()
        else:
            self.rewind()
            return self.get_frame(val)

    @property
    def pixel_type(self):
        pass

    @property
    def frame_shape(self):
        pass
