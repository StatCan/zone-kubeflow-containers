import os


def setup_rstudio():
    start_script = "/opt/jupyter-custom-rstudio-proxy/start_rstudio_server.sh"
    base_path = f"{os.environ.get('NB_PREFIX', '')}/rstudio"

    def _command(port):
        return ["bash", start_script, str(port)]

    def _rewrite_response(response):
        location = response.headers.get("Location")
        if location and location.startswith("/") and not location.startswith(base_path):
            response.headers["Location"] = f"{base_path}{location}"

        cookie = response.headers.get("Set-Cookie")
        if cookie and "Path=/" in cookie and f"Path={base_path}/" not in cookie:
            response.headers["Set-Cookie"] = cookie.replace("Path=/", f"Path={base_path}/")

    return {
        "command": _command,
        "timeout": 60,
        "launcher_entry": {
            "title": "RStudio",
        },
        "rewrite_response": _rewrite_response,
    }
