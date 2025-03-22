#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module for managing RPM repositories.
"""

import os
import subprocess
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

logger = logging.getLogger(__name__)


class RepoManager:
    """
    Manages RPM repositories.
    
    This class provides functionality for creating and managing
    RPM repositories, including adding packages to repositories
    and generating repository metadata.
    """
    
    def __init__(self) -> None:
        """Initialize the repository manager."""
        pass
    
    def create_repository(
        self, 
        repo_path: Union[str, Path], 
        repo_name: str,
        repo_description: Optional[str] = None
    ) -> Path:
        """
        Create a new RPM repository at the specified path.
        
        Args:
            repo_path: Path where the repository will be created
            repo_name: Name of the repository
            repo_description: Optional description of the repository
            
        Returns:
            Path to the created repository
        """
        repo_dir = Path(repo_path)
        repo_dir.mkdir(parents=True, exist_ok=True)
        
        # Create repository subdirectories
        for subdir in ["RPMS", "SRPMS"]:
            (repo_dir / subdir).mkdir(exist_ok=True)
        
        # Create repo configuration file
        repo_file = repo_dir / f"{repo_name}.repo"
        with open(repo_file, "w") as f:
            f.write(f"[{repo_name}]\n")
            f.write(f"name={repo_description or repo_name}\n")
            f.write(f"baseurl=file://{repo_dir}/RPMS\n")
            f.write("enabled=1\n")
            f.write("gpgcheck=0\n")
        
        logger.info(f"Created repository at {repo_dir}")
        return repo_dir
    
    def add_package(self, repo_path: Union[str, Path], package_path: Union[str, Path]) -> bool:
        """
        Add a package to the repository.
        
        Args:
            repo_path: Path to the repository
            package_path: Path to the RPM package file
            
        Returns:
            True if the package was added successfully, False otherwise
        """
        repo_dir = Path(repo_path)
        package_file = Path(package_path)
        
        if not package_file.exists():
            logger.error(f"Package file does not exist: {package_file}")
            return False
        
        if not package_file.name.endswith(".rpm"):
            logger.error(f"File is not an RPM package: {package_file}")
            return False
        
        # Determine if it's a source RPM or binary RPM
        target_dir = repo_dir / ("SRPMS" if package_file.name.endswith(".src.rpm") else "RPMS")
        
        if not target_dir.exists():
            target_dir.mkdir(parents=True)
        
        # Copy the package to the repository
        try:
            shutil.copy2(package_file, target_dir / package_file.name)
            logger.info(f"Added package {package_file.name} to repository {repo_dir}")
            return True
        except (shutil.Error, OSError) as e:
            logger.error(f"Error adding package to repository: {str(e)}")
            return False
    
    def update_repository_metadata(self, repo_path: Union[str, Path]) -> bool:
        """
        Update the repository metadata using createrepo.
        
        Args:
            repo_path: Path to the repository
            
        Returns:
            True if the metadata was updated successfully, False otherwise
        """
        repo_dir = Path(repo_path)
        rpms_dir = repo_dir / "RPMS"
        
        if not rpms_dir.exists():
            logger.error(f"Repository RPMS directory does not exist: {rpms_dir}")
            return False
        
        try:
            # Check if createrepo is available
            createrepo_cmd = "createrepo_c" if self._command_exists("createrepo_c") else "createrepo"
            
            if not self._command_exists(createrepo_cmd):
                logger.error("Neither createrepo_c nor createrepo is available on the system")
                return False
            
            # Run createrepo to generate metadata
            result = subprocess.run(
                [createrepo_cmd, "--update", str(rpms_dir)],
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.info(f"Updated repository metadata at {rpms_dir}")
            logger.debug(f"createrepo output: {result.stdout}")
            
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Error updating repository metadata: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error updating repository metadata: {str(e)}")
            return False
    
    def _command_exists(self, command: str) -> bool:
        """
        Check if a command exists on the system.
        
        Args:
            command: Name of the command to check
            
        Returns:
            True if the command exists, False otherwise
        """
        try:
            subprocess.run(
                ["which", command],
                capture_output=True,
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False 