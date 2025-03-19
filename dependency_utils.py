#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import re
import logging
import platform
import tempfile
import shutil
from pathlib import Path
import json

logger = logging.getLogger("DependencyAnalyzer")


class DependencyAnalyzer:
    """Trieda pre pokročilú analýzu závislostí aplikácií"""
    
    def __init__(self, extracted_dir=None):
        """
        Inicializácia analyzátora závislostí
        
        Args:
            extracted_dir (Path, optional): Adresár s extrahovaným obsahom AppImage
        """
        self.extracted_dir = Path(extracted_dir) if extracted_dir else None
        self.detected_libs = set()
        self.system_libs = set()
        self.dependencies = {}
        
        # Načítanie štandardných systémových knižníc
        self._load_system_libs()
        
    def _load_system_libs(self):
        """Načíta zoznam štandardných systémových knižníc"""
        try:
            # Získanie zoznamu systémových knižníc
            ld_paths = ["/lib", "/lib64", "/usr/lib", "/usr/lib64"]
            
            for path in ld_paths:
                if os.path.exists(path):
                    for root, _, files in os.walk(path):
                        for filename in files:
                            if filename.endswith(".so") or ".so." in filename:
                                self.system_libs.add(filename)
                                
            logger.info(f"Načítaných {len(self.system_libs)} systémových knižníc")
            
        except Exception as e:
            logger.error(f"Chyba pri načítaní systémových knižníc: {e}")
            
    def _get_distribution_info(self):
        """
        Získava informácie o distribúcii
        
        Returns:
            dict: Informácie o distribúcii
        """
        distro_info = {}
        
        try:
            # Detekcia distribúcie a verzie
            if os.path.exists("/etc/os-release"):
                with open("/etc/os-release", "r") as f:
                    os_release = f.read()
                    
                    id_match = re.search(r'^ID=(.+)$', os_release, re.MULTILINE)
                    if id_match:
                        distro_info["id"] = id_match.group(1).strip('"\'')
                        
                    version_match = re.search(r'^VERSION_ID=(.+)$', os_release, re.MULTILINE)
                    if version_match:
                        distro_info["version"] = version_match.group(1).strip('"\'')
            
            # Získanie architektúry
            distro_info["arch"] = platform.machine()
            
        except Exception as e:
            logger.error(f"Chyba pri zisťovaní informácií o distribúcii: {e}")
            
        return distro_info
    
    def _map_lib_to_package(self, lib_name):
        """
        Mapuje názov knižnice na balík, ktorý ho poskytuje
        
        Args:
            lib_name (str): Názov knižnice
            
        Returns:
            str: Názov balíka alebo None
        """
        try:
            distro_info = self._get_distribution_info()
            
            if distro_info.get("id") in ["fedora", "rhel", "centos"]:
                # Použitie dnf pre zistenie balíka, ktorý poskytuje knižnicu
                cmd = ["dnf", "provides", lib_name]
                process = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                if process.returncode == 0:
                    # Parsovanie výstupu pre získanie názvu balíka
                    output = process.stdout
                    
                    # Hľadanie riadka s názvom balíka
                    for line in output.splitlines():
                        if ":" in line and not line.startswith(" "):
                            # Formát: názov_balíka-verzia.arch : popis
                            package_name = line.split(":")[0].strip().split("-")[0]
                            return package_name
            
            elif distro_info.get("id") in ["debian", "ubuntu"]:
                # Pre debian-based systémy
                cmd = ["apt-file", "search", lib_name]
                process = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                if process.returncode == 0:
                    output = process.stdout
                    
                    # Prvý riadok väčšinou obsahuje názov balíka
                    if output.strip():
                        first_line = output.splitlines()[0]
                        package_name = first_line.split(":")[0].strip()
                        return package_name
                        
        except Exception as e:
            logger.error(f"Chyba pri mapovaní knižnice na balík: {e}")
            
        return None
    
    def _scan_executable(self, executable_path):
        """
        Skenuje spustiteľný súbor pre závislosti pomocou ldd
        
        Args:
            executable_path (Path): Cesta k spustiteľnému súboru
            
        Returns:
            list: Zoznam závislostí
        """
        dependencies = set()
        
        try:
            # Kontrola, či súbor existuje a je spustiteľný
            if not executable_path.exists():
                logger.error(f"Súbor neexistuje: {executable_path}")
                return list(dependencies)
                
            # Kontrola, či ide o ELF binárku (spustiteľný súbor alebo knižnicu)
            file_cmd = ["file", str(executable_path)]
            file_output = subprocess.run(
                file_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            ).stdout
            
            if "ELF" not in file_output:
                return list(dependencies)
                
            # Použitie ldd pre zistenie závislostí
            cmd = ["ldd", str(executable_path)]
            process = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if process.returncode != 0:
                logger.warning(f"Chyba pri spúšťaní ldd pre {executable_path}: {process.stderr}")
                return list(dependencies)
                
            output = process.stdout
            
            # Parsovanie výstupu ldd
            for line in output.splitlines():
                parts = line.split("=>")
                
                if len(parts) >= 2:
                    lib_name = parts[0].strip()
                    lib_path = parts[1].strip().split(" ")[0]
                    
                    # Ignorovanie prázdnych ciest alebo "not found"
                    if lib_path and lib_path != "not found":
                        lib_file = os.path.basename(lib_path)
                        dependencies.add(lib_file)
                        
                        # Pridanie do celkového zoznamu detekovaných knižníc
                        self.detected_libs.add(lib_file)
            
        except Exception as e:
            logger.error(f"Chyba pri skenovaní súboru {executable_path}: {e}")
            
        return list(dependencies)
    
    def _find_executables(self, directory):
        """
        Nájde všetky spustiteľné súbory v adresári
        
        Args:
            directory (Path): Adresár na prehľadávanie
            
        Returns:
            list: Zoznam spustiteľných súborov
        """
        executables = []
        
        try:
            for root, _, files in os.walk(directory):
                for filename in files:
                    file_path = Path(root) / filename
                    
                    # Kontrola, či je súbor spustiteľný
                    if os.access(file_path, os.X_OK) and file_path.is_file():
                        executables.append(file_path)
                        
        except Exception as e:
            logger.error(f"Chyba pri hľadaní spustiteľných súborov: {e}")
            
        return executables
    
    def analyze_dependencies(self, extracted_dir=None):
        """
        Analyzuje závislosti aplikácie
        
        Args:
            extracted_dir (Path, optional): Adresár s extrahovaným obsahom AppImage
            
        Returns:
            dict: Zoznam závislostí pre rôzne distribúcie
        """
        if extracted_dir:
            self.extracted_dir = Path(extracted_dir)
            
        if not self.extracted_dir or not self.extracted_dir.exists():
            raise ValueError("Nie je zadaný adresár s extrahovaným obsahom AppImage")
            
        # Nájdenie všetkých spustiteľných súborov
        squashfs_root = self.extracted_dir
        if (self.extracted_dir / "squashfs-root").exists():
            squashfs_root = self.extracted_dir / "squashfs-root"
            
        executables = self._find_executables(squashfs_root)
        logger.info(f"Nájdených {len(executables)} spustiteľných súborov")
        
        # Analýza závislostí pre každý spustiteľný súbor
        all_dependencies = set()
        for executable in executables:
            deps = self._scan_executable(executable)
            all_dependencies.update(deps)
            
        # Filtrovanie systémových knižníc
        external_libs = all_dependencies - self.system_libs
        
        # Mapovanie knižníc na balíky
        package_dependencies = set()
        for lib in external_libs:
            package = self._map_lib_to_package(lib)
            if package:
                package_dependencies.add(package)
                
        # Vytvorenie závislostí pre rôzne distribúcie
        distro_info = self._get_distribution_info()
        
        # Základný zoznam závislostí
        dependencies = {
            "fedora": list(package_dependencies),
            "rhel": list(package_dependencies),
            "centos": list(package_dependencies)
        }
        
        # Uloženie detekovaných závislostí
        self.dependencies = dependencies
        
        return dependencies
        
    def convert_dependencies_to_rpm_requires(self, distro="fedora"):
        """
        Konvertuje závislosti na RPM formát Requires
        
        Args:
            distro (str): Názov distribúcie (fedora, rhel, centos)
            
        Returns:
            list: Zoznam RPM závislostí
        """
        if not self.dependencies:
            return []
            
        if distro not in self.dependencies:
            distro = "fedora"  # Predvolená distribúcia
            
        requires = []
        
        for package in self.dependencies[distro]:
            requires.append(package)
            
        return requires
        
    def get_detected_libs(self):
        """
        Vráti zoznam detekovaných knižníc
        
        Returns:
            list: Zoznam detekovaných knižníc
        """
        return list(self.detected_libs)
        
    def save_dependency_report(self, output_file):
        """
        Uloží report o závislostiach do súboru
        
        Args:
            output_file (str): Cesta k výstupnému súboru
            
        Returns:
            bool: True ak bol report úspešne uložený
        """
        try:
            report = {
                "detected_libs": list(self.detected_libs),
                "dependencies": self.dependencies,
                "distro_info": self._get_distribution_info()
            }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2)
                
            return True
            
        except Exception as e:
            logger.error(f"Chyba pri ukladaní reportu o závislostiach: {e}")
            return False


