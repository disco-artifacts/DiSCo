import click

from disco.transaction_analyzer.transaction_analyzer import transaction_analyzer

@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.option('-a', '--transaction_hash', required=True, type=str, help='The hash of the transaction.')
@click.option('-w', '--working_dir', default="./")
def transaction_analysis(transaction_hash, working_dir):
    transaction_analyzer(transaction_hash, working_dir)