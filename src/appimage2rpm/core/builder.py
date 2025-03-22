#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module for building RPM packages from extracted AppImage content.
"""

import os
import shutil
import tempfile
import subprocess
import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class RPMBuilder:
    """
    Class for building RPM packages from extracted AppImage content.
    
    This class handles creating spec files, organizing files, and building
    RPM packages with proper icon handling.
    """
    
    def __init__(
        self,
        app_name: str,
        app_version: str,
        extracted_dir: Path,
        icon_paths: Optional[List[Path]] = None,
        app_release: str = "1",
        output_dir: Optional[str] = None
    ) -> None:
        """
        Initialize the RPM builder.
        
        Args:
            app_name: Application name
            app_version: Application version
            extracted_dir: Path to the extracted AppImage content
            icon_paths: List of icon paths in priority order
            app_release: RPM release number
            output_dir: Directory to save the RPM package
            
        Raises:
            ValueError: If app_name or app_version is empty or if extracted_dir doesn't exist
        """
        if not app_name:
            raise ValueError("Application name cannot be empty")
        if not app_version:
            raise ValueError("Application version cannot be empty")
        
        self.app_name = app_name
        self.app_version = app_version
        self.app_release = app_release
        
        # Sanitize the app name for use in RPM
        self.rpm_name = self._sanitize_name(app_name)
        
        if not extracted_dir or not os.path.exists(extracted_dir):
            raise ValueError(f"Extracted directory does not exist: {extracted_dir}")
            
        self.extracted_dir = Path(extracted_dir)
        self.icon_paths = icon_paths or []
        
        # If output directory is not specified, use the current directory
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path.cwd()
            
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Build directory for RPM
        self.rpm_build_dir = None
        self.spec_file = None
        self.selected_icon = None
        self.selected_icon_ext = None
        self.icon_install_paths = []

    def select_best_icon(self) -> Optional[Path]:
        """
        Select the best icon from the provided icon paths.
        
        Prioritizes SVG > PNG > XPM and prefers larger sizes for PNG.
        
        Returns:
            Path: The selected icon path or None if no icons are available
        """
        if not self.icon_paths:
            logger.warning("No icon paths provided")
            return None
            
        logger.info(f"Selecting best icon from {len(self.icon_paths)} options")
        
        # Prefer SVG icons
        svg_icons = [p for p in self.icon_paths if p.suffix.lower() == '.svg']
        if svg_icons:
            self.selected_icon = svg_icons[0]
            self.selected_icon_ext = '.svg'
            logger.info(f"Selected SVG icon: {self.selected_icon}")
            return self.selected_icon
            
        # Then prefer PNG icons (try to get largest size)
        png_icons = [p for p in self.icon_paths if p.suffix.lower() == '.png']
        if png_icons:
            # Try to determine the size from the file path
            sized_png_icons = []
            for icon in png_icons:
                size_match = re.search(r'(\d+)x\d+', str(icon))
                if size_match:
                    sized_png_icons.append((int(size_match.group(1)), icon))
                else:
                    # If size cannot be determined, assume 48
                    sized_png_icons.append((48, icon))
                    
            # Sort by size (descending)
            if sized_png_icons:
                self.selected_icon = sorted(sized_png_icons, key=lambda x: -x[0])[0][1]
                self.selected_icon_ext = '.png'
                logger.info(f"Selected PNG icon: {self.selected_icon}")
                return self.selected_icon
            
            # If no sized icons found, just take the first PNG
            self.selected_icon = png_icons[0]
            self.selected_icon_ext = '.png'
            logger.info(f"Selected PNG icon (no size info): {self.selected_icon}")
            return self.selected_icon
            
        # Lastly, use any other icon format
        if self.icon_paths:
            self.selected_icon = self.icon_paths[0]
            self.selected_icon_ext = self.selected_icon.suffix
            logger.info(f"Selected fallback icon: {self.selected_icon}")
            return self.selected_icon
            
        logger.warning("No suitable icon found")
        return None

    def prepare_build_dir(self) -> Path:
        """
        Prepare the RPM build directory structure.
        
        Creates the necessary directories and copies files.
        
        Returns:
            Path: Path to the build directory
        """
        logger.info("Preparing RPM build directory")
        
        # Create a temporary build directory
        self.rpm_build_dir = Path(tempfile.mkdtemp(prefix=f"{self.rpm_name}_build_"))
        logger.info(f"Created build directory: {self.rpm_build_dir}")
        
        # Create RPM build structure
        source_dir = self.rpm_build_dir / "SOURCES"
        source_dir.mkdir(exist_ok=True)
        
        specs_dir = self.rpm_build_dir / "SPECS"
        specs_dir.mkdir(exist_ok=True)
        
        # Create directories for the application
        app_dir = source_dir / self.rpm_name
        app_dir.mkdir(exist_ok=True)
        
        bin_dir = app_dir / "usr" / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        
        share_dir = app_dir / "usr" / "share"
        share_dir.mkdir(parents=True, exist_ok=True)
        
        applications_dir = share_dir / "applications"
        applications_dir.mkdir(exist_ok=True)
        
        # Copy AppImage content
        logger.info(f"Copying AppImage content to build directory")
        
        # Create the main executable script
        logger.info(f"Creating executable script in {bin_dir}")
        exec_script = bin_dir / self.rpm_name
        with open(exec_script, 'w') as f:
            f.write(f"""#!/bin/sh
