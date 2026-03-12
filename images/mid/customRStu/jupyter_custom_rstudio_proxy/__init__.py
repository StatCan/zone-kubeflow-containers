def setup_rstudio():
    start_script = "/opt/jupyter-custom-rstudio-proxy/start_rstudio_server.sh"

    def _command(port):
        return ["bash", start_script, str(port)]

    return {
        "command": _command,
        "timeout": 60,
        "launcher_entry": {
            "title": "RStudio",
        },
    }
