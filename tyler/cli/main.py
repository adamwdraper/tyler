"""Main CLI for Tyler"""
import click
from tyler.database.cli import cli as db_cli

@click.group()
def cli():
    """Tyler CLI - Main command-line interface for Tyler."""
    pass

# Add database commands as a subcommand group
cli.add_command(db_cli, name="db")

# Import other CLI modules and add their commands
try:
    from tyler.cli.chat import cli as chat_cli
    cli.add_command(chat_cli, name="chat")
except ImportError:
    # Chat CLI might not be available, continue without it
    pass

def main():
    """Entry point for the CLI"""
    cli()

if __name__ == "__main__":
    main() 