"""Register the OneLake fsspec implementation."""

try:
    import fsspec

    fsspec.register_implementation(
        "onelake",
        "onelake_fsspec.OneLakeFileSystem",
        clobber=True,
    )
except ImportError:
    pass
