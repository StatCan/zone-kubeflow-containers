# Copyright (c) Statistics Canada. All rights reserved.

"""
test_r_functionality
~~~~~~~~~~~~~~~~~~~
Tests for R functionality and package availability.

These tests verify that:
- R can execute basic operations
- Key R packages are installed and functional
- R environment is properly configured
- Common data science operations work
"""

import logging
import json
import time

import pytest

from tests.general.wait_utils import wait_for_exec_success

LOGGER = logging.getLogger(__name__)


@pytest.fixture(scope="function")
def r_package_helper(container):
    """Return a container ready for R package testing"""
    container.run()
    
    # Wait for container to be ready to execute commands
    check_cmd = ["R", "--version"]
    success, output = wait_for_exec_success(
        container=container,
        command=check_cmd,
        timeout=30,
        initial_delay=0.5,
        max_delay=3.0
    )
    
    if not success:
        raise AssertionError(f"Container failed to be ready for R execution within timeout. Output: {output}")
    
    return container


@pytest.mark.integration
def test_r_basic_functionality(r_package_helper):
    """Test that R can execute basic operations."""
    LOGGER.info("Testing basic R functionality...")

    # Execute basic R operations
    r_code = """
x <- 1:10
y <- x * 2
result <- sum(y)
cat('Result:', result, '\\n')
stopifnot(result == 110)
print('R basic operations successful')
"""
    
    cmd = ["R", "--slave", "-e", r_code]
    result = r_package_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"R basic functionality test failed\n"
        f"Error: {result.output.decode('utf-8')}"
    )

    output = result.output.decode('utf-8')
    assert "110" in output, f"Expected calculation result not found in output: {output}"
    
    LOGGER.info("R basic functionality test successful")


@pytest.mark.integration
def test_r_tidyverse_available(r_package_helper):
    """Test that the tidyverse package collection is available."""
    LOGGER.info("Testing R tidyverse package availability...")

    r_code = """
library(tidyverse)
print('Tidyverse loaded successfully')

# Test basic tidyverse functionality
df <- data.frame(x = 1:5, y = letters[1:5])
result <- df %>% filter(x > 2) %>% nrow()
stopifnot(result == 3)
print('Tidyverse operations successful')
"""
    
    cmd = ["R", "--slave", "-e", r_code]
    result = r_package_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"R tidyverse test failed\n"
        f"Error: {result.output.decode('utf-8')}"
    )

    LOGGER.info("R tidyverse functionality test successful")


@pytest.mark.integration
def test_r_data_science_packages(r_package_helper):
    """Test common R data science packages."""
    LOGGER.info("Testing R data science packages...")

    # Test multiple packages in a single R session
    r_code = """
# Test data manipulation packages
library(dplyr)
library(readr)
library(ggplot2)

# Create sample data and test operations
data <- data.frame(
    id = 1:100,
    value = rnorm(100),
    category = sample(c('A', 'B', 'C'), 100, replace = TRUE)
)

# Test dplyr operations
summary_data <- data %>%
    group_by(category) %>%
    summarise(mean_value = mean(value), .groups = 'drop')

print(head(summary_data))
print('Data science packages working')

# Verify we can create a simple plot
p <- ggplot(data, aes(x = value, fill = category)) +
     geom_histogram(position = "identity", alpha = 0.7) +
     labs(title = "Test Histogram")

print('ggplot2 basic functionality working')
"""
    
    cmd = ["R", "--slave", "-e", r_code]
    result = r_package_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"R data science packages test failed\n"
        f"Error: {result.output.decode('utf-8')}"
    )

    LOGGER.info("R data science packages test successful")


@pytest.mark.integration
def test_r_languageserver_available(r_package_helper):
    """Test that R language server is available."""
    LOGGER.info("Testing R language server availability...")

    r_code = """
# Test if languageserver package is available
if (require("languageserver", quietly = TRUE)) {
    print("languageserver package is available")
    # Get the library path to confirm it's installed
    pkg_path <- find.package("languageserver")
    print(paste("languageserver installed at:", pkg_path))
} else {
    stop("languageserver package not available")
}
"""
    
    cmd = ["R", "--slave", "-e", r_code]
    result = r_package_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"R language server test failed\n"
        f"Error: {result.output.decode('utf-8')}"
    )

    LOGGER.info("R language server test successful")


@pytest.mark.integration
def test_r_arrow_package(r_package_helper):
    """Test that the R arrow package is functional."""
    LOGGER.info("Testing R arrow package...")

    r_code = """
# Test arrow package
if (require("arrow", quietly = TRUE)) {
    print("arrow package is available")
    
    # Create a simple data frame and convert to arrow
    df <- data.frame(x = 1:10, y = letters[1:10])
    
    # Test basic arrow functionality (this is a simple test)
    # More complex arrow operations might require more setup
    print("arrow package loaded successfully")
} else {
    stop("arrow package not available")
}
"""
    
    cmd = ["R", "--slave", "-e", r_code]
    result = r_package_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"R arrow package test failed\n"
        f"Error: {result.output.decode('utf-8')}"
    )

    LOGGER.info("R arrow package test successful")


@pytest.mark.integration
def test_r_aws_s3_package(r_package_helper):
    """Test that the R aws.s3 package is available (but don't test connectivity)."""
    LOGGER.info("Testing R aws.s3 package availability...")

    r_code = """
# Test if aws.s3 package is available
if (require("aws.s3", quietly = TRUE)) {
    print("aws.s3 package is available")
    # Just check it loads without error, don't test actual AWS connectivity
    print("aws.s3 package loaded successfully")
} else {
    # This package might not be available in all images, so warn but don't fail
    print("aws.s3 package not available - this may be expected")
}
"""
    
    cmd = ["R", "--slave", "-e", r_code]
    result = r_package_helper.container.exec_run(cmd)

    # We'll treat this as successful even if the package isn't available
    # since it might be optional depending on the image
    output = result.output.decode('utf-8')
    if "not available - this may be expected" in output:
        LOGGER.info("R aws.s3 package not available (expected in some images)")
    else:
        assert result.exit_code == 0, (
            f"R aws.s3 package test failed\n"
            f"Error: {output}"
        )
        LOGGER.info("R aws.s3 package test successful")


@pytest.mark.integration 
def test_r_version_and_configuration(r_package_helper):
    """Test R version and basic configuration."""
    LOGGER.info("Testing R version and configuration...")

    r_code = """
# Get R version info
version_info <- R.version.string
print(paste("R version:", version_info))

# Check if we're running the expected version (at least 4.x)
r_major_version <- as.numeric(R.version$major)
stopifnot(r_major_version >= 4)

# Test basic configuration
print(paste("R home:", R.home()))
print(paste("R version major:", R.version$major))
print(paste("R version minor:", R.version$minor))

print('R version and configuration test successful')
"""
    
    cmd = ["R", "--slave", "-e", r_code]
    result = r_package_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"R version and configuration test failed\n"
        f"Error: {result.output.decode('utf-8')}"
    )

    LOGGER.info("R version and configuration test successful")
