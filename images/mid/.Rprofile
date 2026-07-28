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

# Package repositories (Posit Package Manager) are configured system-wide in
# /etc/R/Rprofile.site; in-cluster startup appends the internal Artifactory
# PPM remotes there. download.file.method is left at the R default (libcurl):
# the old `options(download.file.method="wget")` workaround (aaw-kubeflow-
# containers#569, needed for conda's R) breaks PPM's prebuilt-binary serving,
# which keys off R's HTTP user agent, and system R does not need it.

