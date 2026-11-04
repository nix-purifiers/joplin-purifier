import sys
import tarfile
from pathlib import PurePosixPath

with tarfile.open(sys.argv[1]) as archive:
    for entry in archive.getmembers():
        path = PurePosixPath(entry.name)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in entry.name
            or not (entry.isfile() or entry.isdir())
        ):
            raise ValueError("unsupported or unsafe JPL archive member")
