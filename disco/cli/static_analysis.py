import click

from disco.static_analyzer.static_analyzer import static_analyzer

@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.option('-a', '--address', required=True, type=str,
              help='The address of the contract.')
@click.option('-w', '--working_dir', default="./")
def static_analysis(address, working_dir):
    static_analyzer(address, working_dir)