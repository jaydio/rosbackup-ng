#!/usr/bin/env bash

_rosbackup_ng_completions()
{
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    opts="--help --dry-run --config-dir --log-file --log-level --no-color --no-parallel --max-parallel --target"

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
            # Complete option names
            COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
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
    opts="-h --help -H --host -u --ssh-user -P --ssh-user-password -i --ssh-user-private-key \
          -p --ssh-port -b --backup-user -B --backup-user-password -g --backup-user-group \
          -k --backup-user-public-key -s --show-backup-credentials -l --log-file -n --no-color \
          -d --dry-run -f --force"

    case "${prev}" in
        -H|--host)
            # No completion for host addresses
            return 0
            ;;
        -u|--ssh-user|-b|--backup-user)
            # No completion for usernames
            return 0
            ;;
        -P|--ssh-user-password|-B|--backup-user-password)
            # No completion for passwords
            return 0
            ;;
        -i|--ssh-user-private-key|-k|--backup-user-public-key)
            # Complete file paths
            COMPREPLY=( $(compgen -f -- ${cur}) )
            return 0
            ;;
        -p|--ssh-port)
            # No completion for port numbers
            return 0
            ;;
        -g|--backup-user-group)
            # Complete common RouterOS groups
            COMPREPLY=( $(compgen -W "full read write" -- ${cur}) )
            return 0
            ;;
        -l|--log-file)
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
