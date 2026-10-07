"""
Domain exceptions of the core. Given.

The core only raises these exceptions: it does not know about HTTP. Whoever
uses it decides how to report them (the API with a status code, the command
line with a message on stderr). Add your own subclasses of ScanError if you
need them.
"""


class ScanError(Exception):
    """Base class of every error of the core."""


class InvalidImage(ScanError):
    """The bytes cannot be opened as an image (empty, corrupt, not an image)."""


class DocumentNotFound(ScanError):
    """The photo is valid, but no document could be recognized in it.

    TODO (team): raise it from the detector, with a message (in Spanish) that
    explains what happened and how to take a better photo.
    """
