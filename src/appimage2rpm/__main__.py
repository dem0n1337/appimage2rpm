#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Main entry point for the AppImage2RPM application.
Provides both CLI and GUI interfaces.
"""

import os
import sys
import logging
from typing import List, Optional, Dict, Any

from appimage2rpm.gui.main_window import MainWindow
from appimage2rpm.core.controller import AppImage2RPMController
import click
from appimage2rpm.utils.logger import configure_logging


# Configure logging
configure_logging()
logger = logging.getLogger(__name__)


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """AppImage2RPM - Convert AppImage packages to RPM format."""
    if ctx.invoked_subcommand is None:
        # If no subcommand is provided, launch the GUI
        start_gui()


@cli.command()
@click.argument("appimage_path", type=click.Path(exists=True, readable=True))
@click.option("--output-dir", "-o", type=click.Path(file_okay=False), 
              help="Directory where the RPM package will be saved")
@click.option("--name", help="Set package name")
@click.option("--version", help="Set package version")
@click.option("--release", default="1", help="Set package release")
@click.option("--auto-deps/--no-auto-deps", default=True, 
              help="Automatically detect dependencies")
@click.option("--distro", help="Target distribution profile")
def convert(appimage_path: str, output_dir: Optional[str] = None, 
            name: Optional[str] = None, version: Optional[str] = None, 
            release: str = "1", auto_deps: bool = True, 
            distro: Optional[str] = None) -> None:
    """
    Convert an AppImage file to RPM package.
    
    APPIMAGE_PATH: Path to the AppImage file to convert.
    """
    logger.info(f"Converting {appimage_path}")
    
    # Create controller
    controller = AppImage2RPMController()
    
    # Prepare metadata
    metadata: Dict[str, Any] = {}
    if name:
        metadata["name"] = name
    if version:
        metadata["version"] = version
    metadata["release"] = release
    
    # Progress callback for CLI
    def progress_callback(percent: int, message: str) -> None:
        """Display progress in CLI."""
        click.echo(f"{percent}% - {message}")
    
    # Run conversion
    try:
        result = controller.convert_appimage(
            appimage_path=appimage_path,
            output_dir=output_dir,
            metadata=metadata,
            distro_profile=distro,
            auto_deps=auto_deps,
            progress_callback=progress_callback
        )
        
        if result and result.get("success", False):
            click.echo(f"Conversion successful. RPM package created: {result['rpm_path']}")
            return 0
        else:
            click.echo(f"Error: {result['message']}", err=True)
            return 1
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        return 1


def start_gui() -> None:
    """Start the GUI application."""
    # Import PySide6 modules for GUI
    from PySide6.QtWidgets import QApplication
    
    app = None
    
    # Check if QApplication instance already exists
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
    
    # Create and show the main window
    window = MainWindow()
    window.show()
    
    # Start the application event loop
    sys.exit(app.exec())


def main() -> int:
    """Main entry point for the application."""
    args = sys.argv[1:]
    
    if args:
        # If arguments are provided, use CLI mode
        return cli()
    else:
        # Otherwise, start the GUI
        try:
            start_gui()
            return 0
        except ImportError as e:
            click.echo(f"Error starting GUI: {str(e)}", err=True)
            click.echo("Make sure PySide6 is installed. You can use CLI mode with --help for options.")
            return 1


if __name__ == "__main__":
    sys.exit(main()) 