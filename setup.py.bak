#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="appimage2rpm",
    version="1.0.0",
    author="AppImage2RPM Team",
    description="Tool for converting AppImage packages to RPM format",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/dem0n1337/appimage2rpm",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
    ],
    python_requires=">=3.8",
    install_requires=[
        "PySide6>=6.5.0",
        "rpm-py-installer>=1.1.0",
        "click>=8.0.0",
        "toml>=0.10.2",
    ],
    entry_points={
        "console_scripts": [
            "appimage2rpm=appimage2rpm.__main__:main",
        ],
    },
) 