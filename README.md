# Twitch Stream Monitor

A reliable, lightweight Python script that monitors Twitch streams and sends push notifications via ntfy.sh when streamers go live. Supports multiple Linux distributions including Raspberry Pi OS, Oracle Linux, Fedora, Ubuntu, and Debian with low resource usage and robust error handling.

## Features

- 🔴 **Real-time monitoring** of multiple Twitch streamers
- 📱 **Push notifications** via ntfy.sh to your phone/desktop
- 🚫 **Smart deduplication** - only one notification per stream session
- 🔄 **Automatic recovery** from network issues and API rate limits
- ⚙️ **Easy configuration** via YAML file
- 🐧 **Multi-OS support** - Raspberry Pi, Oracle Linux, Fedora, Ubuntu, Debian
- 🔧 **Optional systemd service** for auto-start and restart
- 📝 **Comprehensive logging** with configurable levels
- 🛡️ **Robust error handling** with exponential backoff

## Quick Start

### 1. Installation

The installation script supports multiple Linux distributions:
- **Raspberry Pi OS** (Debian-based)
- **Oracle Linux** / **RHEL** (dnf/yum)
- **Fedora** (dnf)
- **Ubuntu** / **Debian** (apt)
- **Arch Linux** (pacman)

```bash
# Clone or download the project files
git clone <repository-url>
cd twitch-monitor

# Run the installation script
chmod +x install.sh
./install.sh
```

The installer will:
- Detect your OS and package manager automatically
- Install Python dependencies
- Set up the application in your home directory
- Optionally configure systemd service (you can choose to skip this)

### 2. Get Twitch API Credentials

