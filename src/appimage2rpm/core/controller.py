#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Controller module for AppImage2RPM application.
Mediates between GUI and core functionality.
"""

import os
import tempfile
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple

from appimage2rpm.core.extractor import AppImageExtractor
from appimage2rpm.core.builder import RPMBuilder
from appimage2rpm.core.dependency_analyzer import DependencyAnalyzer
from appimage2rpm.core.distro_profile import DistroProfileManager
from appimage2rpm.core.directory_packager import DirectoryPackager
from appimage2rpm.core.repo_manager import RepoManager


logger = logging.getLogger(__name__)


class AppImage2RPMController:
    """
    Controller class that mediates between GUI and core functionality.
    
    This class orchestrates the conversion process by coordinating between
    the different modules that handle extraction, dependency analysis,
    and RPM building.
    """
    
    def __init__(self) -> None:
        """Initialize the controller."""
        self.profile_manager = DistroProfileManager()
        
    def get_available_profiles(self) -> List[Dict[str, Any]]:
        """
        Get a list of available distribution profiles.
        
        Returns:
            List[Dict[str, Any]]: A list of profile dictionaries
        """
        return self.profile_manager.get_profiles()
    
    def detect_current_distro(self) -> str:
        """
        Detect the current Linux distribution.
        
        Returns:
            str: The ID of the detected distribution profile
        """
        return self.profile_manager.detect_current_distro()
    
    def convert_appimage(
        self, 
        appimage_path: str, 
        output_dir: Optional[str] = None, 
        metadata: Optional[Dict[str, Any]] = None,
        distro_profile: Optional[str] = None,
        auto_deps: bool = True,
        repo_info: Optional[Dict[str, Any]] = None,
        is_directory: bool = False,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Convert AppImage to RPM package.
        
        Args:
            appimage_path: Path to the AppImage file
            output_dir: Directory where the RPM package will be saved
            metadata: Optional metadata to use instead of auto-detected
            distro_profile: Target distribution profile ID
            auto_deps: Whether to automatically detect dependencies
            repo_info: Optional repository information for publishing
            is_directory: Whether appimage_path is a directory instead of AppImage
            progress_callback: Optional callback for progress updates
                               Function that takes (percent, message)
            
        Returns:
            Dict[str, Any]: Result of the conversion with keys:
                - success: Whether the conversion was successful
                - rpm_path: Path to the generated RPM file (if successful)
                - message: Success or error message
        """
        try:
            # Set default output directory if not provided
            if not output_dir:
                output_dir = os.path.dirname(appimage_path)
            
            # Initialize metadata if not provided
            if metadata is None:
                metadata = {}
                
            # Update progress
            if progress_callback:
                progress_callback(5, "Initializing...")
                
            # Get distribution profile
            if not distro_profile:
                distro_profile = self.detect_current_distro()
                
            profile = self.profile_manager.get_profile(distro_profile)
            if not profile:
                error_msg = f"Unsupported distribution profile: {distro_profile}"
                logger.error(error_msg)
                return {"success": False, "message": error_msg}
                
            if progress_callback:
                progress_callback(10, f"Using profile: {profile['name']}")
                
            # Create RPM macros for the distribution
            macros_file = self.profile_manager.create_rpm_macros(distro_profile)
            if macros_file and progress_callback:
                progress_callback(15, f"Created RPM macros for {profile['name']}")
                
            extracted_dir = None
            icon_paths = []
            
            if is_directory:
                # Use directory instead of extracting AppImage
                if progress_callback:
                    progress_callback(20, "Processing directory...")
                    
                directory_packager = DirectoryPackager(appimage_path)
                extracted_dir = directory_packager.get_directory()
                
                if progress_callback:
                    progress_callback(30, "Getting metadata...")
                    
                # Get metadata
                if not metadata:
                    metadata = directory_packager.guess_metadata()
                else:
                    directory_packager.set_metadata(metadata)
                
                # Get icons with priority
                if progress_callback:
                    progress_callback(45, "Finding icons...")
                    
                icon_paths = directory_packager.get_icon_files()
            else:
                # Extract AppImage
                if progress_callback:
                    progress_callback(20, "Extracting AppImage...")
                    
                extractor = AppImageExtractor(appimage_path)
                extracted_dir = extractor.extract()
                
                if progress_callback:
                    progress_callback(30, "Getting metadata...")
                    
                # Get metadata
                if not metadata:
                    metadata = extractor.parse_metadata()
                    
                # Get icons with priority
                if progress_callback:
                    progress_callback(45, "Finding icons...")
                    
                icon_paths = extractor.get_icon_files()
                
            # Advanced dependency detection
            requires = []
            if auto_deps:
                if progress_callback:
                    progress_callback(35, "Detecting dependencies...")
                    
                analyzer = DependencyAnalyzer(extracted_dir)
                analyzer.analyze_dependencies()
                
                # Get dependencies for the distribution
                distro_id = profile["id"]  # fedora, rhel, centos
                requires = analyzer.convert_dependencies_to_rpm_requires(distro_id)
                
                if requires:
                    if progress_callback:
                        progress_callback(40, f"Detected {len(requires)} dependencies")
                        
                    # Add dependencies to metadata
                    metadata["requires"] = requires
                elif progress_callback:
                    progress_callback(40, "No dependencies detected")
            
            if progress_callback:
                progress_callback(50, "Preparing RPM package...")
                
            # Create RPM package
            builder = RPMBuilder(
                app_name=metadata.get('name', ''),
                app_version=metadata.get('version', '1.0.0'),
                app_release=metadata.get('release', '1'),
                extracted_dir=extracted_dir,
                icon_paths=icon_paths,
                output_dir=output_dir
            )
            
            # Log the selected icon
            selected_icon = builder.select_best_icon()
            if selected_icon:
                logger.info(f"Selected icon: {selected_icon}")
                if progress_callback:
                    progress_callback(55, f"Selected icon: {os.path.basename(str(selected_icon))}")
            else:
                logger.warning("No suitable icon found")
                if progress_callback:
                    progress_callback(55, "No suitable icon found")
            
            if progress_callback:
                progress_callback(70, "Building RPM package...")
                
            # Build RPM
            rpm_path = builder.build(metadata)
            
            if progress_callback:
                progress_callback(90, "Finalizing...")
            
            # Handle repository publishing if requested
            if repo_info and repo_info.get('enabled'):
                if progress_callback:
                    progress_callback(95, "Publishing to repository...")
                    
                repo_manager = RepoManager()
                repo_result = repo_manager.publish_rpm(rpm_path, repo_info)
                
                if not repo_result["success"]:
                    logger.warning(f"Failed to publish to repository: {repo_result['message']}")
            
            if progress_callback:
                progress_callback(100, "Conversion complete!")
                
            return {
                "success": True,
                "rpm_path": str(rpm_path),
                "message": "RPM package created successfully"
            }
            
        except Exception as e:
            logger.exception("Error during conversion")
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            } 