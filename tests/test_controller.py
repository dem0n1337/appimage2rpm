#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tests for the AppImage2RPM controller module.
"""

import os
import tempfile
import shutil
from pathlib import Path
from typing import Generator, Any, Dict

import pytest
from _pytest.monkeypatch import MonkeyPatch
from pytest_mock import MockerFixture

from appimage2rpm.core.controller import AppImage2RPMController


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
def controller() -> AppImage2RPMController:
    """
    Fixture to create a controller instance.
    
    Returns:
        AppImage2RPMController: Controller instance
    """
    return AppImage2RPMController()


def test_controller_init(controller: AppImage2RPMController) -> None:
    """
    Test controller initialization.
    
    Args:
        controller: Controller instance
    """
    assert controller is not None
    assert controller.profile_manager is not None


def test_get_available_profiles(controller: AppImage2RPMController, mocker: MockerFixture) -> None:
    """
    Test get_available_profiles method.
    
    Args:
        controller: Controller instance
        mocker: Mocker fixture
    """
    # Mock the profile manager's get_profiles method
    mock_profiles = [
        {"id": "fedora", "name": "Fedora", "version": "36"},
        {"id": "centos", "name": "CentOS", "version": "9"},
        {"id": "rhel", "name": "RHEL", "version": "9"}
    ]
    mocker.patch.object(controller.profile_manager, "get_profiles", return_value=mock_profiles)
    
    # Get profiles
    profiles = controller.get_available_profiles()
    
    # Should get the mocked profiles
    assert profiles == mock_profiles
    assert len(profiles) == 3
    assert profiles[0]["id"] == "fedora"


def test_detect_current_distro(controller: AppImage2RPMController, mocker: MockerFixture) -> None:
    """
    Test detect_current_distro method.
    
    Args:
        controller: Controller instance
        mocker: Mocker fixture
    """
    # Mock the profile manager's detect_current_distro method
    mocker.patch.object(controller.profile_manager, "detect_current_distro", return_value="fedora")
    
    # Detect distro
    distro = controller.detect_current_distro()
    
    # Should get the mocked distro
    assert distro == "fedora"


def test_convert_appimage_success(controller: AppImage2RPMController, temp_dir: Path, mocker: MockerFixture) -> None:
    """
    Test convert_appimage method with successful conversion.
    
    Args:
        controller: Controller instance
        temp_dir: Temporary directory
        mocker: Mocker fixture
    """
    # Create mock AppImage file
    appimage_path = temp_dir / "test-app-1.0.0-x86_64.AppImage"
    with open(appimage_path, "w") as f:
        f.write("#!/bin/sh\n# Mock AppImage file")
    os.chmod(appimage_path, 0o755)
    
    # Create mock output directory
    output_dir = temp_dir / "output"
    output_dir.mkdir(exist_ok=True)
    
    # Mock dependencies and methods
    
    # Mock profile manager
    mock_profile = {"id": "fedora", "name": "Fedora", "version": "36"}
    mocker.patch.object(controller.profile_manager, "get_profile", return_value=mock_profile)
    mocker.patch.object(controller.profile_manager, "detect_current_distro", return_value="fedora")
    mocker.patch.object(controller.profile_manager, "create_rpm_macros", return_value="/tmp/mock_macros")
    
    # Mock AppImage extractor
    mock_extractor = mocker.patch("appimage2rpm.core.extractor.AppImageExtractor")
    mock_extractor_instance = mock_extractor.return_value
    mock_extractor_instance.extract.return_value = temp_dir / "extracted"
    mock_extractor_instance.parse_metadata.return_value = {"name": "Test App", "version": "1.0.0"}
    mock_extractor_instance.get_icon_files.return_value = [temp_dir / "icon.png"]
    
    # Mock dependency analyzer
    mock_analyzer = mocker.patch("appimage2rpm.core.dependency_analyzer.DependencyAnalyzer")
    mock_analyzer_instance = mock_analyzer.return_value
    mock_analyzer_instance.convert_dependencies_to_rpm_requires.return_value = ["dep1", "dep2"]
    
    # Mock RPM builder
    mock_builder = mocker.patch("appimage2rpm.core.builder.RPMBuilder")
    mock_builder_instance = mock_builder.return_value
    mock_builder_instance.select_best_icon.return_value = temp_dir / "icon.png"
    mock_builder_instance.build.return_value = output_dir / "test-app-1.0.0-1.fc36.x86_64.rpm"
    
    # Mock progress callback
    mock_callback = mocker.Mock()
    
    # Convert AppImage
    result = controller.convert_appimage(
        appimage_path=str(appimage_path),
        output_dir=str(output_dir),
        metadata={"name": "Test App", "version": "1.0.0"},
        distro_profile="fedora",
        auto_deps=True,
        progress_callback=mock_callback
    )
    
    # Check result
    assert result["success"] is True
    assert "rpm_path" in result
    assert "message" in result
    assert "RPM package created successfully" in result["message"]
    
    # Check callbacks
    assert mock_callback.call_count > 0


def test_convert_appimage_failure(controller: AppImage2RPMController, temp_dir: Path, mocker: MockerFixture) -> None:
    """
    Test convert_appimage method with failed conversion.
    
    Args:
        controller: Controller instance
        temp_dir: Temporary directory
        mocker: Mocker fixture
    """
    # Create mock AppImage file
    appimage_path = temp_dir / "test-app-1.0.0-x86_64.AppImage"
    with open(appimage_path, "w") as f:
        f.write("#!/bin/sh\n# Mock AppImage file")
    os.chmod(appimage_path, 0o755)
    
    # Create mock output directory
    output_dir = temp_dir / "output"
    output_dir.mkdir(exist_ok=True)
    
    # Mock dependencies to simulate failure
    
    # Mock profile manager
    mock_profile = {"id": "fedora", "name": "Fedora", "version": "36"}
    mocker.patch.object(controller.profile_manager, "get_profile", return_value=mock_profile)
    mocker.patch.object(controller.profile_manager, "detect_current_distro", return_value="fedora")
    
    # Mock AppImage extractor to raise an exception
    mock_extractor = mocker.patch("appimage2rpm.core.extractor.AppImageExtractor")
    mock_extractor_instance = mock_extractor.return_value
    mock_extractor_instance.extract.side_effect = RuntimeError("Mock extraction error")
    
    # Mock progress callback
    mock_callback = mocker.Mock()
    
    # Convert AppImage
    result = controller.convert_appimage(
        appimage_path=str(appimage_path),
        output_dir=str(output_dir),
        progress_callback=mock_callback
    )
    
    # Check result
    assert result["success"] is False
    assert "message" in result
    assert "Error:" in result["message"]
    
    # Check callbacks
    assert mock_callback.call_count > 0


def test_convert_appimage_invalid_profile(controller: AppImage2RPMController, temp_dir: Path, mocker: MockerFixture) -> None:
    """
    Test convert_appimage method with invalid profile.
    
    Args:
        controller: Controller instance
        temp_dir: Temporary directory
        mocker: Mocker fixture
    """
    # Create mock AppImage file
    appimage_path = temp_dir / "test-app-1.0.0-x86_64.AppImage"
    with open(appimage_path, "w") as f:
        f.write("#!/bin/sh\n# Mock AppImage file")
    os.chmod(appimage_path, 0o755)
    
    # Mock profile manager to return None (invalid profile)
    mocker.patch.object(controller.profile_manager, "get_profile", return_value=None)
    
    # Mock progress callback
    mock_callback = mocker.Mock()
    
    # Convert AppImage with invalid profile
    result = controller.convert_appimage(
        appimage_path=str(appimage_path),
        distro_profile="invalid-profile",
        progress_callback=mock_callback
    )
    
    # Check result
    assert result["success"] is False
    assert "message" in result
    assert "Unsupported distribution profile" in result["message"] 