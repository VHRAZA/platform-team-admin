#!/bin/bash
cp .git-hooks/commit-msg .git/hooks/commit-msg
chmod +x .git/hooks/commit-msg
echo "Git hooks installed."
