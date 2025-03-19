# AppImage2RPM

A tool for converting AppImage files into RPM packages for Fedora and RHEL distributions.

## Features

- Convert AppImage files to RPM packages
- Automatically extract metadata from AppImage files
- Automatic icon detection from AppImage contents
- Customizable RPM specifications
- Dependency management
- Graphical user interface
- Support for multiple distribution profiles

## Requirements

- Fedora 41 or compatible RHEL distribution
- Python 3.10+
- PyQt5
- RPM build tools

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Install RPM build tools
sudo dnf install rpm-build rpmdevtools
```

## Usage

### Graphical Interface

```bash
python appimage2rpm.py
```

### Command Line (Test Script)

For testing or debugging purposes, you can use the test script:

```bash
python test_rpm_builder.py /path/to/extracted/appimage
```

## How It Works

1. **AppImage Extraction:** The tool extracts the contents of the AppImage file to a temporary directory.
2. **Metadata Extraction:** It automatically extracts metadata like application name, version, icon, and description.
3. **Icon Detection:** The tool automatically searches for icons in common locations within the extracted AppImage.
4. **Dependency Analysis:** It analyzes the binaries to detect dependencies required for the application.
5. **RPM Spec Creation:** A spec file is generated based on the extracted information.
6. **RPM Building:** The RPM package is built using rpmbuild.

## Development

### Key Components

- `appimage2rpm.py`: Main application with GUI
- `rpm_utils.py`: Contains the RPMBuilder class for creating RPM packages
- `appimage_utils.py`: Handles AppImage extraction and metadata parsing
- `dependency_utils.py`: Analyzes and manages dependencies
- `repo_utils.py`: Manages RPM repositories

### Debugging

The application creates detailed log files to help diagnose issues:
- `rpm_builder_debug.log`: Contains detailed information about the RPM building process

## License

GPL-3.0

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
