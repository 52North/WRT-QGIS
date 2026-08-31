"""Fix whitespace in NetCDF variable names that stops MDAL pairing u/v components.

Usage: python tools/fix_netcdf_names.py data.nc

A file that needs fixing gets a repaired copy, ``data_fixed.nc``. The input is never modified.
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

_WHITESPACE = re.compile(r"\s+")

_ATTRIBUTE = "long_name"

_FIXED_SUFFIX = "_fixed"


def tidy(name):
    """``name`` with whitespace runs collapsed and the ends trimmed."""
    return _WHITESPACE.sub(" ", name).strip()


def fixed_path_for(path):
    """Where the repaired copy goes: ``data.nc`` -> ``data_fixed.nc``."""
    path = Path(path)
    return path.with_name(f"{path.stem}{_FIXED_SUFFIX}{path.suffix}")


def untidy_names(path):
    """``{variable: tidied long_name}`` for the variables whose name needs it."""
    import netCDF4

    untidy = {}
    with netCDF4.Dataset(str(path), "r") as dataset:
        for variable, handle in dataset.variables.items():
            name = getattr(handle, _ATTRIBUTE, None)
            if isinstance(name, str) and tidy(name) != name:
                untidy[variable] = tidy(name)
    return untidy


def write_fixed_copy(path, untidy, destination):
    """Copy ``path`` to ``destination``, tidying the named attributes in the copy."""
    import netCDF4

    shutil.copy2(path, destination)
    try:
        with netCDF4.Dataset(str(destination), "a") as dataset:
            for variable, tidied in untidy.items():
                handle = dataset.variables.get(variable)
                if handle is not None:
                    handle.setncattr(_ATTRIBUTE, tidied)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination


def fix_file(path):
    """Repair one file if it needs it. Returns True unless something went wrong."""
    path = Path(path)
    try:
        untidy = untidy_names(path)
    except Exception as error:
        print(f"{path.name}: could not read ({error})")
        return False

    if not untidy:
        print(f"{path.name}: no issue found")
        return True

    destination = fixed_path_for(path)
    try:
        write_fixed_copy(path, untidy, destination)
    except Exception as error:
        print(f"{path.name}: could not write {destination.name} ({error})")
        return False

    print(f"{path.name}: fixed {', '.join(sorted(untidy))} → wrote {destination.name}")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Fix whitespace in NetCDF long_name attributes that stops MDAL from pairing "
            "u/v components into a vector field."
        ),
        epilog=(
            "The input file is never modified: a file needing repair gets a full copy "
            "alongside it, named <file>_fixed<ext>."
        ),
    )
    parser.add_argument("paths", nargs="+", type=Path, help="NetCDF files to fix")
    args = parser.parse_args(argv)

    try:
        import netCDF4  # noqa: F401
    except ImportError:
        print("netCDF4 is required: pip install netCDF4", file=sys.stderr)
        return 1

    results = [fix_file(path) for path in args.paths]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
