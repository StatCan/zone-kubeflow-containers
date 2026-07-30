# Vendored internal wheels

`banff` ships from StatCan's internal GitLab
(gitlab.k8s.cloud.statcan.ca/gensys/banff/banff-procs) via Artifactory, which
GitHub CI cannot reach, so the built wheel is vendored here and installed from
file. The wheel is `py3-none-manylinux` (procs are ctypes-loaded `.so`
binaries), so one wheel serves every CPython >= 3.11.

Public PyPI still carries banff 3.1.3, whose `pyarrow<19` / `nanoarrow<0.7`
pins cannot be satisfied on Python 3.14.

`banffprocessor` is currently ABSENT from the image on Python 3.14: public
2.0.3 pins `pyarrow<19` (unsatisfiable on 3.14). Drop its updated internal
wheel in this directory and add it to the pip install in ../Dockerfile to
restore it.
