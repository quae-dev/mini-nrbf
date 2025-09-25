# Copyright (c) 2019-2021 nago
# Copyright (c) 2025 Quae
# SPDX-License-Identifier: BSD-3-Clause

"""
mini_nbrf: A bare-bones MS-NRBF parser.

A feature-less parser and serialiser based on MS-NRBF, the .NET Remoting
Binary Format: <https://msdn.microsoft.com/en-us/library/cc236844.aspx>
"""

from __future__ import annotations

import collections.abc as cabc
import dataclasses
import enum
import io
import pathlib
import struct
import typing as t

if t.TYPE_CHECKING:
    import os

__all__ = [
    "BinaryObjectString",
    "DNBinary",
    "MessageEnd",
    "PrimitiveStream",
    "PrimitiveWriter",
    "RecordItem",
    "RecordStream",
    "RecordTypeEnum",
    "RecordWriter",
    "SerializedStreamHeader",
    "StreamReader",
    "StreamWriter",
    "parse_bytes",
    "parse_file",
    "parse_stream",
    "serialize_records",
    "serialize_to_file",
]


@dataclasses.dataclass(slots=True)
class SerializedStreamHeader:
    """Represents a serialized stream header record."""

    root_id: int
    header_id: int
    major_version: int
    minor_version: int


@dataclasses.dataclass(slots=True)
class BinaryObjectString:
    """Represents a binary object string record."""

    object_id: int
    value: str


@dataclasses.dataclass(slots=True)
class MessageEnd:
    """Represents a message end record."""


RecordItem: t.TypeAlias = (
    SerializedStreamHeader | BinaryObjectString | MessageEnd
)


class StreamReader(t.Protocol):
    def read(self, size: int | None = -1, /) -> bytes: ...


class StreamWriter(t.Protocol):
    def write(self, data: bytes | bytearray, /) -> int: ...


class PrimitiveStream:
    def __init__(self, stream: StreamReader) -> None:
        self.stream: StreamReader = stream

    def read(self, size: int) -> bytes:
        """Read `size` bytes from the stream."""
        rdbytes = self.stream.read(size)

        if len(rdbytes) != size:
            raise EOFError

        return rdbytes

    # 2.1.1 Common Data Types
    def byte(self) -> int:
        """Read an unsigned 8-bit integer."""
        return struct.unpack("<B", self.read(1))[0]

    def int32(self) -> int:
        """Read a signed 32-bit integer."""
        return struct.unpack("<i", self.read(4))[0]

    # 2.1.1.6 Length Prefixed String
    def string(self) -> str:
        """Read a length-prefixed string."""
        length = 0
        shift = 0

        for i in range(5):
            byte = self.byte()
            length += (byte & ~0x80) << shift
            shift += 7

            if not byte & 0x80:
                break

            if i == 4:
                msg = f"Variable Length ({length}) exceeds maximum size"
                raise RuntimeError(msg)

        raw = self.read(length)
        return raw.decode("u8")


class PrimitiveWriter:
    """Stream writer for primitive NRBF data types."""

    def __init__(self, stream: StreamWriter) -> None:
        self.stream: StreamWriter = stream

    def byte(self, value: int) -> None:
        """Write an unsigned 8-bit integer."""
        if not 0 <= value <= 0xFF:
            msg = f"Byte value {value} out of range"
            raise ValueError(msg)

        _ = self.stream.write(struct.pack("<B", value))

    def int32(self, value: int) -> None:
        """Write a signed 32-bit integer."""
        _ = self.stream.write(struct.pack("<i", value))

    def string(self, value: str) -> None:
        """Write a length-prefixed string."""
        encoded = value.encode("u8")
        length = len(encoded)

        while length >= 0x80:
            self.byte((length & 0x7F) | 0x80)
            length >>= 7

        self.byte(length & 0x7F)

        _ = self.stream.write(encoded)


