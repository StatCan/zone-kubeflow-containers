# Set Personal Package Directory with modern upgrade support
#------------------------------------------------------------
home_dir <- Sys.getenv("HOME")

# Current R version-specific package directory
current_package_dir <- paste0(home_dir, "/R/", "r-packages-", R.Version()$major, ".", R.Version()$minor)
dir.create(current_package_dir, recursive = T, showWarnings = F)

# Include any existing older R package directories for seamless upgrade
all_r_package_dirs <- list.files(paste0(home_dir, "/R/"), pattern = "^r-packages-[0-9]+\\.[0-9]+$", full.names = TRUE, include.dirs = TRUE)
existing_r_package_dirs <- all_r_package_dirs[file.info(all_r_package_dirs)$isdir]

# Set library paths with current directory first, then any existing older directories
.libPaths(c(current_package_dir, existing_r_package_dirs[existing_r_package_dirs != current_package_dir]))

# Check for packages from older R versions and handle automatically if needed
old_package_dirs <- existing_r_package_dirs[existing_r_package_dirs != current_package_dir]
has_old_packages <- length(old_package_dirs) > 0 &&
                   any(sapply(old_package_dirs, function(dir) length(list.files(dir))) > 0)

if (has_old_packages) {
  # Count packages in old directories
  package_count <- sum(sapply(old_package_dirs, function(dir) length(list.files(dir))))

  # Check if this is likely a new R version upgrade by comparing version numbers
  current_version <- paste0(R.Version()$major, ".", R.Version()$minor)
  old_versions <- sapply(old_package_dirs, function(dir) {
    version_match <- regmatches(dir, regexec("r-packages-([0-9]+\\.[0-9]+(?:\\.[0-9]+)?)", basename(dir)))
    if (length(version_match[[1]]) > 1) version_match[[1]][2] else NA
  })

  # Determine if there are different R versions represented
  different_versions_exist <- any(!is.na(old_versions) & old_versions != current_version)

  if (different_versions_exist) {
    # This appears to be an R version upgrade - suggest automatic migration
    msg <- paste0(
      "\n",
      "┌─────────────────────────────────────────────────────────────┐\n",
      "| UPGRADE: R upgraded to ", current_version, " - ", sprintf("%2d", package_count), " packages from old R    |\n",
      "| versions detected.                                          |\n",
      "|                                                             |\n",
      "| Auto-migrating packages for optimal compatibility...        |\n",
      "| (Run update_old_packages(force=TRUE) to repeat migration)   |\n",
      "└─────────────────────────────────────────────────────────────┘\n"
    )
    packageStartupMessage(msg)

    # Function to reinstall old packages with pak and base R fallback
    update_old_packages <- function(force = FALSE) {
      # Skip if not forced and auto-migration already happened
      if (!force && exists("auto_migration_completed", envir = .GlobalEnv)) {
        message("Auto-migration already completed. Use update_old_packages(force=TRUE) to repeat.")
        return(invisible(NULL))
      }

      old_dirs <- existing_r_package_dirs[existing_r_package_dirs != current_package_dir]
      all_pkgs <- c()

      for (old_dir in old_dirs) {
        pkgs_in_dir <- list.files(old_dir, full.names = FALSE)
        all_pkgs <- union(all_pkgs, pkgs_in_dir)
      }

      if (length(all_pkgs) > 0) {
        if (requireNamespace("pak", quietly = TRUE)) {
          message("Reinstalling ", length(all_pkgs), " packages using pak (parallel, optimized)...")
          pak::pkg_install(all_pkgs)
          message("Pak reinstallation complete!")
        } else {
          message("pak not available. Installing with base R...")
          install.packages(all_pkgs, repos = getOption("repos"))
          message("Base R reinstallation complete!")
        }
        # Mark that auto-migration has been completed
        assign("auto_migration_completed", TRUE, envir = .GlobalEnv)
      } else {
        message("No packages found in old directories.")
      }
    }

    # Export helper function to global environment
    assign("update_old_packages", update_old_packages, envir = .GlobalEnv)

    # Automatically trigger migration for R version upgrades
    update_old_packages()
  } else {
    # Same R version - just inform user about existing packages
    msg <- paste0(
      "\n",
      "┌─────────────────────────────────────────────────────────────┐\n",
      "| INFO: Found ", sprintf("%2d", package_count), " packages from previous sessions                |\n",
      "| These are accessible.                                       |\n",
      "|                                                             |\n",
      "| Run update_old_packages() to reinstall if needed.           |\n",
      "└─────────────────────────────────────────────────────────────┘\n"
    )
    packageStartupMessage(msg)

    # Helper function for manual migration
    update_old_packages <- function(force = FALSE) {
      old_dirs <- existing_r_package_dirs[existing_r_package_dirs != current_package_dir]
      all_pkgs <- c()

      for (old_dir in old_dirs) {
        pkgs_in_dir <- list.files(old_dir, full.names = FALSE)
        all_pkgs <- union(all_pkgs, pkgs_in_dir)
      }

      if (length(all_pkgs) > 0) {
        if (requireNamespace("pak", quietly = TRUE)) {
          message("Reinstalling ", length(all_pkgs), " packages using pak (parallel, optimized)...")
          pak::pkg_install(all_pkgs)
          message("Pak reinstallation complete!")
        } else {
          message("pak not available. Installing with base R...")
          install.packages(all_pkgs, repos = getOption("repos"))
          message("Base R reinstallation complete!")
        }
      } else {
        message("No packages found in old directories.")
      }
    }

    # Export helper function to global environment
    assign("update_old_packages", update_old_packages, envir = .GlobalEnv)
  }
} else {
  # No old packages found - define a simple function for completeness
  update_old_packages <- function(force = FALSE) {
    message("No packages from older R versions found to migrate.")
  }

  # Export helper function to global environment
  assign("update_old_packages", update_old_packages, envir = .GlobalEnv)
}

# Clean up
rm(home_dir, current_package_dir, all_r_package_dirs, existing_r_package_dirs)

# Add any customizations below
#-----------------------------
#options(stringsAsFactors = FALSE)
#options(prompt = "AAW> ")

# Modern download method for compatibility
options(download.file.method = "libcurl")
# For older systems that don't support libcurl, fall back to wget
if (capabilities("libcurl")) {
  options(download.file.method = "libcurl")
} else {
  options(download.file.method = "wget")
}
