#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import tempfile
import shutil
import logging
import re
import glob
from pathlib import Path

# Nastavenie úrovne logovania pre tento modul
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Ensure file handler is created to capture logs to a file
file_handler = logging.FileHandler('rpm_builder_debug.log')
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

class RPMBuilder:
    """Trieda pre tvorbu RPM balíkov z AppImage súborov"""
    
    def __init__(self, app_name, app_version, extracted_dir, icon_path=None):
        """
        Inicializuje builder pre tvorbu RPM balíka
        
        Args:
            app_name (str): Názov aplikácie
            app_version (str): Verzia aplikácie
            extracted_dir (str/Path): Cesta k priečinku s extrahovanými súbormi z AppImage
            icon_path (str/Path, optional): Cesta k ikone aplikácie
        """
        self.app_name = app_name
        self.app_version = app_version
        self.extracted_dir = Path(extracted_dir)
        
        # Normalizácia názvu balíka pre RPM
        self.rpm_name = self._normalize_name(app_name)
        
        # Pracovné adresáre
        self.rpmbuild_root = None
        self.spec_file = None
        
        # Automatické hľadanie ikony, ak nebola explicitne zadaná
        self.icon_path = Path(icon_path) if icon_path else self._find_icon_in_extracted_dir()
        
        # Kde sa nachádza squashfs-root, ak existuje
        squashfs_root = self.extracted_dir / "squashfs-root"
        if squashfs_root.exists():
            self.app_dir = squashfs_root
        else:
            self.app_dir = self.extracted_dir
            
        # Vytvorenie dočasného priečinka pre rpmbuild
        # self._create_rpmbuild_structure()
            
    def _find_icon_in_extracted_dir(self):
        """
        Automaticky hľadá ikonu v extrahovanom AppImage priečinku
        
        Returns:
            Path: Cesta k nájdenej ikone alebo None ak sa ikona nenašla
        """
        logger.info(f"Hľadám ikonu v extrahovanom AppImage priečinku: {self.extracted_dir}")
        
        # Najprv hľadaj v squashfs-root ak existuje
        squashfs_root = self.extracted_dir / "squashfs-root"
        search_dir = squashfs_root if squashfs_root.exists() else self.extracted_dir
        
        # Prioritné ikony na kontrolu
        # 1. .DirIcon - špeciálny súbor používaný v AppImage
        dir_icon = search_dir / ".DirIcon"
        if dir_icon.exists():
            logger.info(f"Nájdená .DirIcon ikona: {dir_icon}")
            return dir_icon
            
        # 2. Hľadaj ikony v koreňovom adresári
        icon_extensions = ['.png', '.svg', '.jpg', '.jpeg', '.ico']
        for ext in icon_extensions:
            icons = list(search_dir.glob(f"*{ext}"))
            if icons:
                logger.info(f"Nájdená ikona v koreňovom adresári: {icons[0]}")
                return icons[0]
                
        # 3. Hľadaj ikony v .local/share/icons
        icon_dir = search_dir / ".local/share/icons"
        if icon_dir.exists():
            for ext in icon_extensions:
                icons = list(icon_dir.glob(f"**/*{ext}"))
                if icons:
                    logger.info(f"Nájdená ikona v .local/share/icons: {icons[0]}")
                    return icons[0]
                    
        # 4. Hľadaj ikony v /usr/share/icons
        icon_dir = search_dir / "usr/share/icons"
        if icon_dir.exists():
            for ext in icon_extensions:
                icons = list(icon_dir.glob(f"**/*{ext}"))
                if icons:
                    logger.info(f"Nájdená ikona v usr/share/icons: {icons[0]}")
                    return icons[0]
                    
        # 5. Hľadaj ikony kdekoľvek v extrahovanom priečinku
        for ext in icon_extensions:
            icons = list(search_dir.glob(f"**/*{ext}"))
            if icons:
                logger.info(f"Nájdená ikona v extrahovanom priečinku: {icons[0]}")
                return icons[0]
                
        logger.warning("Nebola nájdená žiadna ikona v extrahovanom priečinku AppImage")
        return None
        
    def _normalize_name(self, name):
        """
        Normalizuje názov aplikácie pre použitie v RPM
        
        Args:
            name (str): Pôvodný názov
            
        Returns:
            str: Normalizovaný názov
        """
        # Odstránenie nepovolených znakov, nahradenie medzier pomlčkami
        normalized = re.sub(r'[^a-zA-Z0-9.+_-]', '-', name)
        # Odstránenie viacnásobných pomlčiek
        normalized = re.sub(r'-+', '-', normalized)
        # Odstránenie pomlčiek na začiatku a konci
        normalized = normalized.strip('-')
        # Konverzia na lowercase (štandardný formát pre RPM)
        normalized = normalized.lower()
        
        return normalized
        
    def _create_rpmbuild_structure(self):
        """
        Vytvorí štandardnú štruktúru adresárov pre rpmbuild
        
        Returns:
            Path: Koreňový adresár rpmbuild
        """
        # Vytvorenie dočasného adresára
        rpmbuild_root = Path(tempfile.mkdtemp(prefix="rpmbuild_"))
        
        # Vytvorenie požadovaných adresárov
        dirs = ["BUILD", "RPMS", "SOURCES", "SPECS", "SRPMS", "BUILDROOT"]
        for d in dirs:
            (rpmbuild_root / d).mkdir(exist_ok=True)
            
        self.rpmbuild_root = rpmbuild_root
        return rpmbuild_root
        
    def _create_spec_file(self, requires=None, description=None, license="Unspecified", 
                         summary=None, group="Applications/System", url=None):
        """
        Vytvorí RPM spec súbor
        
        Args:
            requires (list, optional): Zoznam závislostí balíka
            description (str, optional): Popis aplikácie
            license (str, optional): Licencia aplikácie
            summary (str, optional): Krátky popis aplikácie
            group (str, optional): Skupina balíka
            url (str, optional): Domovská stránka aplikácie
            
        Returns:
            Path: Cesta k vytvorenému spec súboru
        """
        if self.rpmbuild_root is None:
            self._create_rpmbuild_structure()
            
        spec_dir = self.rpmbuild_root / "SPECS"
        spec_file = spec_dir / f"{self.rpm_name}.spec"
        
        # Určenie prípony ikony
        icon_ext = ""
        if self.icon_path:
            icon_ext = self.icon_path.suffix
            
        with open(spec_file, "w") as f:
            # Metadáta
            f.write(f"""Name:           {self.rpm_name}
Version:        {self.app_version}
Release:        1%{{?dist}}
Summary:        {summary or self.app_name}

License:        {license}
URL:            {url or 'https://appimage.org'}

BuildArch:      x86_64
AutoReqProv:    no
""")

            # Závislosti
            if requires and len(requires) > 0:
                for req in requires:
                    f.write(f"Requires:       {req}\n")
                    
            # Popis
            f.write(f"""
%description
{description or self.app_name}

%prep
# Nic sa nerobí

%build
# Nic sa nerobí

%install
mkdir -p %{{buildroot}}/opt/{self.rpm_name}
cp -r %{{_sourcedir}}/app/* %{{buildroot}}/opt/{self.rpm_name}/

# Vytvorenie spúšťača
mkdir -p %{{buildroot}}/usr/bin
echo '#!/bin/bash' > %{{buildroot}}/usr/bin/{self.rpm_name}
echo 'exec /opt/{self.rpm_name}/AppRun "$@"' >> %{{buildroot}}/usr/bin/{self.rpm_name}
chmod +x %{{buildroot}}/usr/bin/{self.rpm_name}

# Vytvorenie desktop súboru
mkdir -p %{{buildroot}}/usr/share/applications
echo '[Desktop Entry]' > %{{buildroot}}/usr/share/applications/{self.rpm_name}.desktop
echo 'Name={self.app_name}' >> %{{buildroot}}/usr/share/applications/{self.rpm_name}.desktop
""")

            # Doplnenie cesty k ikone
            if self.icon_path:
                dest_icon_filename = f"{self.rpm_name}{icon_ext}"
                f.write(f"echo 'Icon={self.rpm_name}' >> %{{buildroot}}/usr/share/applications/{self.rpm_name}.desktop\n")
                f.write(f"mkdir -p %{{buildroot}}/usr/share/pixmaps\n")
                f.write(f"cp %{{_sourcedir}}/icon{icon_ext} %{{buildroot}}/usr/share/pixmaps/{dest_icon_filename}\n")
            else:
                f.write(f"echo 'Icon=/opt/{self.rpm_name}/usr/share/icons/hicolor/scalable/apps/{self.app_name}' >> %{{buildroot}}/usr/share/applications/{self.rpm_name}.desktop\n")
            
            f.write(f"""echo 'Exec={self.rpm_name}' >> %{{buildroot}}/usr/share/applications/{self.rpm_name}.desktop
echo 'Terminal=false' >> %{{buildroot}}/usr/share/applications/{self.rpm_name}.desktop
echo 'Type=Application' >> %{{buildroot}}/usr/share/applications/{self.rpm_name}.desktop
echo 'Categories=Utility;' >> %{{buildroot}}/usr/share/applications/{self.rpm_name}.desktop

# Copy icons if available
mkdir -p %{{buildroot}}/usr/share/icons/hicolor/scalable/apps
if [ -f %{{_sourcedir}}/app/co.anysphere.cursor.png ]; then
    cp %{{_sourcedir}}/app/co.anysphere.cursor.png %{{buildroot}}/usr/share/icons/hicolor/scalable/apps/{self.rpm_name}.png
fi

%files
%defattr(-,root,root,-)
%dir /opt/{self.rpm_name}
%dir /usr/share/applications
%dir /usr/share/icons/hicolor/scalable/apps
/opt/{self.rpm_name}/*
/usr/bin/{self.rpm_name}
/usr/share/applications/{self.rpm_name}.desktop
/usr/share/icons/hicolor/scalable/apps/{self.rpm_name}.png
""")

            # Pridanie ikony do zoznamu súborov
            if self.icon_path:
                dest_icon_filename = f"{self.rpm_name}{icon_ext}"
                f.write(f"/usr/share/pixmaps/{dest_icon_filename}\n")
            
            f.write(f"""
%changelog
* {subprocess.check_output(['date', '+%a %b %d %Y'], text=True).strip()} AppImage2RPM <appimage2rpm> - {self.app_version}-1
- Initial RPM package from AppImage
""")
                
        self.spec_file = spec_file
        return spec_file
            
    def prepare_sources(self, desktop_file=None, categories=None):
        """
        Pripraví zdrojové súbory pre balík
        
        Args:
            desktop_file (Path, optional): Cesta k .desktop súboru
            categories (list, optional): Zoznam kategórií aplikácie
        
        Returns:
            bool: True ak bola príprava úspešná
        """
        if self.rpmbuild_root is None:
            self._create_rpmbuild_structure()
            
        source_dir = self.rpmbuild_root / "SOURCES"
        app_dir = source_dir / "app"
        app_dir.mkdir(exist_ok=True)
        
        # Kopírovanie obsahu AppImage súboru
        try:
            # Kopírovanie celého obsahu z squashfs-root
            squashfs_root = self.extracted_dir
            if (self.extracted_dir / "squashfs-root").exists():
                squashfs_root = self.extracted_dir / "squashfs-root"
                
            shutil.copytree(squashfs_root, app_dir, symlinks=True, dirs_exist_ok=True)
            
            # Kopírovanie ikony
            if self.icon_path and self.icon_path.exists():
                icon_ext = self.icon_path.suffix
                icon_dest = source_dir / f"icon{icon_ext}"
                shutil.copy2(self.icon_path, icon_dest)
                
            return True
            
        except Exception as e:
            logger.error(f"Chyba pri príprave zdrojov: {e}")
            return False
            
    def build_rpm(self, output_dir=None, requires=None, description=None, license="Unspecified", 
                 summary=None, group="Applications/System", url=None, desktop_file=None, categories=None):
        """
        Vytvorí RPM balík
        
        Args:
            output_dir (str, optional): Adresár pre výsledný RPM balík
            requires (list, optional): Zoznam závislostí balíka
            description (str, optional): Popis aplikácie
            license (str, optional): Licencia aplikácie
            summary (str, optional): Krátky popis aplikácie
            group (str, optional): Skupina balíka
            url (str, optional): Domovská stránka aplikácie
            desktop_file (Path, optional): Cesta k .desktop súboru
            categories (list, optional): Zoznam kategórií aplikácie
            
        Returns:
            Path: Cesta k vytvorenému RPM balíku alebo None v prípade chyby
        """
        try:
            # Vytvorenie rpmbuild štruktúry
            if self.rpmbuild_root is None:
                self._create_rpmbuild_structure()
                
            # Príprava zdrojov
            logger.info("Príprava zdrojových súborov pre RPM balík")
            if not self.prepare_sources(desktop_file, categories):
                raise RuntimeError("Chyba pri príprave zdrojových súborov")
                
            # Vytvorenie spec súboru
            logger.info("Vytvorenie spec súboru pre RPM balík")
            self._create_spec_file(requires, description, license, summary, group, url)
            
            # Zostavenie RPM balíka
            logger.info(f"Spúšťam rpmbuild na {self.spec_file}")
            cmd = [
                "rpmbuild",
                "-bb",
                "-v",  # Verbose output
                "--define", f"_topdir {self.rpmbuild_root}",
                str(self.spec_file)
            ]
            
            logger.info(f"Príkaz rpmbuild: {' '.join(cmd)}")
            
            process = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            logger.info(f"rpmbuild returncode: {process.returncode}")
            if process.stdout:
                logger.info(f"rpmbuild stdout: {process.stdout[:1000]}")
            if process.stderr:
                logger.error(f"rpmbuild stderr: {process.stderr}")
            
            if process.returncode != 0:
                logger.error(f"Chyba pri zostavení RPM: {process.stderr}")
                raise RuntimeError(f"Chyba pri zostavení RPM: {process.stderr}")
                
            # Nájsť vytvorený RPM balík
            logger.info(f"Hľadám vytvorený RPM balík v {self.rpmbuild_root}/RPMS/x86_64")
            rpm_glob_pattern = f"{self.rpmbuild_root}/RPMS/x86_64/{self.rpm_name}-{self.app_version}*.rpm"
            logger.info(f"Použitý vzor pre glob: {rpm_glob_pattern}")
            rpm_files = list(glob.glob(rpm_glob_pattern))
            logger.info(f"Nájdené RPM súbory: {rpm_files}")
            
            if not rpm_files:
                # Skús nájsť akékoľvek RPM súbory
                all_rpms = list(glob.glob(f"{self.rpmbuild_root}/RPMS/**/*.rpm", recursive=True))
                logger.error(f"RPM balík nebol nájdený v očakávanej ceste. Všetky nájdené RPM súbory: {all_rpms}")
                raise FileNotFoundError(f"RPM balík nebol nájdený. Vzor: {rpm_glob_pattern}")
                
            rpm_file = Path(rpm_files[0])
            logger.info(f"Úspešne vytvorený RPM balík: {rpm_file}")
            
            # Kopírovanie výsledného balíka do výstupného adresára
            if output_dir:
                output_path = Path(output_dir) / rpm_file.name
                os.makedirs(output_dir, exist_ok=True)
                logger.info(f"Kopírujem {rpm_file} do {output_path}")
                shutil.copy2(rpm_file, output_path)
                logger.info(f"RPM balík úspešne skopírovaný do {output_path}")
                return output_path
            
            return rpm_file
            
        except Exception as e:
            logger.error(f"Chyba pri vytváraní RPM balíka: {e}", exc_info=True)
            # List files in BUILDROOT directory to see what was created
            if self.rpmbuild_root and (self.rpmbuild_root / "BUILD").exists():
                try:
                    build_dirs = list((self.rpmbuild_root / "BUILD").glob("*"))
                    logger.info(f"Obsah BUILD adresára: {build_dirs}")
                    for build_dir in build_dirs:
                        if build_dir.is_dir() and (build_dir / "BUILDROOT").exists():
                            buildroot_dirs = list((build_dir / "BUILDROOT").glob("*"))
                            logger.info(f"Obsah BUILDROOT adresára {build_dir}: {buildroot_dirs}")
                except Exception as ex:
                    logger.error(f"Chyba pri výpise adresárov: {ex}")
            return None
            
    def cleanup(self):
        """Vyčistí dočasné súbory"""
        if self.rpmbuild_root and self.rpmbuild_root.exists():
            shutil.rmtree(self.rpmbuild_root, ignore_errors=True)
            self.rpmbuild_root = None
            self.spec_file = None
