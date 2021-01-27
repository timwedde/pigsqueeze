## System ###
import os
import math
import zlib
from abc import abstractmethod
from collections import defaultdict

### Binary Wrangling ###
from plum.int.big import UInt8, UInt16, UInt32


def load_image(file):
    if hasattr(file, "read"):
        header_bytes = file.read(16)
        file.seek(0)
    elif isinstance(file, bytes):
        header_bytes = file[:16]
    elif os.path.isfile(file):
        with open(file, "rb") as f:
            header_bytes = f.read(16)
    else:
        raise ValueError("expected file object, file path as str, or bytes")

    for handler in Image.__subclasses__():
        if handler.tell(file, header_bytes):
            return handler(file)

    raise Exception("No handler for image!")


class Image:
    def __init__(self, file):
        if hasattr(file, "read"):
            self.image_bytes = file.read()
        elif isinstance(file, bytes):
            self.image_bytes = file
        elif os.path.isfile(file):
            with open(file, "rb") as file_descriptor:
                self.image_bytes = file_descriptor.read()
        else:
            raise ValueError("expected file object, file path as str, or bytes")

        self.parse()

    @classmethod
    def tell(cls, file, header_bytes):
        return header_bytes.startswith(cls.HEADER)

    @abstractmethod
    def parse(self):
        pass


class PNGImage(Image):

    HEADER = b"\x89PNG\r\n\x1a\n"
    PNG_CHUNKS = (
        b"IHDR",
        b"PLTE",
        b"IDAT",
        b"IEND",
        b"tRNS",
        b"cHRM",
        b"gAMA",
        b"iCCP",
        b"sBIT",
        b"sRGB",
        b"iTXt",
        b"tEXt",
        b"zTXt",
        b"bKGD",
        b"hIST",
        b"pHYs",
        b"sPLT",
        b"tIME",
    )

    def parse(self):
        # Skip the PNG header
        cursor = len(self.HEADER)

        self.chunks = []
        self.custom_chunks = {}

        while cursor < len(self.image_bytes):
            chunk_length = UInt32.unpack(self.image_bytes[cursor : cursor + 4])
            cursor += 4
            chunk_type = self.image_bytes[cursor : cursor + 4]
            cursor += 4
            chunk_data = self.image_bytes[cursor : cursor + chunk_length]
            cursor += chunk_length
            chunk_crc = UInt32.unpack(self.image_bytes[cursor : cursor + 4])
            cursor += 4
            if chunk_type in self.PNG_CHUNKS:
                self.chunks.append((chunk_length, chunk_type, chunk_data, chunk_crc))
            else:
                self.custom_chunks[chunk_type] = (
                    chunk_length,
                    chunk_type,
                    chunk_data,
                    chunk_crc,
                )

    def read(self, chunk_type, identifier):
        if chunk_type in self.PNG_CHUNKS:
            raise Exception("Chunk name is a reserved PNG name!")

        if len(chunk_type) != 4:
            raise Exception(
                "Chunk types must be a 4-letter word using only letters from A-z!"
            )

        if chunk_type[0].isupper():
            raise Exception("Chunk types must start with a lowercase letter!")

        identifier = f"{identifier}\x00".encode()
        chunk_type = chunk_type.encode()

        if chunk_type not in self.custom_chunks:
            raise Exception(f"Chunk name {chunk_type} not found!")

        chunk_length, chunk_type, chunk_data, chunk_crc = self.custom_chunks[chunk_type]

        if identifier == b"\x00" or not chunk_data.startswith(identifier):
            raise Exception("The identifier of this chunk differs!")

        return chunk_data[len(identifier) :]

    def write(self, chunk_type, identifier, data):
        if chunk_type in self.PNG_CHUNKS:
            raise Exception("Chunk type is a reserved PNG name!")

        if len(chunk_type) != 4:
            raise Exception(
                "Chunk types must be a 4-letter word using only letters from A-z!"
            )

        if chunk_type[0].isupper():
            raise Exception("Chunk types must start with a lowercase letter!")

        identifier = f"{identifier}\x00".encode()
        chunk_type = chunk_type.encode()

        chunk_data = identifier + data
        chunk_crc = zlib.crc32(chunk_type + chunk_data)

        self.custom_chunks[chunk_type] = (
            len(chunk_data),
            chunk_type,
            chunk_data,
            chunk_crc,
        )

    def save(self, file):
        new_bytes = self.HEADER

        for chunk_length, chunk_type, chunk_data, chunk_crc in self.chunks[:1]:
            new_bytes += UInt32.pack(chunk_length)
            new_bytes += chunk_type
            new_bytes += chunk_data
            new_bytes += UInt32.pack(chunk_crc)

        for _, (chunk_length, chunk_type, chunk_data, chunk_crc) in sorted(
            self.custom_chunks.items()
        ):
            new_bytes += UInt32.pack(chunk_length)
            new_bytes += chunk_type
            new_bytes += chunk_data
            new_bytes += UInt32.pack(chunk_crc)

        for chunk_length, chunk_type, chunk_data, chunk_crc in self.chunks[1:]:
            new_bytes += UInt32.pack(chunk_length)
            new_bytes += chunk_type
            new_bytes += chunk_data
            new_bytes += UInt32.pack(chunk_crc)

        if hasattr(file, "write"):
            file.write(new_bytes)
        else:
            with open(file, "wb") as f:
                f.write(new_bytes)


