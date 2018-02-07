# Julia Mirror

Scripts for building a mirror for the Julia language.

It is still a work in progress.

## Usage

```
usage: mirror_julia.py [-h] [--force] [--no-releases] [--no-metadata]
                       [--no-packages] [--max-processes N]
                       [--sync-latest-packages [N]]
                       [--logging-file LOGGING_FILE]
                       [--logging-level {DEBUG,INFO,WARNING,ERROR}]
                       pathname

Build a mirror for the Julia language.

positional arguments:
  pathname              path to the root of the mirror

optional arguments:
  -h, --help            show this help message and exit
  --force               force to rebuild the mirror
  --no-releases         do not mirror Julia releases
  --no-metadata         do not mirror METADATA.jl (and will automatically set
                        --no-packages)
  --no-packages         do not mirror packages (but METADATA.jl)
  --max-processes N     use up to N processes for downloading (default: 4)
  --sync-latest-packages [N]
                        also mirror packages (at most N times in a day) on
                        master branch (default: 1)
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
This will build a mirror for Julia in `/path/to/mirror/julia` with default settings: Julia releases, METADATA.jl, and
releases of packages will be mirrored. The first time would run for up to several hours. Then you can add this command
to tools like crontab for automatic update. It is also recommended to add `--logging-file` argument in production
environment.

See [Mirrors.jl](https://github.com/sunoru/Mirrors.jl) for how to use the mirror as a client.

## File Structure

The version numbers and package names below are just examples. Same rules are applied to every releases and packages:

```
julia  # Mirror root
├── status.json  # Current status
├── releases
│   ├── releaseinfo.json  # Meta info for Julia releases
│   ├── latest            # Nightly builds
│   |   ├── julia-latest.tar.gz     # Source
│   |   ├── julia-latest.md5        # Checksums (md5 or sha256)
│   |   ├── julia-latest-win64.exe  # Binaries for different platforms
|   |   └── ...
│   ├── v0.6              # Releases
│   |   ├── julia-0.6.2-full.tar.gz            # Source with dependencies
│   |   ├── julia-0.6.2-linux-i686.tar.gz.asc  # GPG signatures for tarballs
|   |   └── ...                                # Others same as latest/
│   └── ...
└── packages
    ├── METADATA.jl    # Mirror for the git repository of metadata.
    ├── RandomNumbers  # Packages (named without `.jl`)
    |   ├── RandomNumbers-0.1.1.zip   # Zip files for releases. Contain git info for depth of 1.
    |   ├── RandomNumbers-latest.zip  # if --latest-packages is set
    |   └── ...
    └── ...
```

## Requirements

- Python 3.x
- Free disk space:
  - Julia releases: XXXX MB
  - Packages: XXXX MB
<!-- TODO -->
