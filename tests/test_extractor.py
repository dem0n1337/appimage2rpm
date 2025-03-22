#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for the AppImage extractor module.
"""

import os
import tempfile
import shutil
from pathlib import Path
from typing import Generator, Any

import pytest
from _pytest.monkeypatch import MonkeyPatch
from pytest_mock import MockerFixture

from appimage2rpm.core.extractor import AppImageExtractor


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
def mock_appimage(temp_dir: Path, monkeypatch: MonkeyPatch) -> Path:
    """
    Fixture to create a mock AppImage file for testing.
    
    Args:
        temp_dir: Temporary directory
        monkeypatch: Monkeypatch fixture
        
    Returns:
        Path: Path to the mock AppImage file
    """
    # Create a dummy AppImage file
    appimage_path = temp_dir / "test-app-1.0.0-x86_64.AppImage"
    with open(appimage_path, "w") as f:
        f.write("#!/bin/sh\n# Mock AppImage file")
    
    # Make it executable
    appimage_path.chmod(0o755)
    
    return appimage_path


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
    bin_dir.chmod(0o755)
    
    return extracted_dir


def test_appimage_extractor_init(mock_appimage: Path) -> None:
    """
    Test AppImageExtractor initialization.
    
    Args:
        mock_appimage: Mock AppImage file
    """
    extractor = AppImageExtractor(str(mock_appimage))
    
    assert extractor.appimage_path == mock_appimage
    assert extractor.temp_dir is None
    assert extractor.extracted_dir is None
    assert extractor.metadata == {}


def test_appimage_extractor_init_invalid_path() -> None:
    """Test AppImageExtractor initialization with invalid path."""
    with pytest.raises(FileNotFoundError):
        AppImageExtractor("/path/to/nonexistent/file.AppImage")


def test_get_desktop_file(monkeypatch: MonkeyPatch, mock_extracted_dir: Path) -> None:
    """
    Test get_desktop_file method.
    
    Args:
        monkeypatch: Monkeypatch fixture
        mock_extracted_dir: Mock extracted directory
    """
    extractor = AppImageExtractor("/dummy/path.AppImage")
    
    # Mock extracted_dir
    extractor.extracted_dir = mock_extracted_dir.parent
    
    desktop_file = extractor.get_desktop_file()
    assert desktop_file is not None
    assert desktop_file.name == "test-app.desktop"


def test_get_icon_files(monkeypatch: MonkeyPatch, mock_extracted_dir: Path) -> None:
    """
    Test get_icon_files method.
    
    Args:
        monkeypatch: Monkeypatch fixture
        mock_extracted_dir: Mock extracted directory
    """
    extractor = AppImageExtractor("/dummy/path.AppImage")
    
    # Mock extracted_dir
    extractor.extracted_dir = mock_extracted_dir.parent
    
    # Set metadata for name-based matching
    extractor.metadata = {"name": "test-app"}
    
    icon_files = extractor.get_icon_files()
    
    # Should find multiple icons
    assert len(icon_files) > 0
    
    # SVG should be prioritized
    svg_icons = [i for i in icon_files if str(i).endswith('.svg')]
    assert len(svg_icons) > 0
    assert str(icon_files[0]).endswith('.svg')


def test_extract_version_from_filename() -> None:
    """Test extracting version from filename."""
    # Test with different filename patterns
    test_cases = [
        ("app-1.0.0-x86_64.AppImage", "1.0.0"),
        ("app-v2.1.3-x86_64.AppImage", "2.1.3"),
        ("app-4.2-x86_64.AppImage", "4.2"),
        ("app-5-x86_64.AppImage", "5"),
        ("app_1.0.0-beta.1-x86_64.AppImage", "1.0.0-beta.1"),
        ("app.noversion.AppImage", None),
    ]
    
    for filename, expected_version in test_cases:
        extractor = AppImageExtractor("/dummy/" + filename)
        version = extractor._extract_version_from_filename()
        assert version == expected_version


def test_parse_metadata(mocker: MockerFixture, mock_extracted_dir: Path) -> None:
    """
    Test parse_metadata method.
    
    Args:
        mocker: Mocker fixture
        mock_extracted_dir: Mock extracted directory
    """
    extractor = AppImageExtractor("/dummy/app-1.2.3-x86_64.AppImage")
    
    # Mock extract method
    mocker.patch.object(extractor, 'extract', return_value=mock_extracted_dir)
    
    # Parse metadata
    metadata = extractor.parse_metadata()
    
    # Check metadata values
    assert metadata["name"] == "Test App"
    assert "version" in metadata  # Should extract from filename or use default
    assert metadata["summary"] == "A test application"


def test_cleanup(mocker: MockerFixture) -> None:
    """
    Test cleanup method.
    
    Args:
        mocker: Mocker fixture
    """
    extractor = AppImageExtractor("/dummy/path.AppImage")
    
    # Create a temporary directory manually
    extractor.temp_dir = tempfile.mkdtemp(prefix="appimage2rpm_test_cleanup_")
    
    # Ensure directory exists
    assert os.path.exists(extractor.temp_dir)
    
    # Clean up
    extractor.cleanup()
    
    # Directory should be removed
    assert not os.path.exists(extractor.temp_dir)
    assert extractor.temp_dir is None
    assert extractor.extracted_dir is None 