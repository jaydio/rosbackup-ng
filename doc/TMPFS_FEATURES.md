# Tmpfs Features

RouterOS Backup NG includes support for using tmpfs (temporary file system) to reduce wear on the router's flash storage when creating backups. This document explains the feature in detail.

## Overview

When creating binary backups, the tool can use RouterOS's built-in tmpfs support to store the backup file temporarily in RAM instead of writing it directly to the router's flash storage. This helps preserve the lifespan of the router's storage by reducing write cycles.

## How It Works

1. Before creating a backup, the tool:
   - Checks if tmpfs is enabled (default: true)
   - Calculates appropriate tmpfs size based on available memory
   - Creates a tmpfs mount at `/rosbackup/`

2. During backup:
   - The backup file is created in the tmpfs mount
   - The file is downloaded to the backup server
   - The tmpfs is automatically cleaned up

3. If `keep_binary_backup` is true:
   - The backup is moved from tmpfs to root storage
   - The move operation is verified
   - The tmpfs is then cleaned up

## Memory-Based Size Calculation

The tool automatically calculates the appropriate tmpfs size based on the router's available memory:

- For routers with ≥256MB free memory:
  - Uses a fixed size of 50MB

- For routers with <256MB free memory:
  - Uses 1% of the available memory
  - Minimum size is 1MB

## Configuration

### Global Configuration (global.yaml)

```yaml
# Temporary Storage Settings
use_tmpfs: true              # Use tmpfs for temporary storage
tmpfs_fallback: true         # Fall back to EEPROM if tmpfs fails
tmpfs_size: 50M              # Size of tmpfs in MB (optional)
```

### Target-Specific Configuration (targets.yaml)

```yaml
targets:
  - name: ROUTER-1
    # ... other settings ...
    use_tmpfs: true          # Override global setting
    tmpfs_fallback: true     # Override global fallback behavior
    tmpfs_size: 25M          # Override global size
```

### Command Line Options

- `--no-tmpfs` or `-T`: Disable tmpfs usage for all targets
- `--tmpfs-size` or `-s`: Override tmpfs size for all targets (e.g., "25M")

## Fallback Behavior

If tmpfs creation fails:

1. With `tmpfs_fallback: true` (default):
   - Falls back to using root storage
   - Logs a warning message
   - Continues with backup

2. With `tmpfs_fallback: false`:
   - Logs an error message
   - Aborts the backup operation

## Best Practices

1. **Memory Consideration**:
   - Leave sufficient free memory for router operations
   - Monitor memory usage if customizing tmpfs size

2. **Size Configuration**:
   - Use auto-calculation when possible
   - If setting manual size, ensure it's sufficient for your backups
   - Consider router's total memory when setting size

3. **Fallback Settings**:
   - Keep fallback enabled unless you have specific requirements
   - Monitor backup logs for fallback occurrences

4. **Target-Specific Settings**:
   - Override global settings only when necessary
   - Document reasons for target-specific configurations

## Troubleshooting

1. **Tmpfs Creation Fails**:
   - Check available memory
   - Verify tmpfs size is appropriate
   - Check RouterOS version (requires v7+)

2. **Backup Fails with Tmpfs**:
   - Check system logs for errors
   - Verify tmpfs mount point exists
   - Try reducing tmpfs size

3. **Performance Issues**:
   - Monitor memory usage during backups
   - Adjust tmpfs size if needed
   - Consider disabling tmpfs for affected targets

## Technical Details

The tmpfs implementation uses RouterOS's built-in disk management:

```
# Create tmpfs
/disk/add type=tmpfs tmpfs-max-size=50M slot=rosbackup

# Remove tmpfs
/disk/remove [find slot=rosbackup]
```

The tmpfs is automatically mounted at `/rosbackup/` and is used exclusively for temporary backup storage.
