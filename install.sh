#!/bin/bash
# Twitch Stream Monitor Installation Script
# Supports Raspberry Pi OS, Oracle Linux, Fedora, and other Linux distributions

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Detect OS and package manager
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$NAME
        VER=$VERSION_ID
    elif type lsb_release >/dev/null 2>&1; then
        OS=$(lsb_release -si)
        VER=$(lsb_release -sr)
    elif [ -f /etc/redhat-release ]; then
        OS="Red Hat Enterprise Linux"
        VER=$(cat /etc/redhat-release | sed 's/.*release //' | sed 's/ .*//')
    else
        OS=$(uname -s)
        VER=$(uname -r)
    fi

    # Detect package manager
    if command -v dnf &> /dev/null; then
        PKG_MANAGER="dnf"
        PKG_INSTALL="sudo dnf install -y"
        PKG_UPDATE="sudo dnf update -y"
    elif command -v yum &> /dev/null; then
        PKG_MANAGER="yum"
        PKG_INSTALL="sudo yum install -y"
        PKG_UPDATE="sudo yum update -y"
    elif command -v apt &> /dev/null; then
        PKG_MANAGER="apt"
        PKG_INSTALL="sudo apt install -y"
        PKG_UPDATE="sudo apt update"
    elif command -v pacman &> /dev/null; then
        PKG_MANAGER="pacman"
        PKG_INSTALL="sudo pacman -S --noconfirm"
        PKG_UPDATE="sudo pacman -Sy"
    else
        PKG_MANAGER="unknown"
    fi
}

# Configuration
detect_os
CURRENT_USER=$(whoami)
INSTALL_DIR="/home/$CURRENT_USER/twitch-monitor"
SERVICE_NAME="twitch-monitor"
LOG_FILE="/var/log/twitch-monitor.log"

echo -e "${BLUE}Twitch Stream Monitor Installation${NC}"
echo "=================================="
echo -e "${BLUE}Detected OS: ${NC}$OS $VER"
echo -e "${BLUE}Package Manager: ${NC}$PKG_MANAGER"
echo -e "${BLUE}Install Directory: ${NC}$INSTALL_DIR"
echo ""

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo -e "${RED}Error: This script should not be run as root${NC}"
   echo "Please run as your regular user account"
   exit 1
fi

# Check Python version
echo -e "${BLUE}Checking Python version...${NC}"
python3_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
required_version="3.7"

if python3 -c "import sys; exit(0 if sys.version_info >= (3,7) else 1)"; then
    echo -e "${GREEN}✓ Python ${python3_version} is compatible${NC}"
else
    echo -e "${RED}✗ Python ${python3_version} is too old. Python 3.7+ required.${NC}"
    exit 1
fi

# Install pip based on package manager
install_pip() {
    echo -e "${BLUE}Checking pip installation...${NC}"
    if command -v pip3 &> /dev/null; then
        echo -e "${GREEN}✓ pip3 is available${NC}"
        return 0
    fi

    echo -e "${YELLOW}Installing pip3...${NC}"
    case $PKG_MANAGER in
        "dnf"|"yum")
            $PKG_UPDATE
            $PKG_INSTALL python3-pip
            ;;
        "apt")
            $PKG_UPDATE
            $PKG_INSTALL python3-pip
            ;;
        "pacman")
            $PKG_UPDATE
            $PKG_INSTALL python-pip
            ;;
        *)
            echo -e "${RED}✗ Unknown package manager. Please install pip3 manually.${NC}"
            echo "Try: curl https://bootstrap.pypa.io/get-pip.py | python3"
            exit 1
            ;;
    esac

    # Verify installation
    if command -v pip3 &> /dev/null; then
        echo -e "${GREEN}✓ pip3 installed successfully${NC}"
    else
        echo -e "${RED}✗ Failed to install pip3${NC}"
        exit 1
    fi
}

# Create installation directory
echo -e "${BLUE}Creating installation directory...${NC}"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Copy files to installation directory
echo -e "${BLUE}Copying application files...${NC}"
if [ -f "$(dirname "$0")/twitch_monitor.py" ]; then
    cp "$(dirname "$0")/twitch_monitor.py" "$INSTALL_DIR/"
    cp "$(dirname "$0")/requirements.txt" "$INSTALL_DIR/"
    cp "$(dirname "$0")/config.yaml" "$INSTALL_DIR/config.yaml.example"
    echo -e "${GREEN}✓ Files copied successfully${NC}"
else
    echo -e "${RED}✗ Source files not found. Make sure you're running this from the project directory.${NC}"
    exit 1
fi

# Call the pip installation function
install_pip

# Install Python dependencies
echo -e "${BLUE}Installing Python dependencies...${NC}"
pip3 install --user -r requirements.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Make script executable
chmod +x "$INSTALL_DIR/twitch_monitor.py"

# Create configuration file if it doesn't exist
if [ ! -f "$INSTALL_DIR/config.yaml" ]; then
    echo -e "${BLUE}Creating configuration file...${NC}"
    cp "$INSTALL_DIR/config.yaml.example" "$INSTALL_DIR/config.yaml"
    echo -e "${YELLOW}⚠ Please edit $INSTALL_DIR/config.yaml with your settings${NC}"