@enum.unique
class RecordTypeEnum(enum.IntEnum):
    SerializedStreamHeader = 0
    BinaryObjectString = 6
    MessageEnd = 11

    @classmethod
    def from_record(cls, record: RecordItem) -> RecordTypeEnum:
        """Get the record type enum from a record instance."""
        match record:
            case SerializedStreamHeader():
                return cls.SerializedStreamHeader
            case BinaryObjectString():
                return cls.BinaryObjectString
            case MessageEnd():
                return cls.MessageEnd

    def parse(self, stream: RecordStream) -> RecordItem:
        match self:
            case self.SerializedStreamHeader:
                return SerializedStreamHeader(
                    root_id=stream.int32(),
                    header_id=stream.int32(),
                    major_version=stream.int32(),
                    minor_version=stream.int32(),
                )
            case self.BinaryObjectString:
                object_id = stream.int32()
                record = BinaryObjectString(
                    object_id=object_id, value=stream.string()
                )
                stream.set_object(object_id, record)
                return record
            case self.MessageEnd:
                return MessageEnd()

    def serialize(self, record: RecordItem, writer: RecordWriter) -> None:
        """Serialize a record to the writer stream."""
        writer.writer.byte(self.value)

        match self:
            case self.SerializedStreamHeader:
                if not isinstance(record, SerializedStreamHeader):
                    msg = (
                        f"Expected SerializedStreamHeader, got {type(record)}"
                    )
                    raise TypeError(msg)
                writer.writer.int32(record.root_id)
                writer.writer.int32(record.header_id)
                writer.writer.int32(record.major_version)
                writer.writer.int32(record.minor_version)

            case self.BinaryObjectString:
                if not isinstance(record, BinaryObjectString):
                    msg = f"Expected BinaryObjectString, got {type(record)}"
                    raise TypeError(msg)
                writer.writer.int32(record.object_id)
                writer.writer.string(record.value)
                writer.set_object(record.object_id, record)

            case self.MessageEnd:
                # MessageEnd has no additional data.
                if not isinstance(record, MessageEnd):
                    msg = f"Expected MessageEnd, got {type(record)}"
                    raise TypeError(msg)


class RecordStream(PrimitiveStream):
    def __init__(self, stream: StreamReader) -> None:
        super().__init__(stream)
        self._objects: dict[int, RecordItem] = {}

    def record(self) -> RecordItem:
        """Read an entire record from the stream."""
        record_type = RecordTypeEnum(self.byte())
        return record_type.parse(self)

    def set_object(self, ref: int, obj: RecordItem) -> None:
        """
        Register an object.

        Given an object reference, an object, and optionally its values,
        register this object so that it can be retrieved by later
        references to it.
        """
        self._objects[ref] = obj

    @property
    def object_definitions(self) -> int:
        return len(self._objects)


@t.final
class RecordWriter:
    """Stream writer for NRBF records."""

    def __init__(self, stream: StreamWriter) -> None:
        super().__init__()
        self.writer = PrimitiveWriter(stream)
        self._objects: dict[int, RecordItem] = {}

    def record(self, record: RecordItem) -> None:
        """Write an entire record to the stream."""
        record_type = RecordTypeEnum.from_record(record)
        record_type.serialize(record, self)

    def set_object(self, ref: int, obj: RecordItem) -> None:
        """Register an object for reference tracking."""
        self._objects[ref] = obj

    @property
    def object_definitions(self) -> int:
        return len(self._objects)


@t.final
class DNBinary:
    def __init__(self, stream: StreamReader) -> None:
        self.stream = RecordStream(stream)
        self._records: list[RecordItem] = []

    def parse(self) -> list[RecordItem]:
        while True:
            record = self.stream.record()
            self._records.append(record)

            if isinstance(record, MessageEnd):
                break

        return self._records

    @property
    def object_definitions(self) -> int:
        return self.stream.object_definitions


def parse_stream(stream: StreamReader) -> list[RecordItem]:
    """Parse a given binary MS-NRBF stream into a list of record objects."""
    return DNBinary(stream).parse()


def parse_bytes(data: bytes | bytearray | memoryview) -> list[RecordItem]:
    """Parse a given buffer into a list of record objects."""
    stream = io.BytesIO(data)
    return parse_stream(stream)


def parse_file(path: os.PathLike[str] | str) -> list[RecordItem]:
    """Parse a given file path into a list of record objects."""
    data = pathlib.Path(path).read_bytes()
    return parse_bytes(data)


def serialize_records(records: cabc.Iterable[RecordItem]) -> bytes:
    """Serialize a sequence of `RecordItem` objects into NRBF-formatted data."""
    buffer = io.BytesIO()
    writer = RecordWriter(buffer)

    for record in records:
        writer.record(record)

    return buffer.getvalue()


def serialize_to_file(
    records: cabc.Iterable[RecordItem], path: os.PathLike[str] | str
) -> int:
    """Serialize a sequence of `RecordItem` objects and write to a file."""
    data = serialize_records(records)
    return pathlib.Path(path).write_bytes(data)
