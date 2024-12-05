import click

from disco.cli.static_analysis import static_analysis
from disco.cli.transaction_analysis import transaction_analysis

# graph construction
from disco.cli.build_graph import build_graph

from disco.cli.description_generation import description_generation

@click.group()
@click.version_option(version='0.0.1')
@click.pass_context
def cli(ctx):
    pass

cli.add_command(static_analysis, "static_analysis")
cli.add_command(transaction_analysis, "transaction_analysis")

cli.add_command(build_graph, "build_graph")

cli.add_command(description_generation, "description_generation")