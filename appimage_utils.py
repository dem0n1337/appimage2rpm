#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import tempfile
import shutil
import json
import re
from pathlib import Path


class AppImageExtractor:
    """Trieda pre extrakciu a analýzu AppImage súborov"""

    def __init__(self, appimage_path):
        """
        Inicializácia s cestou k AppImage súboru
        
        Args:
            appimage_path (str): Cesta k AppImage súboru
        """
        self.appimage_path = Path(appimage_path)
        if not self.appimage_path.exists():
            raise FileNotFoundError(f"AppImage súbor nenájdený: {appimage_path}")
        if not self.appimage_path.is_file():
            raise ValueError(f"Zadaná cesta nie je súbor: {appimage_path}")
        if not os.access(self.appimage_path, os.X_OK):
            os.chmod(self.appimage_path, os.stat(self.appimage_path).st_mode | 0o111)

        self.temp_dir = None
        self.extracted_dir = None
        self.metadata = {}

    def extract(self):
        """
        Extrahuje AppImage do dočasného adresára
        
        Returns:
            Path: Cesta k adresáru s extrahovaným obsahom
        """
        self.temp_dir = tempfile.mkdtemp(prefix="appimage2rpm_")
        
        # Vytvorenie adresára pre extrahované súbory
        self.extracted_dir = Path(self.temp_dir) / "extracted"
        self.extracted_dir.mkdir(exist_ok=True)
        
        try:
            # Extrakcia pomocou nástroja v AppImage
            env = os.environ.copy()
            env["DISPLAY"] = ""  # Zabrániť otvoreniu GUI
            
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
                raise RuntimeError(f"Chyba pri extrakcii AppImage: {process.stderr}")
            
            # Typicky AppImage extrahuje obsah do adresára 'squashfs-root'
            expected_dir = self.extracted_dir / "squashfs-root"
            if expected_dir.exists():
                return expected_dir
            
            # Ak nie je v očakávanom adresári, skúsime nájsť extrahovaný adresár
            dirs = [d for d in self.extracted_dir.iterdir() if d.is_dir()]
            if dirs:
                return dirs[0]
            
            raise FileNotFoundError("Extrahovaný obsah AppImage nenájdený")
            
        except Exception as e:
            self.cleanup()
            raise e

    def get_desktop_file(self):
        """
        Nájde .desktop súbor v extrahovanom AppImage
        
        Returns:
            Path: Cesta k .desktop súboru alebo None
        """
        if not self.extracted_dir:
            raise ValueError("AppImage musí byť najprv extrahovaný pomocou extract()")
            
        # Typická cesta k .desktop súboru
        for root, _, files in os.walk(self.extracted_dir):
            for file in files:
                if file.endswith(".desktop"):
                    return Path(root) / file
                    
        return None

    def get_icon_file(self):
        """
        Nájde ikonu aplikácie
        
        Returns:
            Path: Cesta k súboru ikony alebo None
        """
        if not self.extracted_dir:
            raise ValueError("AppImage musí byť najprv extrahovaný pomocou extract()")
            
        # Hľadanie ikon v štandardných adresároch
        icon_dirs = [
            "usr/share/icons",
            "usr/share/pixmaps",
            ".DirIcon"
        ]
        
        for icon_dir in icon_dirs:
            icon_path = self.extracted_dir / "squashfs-root" / icon_dir
            if icon_path.exists():
                if icon_path.is_file():  # .DirIcon je priamo súbor
                    return icon_path
                    
                # Inak prejsť adresáre a nájsť ikony
                for root, _, files in os.walk(icon_path):
                    for file in files:
                        if file.endswith((".png", ".svg", ".xpm")):
                            return Path(root) / file
        
        # Hľadať ikonu s rovnakým názvom ako aplikácia
        if self.metadata.get("name"):
            for root, _, files in os.walk(self.extracted_dir):
                for file in files:
                    if file.startswith(self.metadata["name"]) and file.endswith((".png", ".svg", ".xpm")):
                        return Path(root) / file
        
        return None

    def parse_metadata(self):
        """
        Získa metadáta z AppImage súboru
        
        Returns:
            dict: Metadáta o aplikácii
        """
        # Extrakcia, ak ešte nebola vykonaná
        if not self.extracted_dir:
            self.extract()
            
        metadata = {}
        
        # Získanie metadát z .desktop súboru
        desktop_file = self.get_desktop_file()
        if desktop_file:
            with open(desktop_file, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
                
                # Základné metadáta
                name_match = re.search(r'Name=(.+)', content)
                if name_match:
                    metadata['name'] = name_match.group(1).strip()
                
                # Odstránenie ďalších jazykových verzií názvu (napr. Name[sk]=...)
                if 'name' in metadata:
                    base_name = metadata['name']
                    metadata['name'] = re.sub(r'\[.*?\]', '', base_name).strip()
                
                version_match = re.search(r'X-AppImage-Version=(.+)', content)
                if version_match:
                    metadata['version'] = version_match.group(1).strip()
                
                comment_match = re.search(r'Comment=(.+)', content)
                if comment_match:
                    metadata['description'] = comment_match.group(1).strip()
                
                exec_match = re.search(r'Exec=(.+)', content)
                if exec_match:
                    metadata['exec'] = exec_match.group(1).strip()
                
                icon_match = re.search(r'Icon=(.+)', content)
                if icon_match:
                    metadata['icon'] = icon_match.group(1).strip()
                
                categories_match = re.search(r'Categories=(.+)', content)
                if categories_match:
                    categories = categories_match.group(1).strip()
                    metadata['categories'] = [c.strip() for c in categories.split(';') if c.strip()]
        
        # Hľadanie AppStream metadát
        appstream_paths = [
            "usr/share/metainfo",
            "usr/share/appdata"
        ]
        
        for appstream_dir in appstream_paths:
            dir_path = self.extracted_dir / "squashfs-root" / appstream_dir
            if dir_path.exists():
                for file in dir_path.glob("*.xml"):
                    with open(file, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
                        
                        # Získanie verzie a ďalších metadát
                        version_match = re.search(r'<release version="([^"]+)"', content)
                        if version_match and 'version' not in metadata:
                            metadata['version'] = version_match.group(1)
                            
                        url_match = re.search(r'<url type="homepage">([^<]+)</url>', content)
                        if url_match:
                            metadata['homepage'] = url_match.group(1)
                            
                        license_match = re.search(r'<project_license>([^<]+)</project_license>', content)
                        if license_match:
                            metadata['license'] = license_match.group(1)
                            
        # Získanie skutočného spustiteľného súboru zo symlinku AppRun
        apprun_path = self.extracted_dir / "squashfs-root/AppRun"
        if apprun_path.exists() and apprun_path.is_symlink():
            metadata['apprun_target'] = os.path.realpath(apprun_path)
            
        # Ak nemáme verziu, použijeme 1.0.0 ako predvolenú
        if 'version' not in metadata:
            metadata['version'] = "1.0.0"
            
        # Ak nemáme názov, použijeme názov súboru
        if 'name' not in metadata:
            metadata['name'] = self.appimage_path.stem
            
        self.metadata = metadata
        return metadata

    def cleanup(self):
        """Vyčistí dočasné súbory"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            self.temp_dir = None
            self.extracted_dir = None
