# Set Personal Package Directory
#-------------------------------
home_dir <- Sys.getenv("HOME")
package_dir <- paste0(home_dir, "/R/", "r-packages-", R.Version()$major, ".", R.Version()$minor)
dir.create(package_dir, recursive = T, showWarnings = F)

# Include any existing older R package directories for seamless upgrade
all_r_package_dirs <- list.files(paste0(home_dir, "/R/"), pattern = "^r-packages-[0-9]+\\.[0-9]+$", full.names = TRUE, include.dirs = TRUE)
existing_r_package_dirs <- all_r_package_dirs[file.info(all_r_package_dirs)$isdir]

# Set library paths with current directory first, then any existing older directories
.libPaths(c(package_dir, existing_r_package_dirs[existing_r_package_dirs != package_dir]))

# Clean up
rm(home_dir)
rm(package_dir)
rm(all_r_package_dirs)
rm(existing_r_package_dirs)

# Add any customizations below
#-----------------------------
#options(stringsAsFactors = FALSE)
#options(prompt = "AAW> ")

# download.file.method is left at R's default (libcurl): the old
# `options(download.file.method="wget")` workaround (aaw-kubeflow-containers#569)
# hides R's HTTP user agent, which Posit Package Manager keys off to serve
# prebuilt binaries instead of source packages.