class JPEGImage(Image):

    HEADER = b"\xff\xd8"
    SEG_PREFIX = b"\xff"
    # According to http://www.ozhiker.com/electronics/pjmt/jpeg_info/app_segments.html
    FREE_SEGMENTS = [4, 5, 6, 7, 8, 9, 10, 11, 15]

    def parse(self):
        self.segments = defaultdict(list)

        app_markers = tuple(
            chr(255).encode("latin-1") + chr(224 + i).encode("latin-1")
            for i in range(16)
        )

        cursor = 0
        app_segments = defaultdict(list)
        for cursor in range(0, len(self.image_bytes), 2):
            if self.image_bytes[cursor : cursor + 2] in app_markers:
                app_segments[self.image_bytes[cursor + 1]].append(cursor)

        self.app_seg_start = min(app_segments[min(app_segments)])

        for segment, starts in app_segments.items():
            for start in starts:
                cursor = start
                # the next two bytes are the length of the data
                seg_len = UInt16.unpack(self.image_bytes[start + 2 : start + 4])
                cursor += seg_len + 1

                # If the expected length stops early, keep traversing until another section is found.
                while self.image_bytes[cursor : cursor + 1] != self.SEG_PREFIX:
                    cursor += 1
                    if cursor > len(self.image_bytes):
                        break

                self.segments[segment].append(
                    (None, self.image_bytes[start + 2 : cursor])
                )

        self.app_seg_end = cursor

    def read(self, segment, identifier, multi_chunk=True):
        segment = 224 + segment
        identifier = f"{identifier}\x00".encode()

        if segment not in self.segments:
            return

        if not multi_chunk:
            current_chunk, chunk = self.segments[segment][0]
            if not chunk[2:].startswith(identifier):
                raise Exception("Could not find identifier")
            return chunk[2 + len(identifier) :]

        new_segments = []
        for current_chunk, chunk in self.segments[segment]:
            if not chunk[2:].startswith(identifier):
                raise Exception("Could not find identifier")

            total_chunks, current_chunk = chunk[
                2 + len(identifier) : 2 + len(identifier) + 2
            ]
            new_segments.append((current_chunk, chunk))

        self.segments[segment] = new_segments

        assembled_chunks = b""
        for current_chunk, chunk in sorted(self.segments[segment], key=lambda x: x[0]):
            assembled_chunks += chunk[2 + len(identifier) + 2 :]

        return assembled_chunks

    def write(self, segment, identifier, data, multi_chunk=True):
        if segment < 0 or segment > 15:
            raise Exception("Segment number must be between 0 and 15!")

        if segment not in self.FREE_SEGMENTS:
            raise Exception(
                f"Segment number {segment} is not registered as a free segment, you may overwrite important application data!"
            )

        segment = 224 + segment
        identifier = f"{identifier}\x00".encode()
        chunk_size = (63535 - (len(identifier) + 2)) - 1
        max_size = 256 * chunk_size
        total_chunks = math.ceil(len(data) / chunk_size)

        if len(data) > max_size:
            raise Exception("The provided data is too big!")

        self.segments[segment] = []
        for current_chunk in range(total_chunks):
            chunk_data = data[
                current_chunk * chunk_size : (current_chunk + 1) * chunk_size
            ]
            segment_data = UInt16.pack(
                len(chunk_data) + len(identifier) + 2 + (2 if multi_chunk else 0)
            )
            segment_data += identifier
            if multi_chunk:
                segment_data += UInt8.pack(total_chunks)
                segment_data += UInt8.pack(current_chunk)
            segment_data += chunk_data
            self.segments[segment].append(
                (current_chunk if multi_chunk else None, segment_data)
            )

    def save(self, file):
        assembled_segments = b""
        for segment, chunks in sorted(self.segments.items()):
            for current_chunk, chunk in sorted(chunks, key=lambda x: x[0]):
                chunk = self.SEG_PREFIX + chr(segment).encode("latin-1") + chunk
                assembled_segments += chunk

        new_bytes = self.image_bytes[: self.app_seg_start]
        new_bytes += assembled_segments
        new_bytes += self.image_bytes[self.app_seg_end :]

        if hasattr(file, "write"):
            file.write(new_bytes)
        else:
            with open(file, "wb") as f:
                f.write(new_bytes)
