# Testing Quick Reference

## New Test Commands

### Get Help
```bash
make help-test              # Show detailed test guidance
make test-list              # List all available images
```

### Test All Images (Build + Test)
```bash
make test                   # Builds and tests all available images sequentially
```

### Test Specific Image
```bash
# First, build the image
make bake/base
make bake/jupyterlab-cpu
make bake/sas

# Then test it
make test/base
make test/jupyterlab-cpu
make test/sas
```

### Test Variants
```bash
# Run only critical smoke tests (fast feedback)
make test-smoke/base
make test-smoke/jupyterlab-cpu

# Skip slow and integration tests (for quick iteration)
make test-fast/base
make test-fast/jupyterlab-cpu

# Generate coverage reports
make test-coverage/base
make test-coverage/jupyterlab-cpu
```

## Available Images

- `base` — Foundation image
- `mid` — Extended tools and kernels
- `sas-kernel` — SAS kernel integration
- `jupyterlab-cpu` — Full JupyterLab environment
- `sas` — SAS Studio environment

## Common Workflows

### Quick Development Iteration
```bash
# Build and test quickly (smoke tests only)
make bake/jupyterlab-cpu && make test-smoke/jupyterlab-cpu
```

### Full Validation
```bash
# Build and run all tests
make bake/jupyterlab-cpu && make test/jupyterlab-cpu
```

### Test Everything
```bash
# Build and test all images (takes longer)
make test
```

### Coverage Analysis
```bash
# Build image
make bake/base

# Generate coverage report
make test-coverage/base

# View HTML report
open htmlcov/index.html  # or xdg-open / start depending on OS
```

## Error Messages

If you see `Image name not found in environment variable IMAGE_NAME`, you need to:

1. **Build an image first**: `make bake/<image-name>`
2. **Then test it**: `make test/<image-name>`

Or use the all-in-one command:
```bash
make test  # builds and tests everything
```

## Tips

- `make help-test` — Always available for guidance
- `make test-list` — See what images you can test
- Stack commands for faster iteration: `make bake/base && make test-smoke/base`
- Coverage reports help identify what's being tested: `make test-coverage/base`
