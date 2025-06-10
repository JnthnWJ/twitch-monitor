#!/bin/bash
# Twitch Stream Monitor Installation Script
# Optimized for Raspberry Pi deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/home/pi/twitch-monitor"
SERVICE_NAME="twitch-monitor"
LOG_FILE="/var/log/twitch-monitor.log"

echo -e "${BLUE}Twitch Stream Monitor Installation${NC}"
echo "=================================="

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo -e "${RED}Error: This script should not be run as root${NC}"
   echo "Please run as the pi user or your regular user account"
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

# Check if pip is installed
echo -e "${BLUE}Checking pip installation...${NC}"
if command -v pip3 &> /dev/null; then
    echo -e "${GREEN}✓ pip3 is available${NC}"
else
    echo -e "${YELLOW}Installing pip3...${NC}"
    sudo apt update
    sudo apt install -y python3-pip
fi

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

# Install systemd service
echo -e "${BLUE}Installing systemd service...${NC}"
if [ -f "$(dirname "$0")/twitch-monitor.service" ]; then
    # Update service file with correct paths
    sed "s|/home/pi/twitch-monitor|$INSTALL_DIR|g" "$(dirname "$0")/twitch-monitor.service" > "/tmp/$SERVICE_NAME.service"
    sed -i "s|User=pi|User=$USER|g" "/tmp/$SERVICE_NAME.service"
    sed -i "s|Group=pi|Group=$USER|g" "/tmp/$SERVICE_NAME.service"
    
    sudo cp "/tmp/$SERVICE_NAME.service" "/etc/systemd/system/"
    sudo systemctl daemon-reload
    echo -e "${GREEN}✓ Systemd service installed${NC}"
else
    echo -e "${YELLOW}⚠ Service file not found, skipping systemd installation${NC}"
fi

# Create log file with proper permissions
echo -e "${BLUE}Setting up logging...${NC}"
sudo touch "$LOG_FILE"
sudo chown "$USER:$USER" "$LOG_FILE"
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
echo "6. Enable and start the service:"
echo "   sudo systemctl enable $SERVICE_NAME"
echo "   sudo systemctl start $SERVICE_NAME"
echo ""
echo "7. Check service status:"
echo "   sudo systemctl status $SERVICE_NAME"
echo "   sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo -e "${BLUE}For more information, see the README.md file${NC}"
