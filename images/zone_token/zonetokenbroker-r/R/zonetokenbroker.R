zone_get_token <- function(scope, command = Sys.getenv("ZONE_TOKEN_COMMAND", "zone-token")) {
  if (missing(scope) || !nzchar(scope)) {
    stop("scope is required", call. = FALSE)
  }

  output <- system2(command, args = c("get", "--scope", scope), stdout = TRUE, stderr = TRUE)
  status <- attr(output, "status")
  if (!is.null(status) && status != 0) {
    stop(paste(output, collapse = "\n"), call. = FALSE)
  }

  trimws(paste(output, collapse = "\n"))
}