else
    echo -e "${GREEN}✓ Configuration file already exists${NC}"
fi

# Ask user about systemd service installation
echo ""
echo -e "${BLUE}Systemd Service Setup${NC}"
echo "====================="
echo "Would you like to install the systemd service for automatic startup?"
echo "This will allow the monitor to start automatically on boot and restart if it crashes."
echo ""
read -p "Install systemd service? (Y/n): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    echo -e "${BLUE}Installing systemd service...${NC}"
    if [ -f "$(dirname "$0")/twitch-monitor.service" ]; then
        # Update service file with correct paths and user
        sed "s|/home/pi/twitch-monitor|$INSTALL_DIR|g" "$(dirname "$0")/twitch-monitor.service" > "/tmp/$SERVICE_NAME.service"
        sed -i "s|User=pi|User=$CURRENT_USER|g" "/tmp/$SERVICE_NAME.service"
        sed -i "s|Group=pi|Group=$CURRENT_USER|g" "/tmp/$SERVICE_NAME.service"

        # Update log file path to be user-writable if not root
        if [[ $CURRENT_USER != "root" ]]; then
            USER_LOG_FILE="$INSTALL_DIR/twitch-monitor.log"
            sed -i "s|/var/log/twitch-monitor.log|$USER_LOG_FILE|g" "/tmp/$SERVICE_NAME.service"
            LOG_FILE="$USER_LOG_FILE"
        fi

        sudo cp "/tmp/$SERVICE_NAME.service" "/etc/systemd/system/"
        sudo systemctl daemon-reload
        echo -e "${GREEN}✓ Systemd service installed${NC}"

        # Ask if user wants to enable the service
        echo ""
        read -p "Enable service to start on boot? (Y/n): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            sudo systemctl enable "$SERVICE_NAME"
            echo -e "${GREEN}✓ Service enabled for auto-start${NC}"
        fi

        SYSTEMD_INSTALLED=true
    else
        echo -e "${YELLOW}⚠ Service file not found, skipping systemd installation${NC}"
        SYSTEMD_INSTALLED=false
    fi
else
    echo -e "${YELLOW}⚠ Skipping systemd service installation${NC}"
    SYSTEMD_INSTALLED=false
fi

# Create log file with proper permissions
echo -e "${BLUE}Setting up logging...${NC}"
if [[ "$LOG_FILE" == "/var/log/"* ]]; then
    # System log location - requires sudo
    sudo touch "$LOG_FILE"
    sudo chown "$CURRENT_USER:$CURRENT_USER" "$LOG_FILE"
else
    # User log location - no sudo needed
    touch "$LOG_FILE"
fi
echo -e "${GREEN}✓ Log file created: $LOG_FILE${NC}"

# Test the installation
echo -e "${BLUE}Testing installation...${NC}"
if python3 "$INSTALL_DIR/twitch_monitor.py" --version &> /dev/null; then
    echo -e "${GREEN}✓ Installation test passed${NC}"
else
    echo -e "${RED}✗ Installation test failed${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}Installation completed successfully!${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Edit the configuration file:"
echo "   nano $INSTALL_DIR/config.yaml"
echo ""
echo "2. Get your Twitch API credentials:"
echo "   - Go to https://dev.twitch.tv/console/apps"
echo "   - Create a new application"
echo "   - Copy the Client ID and Client Secret to config.yaml"
echo ""
echo "3. Choose an ntfy.sh topic:"
echo "   - Pick a unique, hard-to-guess topic name"
echo "   - Add it to config.yaml"
echo "   - Subscribe to it on your phone using the ntfy app"
echo ""
echo "4. Add streamers to monitor in config.yaml"
echo ""
echo "5. Test the monitor:"
echo "   cd $INSTALL_DIR && python3 twitch_monitor.py"
echo ""

if [ "$SYSTEMD_INSTALLED" = true ]; then
    echo "6. Start the service:"
    echo "   sudo systemctl start $SERVICE_NAME"
    echo ""
    echo "7. Check service status:"
    echo "   sudo systemctl status $SERVICE_NAME"
    echo "   sudo journalctl -u $SERVICE_NAME -f"
    echo ""
    echo "8. View logs:"
    echo "   tail -f $LOG_FILE"
else
    echo "6. To run manually:"
    echo "   cd $INSTALL_DIR"
    echo "   python3 twitch_monitor.py"
    echo ""
    echo "7. To run in background:"
    echo "   cd $INSTALL_DIR"
    echo "   nohup python3 twitch_monitor.py --log-file twitch-monitor.log > /dev/null 2>&1 &"
    echo ""
    echo "8. View logs:"
    echo "   tail -f $INSTALL_DIR/twitch-monitor.log"
fi

echo ""
echo -e "${BLUE}OS-specific notes:${NC}"
case $PKG_MANAGER in
    "dnf"|"yum")
        echo "- On Oracle Linux/RHEL/Fedora, you may need to configure SELinux if enabled"
        echo "- Check firewall settings if using a custom ntfy server"
        ;;
    "apt")
        echo "- On Debian/Ubuntu systems, everything should work out of the box"
        ;;
esac

echo ""
echo -e "${BLUE}For more information, see the README.md file${NC}"
