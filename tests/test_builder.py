#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for the RPM builder module.
"""

import os
import tempfile
import shutil
import subprocess
import re
from pathlib import Path
from typing import Generator, List, Any

import pytest
from _pytest.monkeypatch import MonkeyPatch
from pytest_mock import MockerFixture

from appimage2rpm.core.builder import RPMBuilder


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """
    Fixture to create a temporary directory for testing.
    
    Returns:
        Generator[Path, None, None]: Path to the temporary directory
    """
    # Create a temporary directory
    temp_dir = Path(tempfile.mkdtemp(prefix="appimage2rpm_test_"))
    
    try:
        yield temp_dir
    finally:
        # Clean up
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


@pytest.fixture
def mock_extracted_dir(temp_dir: Path) -> Path:
    """
    Fixture to create a mock extracted AppImage directory.
    
    Args:
        temp_dir: Temporary directory
        
    Returns:
        Path: Path to the mock extracted directory
    """
    # Create a mock extracted structure
    extracted_dir = temp_dir / "extracted" / "squashfs-root"
    extracted_dir.mkdir(parents=True, exist_ok=True)
    
    # Create AppRun file
    with open(extracted_dir / "AppRun", "w") as f:
        f.write("#!/bin/sh\necho 'Hello, world!'")
    os.chmod(extracted_dir / "AppRun", 0o755)
    
    # Create a .desktop file
    desktop_dir = extracted_dir / "usr" / "share" / "applications"
    desktop_dir.mkdir(parents=True, exist_ok=True)
    desktop_file = desktop_dir / "test-app.desktop"
    
    with open(desktop_file, "w") as f:
        f.write("""[Desktop Entry]
Name=Test App
Comment=A test application
Exec=test-app %F
Icon=test-app
Type=Application
Categories=Utility;
""")
    
    # Create some icon files
    icon_dir = extracted_dir / "usr" / "share" / "icons" / "hicolor"
    
    # Create 48x48 icon
    icon_48_dir = icon_dir / "48x48" / "apps"
    icon_48_dir.mkdir(parents=True, exist_ok=True)
    with open(icon_48_dir / "test-app.png", "w") as f:
        f.write("PNG mock data")
    
    # Create 128x128 icon
    icon_128_dir = icon_dir / "128x128" / "apps"
    icon_128_dir.mkdir(parents=True, exist_ok=True)
    with open(icon_128_dir / "test-app.png", "w") as f:
        f.write("PNG mock data")
    
    # Create scalable icon
    icon_scalable_dir = icon_dir / "scalable" / "apps"
    icon_scalable_dir.mkdir(parents=True, exist_ok=True)
    with open(icon_scalable_dir / "test-app.svg", "w") as f:
        f.write("SVG mock data")
    
    # Create pixmaps icon
    pixmaps_dir = extracted_dir / "usr" / "share" / "pixmaps"
    pixmaps_dir.mkdir(parents=True, exist_ok=True)
    with open(pixmaps_dir / "test-app.xpm", "w") as f:
        f.write("XPM mock data")
    
    # Create DirIcon
    with open(extracted_dir / ".DirIcon", "w") as f:
        f.write("DirIcon mock data")
    
    # Create bin directory with executable
    bin_dir = extracted_dir / "usr" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    with open(bin_dir / "test-app", "w") as f:
        f.write("#!/bin/sh\necho 'Hello, world!'")
    os.chmod(bin_dir / "test-app", 0o755)
    
    return extracted_dir


@pytest.fixture
def mock_icon_paths(mock_extracted_dir: Path) -> List[Path]:
    """
    Fixture to create mock icon paths.
    
    Args:
        mock_extracted_dir: Mock extracted directory
        
    Returns:
        List[Path]: List of icon paths
    """
    return [
        mock_extracted_dir / "usr" / "share" / "icons" / "hicolor" / "scalable" / "apps" / "test-app.svg",
        mock_extracted_dir / "usr" / "share" / "icons" / "hicolor" / "128x128" / "apps" / "test-app.png",
        mock_extracted_dir / "usr" / "share" / "icons" / "hicolor" / "48x48" / "apps" / "test-app.png",
        mock_extracted_dir / "usr" / "share" / "pixmaps" / "test-app.xpm",
        mock_extracted_dir / ".DirIcon"
    ]


def test_rpm_builder_init(mock_extracted_dir: Path, mock_icon_paths: List[Path]) -> None:
    """
    Test RPMBuilder initialization.
    
    Args:
        mock_extracted_dir: Mock extracted directory
        mock_icon_paths: Mock icon paths
    """
    builder = RPMBuilder(
        app_name="Test App",
        app_version="1.0.0",
        extracted_dir=mock_extracted_dir,
        icon_paths=mock_icon_paths,
        app_release="1",
        output_dir=str(mock_extracted_dir.parent)
    )
    
    assert builder.app_name == "Test App"
    assert builder.app_version == "1.0.0"
    assert builder.app_release == "1"
    assert builder.rpm_name == "test-app"  # Should be sanitized
    assert builder.extracted_dir == mock_extracted_dir
    assert builder.icon_paths == mock_icon_paths
    assert builder.output_dir == mock_extracted_dir.parent


def test_rpm_builder_init_validation() -> None:
    """Test RPMBuilder initialization validation."""
    # Test empty app name
    with pytest.raises(ValueError):
        RPMBuilder(
            app_name="",
            app_version="1.0.0",
            extracted_dir=Path("/tmp")
        )
        
    # Test empty app version
    with pytest.raises(ValueError):
        RPMBuilder(
            app_name="Test App",
            app_version="",
            extracted_dir=Path("/tmp")
        )
        
    # Test non-existent extracted directory
    with pytest.raises(ValueError):
        RPMBuilder(
            app_name="Test App",
            app_version="1.0.0",
            extracted_dir=Path("/nonexistent/directory")
        )


def test_sanitize_name() -> None:
    """Test sanitize_name method."""
    builder = RPMBuilder(
        app_name="Test App",
        app_version="1.0.0",
        extracted_dir=Path("/tmp")
    )
    
    test_cases = [
        ("Test App", "test-app"),
        ("App With Spaces", "app-with-spaces"),
        ("App-With-Dashes", "app-with-dashes"),
        ("App_With_Underscores", "app_with_underscores"),
        ("App.With.Dots", "app.with.dots"),
        ("App With Special Ch@rs!", "app-with-special-ch-rs-"),
        ("1App", "app-1app"),  # Should not start with a number
        ("-App", "app--app"),  # Should not start with a dash
    ]
    
    for input_name, expected_output in test_cases:
        sanitized = builder._sanitize_name(input_name)
        assert sanitized == expected_output


def test_select_best_icon(mock_icon_paths: List[Path]) -> None:
    """
    Test select_best_icon method.
    
    Args:
        mock_icon_paths: Mock icon paths
    """
    builder = RPMBuilder(
        app_name="Test App",
        app_version="1.0.0",
        extracted_dir=Path("/tmp"),
        icon_paths=mock_icon_paths
    )
    
    # Test SVG preference
    best_icon = builder.select_best_icon()
    assert best_icon is not None
    assert str(best_icon).endswith(".svg")
    
    # Test PNG preference (when no SVG)
    builder.icon_paths = [p for p in mock_icon_paths if not str(p).endswith(".svg")]
    best_icon = builder.select_best_icon()
    assert best_icon is not None
    assert str(best_icon).endswith(".png")
    assert "128x128" in str(best_icon)  # Should prefer larger size
    
    # Test fallback to any icon
    builder.icon_paths = [p for p in mock_icon_paths if str(p).endswith(".xpm") or str(p).endswith(".DirIcon")]
    best_icon = builder.select_best_icon()
    assert best_icon is not None
    
    # Test no icons
    builder.icon_paths = []
    best_icon = builder.select_best_icon()
    assert best_icon is None


def test_update_desktop_file(temp_dir: Path) -> None:
    """
    Test _update_desktop_file method.
    
    Args:
        temp_dir: Temporary directory
    """
    # Create a test desktop file
    desktop_file = temp_dir / "test-app.desktop"
    with open(desktop_file, "w") as f:
        f.write("""[Desktop Entry]
