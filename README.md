# AppImage2RPM

Convert AppImage packages to RPM format easily with a modern GUI or command line interface.

## Features

- Convert AppImage files to RPM packages with a single click
- Detect and include dependencies automatically
- Support for multiple Linux distributions (Fedora, CentOS, RHEL)
- Advanced icon detection and handling 
- Repository integration (COPR)
- Threaded background processing for responsive UI
- Detailed real-time logging
- Command-line interface for scripting

## Installation

### Requirements

- Python 3.8 or newer
- RPM build tools (`rpmbuild`, `rpm-build` package)
- Qt6 libraries (for GUI)

### From Source

1. Clone the repository:

```bash
git clone https://github.com/dem0n1337/appimage2rpm.git
cd appimage2rpm
```

2. Create a virtual environment and install dependencies:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. Install the package:

```bash
pip install -e .
```

## Usage

### Graphical Interface

To start the GUI:

```bash
appimage2rpm
```

### Command Line Interface

Convert an AppImage to RPM:

```bash
appimage2rpm convert path/to/application.AppImage --output-dir /path/to/output/directory
```

With additional options:

```bash
appimage2rpm convert path/to/application.AppImage --name CustomName --version 1.2.3 --distro fedora --no-auto-deps
```

### Options

- `--output-dir, -o`: Directory where the RPM package will be saved
- `--name`: Set custom package name
- `--version`: Set custom package version
- `--release`: Set package release (default: 1)
- `--auto-deps/--no-auto-deps`: Enable/disable automatic dependency detection
- `--distro`: Target distribution profile (fedora, centos, rhel)

## Building RPM Packages

The application creates well-formed RPM packages that:

1. Install the application to `/usr/lib/<app_name>/`
2. Create a launcher in `/usr/bin/`
3. Install desktop file to `/usr/share/applications/`
4. Install icons to appropriate locations in the hicolor icon theme

## Icon Handling

Icons are detected using the following priority:

1. SVG icons (preferred for scalability)
2. PNG icons (largest size preferred)
3. Icons referenced in .desktop files
4. Icons with matching application name
5. Other icon formats (XPM, etc.)

Icons are properly installed according to the [XDG Icon Theme Specification](https://specifications.freedesktop.org/icon-theme-spec/icon-theme-spec-latest.html).

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
