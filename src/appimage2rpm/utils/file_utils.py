#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
File utilities for the AppImage2RPM application.
"""

import os
import shutil
import tempfile
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

from PySide6.QtGui import QPixmap, QImage, QIcon


logger = logging.getLogger(__name__)


def get_icon_preview(icon_path: str, size: int = 64) -> Optional[QPixmap]:
    """
    Get a preview of an icon file scaled to a specific size.
    
    Args:
        icon_path: Path to the icon file
        size: Size to scale the icon to
        
    Returns:
        QPixmap: Scaled icon pixmap or None if the icon couldn't be loaded
    """
    if not icon_path or not os.path.exists(icon_path):
        logger.warning(f"Icon file does not exist: {icon_path}")
        return None
        
    try:
        # Load icon based on file type
        icon_path_lower = icon_path.lower()
        pixmap = None
        
        if icon_path_lower.endswith('.svg'):
            # Load SVG file
            icon = QIcon(icon_path)
            pixmap = icon.pixmap(size, size)
        else:
            # Load raster image
            pixmap = QPixmap(icon_path)
            
        if pixmap and not pixmap.isNull():
            # Scale the pixmap if needed
            if pixmap.width() > size or pixmap.height() > size:
                pixmap = pixmap.scaled(
                    size, size,
                    aspectRatioMode=Qt.KeepAspectRatio,
                    transformMode=Qt.SmoothTransformation
                )
            return pixmap
        else:
            logger.warning(f"Failed to load icon: {icon_path}")
            return None
    except Exception as e:
        logger.error(f"Error loading icon {icon_path}: {str(e)}")
        return None


def ensure_directory(directory: Union[str, Path]) -> bool:
    """
    Ensure a directory exists.
    
    Args:
        directory: Directory path
        
    Returns:
        bool: True if the directory exists or was created, False otherwise
    """
    try:
        os.makedirs(directory, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Error creating directory {directory}: {str(e)}")
        return False


def copy_file_with_permissions(
    source: Union[str, Path],
    destination: Union[str, Path],
    mode: Optional[int] = None
) -> bool:
    """
    Copy a file and set permissions.
    
    Args:
        source: Source file path
        destination: Destination file path
        mode: Permissions mode (octal)
        
    Returns:
        bool: True if the copy succeeded, False otherwise
    """
    try:
        # Ensure destination directory exists
        dest_dir = os.path.dirname(str(destination))
        if not ensure_directory(dest_dir):
            return False
            
        # Copy the file
        shutil.copy2(source, destination)
        
        # Set mode if provided
        if mode is not None:
            os.chmod(destination, mode)
            
        return True
    except Exception as e:
        logger.error(f"Error copying file from {source} to {destination}: {str(e)}")
        return False


def create_temporary_directory(prefix: str = "appimage2rpm_") -> Optional[str]:
    """
    Create a temporary directory.
    
    Args:
        prefix: Prefix for the directory name
        
    Returns:
        str: Path to the temporary directory or None on failure
    """
    try:
        return tempfile.mkdtemp(prefix=prefix)
    except Exception as e:
        logger.error(f"Error creating temporary directory: {str(e)}")
        return None


def cleanup_directory(directory: Union[str, Path]) -> bool:
    """
    Delete a directory and its contents.
    
    Args:
        directory: Directory to delete
        
    Returns:
        bool: True if the directory was deleted, False otherwise
    """
    try:
        if os.path.exists(directory):
            shutil.rmtree(directory, ignore_errors=True)
        return True
    except Exception as e:
        logger.error(f"Error cleaning up directory {directory}: {str(e)}")
        return False 