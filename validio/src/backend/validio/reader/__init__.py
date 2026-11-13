"""The reader of supplier text. Its output is display only."""

from validio.reader.fake import FakeReader
from validio.reader.schema import Flag, ReaderResult
from validio.reader.service import Reading, read, reader_from_env

__all__ = ["FakeReader", "Flag", "ReaderResult", "Reading", "read", "reader_from_env"]
