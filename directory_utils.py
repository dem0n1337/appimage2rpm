#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
from pathlib import Path
import re

logger = logging.getLogger(__name__)

class DirectoryPackager:
    """Trieda pre prípravu adresára na vytvorenie RPM balíka"""

    def __init__(self, directory_path):
        """
        Inicializácia s cestou k adresáru
        
        Args:
            directory_path (str): Cesta k adresáru s aplikáciou
        """
        self.directory_path = Path(directory_path)
        if not self.directory_path.exists():
            raise FileNotFoundError(f"Adresár nenájdený: {directory_path}")
        if not self.directory_path.is_dir():
            raise ValueError(f"Zadaná cesta nie je adresár: {directory_path}")

        self.metadata = {}

    def get_directory(self):
        """
        Vráti cestu k adresáru s aplikáciou
        
        Returns:
            Path: Cesta k adresáru s aplikáciou
        """
        return self.directory_path

    def get_icon_file(self):
        """
        Nájde ikonu aplikácie v adresári
        
        Returns:
            Path: Cesta k súboru ikony alebo None
        """
        # Hľadanie ikon v štandardných adresároch
        icon_dirs = [
            "usr/share/icons",
            "usr/share/pixmaps",
            ".DirIcon",
            "resources"  # Pridané pre aplikácie založené na Electron/Chromium
        ]
        
        for icon_dir in icon_dirs:
            icon_path = self.directory_path / icon_dir
            if icon_path.exists():
                if icon_path.is_file():  # .DirIcon je priamo súbor
                    return icon_path
                    
                # Inak prejsť adresáre a nájsť ikony
                for root, _, files in os.walk(icon_path):
                    for file in files:
                        if file.endswith((".png", ".svg", ".xpm", ".ico")):
                            return Path(root) / file
        
        # Hľadať ikonu s rovnakým názvom ako aplikácia
        if self.metadata.get("name"):
            for root, _, files in os.walk(self.directory_path):
                for file in files:
                    if file.startswith(self.metadata["name"]) and file.endswith((".png", ".svg", ".xpm", ".ico")):
                        return Path(root) / file
        
        # Prehľadať všetky súbory pre ikony
        for root, _, files in os.walk(self.directory_path):
            for file in files:
                if file.endswith((".png", ".svg", ".xpm", ".ico")):
                    return Path(root) / file
        
        return None

    def guess_metadata(self):
        """
        Pokús sa odhadnúť metadáta z názvu adresára a obsahu
        
        Returns:
            dict: Odhadnuté metadáta o aplikácii
        """
        metadata = {}
        
        # Použitie názvu adresára ako názov aplikácie
        dir_name = self.directory_path.name
        metadata['name'] = dir_name
        
        # Prehľadanie executable súborov pre potenciálne informácie o verzii
        executable_files = []
        for root, _, files in os.walk(self.directory_path):
            for file in files:
                file_path = Path(root) / file
                if os.access(file_path, os.X_OK) and not file_path.is_dir():
                    executable_files.append(file_path)
        
        # Skúsiť nájsť hlavný spustiteľný súbor - rovnaký názov ako adresár
        main_executable = None
        for exe in executable_files:
            if exe.stem.lower() == dir_name.lower():
                main_executable = exe
                break
        
        # Ak sa nenašiel hlavný spustiteľný súbor, použiť prvý nájdený
        if not main_executable and executable_files:
            main_executable = executable_files[0]
        
        if main_executable:
            metadata['exec'] = main_executable.name
        
        # Základná verzia
        metadata['version'] = '1.0.0'
        
        # Pokus o detekciu verzie zo súborov
        version_files = ['version', 'VERSION', 'Version']
        for v_file in version_files:
            version_path = self.directory_path / v_file
            if version_path.exists() and version_path.is_file():
                with open(version_path, 'r') as f:
                    content = f.read().strip()
                    version_match = re.search(r'(\d+\.\d+(\.\d+)?)', content)
                    if version_match:
                        metadata['version'] = version_match.group(1)
                        break
        
        # Základný popis
        metadata['description'] = f"{dir_name} Application"
        
        # Kategórie
        metadata['categories'] = ["Utility"]
        
        # Základná licencia
        metadata['license'] = "Proprietary"
        
        self.metadata = metadata
        return metadata

    def set_metadata(self, metadata):
        """
        Nastaví metadáta manuálne
        
        Args:
            metadata (dict): Metadáta o aplikácii
        """
        self.metadata = metadata
        return self.metadata
