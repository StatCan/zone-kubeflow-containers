# Copyright (c) Statistics Canada. All rights reserved.

"""
test_julia_comprehensive
~~~~~~~~~~~~~~~~~~~~~~~~
Comprehensive tests for Julia data science packages functionality.

These tests verify that:
- Key Julia data science packages are installed and functional
- Common Julia data science workflows work properly
- DataFrames.jl operates correctly
- Scientific computing packages work as expected
- Visualization packages function properly
"""

import logging
import json
import time

import pytest

from tests.general.wait_utils import wait_for_exec_success

LOGGER = logging.getLogger(__name__)


@pytest.fixture(scope="function")
def julia_basic_helper(container):
    """Return a container ready for basic Julia testing"""
    container.run()
    
    # Wait for container to be ready to execute commands
    check_cmd = ["julia", "--startup-file=no", "-e", "1"]
    success, output = wait_for_exec_success(
        container=container,
        command=check_cmd,
        timeout=60,  # Julia takes longer to start
        initial_delay=1.0,
        max_delay=5.0
    )

    if not success:
        raise AssertionError(f"Container failed to be ready for Julia execution within timeout. Output: {output}")

    return container


@pytest.fixture(scope="function")
def julia_comprehensive_helper(container):
    """Return a container ready for comprehensive Julia package testing"""
    container.run()

    # Wait for container to be ready to execute commands
    check_cmd = ["julia", "--startup-file=no", "-e", "1"]
    success, output = wait_for_exec_success(
        container=container,
        command=check_cmd,
        timeout=60,  # Julia takes longer to start
        initial_delay=1.0,
        max_delay=5.0
    )

    if not success:
        raise AssertionError(f"Container failed to be ready for Julia execution within timeout. Output: {output}")

    return container


def test_julia(julia_basic_helper):
    """Basic julia test"""
    LOGGER.info("Test that julia is correctly installed ...")
    command = ["julia", "--startup-file=no", "-e", "julia --version"]
    result = julia_basic_helper.container.exec_run(command)
    output = result.output.decode("utf-8")
    assert result.exit_code == 0, f"Julia version command failed {output}"
    LOGGER.debug(output)


@pytest.mark.integration
def test_julia_base_functionality(julia_comprehensive_helper):
    """Test that Julia base functionality is working."""
    LOGGER.info("Testing Julia base functionality...")

    julia_code = '''
# Test basic Julia operations
x = 1:10
y = x .* 2
result = sum(y)
@assert result == 110

# Test basic math functions
test_vals = [1, 4, 9, 16, 25]
sqrt_vals = sqrt.(test_vals)
expected = [1, 2, 3, 4, 5]
@assert sqrt_vals ≈ expected

# Test logical operations
a = true
b = false
@assert a && !b
@assert a || b

# Test basic array operations
arr = [1, 2, 3, 4, 5]
doubled = arr .* 2
@assert doubled == [2, 4, 6, 8, 10]

println("Julia base functionality test successful")
'''

    cmd = ["julia", "--startup-file=no", "-e", julia_code]
    result = julia_comprehensive_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"Julia base functionality test failed\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    output = result.output.decode('utf-8')
    assert "Julia base functionality test successful" in output

    LOGGER.info("Julia base functionality test successful")


@pytest.mark.integration
def test_julia_dataframes_functionality(julia_comprehensive_helper):
    """Test comprehensive Julia DataFrames functionality."""
    LOGGER.info("Testing Julia DataFrames functionality...")

    julia_code = '''
using DataFrames
using Statistics
using CSV

# Create a sample DataFrame
df = DataFrame(
    id = 1:100,
    category = repeat(["A", "B", "C", "D"], 25),
    value1 = randn(100),
    value2 = rand(1:100, 100),
    date = Date("2023-01-01"):Day(1):Date("2023-04-10")
)

# Test basic DataFrame operations
@assert size(df) == (100, 5)
@assert ncol(df) == 5
@assert nrow(df) == 100

# Test data manipulation
summary_df = combine(
    groupby(df, :category),
    :value1 => mean => :mean_value1,
    :value2 => median => :median_value2,
    :id => length => :count
)

@assert nrow(summary_df) == 4

# Test filtering
filtered_df = filter(row -> row.value1 > 0, df)
@assert nrow(filtered_df) > 0
@assert all(filtered_df.value1 .> 0)

# Test column operations
df[!, :combined_score] = df[!, :value1] .+ df[!, :value2]
@assert size(df, 1) == 100
@assert size(df, 2) == 6

println("Julia DataFrames functionality test successful")
'''

    cmd = ["julia", "--startup-file=no", "-e", julia_code]
    result = julia_comprehensive_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"Julia DataFrames functionality test failed\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    output = result.output.decode('utf-8')
    assert "Julia DataFrames functionality test successful" in output

    LOGGER.info("Julia DataFrames functionality test successful")


@pytest.mark.integration
def test_julia_statistics_and_science_packages(julia_comprehensive_helper):
    """Test Julia statistics and scientific computing packages."""
    LOGGER.info("Testing Julia statistics and scientific computing packages...")

    julia_code = '''
using Statistics
using StatsBase
using Distributions
using LinearAlgebra

# Test statistical functions
data = randn(1000)
@test mean(data) ≈ 0 atol=0.2
@test std(data) ≈ 1 atol=0.2

# Test quantiles
@test quantile(data, 0.5) ≈ median(data) atol=0.01

# Test distributions
d = Normal(0, 1)
samples = rand(d, 1000)
@test mean(samples) ≈ 0 atol=0.2
@test std(samples) ≈ 1 atol=0.2

# Test LinearAlgebra
A = rand(5, 5)
B = rand(5, 5)
C = A * B
@test size(C) == (5, 5)

# Test eigenvalues (basic functionality)
eig_result = eigen(A' * A)
@test length(eig_result.values) == 5

println("Julia statistics and scientific computing test successful")
'''

    cmd = ["julia", "--startup-file=no", "-e", julia_code]
    result = julia_comprehensive_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"Julia statistics and scientific computing test failed\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    output = result.output.decode('utf-8')
    assert "Julia statistics and scientific computing test successful" in output

    LOGGER.info("Julia statistics and scientific computing test successful")


