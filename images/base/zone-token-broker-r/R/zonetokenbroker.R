#' Get a delegated access token from the in-cluster AuthService
#'
#' Calls the AuthService `getPassthroughToken` endpoint and returns the access
#' token as a character scalar. Mirrors the behaviour of the Python
#' `zone_token_broker` module: same default endpoint, same env-var overrides,
#' same 30-second timeout.
#'
#' @param scope Required. Resource scope, e.g. `"https://storage.azure.com/.default"`
#'   for OneLake DFS or `"https://api.fabric.microsoft.com/.default"` for Fabric REST.
#' @param broker_url Optional override for the AuthService base URL. Defaults to
#'   `Sys.getenv("ONELAKE_BROKER_URL")` if set, otherwise the in-cluster
#'   AuthService URL.
#' @param token_path Optional override for the token endpoint path. Defaults to
#'   `Sys.getenv("ONELAKE_BROKER_TOKEN_PATH")` if set, otherwise
#'   `"/getPassthroughToken"`.
#' @return A character scalar containing the bearer access token.
#' @export
zone_get_token <- function(scope, broker_url = NULL, token_path = NULL) {
  if (missing(scope) || !nzchar(scope)) {
    stop("scope is required", call. = FALSE)
  }
  if (is.null(broker_url) || !nzchar(broker_url)) {
    broker_url <- Sys.getenv(
      "ONELAKE_BROKER_URL",
      "http://authservice.kubeflow.svc.cluster.local:8080/authservice"
    )
  }
  if (is.null(token_path) || !nzchar(token_path)) {
    token_path <- Sys.getenv("ONELAKE_BROKER_TOKEN_PATH", "/getPassthroughToken")
  }

  url <- paste0(sub("/+$", "", broker_url), "/", sub("^/+", "", token_path))

  resp <- httr::GET(url, query = list(scope = scope), httr::timeout(30))
  httr::stop_for_status(resp)

  text <- trimws(httr::content(resp, as = "text", encoding = "UTF-8"))
  if (startsWith(text, "Bearer ")) {
    text <- trimws(substring(text, 8))
  }
  if (!nzchar(text)) {
    stop("token broker response is empty", call. = FALSE)
  }
  text
}
