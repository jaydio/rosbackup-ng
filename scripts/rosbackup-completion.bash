#!/usr/bin/env bash

_rosbackup_completions()
{
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    opts="--help --dry-run --config-dir --log-file --log-level"

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
        *)
            # Complete option names
            COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
            return 0
            ;;
    esac
}

complete -F _rosbackup_completions rosbackup.py

_bootstrap_router_completions()
{
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    opts="--help --host --ssh-user --ssh-user-password --ssh-user-private-key --ssh-port --backup-user --backup-user-password --backup-user-public-key --backup-user-group --show-backup-credentials --log-file --no-color"

    case "${prev}" in
        --host)
            # No completion for host, user needs to type IP/hostname
            return 0
            ;;
        --ssh-user|--backup-user)
            # No completion for usernames
            return 0
            ;;
        --ssh-user-private-key|--backup-user-public-key|--log-file)
            # Complete file paths
            COMPREPLY=( $(compgen -f -- ${cur}) )
            return 0
            ;;
        --backup-user-group)
            # Complete common RouterOS groups
            COMPREPLY=( $(compgen -W "full read write" -- ${cur}) )
            return 0
            ;;
        --ssh-port)
            # No completion for port numbers
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
