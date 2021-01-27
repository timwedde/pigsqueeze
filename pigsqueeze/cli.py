### CLI Parsing ###
import click

### Local ###
from .pigsqueeze import load_image


@click.group()
def cli():
    pass


@cli.command()
@click.argument("input_image", type=click.File("rb"))
@click.argument("data", type=click.File("rb"))
@click.argument("output_file", type=click.File("wb"))
@click.option("-s", "--segment", type=int, required=True)
@click.option("-i", "--identifier", type=str, required=True)
def write_jpg(input_image, data, output_file, segment, identifier):
    image = load_image(input_image)
    bytes_to_write = data.read()
    image.write(segment, identifier, bytes_to_write)
    image.save(output_file)


@cli.command()
@click.argument("input_image", type=click.File("rb"))
@click.argument("data", type=click.File("rb"))
@click.argument("output_file", type=click.File("wb"))
@click.option("-c", "--chunk", type=str, required=True)
@click.option("-i", "--identifier", type=str, required=True)
def write_png(input_image, data, output_file, chunk, identifier):
    image = load_image(input_image)
    bytes_to_write = data.read()
    image.write(chunk, identifier, bytes_to_write)
    image.save(output_file)


@cli.command()
@click.argument("input_image", type=click.File("rb"))
@click.argument("output_file", type=click.File("wb"))
@click.option("-s", "--segment", type=int, required=True)
@click.option("-i", "--identifier", type=str, required=True)
def read_jpg(input_image, output_file, segment, identifier):
    image = load_image(input_image)
    result = image.read(segment, identifier)
    if result:
        output_file.write(result)


@cli.command()
@click.argument("input_image", type=click.File("rb"))
@click.argument("output_file", type=click.File("wb"))
@click.option("-c", "--chunk", type=str, required=True)
@click.option("-i", "--identifier", type=str, required=True)
def read_png(input_image, output_file, chunk, identifier):
    image = load_image(input_image)
    result = image.read(chunk, identifier)
    if result:
        output_file.write(result)
