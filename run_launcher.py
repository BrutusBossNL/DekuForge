"""Entry point that also supports Python's isolated Windows distribution."""

from pathlib import Path
import os
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))


def prepare_tk():
    """Use optional Tcl libraries supplied alongside an embedded interpreter."""
    source = Path(sys.executable).parent / "tcl"
    target = Path(__file__).resolve().parent / "local" / "python-support"
    for component, variable in (("tcl", "TCL_LIBRARY"), ("tk", "TK_LIBRARY")):
        if variable in os.environ:
            continue
        archives = sorted(source.glob(f"lib{component}*.zip"))
        if not archives:
            continue
        library = target / f"{component}_library"
        if not (library / ("init.tcl" if component == "tcl" else "tk.tcl")).is_file():
            with zipfile.ZipFile(archives[-1]) as archive:
                for member in archive.infolist():
                    destination = (target / member.filename).resolve()
                    if not destination.is_relative_to(target.resolve()):
                        raise ValueError("Unsafe path in local Python library archive")
                archive.extractall(target)
        os.environ[variable] = str(library)


if __name__ == "__main__":
    prepare_tk()
    from dekuforge.__main__ import main
    main()
