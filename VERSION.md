# Version Information

## Versioning Format
rosbackup-ng follows [Semantic Versioning 2.0.0](https://semver.org/):

```
MAJOR.MINOR.PATCH
```

### Version Components

1. **MAJOR** version (0)
   - Incremented for incompatible API changes
   - Currently 0 as we're in initial development
   - Will become 1.0.0 when we have a stable public API

2. **MINOR** version (1)
   - Incremented for added functionality in a backward compatible manner
   - New features that don't break existing functionality
   - Changes to optional parameters or configuration format

3. **PATCH** version (6)
   - Incremented for backward compatible bug fixes
   - Performance improvements
   - Documentation updates
   - No new features added

### Pre-release and Build Metadata
- Pre-release versions will be denoted with a hyphen: `1.0.0-alpha.1`
- Build metadata will be denoted with a plus sign: `1.0.0+20250106`

### Version Zero
During initial development (0.y.z):
- Public API should not be considered stable
- Breaking changes may occur in minor version increments
- Patch version increments for both fixes and backward-compatible features

### Version History
See [CHANGELOG.md](CHANGELOG.md) for detailed version history and changes.
