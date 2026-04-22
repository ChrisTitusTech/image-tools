# Contributing to image-tools

Thank you for your interest in contributing.

## Reporting bugs

Open an issue using the bug report template. Include:

- Your OS and Python version
- The exact command you ran
- The full error output or unexpected behavior

## Suggesting features

Open an issue using the feature request template. Describe what you want and why it would be useful.

## Submitting a pull request

1. Fork the repo and create a branch from `main`.
2. Make your changes and keep them focused.
3. Test your changes:

   ```bash
   pipx install --force .
   resize --help
   upscale --help
   resize /path/to/test-image.jpg 1920x1080
   upscale /path/to/test-image.jpg
   ```

4. Open a pull request against `main` and fill in the PR template.

## Development setup

```bash
git clone https://github.com/ChrisTitusTech/image-tools
cd image-tools
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Code style

- Keep changes small and readable.
- Avoid adding new dependencies unless they solve a clear problem.
- Match the surrounding Python and shell style.

## License

By contributing you agree that your contributions will be licensed under the [MIT License](LICENSE).