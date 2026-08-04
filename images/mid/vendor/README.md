# Vendored internal wheels

`banff` and `banffprocessor` ship from StatCan's internal GitLab
(gitlab.k8s.cloud.statcan.ca/gensys/banff) via Artifactory, which GitHub CI
cannot reach, so the built wheels are vendored here and installed from file.

- `banff` is `py3-none-manylinux` (procs are ctypes-loaded `.so` binaries),
  so one wheel serves every CPython >= 3.11.
- `banffprocessor` is pure Python (`py3-none-any`) and requires
  `banff>=3.2.0`, satisfied by the wheel alongside it.

Vendoring is needed because the public PyPI releases (banff 3.1.3,
banffprocessor 2.0.3) pin `pyarrow<19`, which cannot be satisfied on
Python 3.14. To update either package: download the new wheel from the
GitLab release's Artifactory link, replace the file here, and adjust the
version assertion in tests/mid/test_banff.py.
