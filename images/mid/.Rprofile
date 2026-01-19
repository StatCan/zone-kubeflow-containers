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

# Inform user about packages from older R versions and provide modern tools
if (length(existing_r_package_dirs[existing_r_package_dirs != current_package_dir]) > 0) {
  package_count <- sum(sapply(existing_r_package_dirs[existing_r_package_dirs != current_package_dir],
                             function(dir) length(list.files(dir))))
  if (package_count > 0) {
    # Show a helpful message about packages from older R versions
    msg <- paste0(
      "\n",
      "┌─────────────────────────────────────────────────────────────┐\n",
      "| INFO: Found ", sprintf("%2d", package_count), " packages from older R versions              |\n",
      "| These are accessible but consider reinstalling for optimal  |\n",
      "| compatibility.                                              |\n",
      "|                                                             |\n",
      "| Quick action:                                               |\n",
      "| • update_old_packages() - Reinstall with pak (fallback R) |\n",
      "└─────────────────────────────────────────────────────────────┘\n"
    )
    packageStartupMessage(msg)

    # Helper function to reinstall old packages using pak with base R fallback
    update_old_packages <- function() {
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
