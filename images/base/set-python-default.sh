#!/bin/bash
# Set conda Python as the default system Python
# This ensures /opt/conda/bin/python is selected over /usr/bin/python3

set -e

CONDA_PYTHON="/opt/conda/bin/python3"

# Check if conda python exists
if [ ! -f "$CONDA_PYTHON" ]; then
    echo "Warning: Conda Python not found at $CONDA_PYTHON"
    exit 0
fi

# Method 1: Update /etc/environment to prioritize conda in PATH
# This affects all sessions system-wide
if ! grep -q "/opt/conda/bin" /etc/environment 2>/dev/null; then
    # Remove any existing PATH line and add new one with conda first
    if grep -q "^PATH=" /etc/environment; then
        sed -i 's|^PATH=.*|PATH="/opt/conda/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"|' /etc/environment
    else
        echo 'PATH="/opt/conda/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"' >> /etc/environment
    fi
    echo "Updated /etc/environment to prioritize conda Python"
fi

# Method 2: Create update-alternatives entries for python3
# This allows system-wide default selection
if command -v update-alternatives &> /dev/null; then
    # Install conda python3 as an alternative
    if ! update-alternatives --list python3 2>/dev/null | grep -q "$CONDA_PYTHON"; then
        update-alternatives --install /usr/bin/python3 python3 "$CONDA_PYTHON" 60 || {
            # If install fails, try to set it directly
            echo "Warning: Could not register conda python3 with update-alternatives"
        }
        echo "Registered conda Python with update-alternatives"
    fi
    
    # Set conda python as the default (auto mode)
    update-alternatives --set python3 "$CONDA_PYTHON" 2>/dev/null || {
        echo "Note: update-alternatives --set failed, may need manual selection"
    }
fi

# Method 3: Ensure /etc/profile.d script for shell sessions
cat > /etc/profile.d/conda-python.sh << 'EOF'
# Prioritize conda Python in interactive shells
export PATH="/opt/conda/bin:$PATH"
EOF

chmod 644 /etc/profile.d/conda-python.sh
echo "Created /etc/profile.d/conda-python.sh for shell sessions"

# Method 4: Update bashrc for non-login shells
if [ -f /etc/bash.bashrc ]; then
    if ! grep -q "/opt/conda/bin" /etc/bash.bashrc; then
        # Add at the beginning to ensure priority
        sed -i '1i export PATH="/opt/conda/bin:$PATH"' /etc/bash.bashrc
        echo "Updated /etc/bash.bashrc"
    fi
fi

echo "Python default configuration complete"
