#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module for packaging directories as RPM packages.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

logger = logging.getLogger(__name__)


class DirectoryPackager:
    """
    Prepares directories for packaging as RPM.
    
    This class is responsible for organizing a directory's contents
    in a way suitable for RPM packaging.
    """
    
    def __init__(self) -> None:
        """Initialize the directory packager."""
        pass
    
    def prepare_directory(
        self, 
        source_dir: Union[str, Path], 
        target_dir: Union[str, Path],
        metadata: Dict[str, Any]
    ) -> Path:
        """
        Prepare a directory for RPM packaging.
        
        Args:
            source_dir: Path to the source directory to package
            target_dir: Path to the target directory where prepared files will be placed
            metadata: Dictionary containing metadata for the package
            
        Returns:
            Path to the prepared directory structure
        """
        source_path = Path(source_dir)
        target_path = Path(target_dir)
        
        if not source_path.exists() or not source_path.is_dir():
            raise ValueError(f"Source directory does not exist: {source_path}")
        
        # Create target directory if it doesn't exist
        target_path.mkdir(parents=True, exist_ok=True)
        
        # Determine install prefix (usually /usr or /opt/appname)
        install_prefix = metadata.get("install_prefix", "/usr")
        if not install_prefix.startswith("/"):
            install_prefix = f"/{install_prefix}"
        
        # Create directory structure
        rpm_build_dir = target_path / "BUILD"
        rpm_build_dir.mkdir(exist_ok=True)
        
        dest_dir = rpm_build_dir / install_prefix.lstrip("/")
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy contents
        self._copy_directory_contents(source_path, dest_dir)
        
        # Create desktop file if requested
        if metadata.get("create_desktop_file", True):
            self._create_desktop_file(rpm_build_dir, metadata)
        
        # Create icon links if requested
        if metadata.get("install_icons", True):
            self._setup_icons(rpm_build_dir, dest_dir, metadata)
        
        return rpm_build_dir
    
    def _copy_directory_contents(self, source_dir: Path, target_dir: Path) -> None:
        """
        Copy contents from source to target directory.
        
        Args:
            source_dir: Source directory path
            target_dir: Target directory path
        """
        logger.info(f"Copying contents from {source_dir} to {target_dir}")
        
        # Copy all files and directories
        for item in source_dir.iterdir():
            if item.is_dir():
                dest_subdir = target_dir / item.name
                dest_subdir.mkdir(exist_ok=True)
                self._copy_directory_contents(item, dest_subdir)
            else:
                try:
                    shutil.copy2(item, target_dir / item.name)
                except (shutil.Error, OSError) as e:
                    logger.warning(f"Error copying {item}: {str(e)}")
    
    def _create_desktop_file(self, build_dir: Path, metadata: Dict[str, Any]) -> None:
        """
        Create a .desktop file in the appropriate location.
        
        Args:
            build_dir: The build directory path
            metadata: Package metadata dictionary
        """
        app_name = metadata.get("name", "Application")
        app_exec = metadata.get("exec", "")
        app_icon = metadata.get("icon", "")
        app_comment = metadata.get("comment", "")
        app_categories = metadata.get("categories", "Utility;")
        
        # Create applications directory if it doesn't exist
        applications_dir = build_dir / "usr" / "share" / "applications"
        applications_dir.mkdir(parents=True, exist_ok=True)
        
        # Create .desktop file
        desktop_file_path = applications_dir / f"{app_name.lower().replace(' ', '-')}.desktop"
        
        with open(desktop_file_path, "w") as f:
            f.write("[Desktop Entry]\n")
            f.write(f"Name={app_name}\n")
            f.write(f"Exec={app_exec}\n")
            f.write(f"Icon={app_icon}\n")
            f.write(f"Comment={app_comment}\n")
            f.write("Type=Application\n")
            f.write(f"Categories={app_categories}\n")
            f.write("Terminal=false\n")
        
        logger.info(f"Created desktop file: {desktop_file_path}")
    
    def _setup_icons(self, build_dir: Path, source_dir: Path, metadata: Dict[str, Any]) -> None:
        """
        Set up icon files in standard locations.
        
        Args:
            build_dir: The build directory path
            source_dir: Source directory containing the app
            metadata: Package metadata dictionary
        """
        icon_name = metadata.get("icon", "")
        if not icon_name:
            logger.warning("No icon name specified in metadata, skipping icon setup")
            return
        
        # Look for icons in the source directory
        icons = list(source_dir.glob(f"**/{icon_name}.*"))
        icons.extend(list(source_dir.glob("**/*.png")))
        icons.extend(list(source_dir.glob("**/*.svg")))
        
        if not icons:
            logger.warning("No icon files found in the package")
            return
        
        # Create icon directories
        icons_dir = build_dir / "usr" / "share" / "icons" / "hicolor"
        icons_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy the first found icon to standard location
        icon_file = icons[0]
        
        # Determine icon type and size
        if icon_file.suffix == ".svg":
            target_dir = icons_dir / "scalable" / "apps"
        else:
            # Default to 128x128 if we can't determine size
            target_dir = icons_dir / "128x128" / "apps"
        
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{icon_name}{icon_file.suffix}"
        
        try:
            shutil.copy2(icon_file, target_path)
            logger.info(f"Copied icon from {icon_file} to {target_path}")
        except (shutil.Error, OSError) as e:
            logger.warning(f"Error copying icon {icon_file}: {str(e)}") 