exec /usr/lib/{self.rpm_name}/{self.rpm_name} "$@"
""")
        
        # Make the script executable
        os.chmod(exec_script, 0o755)
        
        # Create lib directory and copy AppImage content
        lib_dir = app_dir / "usr" / "lib" / self.rpm_name
        lib_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy executable from AppImage
        for item in self.extracted_dir.iterdir():
            # Skip desktop file and icons
            if item.name.endswith('.desktop') or item.name == 'usr':
                continue
                
            if item.is_file():
                shutil.copy2(item, lib_dir)
                logger.debug(f"Copied file: {item} -> {lib_dir / item.name}")
            else:
                shutil.copytree(item, lib_dir / item.name, symlinks=True)
                logger.debug(f"Copied directory: {item} -> {lib_dir / item.name}")
                
        # Make the main application executable
        main_exec = lib_dir / self.rpm_name
        if not main_exec.exists():
            # Try to find the AppRun file
            app_run = self.extracted_dir / "AppRun"
            if app_run.exists():
                shutil.copy2(app_run, main_exec)
                logger.info(f"Copied AppRun to {main_exec}")
            else:
                # Create a simple wrapper script
                with open(main_exec, 'w') as f:
                    f.write(f"""#!/bin/sh
cd "$(dirname "$0")"
exec ./AppRun "$@"
""")
                logger.info(f"Created wrapper script: {main_exec}")
                
        os.chmod(main_exec, 0o755)
        
        # Copy desktop file
        desktop_file = None
        for item in self.extracted_dir.glob("**/*.desktop"):
            desktop_file = item
            break
            
        if desktop_file:
            logger.info(f"Copying desktop file: {desktop_file}")
            desktop_target = applications_dir / f"{self.rpm_name}.desktop"
            shutil.copy2(desktop_file, desktop_target)
            
            # Update the desktop file to use the correct executable path
            self._update_desktop_file(desktop_target)
            
        # Handle icons
        if self.icon_paths:
            self._copy_icons(app_dir)
            
        # Create tarball of the application directory
        tarball_path = source_dir / f"{self.rpm_name}.tar.gz"
        logger.info(f"Creating tarball: {tarball_path}")
        subprocess.run(
            ["tar", "-czf", str(tarball_path), "-C", str(source_dir), self.rpm_name],
            check=True
        )
        
        return self.rpm_build_dir

    def _copy_icons(self, app_dir: Path) -> None:
        """
        Copy icons to appropriate locations in the build directory.
        
        Handles different icon formats and sizes according to the FreeDesktop standard.
        
        Args:
            app_dir: Path to the application directory
        """
        self.icon_install_paths = []
        
        if not self.selected_icon:
            self.select_best_icon()
            
        if not self.selected_icon:
            logger.warning("No icon selected, skipping icon installation")
            return
            
        logger.info(f"Copying icon: {self.selected_icon}")
        
        icon_name = f"{self.rpm_name}{self.selected_icon_ext}"
        
        # Create icon directories
        pixmaps_dir = app_dir / "usr" / "share" / "pixmaps"
        pixmaps_dir.mkdir(parents=True, exist_ok=True)
        
        icons_dir = app_dir / "usr" / "share" / "icons" / "hicolor"
        
        # Copy to pixmaps as a fallback
        pixmap_path = pixmaps_dir / icon_name
        shutil.copy2(self.selected_icon, pixmap_path)
        logger.debug(f"Copied icon to pixmaps: {pixmap_path}")
        self.icon_install_paths.append(f"/usr/share/pixmaps/{icon_name}")
        
        # For PNG icons, try to determine size and copy to appropriate directory
        if self.selected_icon_ext.lower() == '.png':
            try:
                # Try to determine size from path first
                size_match = re.search(r'(\d+)x\d+', str(self.selected_icon))
                if size_match:
                    size = size_match.group(1)
                    size_dir = icons_dir / f"{size}x{size}" / "apps"
                    size_dir.mkdir(parents=True, exist_ok=True)
                    
                    size_path = size_dir / icon_name
                    shutil.copy2(self.selected_icon, size_path)
                    logger.debug(f"Copied icon to size directory: {size_path}")
                    self.icon_install_paths.append(f"/usr/share/icons/hicolor/{size}x{size}/apps/{icon_name}")
                else:
                    # If size can't be determined from path, use 48x48 as default
                    size_dir = icons_dir / "48x48" / "apps"
                    size_dir.mkdir(parents=True, exist_ok=True)
                    
                    size_path = size_dir / icon_name
                    shutil.copy2(self.selected_icon, size_path)
                    logger.debug(f"Copied icon to default size directory: {size_path}")
                    self.icon_install_paths.append(f"/usr/share/icons/hicolor/48x48/apps/{icon_name}")
            except Exception as e:
                logger.error(f"Error copying PNG icon to size directory: {str(e)}")
                
        # For SVG icons, copy to scalable directory
        elif self.selected_icon_ext.lower() == '.svg':
            scalable_dir = icons_dir / "scalable" / "apps"
            scalable_dir.mkdir(parents=True, exist_ok=True)
            
            scalable_path = scalable_dir / icon_name
            shutil.copy2(self.selected_icon, scalable_path)
            logger.debug(f"Copied SVG icon to scalable directory: {scalable_path}")
            self.icon_install_paths.append(f"/usr/share/icons/hicolor/scalable/apps/{icon_name}")
            
        # Ensure all copied files have correct permissions
        for path in self.icon_install_paths:
            full_path = app_dir / path[1:]  # Remove leading slash
            if full_path.exists():
                os.chmod(full_path, 0o644)

    def _update_desktop_file(self, desktop_file: Path) -> None:
        """
        Update the desktop file with correct paths.
        
        Args:
            desktop_file: Path to the desktop file
        """
        logger.info(f"Updating desktop file: {desktop_file}")
        
        try:
            with open(desktop_file, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
                
            with open(desktop_file, 'w', encoding='utf-8') as f:
                for line in lines:
                    if line.startswith('Exec='):
                        # Update the executable path
                        f.write(f"Exec=/usr/bin/{self.rpm_name}\n")
                    elif line.startswith('Icon='):
                        # Update the icon path to use the RPM package name
                        f.write(f"Icon={self.rpm_name}\n")
                    else:
                        f.write(line)
                        
            # Set correct permissions
            os.chmod(desktop_file, 0o644)
            
        except Exception as e:
            logger.error(f"Error updating desktop file: {str(e)}")

    def create_spec_file(self, metadata: Dict[str, Any]) -> Path:
        """
        Create the RPM spec file.
        
        Args:
            metadata: Application metadata
            
        Returns:
            Path: Path to the created spec file
        """
        logger.info("Creating RPM spec file")
        
        # Get additional metadata
        summary = metadata.get('summary', f"{self.app_name} AppImage")
        description = metadata.get('description', summary)
        license_type = metadata.get('license', 'Proprietary')
        requires = metadata.get('requires', [])
        
        # Create spec file
        spec_path = self.rpm_build_dir / "SPECS" / f"{self.rpm_name}.spec"
        
        with open(spec_path, 'w') as f:
            f.write(f"""Name:           {self.rpm_name}
