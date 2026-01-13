# Development Notes

## Build Files - Should These Be Committed?

### NOT Recommended to Commit:
- `FactorioModManager.spec` - PyInstaller spec file (generated/regenerated)
- `FactorioModManager.iss` - Inno Setup installer script (optional, platform-specific)
- `build/` directory - Generated build artifacts
- `dist/` directory - Generated executable files

**Why?** These files are:
1. **Generated/Regenerated** - Created during the build process, not source code
2. **Platform-specific** - Different for each build environment
3. **Large** - Binaries can make the repo huge
4. **Frequently updated** - Every rebuild changes them, cluttering commit history
5. **Reproducible** - Can be regenerated from source code anytime

### RECOMMENDED Approach:

1. **For source code:**
   - Commit Python source files only
   - Commit `requirements.txt` and `pyproject.toml`
   - These contain everything needed to rebuild

2. **For releases:**
   - Generate `.spec` and executable on CI/CD (GitHub Actions, etc.)
   - Upload executable to GitHub Releases
   - Users download pre-built .exe from releases

3. **For .gitignore:**
   - Already updated to exclude build files
   - This prevents accidental commits of generated files

## Current .gitignore Settings

```gitignore
# Build and installer files (generated, not needed in repo)
*.spec
*.iss
.pyinstaller/
dist/
build/
```

## Release Process

### For Users:
1. GitHub Release page with download link for `FactorioModManager.exe`
2. README.md points to latest release
3. Users download and run - no installation needed

### For Developers:
1. Build locally with `pyinstaller FactorioModManager.spec --clean`
2. Or use GitHub Actions to auto-build and create release
3. Upload to GitHub Releases

## Workflow Recommendation

```bash
# For local development/testing
pyinstaller FactorioModManager.spec --clean

# Run the built exe from dist/
./dist/FactorioModManager.exe

# For committing - only commit source changes
git add factorio_mod_manager/
git commit -m "Feature/fix description"

# For releasing
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin main --tags
# Then upload exe to GitHub Releases manually or via CI/CD
```

## GitHub Actions CI/CD Option

If you want to automate releases, create `.github/workflows/build.yml`:
```yaml
name: Build and Release
on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt && pip install pyinstaller
      - run: pyinstaller FactorioModManager.spec --clean
      - uses: softprops/action-gh-release@v1
        with:
          files: dist/FactorioModManager.exe
```

This would automatically build and upload the exe to releases when you create a git tag.
