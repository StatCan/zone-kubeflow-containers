
# Zone Browser: interactive sign-in pages (AzureAuth, AzureRMR, httr OAuth,
# any browseURL()) must open in the secure browser that runs inside this
# workspace, never on the user's device. Plain R already honours R_BROWSER,
# but RStudio replaces options("browser") at session init with a handler
# that opens URLs in the user's LOCAL browser -- re-assert ours after
# RStudio finishes initialising.
local({
    zone_browser <- function(url) {
        invisible(system2("/usr/local/bin/zone-browser", shQuote(url),
                          wait = FALSE))
    }
    if (file.exists("/usr/local/bin/zone-browser")) {
        options(browser = zone_browser)
        setHook("rstudio.sessionInit", function(newSession) {
            options(browser = zone_browser)
        }, action = "append")
    }
})
