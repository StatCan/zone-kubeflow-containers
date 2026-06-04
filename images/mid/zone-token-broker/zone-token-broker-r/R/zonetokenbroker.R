# In-memory token cache for the session, keyed by scope. Mirrors the Python
# zone_token_broker module: a cached token is reused until it is within
# EXPIRY_BUFFER_SECONDS of its expiry.
.broker_cache <- new.env(parent = emptyenv())
.EXPIRY_BUFFER_SECONDS <- 300

#' Get a delegated access token from the in-cluster AuthService
#'
#' Calls the AuthService token endpoint and returns the access token as a
#' character scalar. Mirrors the behaviour of the Python `zone_token_broker`
#' module: same default endpoint, same env-var overrides, same 30-second
#' timeout, and the same per-scope in-memory caching.
#'
#' @param scope Required. Resource scope, e.g.
#'   `"https://storage.azure.com/.default"` or
#'   `"https://api.fabric.microsoft.com/.default"`.
#' @param broker_url Optional override for the AuthService base URL. Defaults to
#'   `Sys.getenv("AUTHSERVICE_BROKER_URL")` if set, otherwise the in-cluster
#'   AuthService URL.
#' @param token_path Optional override for the token endpoint path. Defaults to
#'   `Sys.getenv("AUTHSERVICE_BROKER_TOKEN_PATH")` if set, otherwise
#'   `"/authservice/getPassthroughToken"`.
#' @return A character scalar containing the bearer access token.
#' @export
zone_get_token <- function(scope, broker_url = NULL, token_path = NULL) {
  if (missing(scope) || !nzchar(scope)) {
    stop("scope is required", call. = FALSE)
  }
  if (is.null(broker_url) || !nzchar(broker_url)) {
    broker_url <- Sys.getenv(
      "AUTHSERVICE_BROKER_URL",
      "http://authservice.kubeflow.svc.cluster.local:8080"
    )
  }
  if (is.null(token_path) || !nzchar(token_path)) {
    token_path <- Sys.getenv(
      "AUTHSERVICE_BROKER_TOKEN_PATH",
      "/authservice/getPassthroughToken"
    )
  }

  cached <- .broker_cache[[scope]]
  if (!is.null(cached) &&
    as.numeric(Sys.time()) < cached$expires_on - .EXPIRY_BUFFER_SECONDS) {
    return(cached$access_token)
  }

  url <- paste0(sub("/+$", "", broker_url), "/", sub("^/+", "", token_path))

  resp <- httr::GET(url, query = list(scope = scope), httr::timeout(30))
  httr::stop_for_status(resp)

  text <- httr::content(resp, as = "text", encoding = "UTF-8")
  if (is.na(text)) text <- ""
  text <- trimws(text)
  if (!nzchar(text)) {
    stop("token broker response is empty", call. = FALSE)
  }
  if (startsWith(text, "Bearer ")) {
    text <- trimws(substring(text, 8))
  }

  .broker_cache[[scope]] <- list(
    access_token = text,
    expires_on = .token_expires_on(text)
  )
  text
}

# Extract the JWT `exp` claim (epoch seconds) from a bearer token, mirroring the
# Python module's _expires_on, so cached tokens can be expired proactively.
.token_expires_on <- function(token) {
  parts <- strsplit(token, ".", fixed = TRUE)[[1]]
  if (length(parts) < 2) {
    stop("token broker response did not contain a JWT access token", call. = FALSE)
  }
  payload <- chartr("-_", "+/", parts[[2]])
  pad <- nchar(payload) %% 4
  if (pad > 0) {
    payload <- paste0(payload, strrep("=", 4 - pad))
  }
  claims <- tryCatch(
    jsonlite::fromJSON(rawToChar(jsonlite::base64_dec(payload))),
    error = function(e) NULL
  )
  if (is.null(claims) || is.null(claims$exp)) {
    stop("token broker response did not contain a usable JWT exp claim", call. = FALSE)
  }
  as.numeric(claims$exp)
}
