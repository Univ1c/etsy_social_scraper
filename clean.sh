#!/bin/bash

echo "🧼 Cleaning up __pycache__ and .pyc files..."

# Delete all __pycache__ folders
find . -type d -name '__pycache__' -exec rm -r {} + 2>/dev/null

# Delete all .pyc files
find . -type f -name '*.pyc' -delete 2>/dev/null

echo "✅ Cleanup complete!"