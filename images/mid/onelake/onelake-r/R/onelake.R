ol_command <- function() {
  Sys.getenv("ONELAKE_COMMAND", "onelake")
}

ol_run <- function(args, input = NULL) {
  output <- system2(ol_command(), args = args, input = input, stdout = TRUE, stderr = TRUE)
  status <- attr(output, "status")
  if (!is.null(status) && status != 0) {
    stop(paste(output, collapse = "\n"), call. = FALSE)
  }
  output
}

ol_connect <- function(workspace, lakehouse) {
  if (missing(workspace) || !nzchar(workspace)) {
    stop("workspace is required", call. = FALSE)
  }
  if (missing(lakehouse) || !nzchar(lakehouse)) {
    stop("lakehouse is required", call. = FALSE)
  }
  invisible(ol_run(c("connect", workspace, lakehouse)))
}

ol_status <- function(live = FALSE) {
  args <- "status"
  if (isTRUE(live)) {
    args <- c(args, "--live")
  }
  ol_run(args)
}

ol_ls <- function(path = "/") {
  ol_run(c("ls", path))
}

ol_read_text <- function(path) {
  paste(ol_run(c("cat", path)), collapse = "\n")
}

ol_write_text <- function(path, text) {
  invisible(ol_run(c("write", path), input = text))
}

ol_download <- function(path, local_path) {
  invisible(ol_run(c("get", path, local_path)))
}

ol_upload <- function(local_path, path) {
  invisible(ol_run(c("put", local_path, path)))
}
