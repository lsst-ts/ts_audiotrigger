import setuptools
import setuptools_scm

setuptools.setup(
    version=setuptools_scm.get_version(
        version_file="python/lsst/ts/audiotrigger/version.py",
        relative_to="pyproject.toml",
    )
)
