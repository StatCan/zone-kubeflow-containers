if [ -n "$BASH_VERSION" ]; then
    if [ -f "$HOME/.bashrc" ]; then
        . "$HOME/.bashrc"
    fi
fi
# Persist the active conda env for RStudio Server in the user's home directory so that it can be reloaded on subsequent sessions.
__persist_rstudio_conda_env() {
    local state_dir env_file env_path

    [ -n "$HOME" ] || return 0

    state_dir="$HOME/.local/share/rstudio"
    env_file="$state_dir/active_conda_env"
    env_path="${CONDA_PREFIX:-/opt/conda}"

    mkdir -p "$state_dir" 2>/dev/null || return 0
    [ -n "$env_path" ] || return 0

    printf '%s\n' "$env_path" > "$env_file"
}

if [ -n "$PS1" ]; then
    case ";${PROMPT_COMMAND};" in
        *";__persist_rstudio_conda_env;"*) ;;
        *) PROMPT_COMMAND="__persist_rstudio_conda_env${PROMPT_COMMAND:+;${PROMPT_COMMAND}}" ;;
    esac

    __persist_rstudio_conda_env
fi