Name=Test App
Comment=A test application
Exec=/path/to/original/executable %F
Icon=original-icon
Type=Application
Categories=Utility;
""")
    
    builder = RPMBuilder(
        app_name="Test App",
        app_version="1.0.0",
        extracted_dir=Path("/tmp")
    )
    
    # Update the desktop file
    builder._update_desktop_file(desktop_file)
    
    # Check the updated desktop file
    with open(desktop_file, "r") as f:
        content = f.read()
        
    assert "Exec=/usr/bin/test-app" in content
    assert "Icon=test-app" in content


def test_create_spec_file(mocker: MockerFixture, temp_dir: Path, mock_extracted_dir: Path) -> None:
    """
    Test create_spec_file method.
    
    Args:
        mocker: Mocker fixture
        temp_dir: Temporary directory
        mock_extracted_dir: Mock extracted directory
    """
    builder = RPMBuilder(
        app_name="Test App",
        app_version="1.0.0",
        extracted_dir=mock_extracted_dir
    )
    
    # Mock rpm_build_dir
    build_dir = temp_dir / "build"
    build_dir.mkdir(exist_ok=True)
    specs_dir = build_dir / "SPECS"
    specs_dir.mkdir(exist_ok=True)
    builder.rpm_build_dir = build_dir
    
    # Add some icon paths
    builder.icon_install_paths = [
        "/usr/share/pixmaps/test-app.png",
        "/usr/share/icons/hicolor/scalable/apps/test-app.svg"
    ]
    
    # Create spec file
    metadata = {
        "summary": "Test application",
        "license": "MIT",
        "requires": ["lib1", "lib2"]
    }
    
    spec_file = builder.create_spec_file(metadata)
    
    # Check spec file exists
    assert spec_file.exists()
    assert spec_file == build_dir / "SPECS" / "test-app.spec"
    
    # Check spec file content
    with open(spec_file, "r") as f:
        content = f.read()
        
    assert "Name:           test-app" in content
    assert "Version:        1.0.0" in content
    assert "Release:        1" in content
    assert "Summary:        Test application" in content
    assert "License:        MIT" in content
    assert "Requires:" in content
    assert "lib1 lib2" in content
    
    # Check icon paths included
    for icon_path in builder.icon_install_paths:
        assert icon_path in content 