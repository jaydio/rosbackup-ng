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
