import click

from disco.app.description_generator import generate_descriptions

@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.option('-a', '--address', required=True, type=str,
              help='The address of the contract.')
@click.option('-w', '--working_dir', default="./")
def description_generation(address, working_dir):
    generate_descriptions(address, working_dir)