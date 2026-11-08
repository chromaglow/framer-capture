"""PyInstaller entry point. Runs the package entry so relative imports inside `framer` work when frozen."""
import sys

from framer.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