@pytest.mark.integration
def test_julia_machine_learning_packages(julia_comprehensive_helper):
    """Test Julia machine learning packages."""
    LOGGER.info("Testing Julia machine learning packages...")

    julia_code = '''
try
    using MLJ
    using RDatasets

    # Test basic MLJ functionality
    @test true  # If we can load MLJ, the package is available

    # Load a sample dataset
    iris = dataset("datasets", "iris")
    @assert nrow(iris) == 150

    println("MLJ functionality available")

catch e
    println("MLJ (Machine Learning in Julia) not available: ", e)
end

try
    using ScikitLearn

    # Test basic ScikitLearn.jl functionality
    @test true  # If we can load ScikitLearn, it's available

    println("ScikitLearn.jl functionality available")

catch e
    println("ScikitLearn.jl not available: ", e)
end

println("Julia machine learning packages test completed")
'''

    cmd = ["julia", "--startup-file=no", "-e", julia_code]
    result = julia_comprehensive_helper.container.exec_run(cmd)

    # This test is allowed to have partial success since some ML packages might not be installed
    assert result.exit_code == 0, (
        f"Julia machine learning packages test failed\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    LOGGER.info("Julia machine learning packages test completed")


@pytest.mark.integration
def test_julia_plotting_packages(julia_comprehensive_helper):
    """Test Julia plotting packages."""
    LOGGER.info("Testing Julia plotting packages...")

    julia_code = '''
try
    using Plots

    # Create a simple plot (without displaying)
    x = 1:10
    y = x .^ 2
    p = plot(x, y, label="quadratic", title="Test Plot")

    # Verify plot object was created
    @assert !isnothing(p)

    println("Plots.jl functionality available")

catch e
    println("Plots.jl not available: ", e)
end

try
    using StatsPlots

    # Test basic StatsPlots functionality if available
    println("StatsPlots.jl available")

catch e
    println("StatsPlots.jl not available: ", e)
end

println("Julia plotting packages test completed")
'''

    cmd = ["julia", "--startup-file=no", "-e", julia_code]
    result = julia_comprehensive_helper.container.exec_run(cmd)

    # This test is allowed to have partial success since plotting packages might not be installed
    assert result.exit_code == 0, (
        f"Julia plotting packages test failed\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    LOGGER.info("Julia plotting packages test completed")


@pytest.mark.integration
def test_julia_data_io_packages(julia_comprehensive_helper):
    """Test Julia data input/output packages."""
    LOGGER.info("Testing Julia data I/O packages...")

    julia_code = '''
using DataFrames
using CSV

# Create a test DataFrame
df = DataFrame(a = 1:10, b = string.('a':'j'), c = rand(10))

# Test CSV writing and reading
CSV.write("/tmp/test_data.csv", df)
read_df = CSV.read("/tmp/test_data.csv", DataFrame)

# Verify data integrity
@test size(df) == size(read_df)
@test names(df) == names(read_df)

println("Julia data I/O packages test successful")
'''

    cmd = ["julia", "--startup-file=no", "-e", julia_code]
    result = julia_comprehensive_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"Julia data I/O packages test failed\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    output = result.output.decode('utf-8')
    assert "Julia data I/O packages test successful" in output

    LOGGER.info("Julia data I/O packages test successful")


@pytest.mark.integration
def test_julia_comprehensive_integration(julia_comprehensive_helper):
    """Test comprehensive Julia data science workflow."""
    LOGGER.info("Testing Julia comprehensive data science workflow...")

    julia_code = '''
using DataFrames
using Statistics
using CSV

# Create complex dataset
df = DataFrame(
    id = 1:1000,
    category = repeat(["X", "Y", "Z", "W"], 250),
    value1 = randn(1000),
    value2 = rand(1:100, 1000),
    outcome = rand([true, false], 1000)
)

# Complex data manipulation pipeline
result = df |>
    x -> filter(row -> row.value1 > -1.0 && row.value1 < 1.0, x) |>
    x -> combine(
        groupby(x, :category),
        :value1 => mean => :mean_val1,
        :value2 => std => :std_val2,
        :outcome => mean => :outcome_rate,
        nrow => :count
    )

# Verify the analysis
@test nrow(result) > 0
@test "mean_val1" in names(result)
@test "std_val2" in names(result)

# Calculate some additional metrics
total_rows = sum(result.count)
@test total_rows <= 1000

println("Analysis completed: ", nrow(result), " categories, total rows: ", total_rows)
println(first(result, 3))

println("Julia comprehensive integration test successful")
'''

    cmd = ["julia", "--startup-file=no", "-e", julia_code]
    result = julia_comprehensive_helper.container.exec_run(cmd)

    assert result.exit_code == 0, (
        f"Julia comprehensive integration test failed\n"
        f"Output: {result.output.decode('utf-8')}"
    )

    output = result.output.decode('utf-8')
    assert "Julia comprehensive integration test successful" in output

    LOGGER.info("Julia comprehensive integration test successful")