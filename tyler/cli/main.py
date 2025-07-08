"""Main CLI for Tyler"""
import click

@click.group()
def cli():
    """Tyler CLI - Main command-line interface for Tyler."""
    pass

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