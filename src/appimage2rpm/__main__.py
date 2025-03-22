#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Main entry point for the appimage2rpm application.
Provides both CLI and GUI interfaces.
"""

import sys
import logging
from typing import List, Optional

from appimage2rpm.gui.main_window import MainWindow
from appimage2rpm.core.controller import AppImage2RPMController
import click


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("appimage2rpm")


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
    # Initialize the controller
    controller = AppImage2RPMController()
    
    # Prepare metadata
    metadata = {}
    if name:
        metadata["name"] = name
    if version:
        metadata["version"] = version
    metadata["release"] = release
    
    # Start the conversion
    result = controller.convert_appimage(
        appimage_path=appimage_path,
        output_dir=output_dir,
        metadata=metadata,
        distro_profile=distro,
        auto_deps=auto_deps
    )
    
    if result["success"]:
        logger.info(f"Conversion successful: {result['rpm_path']}")
        click.echo(f"RPM package created: {result['rpm_path']}")
        return 0
    else:
        logger.error(f"Conversion failed: {result['message']}")
        click.echo(f"Error: {result['message']}", err=True)
        return 1


def start_gui() -> None:
    """Start the GUI application."""
    app = None
    
    # Check if QApplication instance already exists
    if not QApplication.instance():
        from PySide6.QtWidgets import QApplication
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
    
    # Create and show the main window
    window = MainWindow()
    window.show()
    
    # Start the application event loop
    sys.exit(app.exec())


def main(args: Optional[List[str]] = None) -> None:
    """Main entry point for the application."""
    if args is None:
        args = sys.argv[1:]
    
    if args:
        # If arguments are provided, use CLI mode
        cli()
    else:
        # Otherwise, start the GUI
        start_gui()


if __name__ == "__main__":
    main() 