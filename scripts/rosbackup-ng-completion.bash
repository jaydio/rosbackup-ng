#!/usr/bin/env bash

# NOTE: We don't want short-form parameters in favor of long-form only

_rosbackup_ng_completions()
{
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Define all available options (long-form only)
    opts="--help --dry-run --config-dir --log-file --log-level --no-color --no-parallel --max-parallel --target --compose-style --no-tmpfs --tmpfs-size"

    # Check if any output style or logging option is already used
    local has_output_style=false
    local has_logging=false
    for word in "${COMP_WORDS[@]}"; do
        case "$word" in
            --compose-style)
                has_output_style=true
                ;;
            --log-file|--log-level)
                has_logging=true
                ;;
        esac
    done

    case "${prev}" in
        --config-dir)
            # Complete directory paths
            COMPREPLY=( $(compgen -d -- ${cur}) )
            return 0
            ;;
        --log-file)
            # Complete file paths
            COMPREPLY=( $(compgen -f -- ${cur}) )
            return 0
            ;;
        --log-level)
            # Complete log levels
            COMPREPLY=( $(compgen -W "DEBUG INFO WARNING ERROR CRITICAL" -- ${cur}) )
            return 0
            ;;
        --max-parallel)
            # No completion for numbers
            return 0
            ;;
        --tmpfs-size)
            # No completion for size values
            return 0
            ;;
        --target)
            # Complete target names from targets.yaml
            if [ -f "./config/targets.yaml" ]; then
                # Use awk to extract target names from targets.yaml
                local targets=$(awk '/name:/ {print $3}' ./config/targets.yaml)
                COMPREPLY=( $(compgen -W "${targets}" -- ${cur}) )
            fi
            return 0
            ;;
        *)
            # Filter out mutually exclusive options
            local filtered_opts="${opts}"
            if $has_output_style; then
                filtered_opts="${filtered_opts/--log-file/}"
                filtered_opts="${filtered_opts/--log-level/}"
            fi
            if $has_logging; then
                filtered_opts="${filtered_opts/--compose-style/}"
            fi
            COMPREPLY=( $(compgen -W "${filtered_opts}" -- ${cur}) )
            return 0
            ;;
    esac
}

complete -F _rosbackup_ng_completions rosbackup.py

_bootstrap_router_completions()
{
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Define all available options (long-form only)
    opts="--help --host --backup-user-public-key --ssh-user-password --ssh-user-private-key --ssh-user --ssh-port --backup-user --backup-user-password --backup-user-group --show-backup-credentials --log-file --no-color --dry-run --force"

    case "${prev}" in
        --host)
            # No completion for hostnames
            return 0
            ;;
        --backup-user-public-key|--ssh-user-private-key|--log-file)
            # Complete file paths
            COMPREPLY=( $(compgen -f -- ${cur}) )
            return 0
            ;;
        --ssh-user|--backup-user)
            # No completion for usernames
            return 0
            ;;
        --backup-user-group)
            # Complete common RouterOS user groups
            COMPREPLY=( $(compgen -W "read write full" -- ${cur}) )
            return 0
            ;;
        --ssh-port)
            # No completion for port numbers
            return 0
            ;;
        *)
            COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
            return 0
            ;;
    esac
}

complete -F _bootstrap_router_completions bootstrap_router.py
