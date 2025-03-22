#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module for managing distribution profiles and configurations.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

logger = logging.getLogger(__name__)


class DistroProfileManager:
    """
    Manages distribution profiles for RPM packaging.
    
    This class handles loading and accessing distribution-specific
    configurations that are used during the RPM building process.
    """
    
    def __init__(self, custom_profiles_dir: Optional[Union[str, Path]] = None) -> None:
        """
        Initialize the distribution profile manager.
        
        Args:
            custom_profiles_dir: Optional path to directory containing custom profiles
        """
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.system_profiles_dir = Path(__file__).parent.parent / "data" / "profiles"
        self.custom_profiles_dir = Path(custom_profiles_dir) if custom_profiles_dir else None
        self._load_profiles()
    
    def _load_profiles(self) -> None:
        """Load all available distribution profiles."""
        # Load system profiles
        if self.system_profiles_dir.exists():
            self._load_profiles_from_dir(self.system_profiles_dir)
        
        # Load custom profiles if specified
        if self.custom_profiles_dir and self.custom_profiles_dir.exists():
            self._load_profiles_from_dir(self.custom_profiles_dir)
    
    def _load_profiles_from_dir(self, directory: Path) -> None:
        """
        Load profiles from the specified directory.
        
        Args:
            directory: Path to directory containing profile JSON files
        """
        for profile_file in directory.glob("*.json"):
            try:
                with open(profile_file, "r") as f:
                    profile_data = json.load(f)
                    if "id" in profile_data:
                        self.profiles[profile_data["id"]] = profile_data
                        logger.debug(f"Loaded profile: {profile_data['id']}")
                    else:
                        logger.warning(f"Profile missing 'id' field: {profile_file}")
            except Exception as e:
                logger.error(f"Error loading profile {profile_file}: {str(e)}")
    
    def get_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a distribution profile by ID.
        
        Args:
            profile_id: ID of the distribution profile to retrieve
            
        Returns:
            Dict containing profile data or None if not found
        """
        return self.profiles.get(profile_id)
    
    def get_all_profiles(self) -> List[Dict[str, Any]]:
        """
        Get all available distribution profiles.
        
        Returns:
            List of all profile data dictionaries
        """
        return list(self.profiles.values())
    
    def detect_current_distro(self) -> Optional[str]:
        """
        Detect the current distribution ID.
        
        Returns:
            String ID of the detected distribution or None if not detected
        """
        # Try to read /etc/os-release
        try:
            os_release = {}
            if os.path.exists("/etc/os-release"):
                with open("/etc/os-release", "r") as f:
                    for line in f:
                        if "=" in line:
                            key, value = line.strip().split("=", 1)
                            os_release[key] = value.strip('"')
            
            # Get ID
            if "ID" in os_release:
                distro_id = os_release["ID"]
                # Check if we have a matching profile
                if distro_id in self.profiles:
                    return distro_id
                # Try with VERSION_ID if available
                if "VERSION_ID" in os_release:
                    combined_id = f"{distro_id}{os_release['VERSION_ID']}"
                    if combined_id in self.profiles:
                        return combined_id
            
            return None
        except Exception as e:
            logger.error(f"Error detecting distribution: {str(e)}")
            return None 