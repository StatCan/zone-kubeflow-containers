# Seamless R Package Upgrade Setup
# Sets up personal library with automatic migration support

# Create current R version's package directory
home_dir <- Sys.getenv("HOME")
current_version <- paste0(R.Version()$major, ".", R.Version()$minor)
current_package_dir <- file.path(home_dir, "R", paste0("r-packages-", current_version))
dir.create(current_package_dir, recursive = TRUE, showWarnings = FALSE)

# Find existing package directories from older R versions
r_dir <- file.path(home_dir, "R")
existing_dirs <- list.dirs(r_dir, full.names = TRUE, recursive = FALSE)
existing_dirs <- existing_dirs[grepl("r-packages-\\d+\\.\\d+", basename(existing_dirs))]
existing_dirs <- existing_dirs[existing_dirs != current_package_dir]

# Set library paths (current first, then older versions)
.libPaths(c(current_package_dir, existing_dirs))

# Migration helper function
update_old_packages <- function(force = FALSE) {
  # Skip if migration was already done and not forced
  if (!force && exists(".package_migration_done", envir = .GlobalEnv)) {
    message("Package migration already completed. Use force=TRUE to repeat.")
    return(invisible())
  }

  # Get packages from old directories
  old_pkgs <- unique(unlist(lapply(existing_dirs, list.files)))
  if (length(old_pkgs) == 0) {
    message("No packages found in old directories.")
    return(invisible())
  }

  message("Migrating ", length(old_pkgs), " packages to R ", current_version, "...")

  # Try pak first, fall back to base install
  if (requireNamespace("pak", quietly = TRUE)) {
    pak::pkg_install(old_pkgs)
    message("✓ Migration complete using pak")
  } else {
    message("Installing packages with base R...")
    install.packages(old_pkgs, dependencies = TRUE, repos = getOption("repos"))
    message("✓ Migration complete using base R")
  }

  # Mark migration as done
  assign(".package_migration_done", TRUE, envir = .GlobalEnv)
}

# Auto-migrate if this is a new R version
if (length(existing_dirs) > 0) {
  # Extract version numbers from directory names
  old_versions <- gsub("r-packages-(\\d+\\.\\d+).*", "\\1", basename(existing_dirs))

  # Check if any old directories are from different R versions
  if (any(old_versions != current_version)) {
    cat("\n📦 R ", current_version, " detected with packages from older version(s)\n")
    cat("   Run update_old_packages() to migrate\n\n")

    # Auto-migrate if current directory is empty
    if (length(list.files(current_package_dir)) == 0) {
      cat("Auto-migrating packages...\n")
      tryCatch({
        update_old_packages()
        cat("✓ Migration completed successfully\n")
      }, error = function(e) {
        cat("⚠ Migration failed: ", e$message, "\n")
        cat("  Run update_old_packages() manually to retry\n")
      })
    }
  }
}

# Export migration function
assign("update_old_packages", update_old_packages, envir = .GlobalEnv)

# Set download method for best compatibility
if (capabilities("libcurl")) {
  options(download.file.method = "libcurl")
} else if (Sys.which("wget") != "") {
  options(download.file.method = "wget")
} else {
  options(download.file.method = "libcurl")  # fallback
}

# Cleanup
rm(home_dir, current_package_dir, r_dir, existing_dirs, current_version)
