"""
test_banff
~~~~~~~~~~
Test the vendored banff wheel (see images/mid/vendor/README.md).

banff is installed from an internal StatCan wheel rather than PyPI, and its
procedures are ctypes-loaded native libraries, so an import alone exercises
the packaging, the dependency set (pyarrow/nanoarrow/pandas/duckdb), and the
bundled binaries' loadability.
"""

import logging
import pytest

from tests.general.wait_utils import wait_for_exec_success

LOGGER = logging.getLogger(__name__)


@pytest.mark.integration
def test_banff_import(container):
    """banff imports and reports the vendored 3.2.x version"""
    image_name = container.image_name.lower()
    if 'base' in image_name:
        pytest.skip("banff not expected in base image")

    container.run()

    success, output = wait_for_exec_success(
        container=container,
        command=["python3", "--version"],
        timeout=30,
        initial_delay=0.5,
        max_delay=3.0,
    )
    if not success:
        raise AssertionError(
            f"Container failed to be ready for execution within timeout. Output: {output}"
        )

    test_script = (
        "import banff\n"
        "import pyarrow\n"
        "import nanoarrow\n"
        "print('banff', banff.__version__)\n"
        "print('pyarrow', pyarrow.__version__)\n"
        "assert banff.__version__.startswith('3.2'), banff.__version__\n"
    )
    result = container.container.exec_run(["python3", "-c", test_script])
    output = result.output.decode("utf-8")
    LOGGER.info(f"banff import: {output}")
    assert result.exit_code == 0, output