Version:        {self.app_version}
Release:        {self.app_release}%{{?dist}}
Summary:        {summary}

License:        {license_type}
URL:            {metadata.get('url', '')}
Source0:        %{{name}}.tar.gz

BuildArch:      x86_64
AutoReqProv:    no
""")

            # Add requires
            if requires:
                f.write("Requires:       %{?_isa:%{_isa}} ")
                f.write(" ".join(requires))
                f.write("\n\n")
            else:
                f.write("\n")
                
            # Description
            f.write(f"%description\n{description}\n\n")
            
            # Prep section
            f.write("""%prep
%setup -q -c

%build
# No build required

%install
cp -a %{name}/* %{buildroot}/

%post
/bin/touch --no-create %{_datadir}/icons/hicolor &>/dev/null || :

%postun
if [ $1 -eq 0 ] ; then
    /bin/touch --no-create %{_datadir}/icons/hicolor &>/dev/null || :
fi

%posttrans
/usr/bin/gtk-update-icon-cache %{_datadir}/icons/hicolor &>/dev/null || :

%files
%attr(755,root,root) %{_bindir}/%{name}
%{_datadir}/applications/%{name}.desktop
%{_libdir}/%{name}
""")

            # Add icon files
            for icon_path in self.icon_install_paths:
                f.write(f"{icon_path}\n")
                
            f.write("\n%changelog\n")
            f.write(f"* {self._get_date_str()} AppImage2RPM <appimage2rpm@localhost> - {self.app_version}-{self.app_release}\n")
            f.write(f"- Automatic RPM package built from AppImage\n")
            
        logger.info(f"Created spec file: {spec_path}")
        self.spec_file = spec_path
        return spec_path

    def build(self, metadata: Dict[str, Any]) -> Path:
        """
        Build the RPM package.
        
        Args:
            metadata: Application metadata
            
        Returns:
            Path: Path to the built RPM package
            
        Raises:
            RuntimeError: If the build fails
        """
        # Prepare build directory
        self.prepare_build_dir()
        
        # Create spec file
        self.create_spec_file(metadata)
        
        # Build RPM
        logger.info("Building RPM package")
        
        build_cmd = [
            "rpmbuild",
            "--define", f"_topdir {self.rpm_build_dir}",
            "--define", "_builddir %{_topdir}/BUILD",
            "--define", "_rpmdir %{_topdir}/RPMS",
            "--define", "_sourcedir %{_topdir}/SOURCES",
            "--define", "_specdir %{_topdir}/SPECS",
            "--define", "_srcrpmdir %{_topdir}/SRPMS",
            "--define", "_buildrootdir %{_topdir}/BUILDROOT",
            "-bb", str(self.spec_file)
        ]
        
        try:
            logger.debug(f"Running build command: {' '.join(build_cmd)}")
            process = subprocess.run(
                build_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            
            logger.debug(f"Build output: {process.stdout}")
            
            # Find the built RPM
            rpm_dir = self.rpm_build_dir / "RPMS" / "x86_64"
            rpm_files = list(rpm_dir.glob(f"{self.rpm_name}*.rpm"))
            
            if not rpm_files:
                error_msg = "No RPM package found after build"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
                
            built_rpm = rpm_files[0]
            logger.info(f"Built RPM package: {built_rpm}")
            
            # Copy the RPM to the output directory
            output_rpm = self.output_dir / built_rpm.name
            shutil.copy2(built_rpm, output_rpm)
            logger.info(f"Copied RPM package to: {output_rpm}")
            
            return output_rpm
            
        except subprocess.CalledProcessError as e:
            error_msg = f"RPM build failed: {e.stderr}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Error during RPM build: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        finally:
            # Clean up
            self._cleanup()

    def _cleanup(self) -> None:
        """Clean up temporary build files."""
        if self.rpm_build_dir and os.path.exists(self.rpm_build_dir):
            logger.info(f"Cleaning up build directory: {self.rpm_build_dir}")
            try:
                shutil.rmtree(self.rpm_build_dir)
            except Exception as e:
                logger.warning(f"Error cleaning up build directory: {str(e)}")

    def _sanitize_name(self, name: str) -> str:
        """
        Sanitize application name for use in RPM.
        
        Args:
            name: Original application name
            
        Returns:
            str: Sanitized name
        """
        # Replace spaces and special characters
        sanitized = re.sub(r'[^a-zA-Z0-9_.-]', '-', name)
        
        # Ensure the name doesn't start with a number or dash
        if sanitized[0].isdigit() or sanitized[0] == '-':
            sanitized = 'app-' + sanitized
            
        return sanitized.lower()

    def _get_date_str(self) -> str:
        """
        Get the current date in RPM changelog format.
        
        Returns:
            str: Formatted date string
        """
        from datetime import datetime
        
        # Format: Day Month Date Year
        return datetime.now().strftime("%a %b %d %Y") 