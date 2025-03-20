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
        Automaticky hľadá ikonu v extrahovanom priečinku aplikácie
        
        Returns:
            Path: Cesta k nájdenej ikone alebo None ak sa ikona nenašla
        """
        if not self.extracted_dir.exists():
            logger.warning(f"Priečinok {self.extracted_dir} neexistuje")
            return None
            
        # Najprv skontrolujeme obvyklú cestu v AppImage štruktúre
        icon_paths = []
        
        # 1. Skúsime nájsť ikony v štandardných adresároch
        standard_icon_dirs = [
            self.app_dir / "usr" / "share" / "icons",
            self.app_dir / "usr" / "share" / "pixmaps",
            self.app_dir / "usr" / "share" / "icons" / "hicolor" / "scalable" / "apps",
            self.app_dir / ".DirIcon",
            self.app_dir
        ]
        
        # 2. Hľadáme ikony podľa názvu aplikácie
        icon_names = [
            self.app_name.lower(),
            self.rpm_name.lower(),
            "icon",
            "app",
            "application",
            "logo"
        ]
        
        # Hľadanie v štandardných adresároch
        for icon_dir in standard_icon_dirs:
            if not isinstance(icon_dir, Path):
                icon_dir = Path(icon_dir)
                
            if not icon_dir.exists():
                continue
                
            # Ak je to súbor (napr. .DirIcon), použijeme ho
            if icon_dir.is_file():
                icon_paths.append(icon_dir)
                continue
                
            # Hľadáme ikony v adresári
            for icon_name in icon_names:
                for ext in [".svg", ".png", ".xpm", ".ico"]:
                    icon_path = icon_dir / f"{icon_name}{ext}"
                    if icon_path.exists():
                        icon_paths.append(icon_path)
                        
        # 3. Rekurzívne hľadanie ikon v celom adresári
        if not icon_paths:
            # Prioritné prípony
            exts = [".svg", ".png", ".xpm", ".ico"]
            all_icons = []
            
            # Rekurzívne hľadanie všetkých súborov s podporovanou príponou
            for ext in exts:
                for root, _, files in os.walk(self.app_dir):
                    root_path = Path(root)
                    for file in files:
                        if file.lower().endswith(ext):
                            all_icons.append(root_path / file)
            
            # Prioritizácia ikon podľa názvu
            for icon_name in icon_names:
                for icon_path in all_icons:
                    if icon_name in icon_path.stem.lower():
                        icon_paths.append(icon_path)
                        
            # Ak sme nenašli žiadnu ikonu podľa názvu, použijeme prvú nájdenú
            if not icon_paths and all_icons:
                icon_paths.append(all_icons[0])
                
        # Výber najlepšej ikony
        if icon_paths:
            # Prioritizácia SVG > PNG > iné formáty
            for ext in [".svg", ".png", ".xpm", ".ico"]:
                for icon_path in icon_paths:
                    if icon_path.suffix.lower() == ext:
                        logger.info(f"Nájdená ikona: {icon_path}")
                        return icon_path
                        
            # Ak sme nedostali zhodu podľa formátu, vrátime prvú nájdenú
            logger.info(f"Nájdená ikona: {icon_paths[0]}")
            return icon_paths[0]
            
        logger.warning("Nenájdená žiadna ikona pre aplikáciu")
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
cat > %{{buildroot}}/usr/bin/{self.rpm_name} << 'EOF'
#!/bin/bash
cd /opt/{self.rpm_name}
if [ -x /opt/{self.rpm_name}/AppRun ]; then
    exec /opt/{self.rpm_name}/AppRun "$@"
else
    # Skontrolovať, či existuje iný spustiteľný súbor
    for executable in $(find /opt/{self.rpm_name} -type f -executable ! -path "*/\.*" | sort); do
        if [ -f "$executable" ] && [ -x "$executable" ]; then
            exec "$executable" "$@"
            break
        fi
    done
    echo "Nenájdený žiadny spustiteľný súbor v /opt/{self.rpm_name}"
    exit 1
fi
EOF
chmod +x %{{buildroot}}/usr/bin/{self.rpm_name}

# Vytvorenie desktop súboru
mkdir -p %{{buildroot}}/usr/share/applications
cat > %{{buildroot}}/usr/share/applications/{self.rpm_name}.desktop << EOF
[Desktop Entry]
Name={self.app_name}
Exec={self.rpm_name}
Terminal=false
Type=Application
Categories=Utility;
EOF

""")

            # Doplnenie cesty k ikone
            if self.icon_path:
                dest_icon_filename = f"{self.rpm_name}{icon_ext}"
                f.write(f"echo 'Icon={dest_icon_filename}' >> %{{buildroot}}/usr/share/applications/{self.rpm_name}.desktop\n")
                f.write(f"mkdir -p %{{buildroot}}/usr/share/pixmaps\n")
                f.write(f"cp %{{_sourcedir}}/icon{icon_ext} %{{buildroot}}/usr/share/pixmaps/{dest_icon_filename}\n")
            else:
                # Hľadá ikony v app_dir a používa prvú nájdenú
                f.write(f"""
# Hľadanie ikony v aplikácií
for ICON_PATH in $(find %{{_sourcedir}}/app -type f -name "*.png" -o -name "*.svg" -o -name "*.ico" | sort); do
    if [ -n "$ICON_PATH" ]; then
        ICON_BASENAME=$(basename "$ICON_PATH")
        ICON_EXT="${{ICON_BASENAME##*.}}"
        mkdir -p %{{buildroot}}/usr/share/pixmaps
        cp "$ICON_PATH" %{{buildroot}}/usr/share/pixmaps/{self.rpm_name}.$ICON_EXT
        echo "Icon={self.rpm_name}.$ICON_EXT" >> %{{buildroot}}/usr/share/applications/{self.rpm_name}.desktop
        break
    fi
done

# Ak nebola nájdená žiadna ikona, použije sa predvolená
if ! grep -q "Icon=" %{{buildroot}}/usr/share/applications/{self.rpm_name}.desktop; then
    echo "Icon={self.rpm_name}" >> %{{buildroot}}/usr/share/applications/{self.rpm_name}.desktop
fi
""")

            # Zoznam súborov
            f.write(f"""
%files
%defattr(-,root,root,-)
%dir /opt/{self.rpm_name}
/opt/{self.rpm_name}/*
/usr/bin/{self.rpm_name}
/usr/share/applications/{self.rpm_name}.desktop
""")

            # Pridanie ikôn do zoznamu súborov
            if self.icon_path:
                dest_icon_filename = f"{self.rpm_name}{icon_ext}"
                f.write(f"/usr/share/pixmaps/{dest_icon_filename}\n")
            else:
                f.write(f"""
# Podmienene pridanie ikony ak existuje
if [ -f %{{buildroot}}/usr/share/pixmaps/{self.rpm_name}.* ]; then
    /usr/share/pixmaps/{self.rpm_name}.*
fi
""")
            
            f.write(f"""
%changelog
* {subprocess.check_output(['date', '+%a %b %d %Y'], text=True).strip()} AppImage2RPM <appimage2rpm> - {self.app_version}-1
- Initial RPM package
""")
                
        self.spec_file = spec_file
        logger.info(f"Vytvorený spec súbor: {spec_file}")
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
            
            # Kontrola existencie spustiteľného súboru
            app_dir = self.rpmbuild_root / "SOURCES" / "app"
            app_run_path = app_dir / "AppRun"
            main_executable = None
            
            # Ak neexistuje AppRun, nájdeme hlavný spustiteľný súbor
            if not app_run_path.exists():
                logger.info("AppRun súbor nebol nájdený, hľadám hlavný spustiteľný súbor")
                executable_files = []
                
                # Nájdenie všetkých spustiteľných súborov v app_dir
                for root, _, files in os.walk(app_dir):
                    root_path = Path(root)
                    for file in files:
                        file_path = root_path / file
                        if os.access(file_path, os.X_OK) and file_path.is_file():
                            # Ak názov binárky zodpovedá názvu aplikácie, prioritizujeme
                            if file.lower() == self.rpm_name.lower() or file.lower() == self.app_name.lower():
                                main_executable = file_path
                                break
                            executable_files.append(file_path)
                
                # Ak nebol nájdený súbor so zhodným názvom, použijeme prvý nájdený
                if not main_executable and executable_files:
                    main_executable = executable_files[0]
                
                if main_executable:
                    # Získať relatívnu cestu od app_dir
                    rel_path = main_executable.relative_to(app_dir)
                    logger.info(f"Nájdený hlavný spustiteľný súbor: {rel_path}")
                    
                    # Vytvorenie AppRun súboru
                    with open(app_run_path, 'w') as f:
                        f.write("#!/bin/bash\n")
                        f.write(f"cd \"$(dirname \"$0\")\"\n")  # Prejdeme do adresára s aplikáciou
                        f.write(f"exec ./{rel_path} \"$@\"\n")
                    
                    # Nastavenie práv na spustenie
                    os.chmod(app_run_path, 0o755)
                    logger.info(f"Vytvorený AppRun súbor s odkazom na {rel_path}")
                else:
                    logger.warning("Nebol nájdený žiadny spustiteľný súbor. RPM balík nemusí fungovať správne.")
                    # Vytvoríme aspoň prázdny AppRun, aby sa RPM zostavil
                    with open(app_run_path, 'w') as f:
                        f.write("#!/bin/bash\n")
                        f.write("echo 'Nenájdený žiadny spustiteľný súbor'\n")
                        f.write("exit 1\n")
                    os.chmod(app_run_path, 0o755)
                
            # Vytvorenie spec súboru s vhodným entryscrpt
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
                logger.info(f"Hľadám všetky RPM v {self.rpmbuild_root}/RPMS/: {all_rpms}")
                
                if all_rpms:
                    rpm_file = Path(all_rpms[0])
                else:
                    logger.error(f"RPM balík nebol nájdený v očakávanej ceste.")
                    raise FileNotFoundError(f"RPM balík nebol nájdený. Vzor: {rpm_glob_pattern}")
            else:
                rpm_file = Path(rpm_files[0])
                
            logger.info(f"Úspešne vytvorený RPM balík: {rpm_file}")
            
            # Kopírovanie výsledného balíka do výstupného adresára
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
                output_path = Path(output_dir) / rpm_file.name
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
