import click

from disco.app.graph_construction import construct_graph

@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.option('-a', '--address', required=True, type=str,
              help='The address of the contract.')
@click.option('-w', '--working_dir', default="./")
def build_graph(address, working_dir):
    construct_graph(address, working_dir)