class DistroProfileManager:
    """Správca profilov pre rôzne distribúcie"""
    
    def __init__(self):
        """Inicializácia správcu profilov"""
        self.profiles = {}
        self.load_profiles()
        
    def load_profiles(self):
        """Načíta profily distribúcií z konfiguračného súboru"""
        config_paths = [
            Path.home() / ".config" / "appimage2rpm" / "distros.toml",
            Path("/etc/appimage2rpm/distros.toml")
        ]
        
        for config_path in config_paths:
            if config_path.exists():
                try:
                    self.profiles = toml.load(config_path)
                    return
                except Exception as e:
                    logger.error(f"Chyba pri načítaní profilov distribúcií: {e}")
        
        # Vytvorenie predvolených profilov, ak neexistujú
        self.profiles = {
            "fedora40": {
                "name": "Fedora 40",
                "id": "fedora",
                "version": "40",
                "packages": {
                    "build": ["rpm-build", "rpmdevtools", "createrepo"],
                    "runtime": ["dnf", "glibc"]
                },
                "macro_template": """
# Fedora 40 RPM makrá
%_topdir %(echo $HOME)/rpmbuild
%dist .fc40
%fedora 40
%__os_install_post %{nil}
%_build_id_links none
"""
            },
            "fedora41": {
                "name": "Fedora 41",
                "id": "fedora",
                "version": "41",
                "packages": {
                    "build": ["rpm-build", "rpmdevtools", "createrepo"],
                    "runtime": ["dnf", "glibc"]
                },
                "macro_template": """
# Fedora 41 RPM makrá
%_topdir %(echo $HOME)/rpmbuild
%dist .fc41
%fedora 41
%__os_install_post %{nil}
%_build_id_links none
"""
            },
            "rhel9": {
                "name": "RHEL 9",
                "id": "rhel",
                "version": "9",
                "packages": {
                    "build": ["rpm-build", "rpmdevtools", "createrepo"],
                    "runtime": ["dnf", "glibc"]
                },
                "macro_template": """
# RHEL 9 RPM makrá
%_topdir %(echo $HOME)/rpmbuild
%dist .el9
%rhel 9
%__os_install_post %{nil}
%_build_id_links none
"""
            },
            "centos9": {
                "name": "CentOS 9 Stream",
                "id": "centos",
                "version": "9",
                "packages": {
                    "build": ["rpm-build", "rpmdevtools", "createrepo"],
                    "runtime": ["dnf", "glibc"]
                },
                "macro_template": """
# CentOS 9 RPM makrá
%_topdir %(echo $HOME)/rpmbuild
%dist .el9
%rhel 9
%centos 9
%__os_install_post %{nil}
%_build_id_links none
"""
            }
        }
        
    def save_profiles(self):
        """Uloží profily distribúcií do konfiguračného súboru"""
        config_dir = Path.home() / ".config" / "appimage2rpm"
        os.makedirs(config_dir, exist_ok=True)
        
        config_path = config_dir / "distros.toml"
        
        try:
            import toml
            with open(config_path, 'w') as f:
                toml.dump(self.profiles, f)
            return True
        except Exception as e:
            logger.error(f"Chyba pri ukladaní profilov distribúcií: {e}")
            return False
    
    def get_profile(self, profile_id):
        """
        Vráti profil distribúcie
        
        Args:
            profile_id (str): ID profilu
            
        Returns:
            dict: Profil distribúcie alebo None
        """
        return self.profiles.get(profile_id)
        
    def get_all_profiles(self):
        """
        Vráti zoznam všetkých profilov
        
        Returns:
            list: Zoznam profilov
        """
        return self.profiles
        
    def detect_current_distro(self):
        """
        Detekuje aktuálnu distribúciu
        
        Returns:
            str: ID profilu alebo None
        """
        try:
            # Získanie informácií o distribúcii
            if os.path.exists("/etc/os-release"):
                with open("/etc/os-release", "r") as f:
                    os_release = f.read()
                    
                    id_match = re.search(r'^ID=(.+)$', os_release, re.MULTILINE)
                    version_match = re.search(r'^VERSION_ID=(.+)$', os_release, re.MULTILINE)
                    
                    if id_match and version_match:
                        distro_id = id_match.group(1).strip('"\'')
                        distro_version = version_match.group(1).strip('"\'')
                        
                        # Hľadanie zodpovedajúceho profilu
                        for profile_id, profile in self.profiles.items():
                            if (profile["id"] == distro_id and 
                                profile["version"] == distro_version):
                                return profile_id
                                
                        # Ak nenájdeme presný match, skúsime hľadať profil s rovnakým ID
                        for profile_id, profile in self.profiles.items():
                            if profile["id"] == distro_id:
                                return profile_id
                                
        except Exception as e:
            logger.error(f"Chyba pri detekcii distribúcie: {e}")
            
        # Predvolená distribúcia je Fedora 41
        return "fedora41"
        
    def create_rpm_macros(self, profile_id):
        """
        Vytvorí súbor s RPM makrami pre danú distribúciu
        
        Args:
            profile_id (str): ID profilu
            
        Returns:
            str: Cesta k súboru s makrami alebo None
        """
        profile = self.get_profile(profile_id)
        
        if not profile:
            return None
            
        try:
            # Vytvorenie adresára pre konfiguračné súbory
            config_dir = Path.home() / ".config" / "appimage2rpm"
            os.makedirs(config_dir, exist_ok=True)
            
            # Vytvorenie súboru s makrami
            macros_file = config_dir / f"macros.{profile_id}"
            
            with open(macros_file, 'w') as f:
                f.write(profile["macro_template"])
                
            return str(macros_file)
            
        except Exception as e:
            logger.error(f"Chyba pri vytváraní RPM makier: {e}")
            return None
