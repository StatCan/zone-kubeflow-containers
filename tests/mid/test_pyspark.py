"""
test_pyspark
~~~~~~~~~~~~
Runtime smoke test for PySpark.

Importing pyspark proves packaging only; actually creating a SparkSession
exercises the JVM handoff, which is where version mismatches surface (Spark 4
requires Java 17+ -- on an image with only Java 8 the import succeeds and the
session start dies). This is the test that would have caught shipping
pyspark 4.x alongside openjdk-8.
"""

import logging
import pytest

from tests.general.wait_utils import wait_for_exec_success

LOGGER = logging.getLogger(__name__)


@pytest.mark.integration
def test_pyspark_session(container):
    """A local SparkSession starts, runs a trivial job, and reports Spark 4"""
    image_name = container.image_name.lower()
    if 'base' in image_name:
        pytest.skip("pyspark not expected in base image")

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
        "from pyspark.sql import SparkSession\n"
        "spark = (SparkSession.builder.master('local[1]')\n"
        "         .config('spark.ui.enabled', 'false')\n"
        "         .appName('smoke').getOrCreate())\n"
        "assert spark.range(10).count() == 10\n"
        "print('spark', spark.version)\n"
        "assert spark.version.startswith('4.'), spark.version\n"
        "spark.stop()\n"
    )
    result = container.container.exec_run(["python3", "-c", test_script])
    output = result.output.decode("utf-8")
    LOGGER.info(f"pyspark smoke: {output[-500:]}")
    assert result.exit_code == 0, output[-2000:]
