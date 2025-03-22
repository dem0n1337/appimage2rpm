#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module for extracting and analyzing AppImage files.
"""

import os
import subprocess
import tempfile
import shutil
import json
import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class AppImageExtractor:
    """
    Class for extracting and analyzing AppImage files.
    
    This class handles extracting AppImage contents and gathering metadata
    including application name, version, and icon files.
    """

    def __init__(self, appimage_path: str) -> None:
        """
        Initialize with the path to an AppImage file.
        
        Args:
            appimage_path: Path to the AppImage file
            
        Raises:
            FileNotFoundError: If the AppImage file doesn't exist
            ValueError: If the path is not a file
        """
        self.appimage_path = Path(appimage_path)
        if not self.appimage_path.exists():
            raise FileNotFoundError(f"AppImage file not found: {appimage_path}")
        if not self.appimage_path.is_file():
            raise ValueError(f"The specified path is not a file: {appimage_path}")
        
        # Make sure the AppImage file is executable
        if not os.access(self.appimage_path, os.X_OK):
            logger.info(f"Making AppImage file executable: {self.appimage_path}")
            os.chmod(self.appimage_path, os.stat(self.appimage_path).st_mode | 0o111)

        self.temp_dir: Optional[str] = None
        self.extracted_dir: Optional[Path] = None
        self.metadata: Dict[str, Any] = {}

    def extract(self) -> Path:
        """
        Extract the AppImage to a temporary directory.
        
        Returns:
            Path: Path to the directory with extracted content
            
        Raises:
            RuntimeError: If the extraction fails
            FileNotFoundError: If the extracted content cannot be found
        """
        self.temp_dir = tempfile.mkdtemp(prefix="appimage2rpm_")
        logger.info(f"Created temporary directory: {self.temp_dir}")
        
        # Create directory for extracted files
        self.extracted_dir = Path(self.temp_dir) / "extracted"
        self.extracted_dir.mkdir(exist_ok=True)
        
        try:
            # Extract using the AppImage's built-in tool
            env = os.environ.copy()
            env["DISPLAY"] = ""  # Prevent GUI from opening
            
            logger.info(f"Extracting AppImage: {self.appimage_path}")
            cmd = [str(self.appimage_path), "--appimage-extract"]
            process = subprocess.run(
                cmd, 
                cwd=str(self.extracted_dir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if process.returncode != 0:
                error_msg = f"Error extracting AppImage: {process.stderr}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            logger.info("AppImage extracted successfully")
            
            # Typically AppImage extracts content to 'squashfs-root'
            expected_dir = self.extracted_dir / "squashfs-root"
            if expected_dir.exists():
                logger.debug(f"Using expected extraction directory: {expected_dir}")
                return expected_dir
            
            # If not in the expected directory, try to find the extracted directory
            logger.debug("Searching for extracted directory")
            dirs = [d for d in self.extracted_dir.iterdir() if d.is_dir()]
            if dirs:
                logger.debug(f"Found extraction directory: {dirs[0]}")
                return dirs[0]
            
            error_msg = "Extracted AppImage content not found"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
            
        except Exception as e:
            logger.exception("Error during AppImage extraction")
            self.cleanup()
            raise e

    def get_desktop_file(self) -> Optional[Path]:
        """
        Find the .desktop file in the extracted AppImage.
        
        Returns:
            Path: Path to the .desktop file or None if not found
            
        Raises:
            ValueError: If the AppImage hasn't been extracted yet
        """
        if not self.extracted_dir:
            error_msg = "AppImage must be extracted first using extract()"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        logger.info("Searching for .desktop file")
        
        # Typical path to .desktop file
        for root, _, files in os.walk(self.extracted_dir):
            for file in files:
                if file.endswith(".desktop"):
                    desktop_file = Path(root) / file
                    logger.info(f"Found .desktop file: {desktop_file}")
                    return desktop_file
        
        logger.warning("No .desktop file found")
        return None

    def get_icon_files(self) -> List[Path]:
        """
        Find icon files in the extracted AppImage, prioritized by quality.
        
        Searches for icons in standard directories and by matching app name.
        
        Returns:
            List[Path]: List of icon file paths, ordered by priority
            
        Raises:
            ValueError: If the AppImage hasn't been extracted yet
        """
        if not self.extracted_dir:
            error_msg = "AppImage must be extracted first using extract()"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        logger.info("Searching for icon files")
        
        # Dictionary to store found icons with priorities
        icons: Dict[str, Tuple[int, Path]] = {}
        
        # Look for the .DirIcon which is often the main application icon
        dir_icon = self.extracted_dir / "squashfs-root" / ".DirIcon"
        if dir_icon.exists() and dir_icon.is_file():
            logger.info(f"Found .DirIcon: {dir_icon}")
            icons[".DirIcon"] = (10, dir_icon)
        
        # Search icons in standard hicolor theme directory
        hicolor_dir = self.extracted_dir / "squashfs-root" / "usr" / "share" / "icons" / "hicolor"
        if hicolor_dir.exists():
            logger.info(f"Searching for icons in hicolor theme directory: {hicolor_dir}")
            # Priority based on size (larger is better)
            for size_dir in hicolor_dir.glob("*x*"):
                size_str = size_dir.name
                try:
                    size = int(size_str.split("x")[0])
                    for apps_dir in size_dir.glob("apps"):
                        for icon_file in apps_dir.glob("*"):
                            if icon_file.suffix.lower() in (".png", ".svg", ".xpm"):
                                logger.info(f"Found hicolor icon: {icon_file} (size: {size})")
                                icons[f"hicolor_{size}_{icon_file.name}"] = (size, icon_file)
                except (ValueError, IndexError):
                    continue
        
        # Search in pixmaps directory (common location)
        pixmap_dir = self.extracted_dir / "squashfs-root" / "usr" / "share" / "pixmaps"
        if pixmap_dir.exists():
            logger.info(f"Searching for icons in pixmaps directory: {pixmap_dir}")
            for icon_file in pixmap_dir.glob("*"):
                if icon_file.suffix.lower() in (".png", ".svg", ".xpm"):
                    logger.info(f"Found pixmap icon: {icon_file}")
                    icons[f"pixmap_{icon_file.name}"] = (5, icon_file)
        
        # Look for icons with the same name as the application
        app_name = self.metadata.get("name", "")
        if app_name:
            logger.info(f"Searching for icons matching application name: {app_name}")
            for root, _, files in os.walk(self.extracted_dir):
                for file in files:
                    if (file.startswith(app_name) or 
                        file.lower().startswith(app_name.lower())) and \
                       file.endswith((".png", ".svg", ".xpm")):
                        icon_file = Path(root) / file
                        logger.info(f"Found icon matching app name: {icon_file}")
                        icons[f"name_match_{file}"] = (1, icon_file)
        
        # Extract icon path from .desktop file
        desktop_file = self.get_desktop_file()
        if desktop_file:
            icon_name = self._extract_icon_name_from_desktop(desktop_file)
            if icon_name:
                logger.info(f"Looking for icon named in .desktop file: {icon_name}")
                # Look for the icon in standard locations
                for root, _, files in os.walk(self.extracted_dir):
                    for file in files:
                        file_base = Path(file).stem
                        if (file_base == icon_name or 
                            file_base.lower() == icon_name.lower()) and \
                           file.endswith((".png", ".svg", ".xpm")):
                            icon_file = Path(root) / file
                            logger.info(f"Found icon from .desktop file: {icon_file}")
                            icons[f"desktop_ref_{file}"] = (8, icon_file)
        
        # Return icons ordered by priority (highest first)
        sorted_icons = [path for _, path in sorted(icons.values(), key=lambda x: -x[0])]
        
        # Log the detected icons in priority order
        if sorted_icons:
            logger.info(f"Found {len(sorted_icons)} icons, best: {sorted_icons[0]}")
        else:
            logger.warning("No icons found")
            
        return sorted_icons

    def _extract_icon_name_from_desktop(self, desktop_file: Path) -> Optional[str]:
        """
        Extract icon name from .desktop file.
        
        Args:
            desktop_file: Path to the .desktop file
            
        Returns:
            str: The icon name or None if not found
        """
        try:
            logger.debug(f"Extracting icon name from .desktop file: {desktop_file}")
            with open(desktop_file, 'r', errors='replace') as f:
                for line in f:
                    if line.startswith('Icon='):
                        icon_name = line.split('=', 1)[1].strip()
                        logger.info(f"Found icon name in .desktop file: {icon_name}")
                        return icon_name
            logger.debug("No icon entry found in .desktop file")
            return None
        except Exception as e:
            logger.error(f"Error reading .desktop file: {str(e)}")
            return None

    def parse_metadata(self) -> Dict[str, Any]:
        """
        Get metadata from the AppImage file.
        
        Returns:
            Dict[str, Any]: Application metadata
        """
        # Extract if not done already
        if not self.extracted_dir:
            self.extract()
            
        logger.info("Parsing AppImage metadata")
        metadata: Dict[str, Any] = {}
        
        # Get metadata from .desktop file
        desktop_file = self.get_desktop_file()
        if desktop_file:
            logger.info(f"Extracting metadata from .desktop file: {desktop_file}")
            desktop_metadata = self._parse_desktop_file(desktop_file)
            metadata.update(desktop_metadata)
        
        # Try to extract version information from filename
        if 'version' not in metadata:
            version = self._extract_version_from_filename()
            if version:
                logger.info(f"Extracted version from filename: {version}")
                metadata['version'] = version
        
        # Set defaults if information is missing
        if 'name' not in metadata:
            app_name = self.appimage_path.stem
            logger.info(f"Using filename as application name: {app_name}")
            metadata['name'] = app_name
            
        if 'version' not in metadata:
            logger.info("Using default version 1.0.0")
            metadata['version'] = '1.0.0'
            
        if 'release' not in metadata:
            logger.info("Using default release 1")
            metadata['release'] = '1'
        
        # Store metadata for later use
        self.metadata = metadata
        
        return metadata

    def _parse_desktop_file(self, desktop_file: Path) -> Dict[str, Any]:
        """
        Parse a .desktop file to extract application metadata.
        
        Args:
            desktop_file: Path to the .desktop file
            
        Returns:
            Dict[str, Any]: Metadata extracted from the .desktop file
        """
        metadata: Dict[str, Any] = {}
        
        try:
            logger.debug(f"Parsing .desktop file: {desktop_file}")
            with open(desktop_file, 'r', errors='replace') as f:
                current_section = None
                
                for line in f:
                    line = line.strip()
                    
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                        
                    # Check for section headers
                    if line.startswith('[') and line.endswith(']'):
                        current_section = line[1:-1]
                        continue
                        
                    # Only process the Desktop Entry section
                    if current_section != 'Desktop Entry':
                        continue
                        
                    # Parse key-value pairs
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # Map desktop file keys to metadata
                        if key == 'Name':
                            metadata['name'] = value
                        elif key == 'Version':
                            metadata['version'] = value
                        elif key == 'Comment':
                            metadata['summary'] = value
                        elif key == 'GenericName':
                            metadata['generic_name'] = value
                        elif key == 'Categories':
                            metadata['categories'] = value.split(';')
                        elif key == 'Exec':
                            metadata['exec'] = value
                        elif key == 'Type':
                            metadata['type'] = value
                        elif key == 'Icon':
                            metadata['icon'] = value
                        elif key == 'X-AppImage-Version':
                            metadata['version'] = value
                        elif key == 'X-AppImage-Name':
                            metadata['name'] = value
        
            logger.debug(f"Extracted metadata from .desktop file: {metadata}")
            return metadata
                
        except Exception as e:
            logger.error(f"Error parsing .desktop file: {str(e)}")
            return {}

    def _extract_version_from_filename(self) -> Optional[str]:
        """
        Try to extract version information from AppImage filename.
        
        Returns:
            str: Version string if found, otherwise None
        """
        filename = self.appimage_path.name
        
        # Common patterns in AppImage filenames
        patterns = [
            # AppName-x.y.z-arch.AppImage
            r'[-_](\d+\.\d+\.\d+(?:-\w+(?:\.\d+)?)?)-',
            # AppName-vx.y.z-arch.AppImage
            r'[-_]v(\d+\.\d+\.\d+(?:-\w+(?:\.\d+)?)?)-',
            # AppName-x.y-arch.AppImage
            r'[-_](\d+\.\d+)-',
            # AppName-x-arch.AppImage
            r'[-_](\d+)-',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename)
            if match:
                return match.group(1)
                
        return None

    def cleanup(self) -> None:
        """Clean up temporary files."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            logger.info(f"Cleaning up temporary directory: {self.temp_dir}")
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            self.temp_dir = None
            self.extracted_dir = None 