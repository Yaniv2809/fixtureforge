"""CLI interface for FixtureForge"""
import click
import sys
import importlib.util
from pathlib import Path
from rich.console import Console
from rich.table import Table
from fixtureforge import Forge
from fixtureforge.core.exporter import DataExporter

console = Console()

@click.group()
def cli():
    """FixtureForge - AI-powered test data generation"""
    pass

@cli.command()
@click.argument('model_path')
@click.option('--count', '-n', default=1, help='Number of instances')
@click.option('--no-ai', is_flag=True, default=False, help='Disable AI features')
@click.option('--output', '-o', help='Output file (e.g., data.json)')
@click.option('--context', '-c', help='Context for AI generation (Director Mode)')
def generate(model_path, count, no_ai, output, context):
    """
    Generate test data.
    """
    try:
        console.print(f"[bold blue]🔮 Loading model: {model_path}[/bold blue]")
        model_class = load_model_from_string(model_path)
        
        forge = Forge(use_ai=not no_ai)
        
        if context:
             console.print(f"[bold yellow]🎬 Director Mode: {context}[/bold yellow]")

        console.print(f"[bold blue]📦 Generating {count} instances...[/bold blue]")
        
        instances = forge.create_batch(model_class, count=count, context=context)
        
        display_table(instances)

        if output:
            console.print(f"[yellow]💾 Saving to {output}...[/yellow]")
            DataExporter.export(instances, output)
        
    except Exception as e:
        console.print(f"[bold red]❌ Error:[/bold red] {e}")
        sys.exit(1)

def load_model_from_string(model_path: str):
    try:
        module_name, class_name = model_path.split(":")
    except ValueError:
        raise ValueError("Model path must be in format 'filename:ClassName'")
    
    sys.path.append(str(Path.cwd()))
    
    try:
        module = importlib.import_module(module_name)
    except ImportError:
        spec = importlib.util.spec_from_file_location(module_name, f"{module_name}.py")
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        else:
            raise ImportError(f"Could not find module '{module_name}'")

    if not hasattr(module, class_name):
        raise AttributeError(f"Class '{class_name}' not found in {module_name}")
        
    return getattr(module, class_name)

def display_table(instances):
    if not instances:
        return
        
    first_item = instances[0]
    headers = first_item.model_dump().keys()
    
    table = Table(show_header=True, header_style="bold magenta")

    for h in headers:
        table.add_column(h)
        
    for item in instances:
        row = [str(getattr(item, h)) for h in headers]
        table.add_row(*row)
        
    console.print(table)