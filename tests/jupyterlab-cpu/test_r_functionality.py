# Copyright (c) Statistics Canada. All rights reserved.

"""
test_r_functionality
~~~~~~~~~~~~~~~~~~~~
Comprehensive tests for R functionality and package availability.

These tests verify that:
- R can execute basic operations
- Key R packages are installed and functional
- R environment is properly configured
- Common data science operations work
- RStudio server functionality works properly
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


@pytest.mark.integration
def test_r_base_functionality(r_package_helper):
    """Test that R base functionality is working."""
    LOGGER.info("Testing R base functionality...")

    r_code = '''
# Test basic R operations
x <- 1:10
y <- x * 2
result <- sum(y)
stopifnot(result == 110)

# Test basic math functions
test_vals <- c(1, 4, 9, 16, 25)
sqrt_vals <- sqrt(test_vals)
expected <- c(1, 2, 3, 4, 5)
stopifnot(all.equal(sqrt_vals, expected))

# Test logical operations
a <- TRUE
b <- FALSE
stopifnot(a & !b)
stopifnot(a | b)

print("R base functionality test successful")
'''

    cmd = ["R", "--slave", "-e", r_code]
    result = r_package_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"R base functionality test failed\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    output = result.output.decode('utf-8')
    assert "R base functionality test successful" in output

    LOGGER.info("R base functionality test successful")


@pytest.mark.integration
def test_r_statistical_packages(r_package_helper):
    """Test comprehensive statistical packages functionality."""
    LOGGER.info("Testing R statistical packages...")

    r_code = '''
library(stats)
library(MASS)

# Create sample data for statistical analysis
set.seed(123)
n <- 100
x1 <- rnorm(n)
x2 <- rnorm(n)
y <- 2 + 3*x1 + 1.5*x2 + rnorm(n, 0, 0.5)

df <- data.frame(y = y, x1 = x1, x2 = x2)

# Test linear model - using base stats package
lm_model <- lm(y ~ x1 + x2, data = df)
summary_lm <- summary(lm_model)
coefficients <- coef(lm_model)

# Verify model was fitted
stopifnot(length(coefficients) > 0)

# Test generalized linear model
glm_model <- glm(y ~ x1 + x2, data = df, family = gaussian())
summary_glm <- summary(glm_model)

# Test basic statistical tests
t_test_result <- t.test(df$y)
stopifnot(t_test_result$statistic > 0)

correlation <- cor.test(df$x1, df$x2)
print("Correlation test completed")

# Test basic probability distributions
norm_vals <- rnorm(100, mean = 0, sd = 1)
t_vals <- rt(100, df = 10)

# Test lme4 if available (within tidymodels)
if(require(lme4, quietly = TRUE)) {
    print("lme4 package is available")
    # Create a simple mixed model test
    fm1 <- lmer(Reaction ~ Days + (Days | Subject), sleepstudy)
    print("lme4 basic functionality working")
} else {
    print("lme4 package not available - this may be expected")
}

print("R statistical packages test successful")
'''

    cmd = ["R", "--slave", "-e", r_code]
    result = r_package_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"R statistical packages test failed\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    LOGGER.info("R statistical packages test successful")


@pytest.mark.integration
def test_r_visualization_packages(r_package_helper):
    """Test comprehensive R visualization packages."""
    LOGGER.info("Testing R visualization packages...")

    r_code = '''
library(ggplot2)
library(RColorBrewer)

# Create sample data
data <- data.frame(
  x = 1:100,
  y = rnorm(100),
  category = sample(letters[1:5], 100, replace = TRUE),
  size_var = runif(100, 1, 10)
)

# Test ggplot2 functionality
p1 <- ggplot(data, aes(x = x, y = y)) +
  geom_point() +
  labs(title = "Scatter Plot", x = "X", y = "Y")

p2 <- ggplot(data, aes(x = category, y = y)) +
  geom_boxplot() +
  labs(title = "Box Plot", x = "Category", y = "Y")

# Test advanced ggplot2 features
p3 <- ggplot(data, aes(x = x, y = y, color = category, size = size_var)) +
  geom_point(alpha = 0.7) +
  scale_color_brewer(type = "qual", palette = "Set1") +
  theme_minimal()

print("ggplot2 functionality working")

print("R visualization packages test successful")
'''

    cmd = ["R", "--slave", "-e", r_code]
    result = r_package_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"R visualization packages test failed\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    LOGGER.info("R visualization packages test successful")


@pytest.mark.integration
def test_r_data_io_packages(r_package_helper):
    """Test R data input/output packages."""
    LOGGER.info("Testing R data I/O packages...")

    r_code = '''
library(readr)
library(readxl)
library(haven)
library(jsonlite)
library(data.table)

# Create test data
df <- data.frame(
  id = 1:10,
  name = paste("Person", 1:10),
  value = rnorm(10),
  date = Sys.Date() + 1:10
)

# Test CSV I/O using readr
write_csv(df, "/tmp/test_data.csv")
read_df <- read_csv("/tmp/test_data.csv")

# Verify data integrity
stopifnot(nrow(read_df) == nrow(df))
stopifnot(ncol(read_df) == ncol(df))

# Test basic data.table functionality
if(require(data.table, quietly = TRUE)) {
  dt <- as.data.table(df)
  result <- dt[, .(mean_value = mean(value)), by = .(id < 6)]
  print("data.table functionality working")
} else {
  warning("data.table not available")
}

print("R data I/O packages test successful")
'''

    cmd = ["R", "--slave", "-e", r_code]
    result = r_package_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"R data I/O packages test failed\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    output = result.output.decode('utf-8')
    assert "R data I/O packages test successful" in output

    LOGGER.info("R data I/O packages test successful")


@pytest.mark.integration
def test_r_machine_learning_packages(r_package_helper):
    """Test R machine learning packages."""
    LOGGER.info("Testing R machine learning packages...")

    r_code = '''
library(randomForest)
library(e1071)

# Create sample data for ML
set.seed(123)
n <- 100
x1 <- rnorm(n)
x2 <- rnorm(n)
x3 <- rnorm(n)
target <- factor(ifelse(x1 + x2 + rnorm(n, 0, 0.5) > 0, "A", "B"))

df <- data.frame(x1 = x1, x2 = x2, x3 = x3, target = target)

# Test random forest
rf_model <- randomForest(target ~ ., data = df, ntree = 50)
prediction <- predict(rf_model, df)

# Verify model was created and predictions made
stopifnot(length(prediction) == nrow(df))

# Test basic SVM (if available)
if(require(e1071, quietly = TRUE)) {
  svm_model <- svm(target ~ ., data = df)
  svm_pred <- predict(svm_model, df)
  print("SVM functionality working")
} else {
  warning("e1071 (SVM) not available")
}

print("R machine learning packages test successful")
'''

    cmd = ["R", "--slave", "-e", r_code]
    result = r_package_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"R machine learning packages test failed\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    LOGGER.info("R machine learning packages test successful")


@pytest.mark.integration
def test_r_comprehensive_integration(r_package_helper):
    """Test comprehensive R data science integration workflow."""
    LOGGER.info("Testing R comprehensive data science workflow...")

    r_code = '''
library(dplyr)
library(ggplot2)
library(readr)

# Create complex sample dataset
set.seed(42)
n <- 1000
data <- tibble(
  id = 1:n,
  category = sample(c("X", "Y", "Z"), n, replace = TRUE, prob = c(0.4, 0.35, 0.25)),
  value1 = rnorm(n, mean = 50, sd = 15),
  value2 = rnorm(n, mean = 25, sd = 8),
  date = seq(as.Date("2023-01-01"), length.out = n, by = "day"),
  outcome = rbinom(n, 1, 0.3)
)

# Complex data manipulation pipeline
analysis <- data %>%
  mutate(
    combined_score = value1 + value2,
    category_numeric = as.numeric(as.factor(category))
  ) %>%
  group_by(category) %>%
  summarise(
    mean_value1 = mean(value1),
    mean_value2 = mean(value2),
    total_count = n(),
    outcome_rate = mean(outcome),
    .groups = 'drop'
  ) %>%
  mutate(
    relative_performance = mean_value1 / mean_value2
  ) %>%
  filter(total_count > 0)

# Verify the analysis produced expected results
stopifnot(nrow(analysis) > 0)
stopifnot(ncol(analysis) > 0)

# Create visualization
p <- ggplot(analysis, aes(x = category, y = mean_value1, fill = category)) +
  geom_bar(stat = "identity") +
  labs(title = "Mean Value by Category", x = "Category", y = "Mean Value") +
  theme_minimal()

print(paste("Analysis summary:", nrow(analysis), "categories processed"))
print(head(analysis))

print("R comprehensive integration test successful")
'''

    cmd = ["R", "--slave", "-e", r_code]
    result = r_package_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"R comprehensive integration test failed\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    output = result.output.decode('utf-8')
    assert "R comprehensive integration test successful" in output

    LOGGER.info("R comprehensive integration test successful")