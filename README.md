# Julia Mirror

Scripts for building a mirror for the Julia language.

It is still a work in progress.

## Usage

```
usage: mirror_julia.py [-h] [--no-releases] [--no-metadata] [--no-general]
                       [--no-packages] [--add-registry {General}]
                       [--add-custom-registry CUSTOM_REGISTRIES CUSTOM_REGISTRIES]
                       [--max-processes N] [--sync-latest-packages]
                       [--ignore-invalid-registry] [--ignore-404]
                       [--temp-dir TEMP_DIR] [--logging-file LOGGING_FILE]
                       [--logging-level {DEBUG,INFO,WARNING,ERROR}]
                       pathname

Build a mirror for the Julia language.

positional arguments:
  pathname              path to the root of the mirror

optional arguments:
  -h, --help            show this help message and exit
  --no-releases         do not mirror Julia releases
  --no-metadata         do not mirror METADATA.jl
  --no-general          do not mirror General registry (which is the default
                        for registries)
  --no-packages         do not mirror packages (and will be automatically set
                        if no registries are to mirrored)
  --add-registry {General}
                        add a registry specified by name
  --add-custom-registry CUSTOM_REGISTRIES CUSTOM_REGISTRIES
                        add a registry specified by a custom URL
  --max-processes N     use up to N processes for downloading (default: 4)
  --sync-latest-packages
                        also mirror packages on master branch
  --ignore-invalid-registry
                        ignore when a registry is not valid
  --ignore-404          ignore when a download file is not found
  --temp-dir TEMP_DIR   directory for saving temporary files
  --logging-file LOGGING_FILE
                        save log to a file instead of to STDOUT
  --logging-level {DEBUG,INFO,WARNING,ERROR}
                        set logging level (default: WARNING)
```

To have a simple start, download
[mirror_julia.py](https://github.com/sunoru/julia-mirror/raw/master/scripts/mirror_julia.py) and do:
```bash
$ ./mirror_julia.py /path/to/mirror/julia
```
This will build a mirror for Julia in `/path/to/mirror/julia` with default settings: Julia releases, METADATA.jl,
General registry and releases of packages will be mirrored. The first time would run for up to several hours. Then you
can add this command to tools like cron for automatic update. It is also recommended to add `--logging-file` argument
in production environments.

See [Mirrors.jl](https://github.com/sunoru/Mirrors.jl) for how to use the mirror as a client.

## File Structure

The version numbers and package names below are just examples. Same rules are applied to every releases and packages:

```
julia  # Mirror root
├── status.json  # Current status
├── releases
│   ├── releaseinfo.json  # Meta info for Julia releases
│   ├── latest            # Nightly builds
│   │   ├── julia-latest.tar.gz     # Source
│   │   ├── julia-latest.md5        # Checksums (md5 or sha256)
│   │   ├── julia-latest-win64.exe  # Binaries for different platforms
│   │   └── ...
│   ├── v0.6              # Releases
│   │   ├── julia-0.6.2-full.tar.gz            # Source with dependencies
│   │   ├── julia-0.6.2-linux-i686.tar.gz.asc  # GPG signatures for tarballs
│   │   └── ...                                # Others same as latest/
│   └── ...
│── packages
│   ├── METADATA.jl      # Mirror for the git repository of metadata (For Julia versions before 0.7)
│   └── METADATA.jl.git  # Bare copy for the mirror of metadata
│── packages
│   ├── RandomNumbers  # Packages (named without `.jl`)
│   │   ├── General  # Folder with a name where the package is registered
│   │   │   ├── RandomNumbers-v0.1.1.tar.gz         # Zip files for releases
│   │   │   ├── RandomNumbers-v0.1.1.tar.gz.sha256  # Checksum
│   │   │   ├── RandomNumbers-v0.1.1.git            # Git info for depth of 1 (a shallow clone). Deprecated.
│   │   │   ├── RandomNumbers-latest.tar.gz         # if --latest-packages is set
│   │   │   └── ...
│   │   └── ...
│   └── ...
└── registries
    ├── General      # General registry for Pkg.jl (For Julia versions from 0.7)
    │   ├── A  # Alphabetically named folders
    │   ├── B
    │   ├── ...
    │   ├── R
    │   │   ├── RandomNumbers
    │   │   │   ├── Package.toml   # Basic information of the package
    │   │   │   ├── Versions.toml  # List versions of the package
    │   │   │   ├── Deps.toml      # Dependencies of each version
    │   │   │   ├── Compat.toml    # Compatibility of each version
    │   │   │   └── releases       # Symbolic link to the package folder above
    │   │   └── ...
    │   └── ...
    └── General.git  # Bare copy for the mirror of general registry
```

## Requirements

- Python 3.x
- Git
- Free disk space:
  - Julia releases: XXXX MB
  - Packages: XXXX MB
<!-- TODO -->
