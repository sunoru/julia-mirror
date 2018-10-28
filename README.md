# Julia Mirror

Scripts for building a mirror for the Julia language.

## Usage

```
usage: mirror_julia.py [-h] [--no-releases] [--no-metadata] [--no-general]
                       [--no-packages] [--add-registry {General}]
                       [--add-custom-registry CUSTOM_REGISTRIES CUSTOM_REGISTRIES]
                       [--max-processes N] [--sync-latest-packages]
                       [--ignore-invalid-registry] [--temp-dir TEMP_DIR]
                       [--logging-file LOGGING_FILE]
                       [--logging-level {DEBUG,INFO,WARNING,ERROR}]
                       [--mirror-name MIRROR_NAME]
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
  --temp-dir TEMP_DIR   directory for saving temporary files
  --logging-file LOGGING_FILE
                        save log to a file instead of to STDOUT
  --logging-level {DEBUG,INFO,WARNING,ERROR}
                        set logging level (default: WARNING)
  --mirror-name MIRROR_NAME
                        name of this mirror (default: $HOSTNAME)
```

To have a simple start, download
[mirror_julia.py](https://github.com/sunoru/julia-mirror/raw/master/scripts/mirror_julia.py) and run:
```bash
$ ./mirror_julia.py /path/to/mirror/julia
```
This will build a mirror for Julia in `/path/to/mirror/julia` with default settings: Julia releases, METADATA.jl,
General registry and releases of packages will be mirrored. The first time would run for up to several hours. Then you
can add this command to tools like cron for automatic update. It is also recommended to add `--logging-file` argument
in production environments.

Since the server for git needs Smart HTTP support, nginx is recommended to be installed. See the
[nginx config file](./config/nginx.conf) for example.

See [PkgMirrors.jl](https://github.com/sunoru/PkgMirrors.jl) for how to use the mirror as a client.

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
│   ├── v1.0              # Releases
│   │   ├── julia-1.0.0-full.tar.gz            # Source with dependencies
│   │   ├── julia-1.0.0-linux-i686.tar.gz.asc  # GPG signatures for tarballs
│   │   └── ...                                # Others same as latest/
│   └── ...
├── PkgMirrors.jl.git  # Bare copy for the mirror of the client
├── metadata
│   ├── METADATA.jl      # Mirror for the git repository of metadata (For Julia versions before 0.7)
│   └── METADATA.jl.git  # Bare copy for the mirror of metadata
├── packages
│   ├── RandomNumbers  # Packages (named without `.jl`)
│   │   ├── General  # Folder with a name where the package is registered
│   │   │   ├── RandomNumbers                       # Symbolic link to the package folder in the registry
│   │   │   ├── RandomNumbers-v1.0.1.tar.gz         # Tarballs for releases
│   │   │   ├── RandomNumbers-v1.0.1.tar.gz.sha256  # Checksum
│   │   │   ├── RandomNumbers-latest.tar.gz         # if --latest-packages is set
│   │   │   ├── RandomNumbers-292ba49037aea380eb102bb923b69bf17d16289b.tar.gz  # Tarballs for releases named with tree sha1 hash
│   │   │   └── ...
│   │   └── ...
│   └── ...
└── registries
    ├── list.txt     # List of registry names
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
- Dependencies (see [`requirements.txt`](./requirements.txt)):
  - GitPython
  - TOML
- Free disk space (in total - about 22 GB, but increasing every day):
  - Metadata: 324 MB
  - Registries: 72MB (General)
  - Julia releases: 4324 MB
  - Packages: 16889 MB
