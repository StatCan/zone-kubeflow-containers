"""Register local filesystem adapters for tools that discover fsspec protocols."""

try:
    import fsspec

    fsspec.register_implementation(
        "onelake",
        "onelake_fsspec.OneLakeFileSystem",
        clobber=True,
    )
except ImportError:
    pass
