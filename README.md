# pigsqueeze
[![CircleCI](https://circleci.com/gh/timwedde/pigsqueeze.svg?style=svg)](https://circleci.com/gh/timwedde/pigsqueeze)
[![Downloads](https://pepy.tech/badge/pigsqueeze)](https://pepy.tech/project/pigsqueeze)

A library to write and read arbitrary data to and from image files. You probably already know why you need it.

pigsuqeeze is a command line tool as well as a Python library for easily writing arbitrary to (and later retrieving it from) image files. Currently only JPEG is supported, but I'm open to add support for more file formats, if they support this. It stores binary data in one or more chunks of app-specific data segments as enabled by the JPEG specification. pigsqueeze automatically handles splitting large blobs of data across multiple chunks, since the limit per chunk is ~65KB. pigsqueeze's method allows for payload sizes of up ot ~15MB per segment. Multiple unused segments are available, so there is a theoretical limit of 135MB per image, which is probably plenty. If you need more, you should probably look at a different solution to your problem.

## Installation
pigsuqeeze can be installed via pip:
```bash
$ pip install pigsqueeze
```

## Usage
```bash
Usage: psz write [OPTIONS] INPUT_IMAGE DATA OUTPUT_FILE

Options:
  -s, --segment INTEGER  [required]
  -i, --identifier TEXT  [required]
  --help                 Show this message and exit.
```

```bash
Usage: psz read [OPTIONS] INPUT_IMAGE OUTPUT_FILE

Options:
  -s, --segment INTEGER  [required]
  -i, --identifier TEXT  [required]
  --help                 Show this message and exit.
```

As a Python library:
```python
from pigsqueeze import Image

# Write some text to App segment 4 with identifier PSZ
image = Image("path/to/image.jpg")
image.write(4, "PSZ", b"Some bytes to save in the file.")
image.save("path/to/output.jpg")

# Retrieve the text from the modified image file
image = Image("path/to/output.jpg")
result = image.read(4, "PSZ")
```
