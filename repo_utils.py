#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import tempfile
import shutil
import logging
import re
import glob
import configparser
import toml
from pathlib import Path
import datetime


class RepoManager:
    """Trieda pre správu a publikovanie do RPM repozitárov"""
    
    def __init__(self, repo_root=None):
        """
        Inicializácia správcu repozitárov
        
        Args:
            repo_root (str, optional): Koreňový adresár repozitára
        """
        self.repo_root = repo_root
        self.repo_config = {}
        self.repo_profiles = {}
        self.load_profiles()
        
    def load_profiles(self):
        """Načíta profily repozitárov z konfiguračného súboru"""
        config_paths = [
            Path.home() / ".config" / "appimage2rpm" / "repos.toml",
            Path("/etc/appimage2rpm/repos.toml")
        ]
        
        for config_path in config_paths:
            if config_path.exists():
                try:
                    self.repo_profiles = toml.load(config_path)
                    return
                except Exception as e:
                    logging.error(f"Chyba pri načítaní profilov repozitárov: {e}")
        
        # Vytvorenie predvolených profilov, ak neexistujú
        self.repo_profiles = {
            "copr": {
                "name": "Fedora COPR",
                "type": "copr",
                "description": "Fedora COPR (Cool Other Package Repo)",
                "commands": {
                    "create": "copr-cli create {repo_name} --chroot fedora-{fedora_version}-x86_64",
                    "add": "copr-cli add-package-scm {repo_name} --name {pkg_name} --clone-url {clone_url} --subdir {pkg_dir} --spec {pkg_spec}",
                    "build": "copr-cli build {repo_name} {srpm_path}"
                }
            },
            "local": {
                "name": "Lokálny repozitár",
                "type": "createrepo",
                "description": "Lokálny RPM repozitár s createrepo",
                "commands": {
                    "create": "mkdir -p {repo_path}",
                    "add": "cp {rpm_path} {repo_path}/",
                    "update": "createrepo --update {repo_path}"
                }
            },
            "ocs": {
                "name": "Open Build Service",
                "type": "obs",
                "description": "openSUSE Open Build Service",
                "commands": {
                    "create": "osc mkpac {pkg_name}",
                    "checkout": "osc checkout {project}/{pkg_name}",
                    "add": "osc add {rpm_path}",
                    "commit": "osc commit -m 'Initial import from AppImage2RPM'"
                }
            }
        }
        
    def save_profiles(self):
        """Uloží profily repozitárov do konfiguračného súboru"""
        config_dir = Path.home() / ".config" / "appimage2rpm"
        os.makedirs(config_dir, exist_ok=True)
        
        config_path = config_dir / "repos.toml"
        
        try:
            with open(config_path, 'w') as f:
                toml.dump(self.repo_profiles, f)
            return True
        except Exception as e:
            logging.error(f"Chyba pri ukladaní profilov repozitárov: {e}")
            return False
    
    def _check_command_exists(self, command):
        """
        Kontroluje, či príkaz existuje v systéme
        
        Args:
            command (str): Názov príkazu na kontrolu
            
        Returns:
            bool: True ak príkaz existuje, inak False
        """
        try:
            # Kontrola, či príkaz existuje pomocou ktorejkoľvek z týchto metód
            result = subprocess.run(
                ["which", command],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            return result.returncode == 0
        except Exception:
            return False

    def _check_copr_auth(self):
        """
        Kontroluje, či existuje konfigurácia pre COPR a či je používateľ autentifikovaný
        
        Returns:
            tuple: (bool, str) - (je_autentifikovaný, chybová_správa)
        """
        config_path = os.path.expanduser("~/.config/copr")
        
        if not os.path.exists(config_path):
            return False, ("Konfigurácia COPR nebola nájdená. Vytvorte súbor ~/.config/copr "
                          "s API tokenom z https://copr.fedorainfracloud.org/api/")
                          
        # Kontrola obsahu konfiguračného súboru
        try:
            with open(config_path, 'r') as f:
                config_content = f.read()
                
            if "login" not in config_content or "token" not in config_content:
                return False, ("Neplatná konfigurácia COPR. V súbore ~/.config/copr "
                              "chýba login alebo token. Navštívte https://copr.fedorainfracloud.org/api/")
                              
            return True, ""
        except Exception as e:
            return False, f"Chyba pri kontrole COPR konfigurácie: {e}"

    def create_repo(self, profile_name, repo_name, repo_path=None, fedora_version=None):
        """
        Vytvorí nový repozitár
        
        Args:
            profile_name (str): Názov profilu repozitára
            repo_name (str): Názov repozitára
            repo_path (str, optional): Cesta k repozitáru (pre lokálne repozitáre)
            fedora_version (str, optional): Verzia Fedory (pre COPR)
            
        Returns:
            bool: True ak repozitár bol úspešne vytvorený
            
        Raises:
            Exception: Ak dôjde k chybe pri vytváraní repozitára
        """
        if profile_name not in self.repo_profiles:
            raise ValueError(f"Neznámy profil repozitára: {profile_name}")
            
        profile = self.repo_profiles[profile_name]
        
        if profile["type"] == "copr" and not fedora_version:
            fedora_version = "41"  # Predvolená verzia
            
        if profile["type"] == "createrepo" and not repo_path:
            repo_path = os.path.expanduser(f"~/rpmbuild/repos/{repo_name}")
            
        # Kontrola, či sú potrebné nástroje nainštalované
        if profile["type"] == "copr":
            if not self._check_command_exists("copr-cli"):
                raise Exception("Nástroj 'copr-cli' nie je nainštalovaný. Nainštalujte ho príkazom 'sudo dnf install copr-cli'")
                
            # Kontrola autentifikácie pre COPR
            is_auth, auth_message = self._check_copr_auth()
            if not is_auth:
                raise Exception(f"Chyba autentifikácie pre COPR: {auth_message}")
                
        elif profile["type"] == "createrepo":
            if not self._check_command_exists("createrepo"):
                raise Exception("Nástroj 'createrepo' nie je nainštalovaný. Nainštalujte ho príkazom 'sudo dnf install createrepo'")
                
        # Substitúcia parametrov v príkaze
        create_cmd = profile["commands"]["create"].format(
            repo_name=repo_name,
            repo_path=repo_path,
            fedora_version=fedora_version
        )
        
        try:
            # Spustenie príkazu pre vytvorenie repozitára
            process = subprocess.run(
                create_cmd,
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Uloženie konfigurácie repozitára
            self.repo_config = {
                "profile": profile_name,
                "name": repo_name,
                "path": repo_path,
                "fedora_version": fedora_version,
                "created": datetime.datetime.now().isoformat()
            }
            
            return True
            
        except subprocess.CalledProcessError as e:
            logging.error(f"Chyba pri vytváraní repozitára: {e.stderr}")
            return False
            
        except Exception as e:
            logging.error(f"Chyba pri vytváraní repozitára: {e}")
            return False
    
    def publish_rpm(self, rpm_path, pkg_name=None, repo_name=None):
        """
        Publikuje RPM balík do repozitára
        
        Args:
            rpm_path (str): Cesta k RPM balíku
            pkg_name (str, optional): Názov balíka
            repo_name (str, optional): Názov repozitára
            
        Returns:
            bool: True ak publikovanie bolo úspešné
        """
        rpm_path = Path(rpm_path)
        
        if not rpm_path.exists():
            raise FileNotFoundError(f"RPM balík nenájdený: {rpm_path}")
            
        if not pkg_name:
            # Získanie názvu balíka z RPM súboru
            pkg_name = rpm_path.stem.split('-')[0]
            
        if not repo_name and self.repo_config:
            # Použitie konfigurácie z vytvoreného repozitára
            profile_name = self.repo_config.get("profile")
            repo_name = self.repo_config.get("name")
            repo_path = self.repo_config.get("path")
        else:
            # Použitie predvoleného profilu
            profile_name = "local"
            repo_name = "local-repo"
            repo_path = os.path.expanduser("~/rpmbuild/repos/local-repo")
            
        if profile_name not in self.repo_profiles:
            raise ValueError(f"Neznámy profil repozitára: {profile_name}")
            
        profile = self.repo_profiles[profile_name]
        
        try:
            if profile["type"] == "createrepo":
                # Lokálny repozitár - kopírovanie + createrepo
                
                # Vytvorenie adresára, ak neexistuje
                os.makedirs(repo_path, exist_ok=True)
                
                # Kopírovanie RPM do repozitára
                add_cmd = profile["commands"]["add"].format(
                    rpm_path=rpm_path,
                    repo_path=repo_path,
                    pkg_name=pkg_name
                )
                
                subprocess.run(
                    add_cmd,
                    shell=True,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Aktualizácia metadát repozitára
                update_cmd = profile["commands"]["update"].format(
                    repo_path=repo_path
                )
                
                subprocess.run(
                    update_cmd,
                    shell=True,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                return True
                
            elif profile["type"] == "copr":
                # COPR repozitár - vytvorenie SRPM a odoslanie
                # COPR build command
                build_cmd = profile["commands"]["build"].format(
                    repo_name=repo_name,
                    srpm_path=rpm_path
                )
                
                subprocess.run(
                    build_cmd,
                    shell=True,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                return True
                
            elif profile["type"] == "obs":
                # OBS repozitár - vytvorenie projektu a balíka
                checkout_cmd = profile["commands"]["checkout"].format(
                    project="home:appimage2rpm",
                    pkg_name=pkg_name
                )
                
                subprocess.run(
                    checkout_cmd,
                    shell=True,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                add_cmd = profile["commands"]["add"].format(
                    rpm_path=rpm_path
                )
                
                subprocess.run(
                    add_cmd,
                    shell=True,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                commit_cmd = profile["commands"]["commit"]
                
                subprocess.run(
                    commit_cmd,
                    shell=True,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                return True
                
            else:
                logging.error(f"Nepodporovaný typ repozitára: {profile['type']}")
                return False
                
        except subprocess.CalledProcessError as e:
            logging.error(f"Chyba pri publikovaní RPM: {e.stderr}")
            return False
            
        except Exception as e:
            logging.error(f"Chyba pri publikovaní RPM: {e}")
            return False
            
    def generate_repo_config(self, repo_type="local", repo_name="appimage2rpm"):
        """
        Vygeneruje konfiguráciu pre použitie lokálneho repozitára
        
        Args:
            repo_type (str): Typ repozitára (local, copr, obs)
            repo_name (str): Názov repozitára
            
        Returns:
            str: Konfigurácia repozitára pre /etc/yum.repos.d/
        """
        if repo_type == "local":
            repo_path = self.repo_config.get("path", os.path.expanduser(f"~/rpmbuild/repos/{repo_name}"))
            
            return f"""[{repo_name}]
name={repo_name} - AppImage2RPM Local Repository
baseurl=file://{repo_path}
enabled=1
gpgcheck=0
"""
        elif repo_type == "copr":
            return f"""[copr:{repo_name}]
name=Copr repo for {repo_name}
baseurl=https://copr-be.cloud.fedoraproject.org/results/{repo_name}/fedora-$releasever-$basearch/
type=rpm-md
skip_if_unavailable=True
gpgcheck=1
gpgkey=https://copr-be.cloud.fedoraproject.org/results/{repo_name}/pubkey.gpg
repo_gpgcheck=0
enabled=1
enabled_metadata=1
"""
        else:
            return "# Nepodporovaný typ repozitára pre automatickú konfiguráciu"
            
    def save_repo_config(self, repo_type="local", repo_name="appimage2rpm"):
        """
        Uloží konfiguráciu repozitára do súboru
        
        Args:
            repo_type (str): Typ repozitára (local, copr, obs)
            repo_name (str): Názov repozitára
            
        Returns:
            str: Cesta k vytvorenému konfiguračnému súboru alebo None
        """
        config_content = self.generate_repo_config(repo_type, repo_name)
        
        config_dir = Path.home() / ".config" / "appimage2rpm"
        os.makedirs(config_dir, exist_ok=True)
        
        config_path = config_dir / f"{repo_name}.repo"
        
        try:
            with open(config_path, 'w') as f:
                f.write(config_content)
            return str(config_path)
        except Exception as e:
            logging.error(f"Chyba pri ukladaní konfigurácie repozitára: {e}")
            return None
            
    def get_available_profiles(self):
        """
        Vráti zoznam dostupných profilov repozitárov
        
        Returns:
            list: Zoznam názvov profilov
        """
        return list(self.repo_profiles.keys())
        
    def get_profile_info(self, profile_name):
        """
        Vráti informácie o profile repozitára
        
        Args:
            profile_name (str): Názov profilu
            
        Returns:
            dict: Informácie o profile alebo None
        """
        return self.repo_profiles.get(profile_name)
