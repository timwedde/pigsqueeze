## System ###
import os
import math
from collections import defaultdict

### Binary Wrangling ###
from plum.int.big import UInt8, UInt16

### CLI Parsing ###
import click


class Image:

    SEG_PREFIX = b"\xff"

    # According to http://www.ozhiker.com/electronics/pjmt/jpeg_info/app_segments.html
    FREE_SEGMENTS = [4, 5, 6, 7, 8, 9, 10, 11, 15]

    def __init__(self, image_file):
        self.segments = defaultdict(list)

        if hasattr(image_file, "read"):
            self.image_bytes = image_file.read()
        elif isinstance(image_file, bytes):
            self.image_bytes = image_file
        elif os.path.isfile(image_file):
            with open(image_file, "rb") as file_descriptor:
                self.image_bytes = file_descriptor.read()
        else:
            raise ValueError("expected file object, file path as str, or bytes")

        self.parse_segments()

    def parse_segments(self):
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


@click.group()
def cli():
    pass


@cli.command()
@click.argument("input_image", type=click.File("rb"))
@click.argument("data", type=click.File("rb"))
@click.argument("output_file", type=click.File("wb"))
@click.option("-s", "--segment", type=int, required=True)
@click.option("-i", "--identifier", type=str, required=True)
def write(input_image, data, output_file, segment, identifier):
    image = Image(input_image)
    bytes_to_write = data.read()
    image.write(segment, identifier, bytes_to_write)
    image.save(output_file)


@cli.command()
@click.argument("input_image", type=click.File("rb"))
@click.argument("output_file", type=click.File("wb"))
@click.option("-s", "--segment", type=int, required=True)
@click.option("-i", "--identifier", type=str, required=True)
def read(input_image, output_file, segment, identifier):
    image = Image(input_image)
    result = image.read(segment, identifier)
    if result:
        output_file.write(result)
