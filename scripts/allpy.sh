#!/bin/bash

# Usage: ./print_python.sh /path/to/directory
DIR="${1:-.}"  # default to current directory if no argument given

# Find all .py files recursively
find "$DIR" -type f -name "*.py" | while read -r file; do
    echo "===== $file ====="
    cat "$file"
    echo -e "\n"
done
