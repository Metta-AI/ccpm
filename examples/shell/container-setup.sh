# Container shell setup — loaded via [shell] file reference
# Sets up the minimal environment for Claude Code in Docker

export PATH="/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin:$HOME/.cargo/bin"

# Source credentials if available
if [ -f "$HOME/.env.claude" ]; then
    set -a
    source "$HOME/.env.claude"
    set +a
fi

# Node.js for MCP servers
if [ -d "$HOME/.nvm" ]; then
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"
fi

# Ensure git is configured
if ! git config user.email &>/dev/null; then
    git config --global user.email "claude@container"
    git config --global user.name "Claude (Container)"
fi
