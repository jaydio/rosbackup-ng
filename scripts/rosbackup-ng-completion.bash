#!/usr/bin/env bash

_rosbackup_ng_completions()
{
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    opts="--help --dry-run --config-dir --log-file --log-level --no-color --no-parallel --max-parallel --target --progress-bar --compose-style"

    # Check if any output style or logging option is already used
    local has_output_style=false
    local has_logging=false
    for word in "${COMP_WORDS[@]}"; do
        case "$word" in
            --progress-bar|--compose-style)
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
            local filtered_opts="$opts"
            if [ "$has_output_style" = true ]; then
                # If progress bar or compose style is used, remove logging options and other output style
                filtered_opts=$(echo "$filtered_opts" | tr ' ' '\n' | grep -v -E '^(--progress-bar|--compose-style|--log-file|--log-level)$' | tr '\n' ' ')
            elif [ "$has_logging" = true ]; then
                # If logging options are used, remove output style options
                filtered_opts=$(echo "$filtered_opts" | tr ' ' '\n' | grep -v -E '^(--progress-bar|--compose-style)$' | tr '\n' ' ')
            fi
            # Complete option names
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
    opts="--help --host --ssh-user --ssh-user-password --ssh-user-private-key \
          --ssh-port --backup-user --backup-user-password --backup-user-group \
          --backup-user-public-key --show-backup-credentials --log-file --no-color \
          --dry-run --force"

    case "${prev}" in
        --host)
            # No completion for host addresses
            return 0
            ;;
        --ssh-user|--backup-user)
            # No completion for usernames
            return 0
            ;;
        --ssh-user-password|--backup-user-password)
            # No completion for passwords
            return 0
            ;;
        --ssh-user-private-key|--backup-user-public-key)
            # Complete file paths
            COMPREPLY=( $(compgen -f -- ${cur}) )
            return 0
            ;;
        --ssh-port)
            # No completion for port numbers
            return 0
            ;;
        --backup-user-group)
            # Complete common RouterOS groups
            COMPREPLY=( $(compgen -W "full read write" -- ${cur}) )
            return 0
            ;;
        --log-file)
            # Complete file paths
            COMPREPLY=( $(compgen -f -- ${cur}) )
            return 0
            ;;
        *)
            # Complete option names
            COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
            return 0
            ;;
    esac
}

complete -F _bootstrap_router_completions bootstrap_router.py
