#!/bin/bash
# Twitch Stream Monitor Uninstall Script

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

echo -e "${BLUE}Twitch Stream Monitor Uninstall${NC}"
echo "================================="

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo -e "${RED}Error: This script should not be run as root${NC}"
   echo "Please run as the pi user or your regular user account"
   exit 1
fi

# Confirm uninstallation
echo -e "${YELLOW}This will remove the Twitch Stream Monitor and all its files.${NC}"
echo -e "${YELLOW}Your configuration will be backed up to config.yaml.backup${NC}"
read -p "Are you sure you want to continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstall cancelled."
    exit 0
fi

# Stop and disable service
echo -e "${BLUE}Stopping and disabling service...${NC}"
if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    sudo systemctl stop "$SERVICE_NAME"
    echo -e "${GREEN}✓ Service stopped${NC}"
fi

if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
    sudo systemctl disable "$SERVICE_NAME"
    echo -e "${GREEN}✓ Service disabled${NC}"
fi

# Remove systemd service file
if [ -f "/etc/systemd/system/$SERVICE_NAME.service" ]; then
    sudo rm "/etc/systemd/system/$SERVICE_NAME.service"
    sudo systemctl daemon-reload
    echo -e "${GREEN}✓ Service file removed${NC}"
fi

# Backup configuration if it exists
if [ -f "$INSTALL_DIR/config.yaml" ]; then
    echo -e "${BLUE}Backing up configuration...${NC}"
    cp "$INSTALL_DIR/config.yaml" "$INSTALL_DIR/config.yaml.backup"
    echo -e "${GREEN}✓ Configuration backed up to config.yaml.backup${NC}"
fi

# Remove installation directory
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${BLUE}Removing installation directory...${NC}"
    
    # Ask if user wants to keep the backup
    read -p "Keep configuration backup? (Y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        rm -rf "$INSTALL_DIR"
        echo -e "${GREEN}✓ Installation directory removed completely${NC}"
    else
        # Remove everything except the backup
        find "$INSTALL_DIR" -type f ! -name "config.yaml.backup" -delete
        find "$INSTALL_DIR" -type d -empty -delete 2>/dev/null || true
        echo -e "${GREEN}✓ Installation directory cleaned (backup preserved)${NC}"
    fi
fi

# Remove log file
if [ -f "$LOG_FILE" ]; then
    echo -e "${BLUE}Removing log file...${NC}"
    sudo rm "$LOG_FILE"
    echo -e "${GREEN}✓ Log file removed${NC}"
fi

# Note about Python packages
echo -e "${BLUE}Python packages information:${NC}"
echo -e "${YELLOW}Note: Python packages installed with pip were not removed.${NC}"
echo -e "${YELLOW}If you want to remove them, run:${NC}"
echo "pip3 uninstall twitchAPI requests PyYAML aiohttp"

echo ""
echo -e "${GREEN}Uninstall completed successfully!${NC}"

if [ -f "$INSTALL_DIR/config.yaml.backup" ]; then
    echo -e "${BLUE}Your configuration backup is saved at:${NC}"
    echo "$INSTALL_DIR/config.yaml.backup"
fi

echo ""
echo -e "${BLUE}Thank you for using Twitch Stream Monitor!${NC}"
