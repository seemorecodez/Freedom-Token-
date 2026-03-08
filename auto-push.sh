#!/bin/bash
# FreedomToken Auto-Commit Script
# One-command commit and push to GitHub

cd /root/.openclaw/workspace/freedomtoken-deploy

echo "═══════════════════════════════════════════════════════════"
echo "FreedomToken GitHub Auto-Push"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Check if git is configured
if [ -z "$(git config --global user.name)" ]; then
    echo "❌ Git user name not set"
    echo "Run: git config --global user.name 'Your Name'"
    exit 1
fi

if [ -z "$(git config --global user.email)" ]; then
    echo "❌ Git email not set"
    echo "Run: git config --global user.email 'your@email.com'"
    exit 1
fi

# Check if remote is configured
if ! git remote -v > /dev/null 2>&1; then
    echo "❌ No GitHub remote configured"
    echo "Run: git remote add origin https://github.com/YOUR_USERNAME/freedomtoken.git"
    exit 1
fi

echo "✓ Git configured: $(git config --global user.name)"
echo "✓ Remote: $(git remote get-url origin)"
echo ""

# Check for changes
if git diff-index --quiet HEAD --; then
    echo "No changes to commit"
    exit 0
fi

# Get commit message
DEFAULT_MSG="Update: $(date '+%Y-%m-%d %H:%M')"
read -p "Commit message [${DEFAULT_MSG}]: " msg
COMMIT_MSG=${msg:-$DEFAULT_MSG}

echo ""
echo "Adding files..."
git add .

echo "Committing..."
git commit -m "$COMMIT_MSG"

echo "Pushing to GitHub..."
git push origin master

echo ""
echo "✅ Successfully pushed to GitHub!"
echo "View: $(git remote get-url origin | sed 's/\.git$//' | sed 's/git@github.com:/https:\/\/github.com\//')"