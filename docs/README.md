# Elevator Saga Documentation

This directory contains the Sphinx documentation for Elevator Saga.

## Building the Documentation

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Build HTML Documentation

```bash
make html
```

The generated HTML documentation will be in `_build/html/`.

### View Documentation

Open `_build/html/index.html` in your browser:

```bash
# On Linux
xdg-open _build/html/index.html

# On macOS
open _build/html/index.html

# On Windows
start _build/html/index.html
```

### Other Build Formats

```bash
make latexpdf  # Build PDF documentation
make epub      # Build EPUB documentation
make clean     # Clean build directory
```

## Documentation Structure

- `index.rst` - Main documentation index
- `models.rst` - Data models documentation
- `client.rst` - Client architecture and proxy models
- `communication.rst` - HTTP communication protocol
- `events.rst` - Event system and tick-based simulation
- `api/modules.rst` - Auto-generated API reference

## Contributing

When adding new documentation:

1. Create `.rst` files for new topics
2. Add them to the `toctree` in `index.rst`
3. Follow reStructuredText syntax
4. Build locally to verify formatting
5. Submit PR with documentation changes
