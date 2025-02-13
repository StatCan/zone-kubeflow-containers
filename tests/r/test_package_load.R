# Function to test if a package can be loaded
test_package_load <- function(package_name) {
  if (!requireNamespace(package_name, quietly = TRUE)) {
    message(sprintf("Package '%s' is not installed. Skipping.", package_name))
    return(FALSE)
  }
  
  message(sprintf("Testing package: %s", package_name))
  
  # Attempt to load the package
  tryCatch({
    library(package_name, character.only = TRUE)
    message(sprintf("Package '%s' loaded successfully.", package_name))
    return(TRUE)
  }, error = function(e) {
    message(sprintf("Failed to load package '%s': %s", package_name, e$message))
    return(FALSE)
  })
}# Get the list of all installed packages
packages_to_test <- installed.packages()[, "Package"]# Run load tests for all installed packages
results <- sapply(packages_to_test, test_package_load)# Summary of results
message("\nTesting completed.")
message("Summary:")
summary_results <- sapply(seq_along(packages_to_test), function(i) {
  pkg <- packages_to_test[i]
  result <- ifelse(results[i], "Success", "Failed")
  sprintf("%s: %s", pkg, result)
})
message(paste(summary_results, collapse = "\n"))# Exit with non-zero code if any test fails
if (!all(results)) {
  stop("One or more packages failed to load. Check the logs for details.", call. = FALSE)
}  
