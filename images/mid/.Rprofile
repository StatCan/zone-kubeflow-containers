# Set Personal Package Directory
#-------------------------------
home_dir <- Sys.getenv("HOME")
package_dir <- paste0(home_dir, "/R/", "r-packages-", R.Version()$major, ".", R.Version()$minor)
dir.create(package_dir, recursive = T, showWarnings = F)
# Only this R version's library: packages built for an older R are not
# binary-compatible and must be reinstalled after an R upgrade.
.libPaths(new = package_dir)
# Clean up
rm(home_dir)
rm(package_dir)

# Add any customizations below
#-----------------------------
#options(stringsAsFactors = FALSE)
#options(prompt = "AAW> ")

# download.file.method is left at R's default (libcurl): the old
# `options(download.file.method="wget")` workaround (aaw-kubeflow-containers#569)
# hides R's HTTP user agent, which Posit Package Manager keys off to serve
# prebuilt binaries instead of source packages.

