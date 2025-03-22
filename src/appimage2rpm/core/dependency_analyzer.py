#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module for analyzing dependencies in AppImage applications.
"""

import os
import subprocess
import re
import logging
import platform
import tempfile
import shutil
from pathlib import Path
import json
from typing import Dict, List, Set, Optional, Any, Union

logger = logging.getLogger(__name__)


class DependencyAnalyzer:
    """
    Class for advanced dependency analysis of applications.
    
    This class scans executables and libraries to determine required
    dependencies for different Linux distributions.
    """
    
    def __init__(self, extracted_dir: Optional[Union[str, Path]] = None) -> None:
        """
        Initialize the dependency analyzer.
        
        Args:
            extracted_dir: Directory with extracted AppImage content
        """
        self.extracted_dir = Path(extracted_dir) if extracted_dir else None
        self.detected_libs: Set[str] = set()
        self.system_libs: Set[str] = set()
        self.dependencies: Dict[str, List[str]] = {}
        
        # Load standard system libraries
        self._load_system_libs()
        
    def _load_system_libs(self) -> None:
        """Load the list of standard system libraries."""
        try:
            # Get the list of system libraries
            ld_paths = ["/lib", "/lib64", "/usr/lib", "/usr/lib64"]
            
            for path in ld_paths:
                if os.path.exists(path):
                    for root, _, files in os.walk(path):
                        for filename in files:
                            if filename.endswith(".so") or ".so." in filename:
                                self.system_libs.add(filename)
                                
            logger.info(f"Loaded {len(self.system_libs)} system libraries")
            
        except Exception as e:
            logger.error(f"Error loading system libraries: {e}")
            
    def _find_executables(self, directory: Path) -> List[Path]:
        """
        Find all executable files in a directory.
        
        Args:
            directory: Directory to search in
            
        Returns:
            List of paths to executable files
        """
        executables = []
        for root, _, files in os.walk(directory):
            for filename in files:
                file_path = Path(root) / filename
                if os.access(file_path, os.X_OK) and not file_path.is_dir():
                    # Check if it's an ELF file
                    try:
                        result = subprocess.run(
                            ["file", file_path], 
                            capture_output=True, 
                            text=True, 
                            check=True
                        )
                        if "ELF" in result.stdout:
                            executables.append(file_path)
                    except subprocess.SubprocessError:
                        # If the 'file' command fails, assume it's not an ELF
                        pass
                            
        return executables
        
    def _scan_executable(self, executable: Path) -> Set[str]:
        """
        Scan an executable for dependencies.
        
        Args:
            executable: Path to the executable
            
        Returns:
            Set of library names
        """
        dependencies = set()
        try:
            result = subprocess.run(
                ["ldd", executable], 
                capture_output=True, 
                text=True, 
                check=False
            )
            
            # Extract library names from ldd output
            for line in result.stdout.splitlines():
                match = re.search(r"=> (.*) \(", line)
                if match:
                    lib_path = match.group(1).strip()
                    if lib_path and lib_path != "not found":
                        lib_name = os.path.basename(lib_path)
                        dependencies.add(lib_name)
                        
        except subprocess.SubprocessError as e:
            logger.warning(f"Error scanning {executable}: {e}")
            
        return dependencies
        
    def _map_lib_to_package(self, lib_name: str) -> Optional[str]:
        """
        Map a library name to its package name.
        
        Args:
            lib_name: Library name
            
        Returns:
            Package name or None if not found
        """
        try:
            # Try to find the package that provides the library
            result = subprocess.run(
                ["dnf", "provides", lib_name], 
                capture_output=True, 
                text=True, 
                check=False
            )
            
            for line in result.stdout.splitlines():
                # Look for package names in the output
                match = re.search(r"([a-zA-Z0-9._-]+)-\d", line)
                if match:
                    return match.group(1)
                    
        except subprocess.SubprocessError:
            pass
            
        return None
        
    def _get_distribution_info(self) -> Dict[str, str]:
        """
        Get information about the current distribution.
        
        Returns:
            Dictionary with distribution information
        """
        info = {
            "id": "unknown",
            "version": "unknown"
        }
        
        # Try to read /etc/os-release
        try:
            if os.path.exists("/etc/os-release"):
                with open("/etc/os-release", "r") as f:
                    content = f.read()
                    
                    id_match = re.search(r'ID="?([^"\n]+)"?', content)
                    if id_match:
                        info["id"] = id_match.group(1).lower()
                        
                    version_match = re.search(r'VERSION_ID="?([^"\n]+)"?', content)
                    if version_match:
                        info["version"] = version_match.group(1)
                        
        except Exception as e:
            logger.error(f"Error getting distribution info: {e}")
            
        return info
    
    def analyze_dependencies(self, extracted_dir: Optional[Union[str, Path]] = None) -> Dict[str, List[str]]:
        """
        Analyze application dependencies.
        
        Args:
            extracted_dir: Directory with extracted AppImage content
            
        Returns:
            Dictionary of dependencies for different distributions
            
        Raises:
            ValueError: If no extracted directory is specified
        """
        if extracted_dir:
            self.extracted_dir = Path(extracted_dir)
            
        if not self.extracted_dir or not self.extracted_dir.exists():
            raise ValueError("No directory with extracted AppImage content specified")
            
        # Find all executable files
        squashfs_root = self.extracted_dir
        if (self.extracted_dir / "squashfs-root").exists():
            squashfs_root = self.extracted_dir / "squashfs-root"
            
        executables = self._find_executables(squashfs_root)
        logger.info(f"Found {len(executables)} executable files")
        
        # Analyze dependencies for each executable
        all_dependencies = set()
        for executable in executables:
            deps = self._scan_executable(executable)
            all_dependencies.update(deps)
            
        # Filter system libraries
        external_libs = all_dependencies - self.system_libs
        
        # Map libraries to packages
        package_dependencies = set()
        for lib in external_libs:
            package = self._map_lib_to_package(lib)
            if package:
                package_dependencies.add(package)
                
        # Create dependencies for different distributions
        distro_info = self._get_distribution_info()
        
        # Basic dependency list
        dependencies = {
            "fedora": list(package_dependencies),
            "rhel": list(package_dependencies),
            "centos": list(package_dependencies)
        }
        
        # Save detected dependencies
        self.dependencies = dependencies
        
        return dependencies
        
    def convert_dependencies_to_rpm_requires(self, distro_id: str) -> List[str]:
        """
        Convert detected dependencies to RPM requires format.
        
        Args:
            distro_id: Distribution ID (fedora, rhel, centos)
            
        Returns:
            List of formatted RPM requires
        """
        if not self.dependencies:
            return []
            
        # Get dependencies for the given distribution
        if distro_id not in self.dependencies:
            logger.warning(f"No dependencies for distribution: {distro_id}")
            return []
            
        requires = []
        for package in self.dependencies[distro_id]:
            requires.append(package)
            
        return requires 