1. Go to [Twitch Developer Console](https://dev.twitch.tv/console/apps)
2. Click "Register Your Application"
3. Fill in the form:
   - **Name**: "Twitch Stream Monitor" (or any name)
   - **OAuth Redirect URLs**: `http://localhost`
   - **Category**: "Application Integration"
4. Click "Create"
5. Copy the **Client ID** and **Client Secret**

### 3. Setup ntfy.sh

1. Install the [ntfy app](https://ntfy.sh/) on your phone
2. Choose a unique topic name (e.g., `myname_twitch_alerts_xyz123`)
3. Subscribe to your topic in the app

### 4. Configure the Monitor

Edit the configuration file:

```bash
nano /home/pi/twitch-monitor/config.yaml
```

Update these required fields:
```yaml
twitch:
  client_id: "your_client_id_here"
  client_secret: "your_client_secret_here"

ntfy:
  topic: "your_unique_topic_here"

streamers:
  - "your_favorite_streamer"
  - "another_streamer"
```

### 5. Test the Monitor

```bash
cd ~/twitch-monitor  # or your installation directory
python3 twitch_monitor.py
```

### 6. Enable as a Service (if installed)

If you chose to install the systemd service during installation:

```bash
sudo systemctl start twitch-monitor
sudo systemctl status twitch-monitor
```

If you skipped systemd installation, you can run manually:

```bash
cd ~/twitch-monitor
nohup python3 twitch_monitor.py --log-file twitch-monitor.log > /dev/null 2>&1 &
```

## Configuration

### Complete Configuration Example

```yaml
# Twitch API Configuration
twitch:
  client_id: "your_twitch_client_id"
  client_secret: "your_twitch_client_secret"

# ntfy.sh Notification Configuration
ntfy:
  topic: "your_unique_topic"
  server: "https://ntfy.sh"  # or your self-hosted server
  priority: "high"           # min/low/default/high/max
  tags: "twitch,live,gaming"
  click_url: true           # include link to stream
  timeout: 10

# Streamers to monitor
streamers:
  - "ninja"
  - "pokimane"
  - "shroud"

# Monitoring settings
poll_interval: 120    # seconds between checks
max_retries: 3        # retries on API failures
retry_delay: 60       # seconds between retries

# Custom notification message
message_template: |
  {username} is now live! 🎮
  
  📺 {title}
  🎮 Playing: {game}
  🕐 Started at: {started_at}
  
  Watch now: {url}
```

### Message Template Variables

- `{username}` - Streamer's username
- `{title}` - Stream title
- `{game}` - Game being played
- `{url}` - Direct link to stream
- `{started_at}` - Stream start time (HH:MM format)

## Usage

### Command Line Options

```bash
# Use default config.yaml
python3 twitch_monitor.py

# Use custom config file
python3 twitch_monitor.py -c /path/to/config.yaml

# Enable debug logging
python3 twitch_monitor.py --log-level DEBUG

# Log to file
python3 twitch_monitor.py --log-file monitor.log

# Show help
python3 twitch_monitor.py --help
```

### Service Management

```bash
# Start the service
sudo systemctl start twitch-monitor

# Stop the service
sudo systemctl stop twitch-monitor

# Restart the service
sudo systemctl restart twitch-monitor

# Check status
sudo systemctl status twitch-monitor

# View logs
sudo journalctl -u twitch-monitor -f

# Enable auto-start on boot
sudo systemctl enable twitch-monitor

# Disable auto-start
sudo systemctl disable twitch-monitor
```

## Monitoring and Logs

### Log Locations

- **Service logs**: `sudo journalctl -u twitch-monitor`
- **File logs**: `/var/log/twitch-monitor.log` (if configured)
- **State file**: `/home/pi/twitch-monitor/stream_state.json`

### Log Levels

- **DEBUG**: Detailed information for troubleshooting
- **INFO**: General information about operations
- **WARNING**: Important events that don't stop operation
- **ERROR**: Errors that may affect functionality

### Monitoring Commands

```bash
# Follow live logs
sudo journalctl -u twitch-monitor -f

# View recent logs
sudo journalctl -u twitch-monitor --since "1 hour ago"

# Check service status
sudo systemctl status twitch-monitor

# View resource usage
top -p $(pgrep -f twitch_monitor.py)
```

## OS-Specific Notes

### Oracle Linux / RHEL / Fedora

The installer automatically detects and uses `dnf` (or `yum` on older systems). Additional considerations:

**SELinux**: If SELinux is enabled and you encounter permission issues:
```bash
# Check SELinux status
sestatus

# If needed, set SELinux to permissive mode temporarily
sudo setenforce 0

# Or create a custom SELinux policy (advanced)
```

**Firewall**: If using a custom ntfy server, ensure firewall allows outbound HTTPS:
```bash
# Check firewall status
sudo firewall-cmd --state

# Allow HTTPS if needed
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

**Python Path**: On some Oracle Linux systems, you might need to use `python3.9` or `python3.11` instead of `python3`.

### Raspberry Pi OS

- Uses `apt` package manager
- Optimized resource limits in systemd service
- Works out of the box with default settings

### Ubuntu / Debian

- Uses `apt` package manager
- Standard installation, no special considerations

## Troubleshooting

### Common Issues

**1. "No streamers configured" error**
- Check that the `streamers` list in config.yaml is not empty
- Ensure proper YAML formatting (use spaces, not tabs)

**2. "Twitch client_id and client_secret are required" error**
- Verify your Twitch API credentials in config.yaml
- Make sure there are no extra spaces or quotes

**3. "ntfy topic is required" error**
- Set a unique topic name in the ntfy configuration
- Avoid using common words that others might guess

**4. No notifications received**
- Test ntfy.sh manually: `curl -d "test" ntfy.sh/your_topic`
- Check if streamers are actually live
- Verify the topic name matches between config and your phone app

**5. High CPU/memory usage**
- Increase `poll_interval` to check less frequently
- Reduce the number of monitored streamers
- Check logs for excessive error messages

### Debug Mode

Run with debug logging to see detailed information:

```bash
python3 twitch_monitor.py --log-level DEBUG
```

### Manual Testing

Test individual components:

```bash
# Test configuration loading
python3 -c "import yaml; print(yaml.safe_load(open('config.yaml')))"

# Test ntfy.sh connectivity
curl -d "Test notification" ntfy.sh/your_topic

# Test Twitch API (requires valid credentials)
python3 twitch_monitor.py --log-level DEBUG
```

## Resource Usage

Typical resource usage on Raspberry Pi 4:
- **Memory**: 20-40 MB
- **CPU**: <1% average, 2-5% during API calls
- **Network**: ~1 KB per streamer per check
- **Storage**: <1 MB for application + logs

## Security Considerations

- Keep your Twitch API credentials secure
- Choose a unique, hard-to-guess ntfy topic
- Consider using a self-hosted ntfy server for privacy
- The systemd service runs with limited privileges
- Logs may contain streamer information

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

- **Issues**: Report bugs and request features via GitHub issues
- **Documentation**: Check this README and inline code comments
- **Community**: Join discussions in GitHub Discussions

## Acknowledgments

- [twitchAPI](https://github.com/Teekeks/pyTwitchAPI) - Excellent Python Twitch API library
- [ntfy.sh](https://ntfy.sh/) - Simple, reliable push notifications
- Raspberry Pi Foundation - For creating an amazing platform for projects like this
