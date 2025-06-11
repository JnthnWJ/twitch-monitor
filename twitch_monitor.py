#!/usr/bin/env python3
"""
Twitch Stream Monitor
A reliable monitoring script for Twitch streams with ntfy.sh notifications.
Optimized for Raspberry Pi deployment with low resource usage.
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set

import requests
import yaml
from twitchAPI.twitch import Twitch
from twitchAPI.type import AuthScope


class TwitchMonitorError(Exception):
    """Custom exception for Twitch Monitor errors."""
    pass


class StreamState:
    """Represents the state of a stream for deduplication."""
    
    def __init__(self, username: str):
        self.username = username
        self.is_live = False
        self.stream_id: Optional[str] = None
        self.title: Optional[str] = None
        self.game_name: Optional[str] = None
        self.started_at: Optional[datetime] = None
        self.last_checked = datetime.now()
        self.notification_sent = False
    
    def update_from_stream_data(self, stream_data: Optional[Dict]) -> bool:
        """
        Update state from Twitch API stream data.
        Returns True if this represents a new stream session.
        """
        self.last_checked = datetime.now()
        
        if not stream_data:
            # Stream is offline
            was_live = self.is_live
            self.is_live = False
            self.stream_id = None
            self.title = None
            self.game_name = None
            self.started_at = None
            self.notification_sent = False
            return False
        
        # Stream is live
        new_stream_id = stream_data.get('id')
        is_new_stream = (
            not self.is_live or 
            self.stream_id != new_stream_id or
            not self.notification_sent
        )
        
        self.is_live = True
        self.stream_id = new_stream_id
        self.title = stream_data.get('title', 'Untitled Stream')
        self.game_name = stream_data.get('game_name', 'Unknown Game')
        
        # Parse started_at timestamp
        started_at_str = stream_data.get('started_at')
        if started_at_str:
            try:
                self.started_at = datetime.fromisoformat(started_at_str.replace('Z', '+00:00'))
            except ValueError:
                self.started_at = datetime.now()
        
        return is_new_stream
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'username': self.username,
            'is_live': self.is_live,
            'stream_id': self.stream_id,
            'title': self.title,
            'game_name': self.game_name,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'last_checked': self.last_checked.isoformat(),
            'notification_sent': self.notification_sent
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'StreamState':
        """Create StreamState from dictionary."""
        state = cls(data['username'])
        state.is_live = data.get('is_live', False)
        state.stream_id = data.get('stream_id')
        state.title = data.get('title')
        state.game_name = data.get('game_name')
        state.notification_sent = data.get('notification_sent', False)
        
        # Parse timestamps
        if data.get('started_at'):
            try:
                state.started_at = datetime.fromisoformat(data['started_at'])
            except ValueError:
                state.started_at = None
        
        if data.get('last_checked'):
            try:
                state.last_checked = datetime.fromisoformat(data['last_checked'])
            except ValueError:
                state.last_checked = datetime.now()
        
        return state


class NotificationSender:
    """Handles sending notifications via ntfy.sh."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.ntfy_config = config.get('ntfy', {})
        self.base_url = self.ntfy_config.get('server', 'https://ntfy.sh')
        self.topic = self.ntfy_config.get('topic')
        self.timeout = self.ntfy_config.get('timeout', 10)
        
        if not self.topic:
            raise TwitchMonitorError("ntfy topic is required in configuration")
    
    def send_notification(self, stream_state: StreamState, message_template: str) -> bool:
        """
        Send a notification for a stream going live.
        Returns True if successful, False otherwise.
        """
        try:
            # Format the message using stream data
            message = self._format_message(message_template, stream_state)
            
            # Prepare notification data
            headers = {
                'Title': f'🔴 {stream_state.username} is now live!',
                'Priority': self.ntfy_config.get('priority', 'default'),
                'Tags': self.ntfy_config.get('tags', 'twitch,live'),
            }
            
            # Add optional headers
            if self.ntfy_config.get('click_url'):
                headers['Click'] = f"https://twitch.tv/{stream_state.username}"
            
            if self.ntfy_config.get('icon'):
                headers['Icon'] = self.ntfy_config['icon']
            
            # Send the notification
            url = f"{self.base_url}/{self.topic}"
            response = requests.post(
                url,
                data=message.encode('utf-8'),
                headers=headers,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            logging.info(f"Notification sent successfully for {stream_state.username}")
            return True
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to send notification for {stream_state.username}: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error sending notification for {stream_state.username}: {e}")
            return False
    
    def _format_message(self, template: str, stream_state: StreamState) -> str:
        """Format message template with stream data."""
        return template.format(
            username=stream_state.username,
            title=stream_state.title or 'Untitled Stream',
            game=stream_state.game_name or 'Unknown Game',
            url=f"https://twitch.tv/{stream_state.username}",
            started_at=stream_state.started_at.strftime('%H:%M') if stream_state.started_at else 'Unknown'
        )


class StateManager:
    """Manages persistent state for stream monitoring."""
    
    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.states: Dict[str, StreamState] = {}
        self.load_state()
    
    def load_state(self):
        """Load state from file."""
        if not self.state_file.exists():
            logging.info("No existing state file found, starting fresh")
            return
        
        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)
            
            for username, state_data in data.items():
                self.states[username] = StreamState.from_dict(state_data)
            
            logging.info(f"Loaded state for {len(self.states)} streamers")
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logging.warning(f"Failed to load state file: {e}. Starting fresh.")
            self.states = {}
    
    def save_state(self):
        """Save current state to file."""
        try:
            # Create directory if it doesn't exist
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert states to dictionary
            data = {username: state.to_dict() for username, state in self.states.items()}
            
            # Write to temporary file first, then rename (atomic operation)
            temp_file = self.state_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            temp_file.rename(self.state_file)
            logging.debug(f"State saved for {len(self.states)} streamers")
            
        except Exception as e:
            logging.error(f"Failed to save state: {e}")
    
    def get_state(self, username: str) -> StreamState:
        """Get or create state for a username."""
        if username not in self.states:
            self.states[username] = StreamState(username)
        return self.states[username]
    
    def cleanup_old_states(self, active_usernames: Set[str], max_age_days: int = 7):
        """Remove states for streamers no longer being monitored."""
        cutoff_time = datetime.now() - timedelta(days=max_age_days)
        to_remove = []
        
        for username, state in self.states.items():
            if (username not in active_usernames and 
                state.last_checked < cutoff_time):
                to_remove.append(username)
        
        for username in to_remove:
            del self.states[username]
            logging.info(f"Removed old state for {username}")


class TwitchMonitor:
    """Main monitoring class that coordinates all components."""

    def __init__(self, config_file: Path):
        self.config_file = config_file
        self.config = self._load_config()
        self.running = False

        # Initialize components
        self.state_manager = StateManager(Path(self.config['state_file']))
        self.notification_sender = NotificationSender(self.config)
        self.twitch_client: Optional[Twitch] = None

        # Configuration
        self.poll_interval = self.config.get('poll_interval', 120)  # seconds
        self.max_retries = self.config.get('max_retries', 3)
        self.retry_delay = self.config.get('retry_delay', 60)  # seconds
        self.message_template = self.config.get('message_template',
            "{username} is now live!\n\n🎮 {game}\n📺 {title}\n🔗 {url}")

        # Get list of streamers to monitor
        self.streamers = self.config.get('streamers', [])
        if not self.streamers:
            raise TwitchMonitorError("No streamers configured for monitoring")

        logging.info(f"Initialized monitor for {len(self.streamers)} streamers")

    def _load_config(self) -> Dict:
        """Load configuration from YAML file."""
        if not self.config_file.exists():
            raise TwitchMonitorError(f"Configuration file not found: {self.config_file}")

        try:
            with open(self.config_file, 'r') as f:
                config = yaml.safe_load(f)

            # Validate required configuration
            required_fields = ['twitch', 'ntfy', 'streamers']
            for field in required_fields:
                if field not in config:
                    raise TwitchMonitorError(f"Missing required configuration field: {field}")

            # Validate Twitch config
            twitch_config = config['twitch']
            if not twitch_config.get('client_id') or not twitch_config.get('client_secret'):
                raise TwitchMonitorError("Twitch client_id and client_secret are required")

            # Validate ntfy config
            ntfy_config = config['ntfy']
            if not ntfy_config.get('topic'):
                raise TwitchMonitorError("ntfy topic is required")

            return config

        except yaml.YAMLError as e:
            raise TwitchMonitorError(f"Invalid YAML configuration: {e}")
        except Exception as e:
            raise TwitchMonitorError(f"Failed to load configuration: {e}")

    async def _initialize_twitch_client(self):
        """Initialize the Twitch API client."""
        try:
            twitch_config = self.config['twitch']
            self.twitch_client = await Twitch(
                twitch_config['client_id'],
                twitch_config['client_secret']
            )
            logging.info("Twitch API client initialized successfully")

        except Exception as e:
            raise TwitchMonitorError(f"Failed to initialize Twitch client: {e}")

    async def _get_user_ids(self, usernames: List[str]) -> Dict[str, str]:
        """Get user IDs for the given usernames."""
        try:
            # get_users returns an async generator, so we need to collect all results
            users = []
            async for user in self.twitch_client.get_users(logins=usernames):
                users.append(user)

            user_map = {user.login.lower(): user.id for user in users}

            # Check for missing users
            missing_users = set(u.lower() for u in usernames) - set(user_map.keys())
            if missing_users:
                logging.warning(f"Could not find Twitch users: {', '.join(missing_users)}")

            return user_map

        except Exception as e:
            logging.error(f"Failed to get user IDs: {e}")
            return {}

    async def _check_streams(self, user_ids: List[str]) -> Dict[str, Optional[Dict]]:
        """Check stream status for the given user IDs."""
        try:
            # get_streams returns an async generator, so we need to collect all results
            streams = []
            async for stream in self.twitch_client.get_streams(user_id=user_ids):
                streams.append(stream)

            # Create a map of user_id -> stream_data
            stream_map = {}
            for user_id in user_ids:
                stream_map[user_id] = None

            # Fill in live streams
            for stream in streams:
                stream_data = {
                    'id': stream.id,
                    'title': stream.title,
                    'game_name': stream.game_name,
                    'started_at': stream.started_at.isoformat() if stream.started_at else None,
                    'viewer_count': stream.viewer_count
                }
                stream_map[stream.user_id] = stream_data

            return stream_map

        except Exception as e:
            logging.error(f"Failed to check streams: {e}")
            return {}

    async def _monitor_cycle(self):
        """Perform one monitoring cycle."""
        try:
            # Get user IDs for all streamers
            user_id_map = await self._get_user_ids(self.streamers)
            if not user_id_map:
                logging.error("No valid users found, skipping cycle")
                return

            # Check stream status
            user_ids = list(user_id_map.values())
            stream_data_map = await self._check_streams(user_ids)

            # Process each streamer
            for username in self.streamers:
                username_lower = username.lower()
                if username_lower not in user_id_map:
                    continue

                user_id = user_id_map[username_lower]
                stream_data = stream_data_map.get(user_id)

                # Get current state
                state = self.state_manager.get_state(username)

                # Update state and check if this is a new stream
                is_new_stream = state.update_from_stream_data(stream_data)

                # Send notification if this is a new stream
                if is_new_stream and state.is_live:
                    success = self.notification_sender.send_notification(state, self.message_template)
                    if success:
                        state.notification_sent = True

                    logging.info(f"New stream detected for {username}: {state.title}")
                elif state.is_live:
                    logging.debug(f"{username} is still live: {state.title}")
                else:
                    logging.debug(f"{username} is offline")

            # Save state after processing all streamers
            self.state_manager.save_state()

            # Cleanup old states periodically
            active_usernames = set(s.lower() for s in self.streamers)
            self.state_manager.cleanup_old_states(active_usernames)

        except Exception as e:
            logging.error(f"Error in monitoring cycle: {e}")

    async def run(self):
        """Main monitoring loop."""
        self.running = True
        retry_count = 0

        try:
            await self._initialize_twitch_client()
            logging.info("Starting Twitch stream monitoring...")

            while self.running:
                try:
                    await self._monitor_cycle()
                    retry_count = 0  # Reset retry count on successful cycle

                    # Wait for next cycle with cancellation support
                    try:
                        await asyncio.sleep(self.poll_interval)
                    except asyncio.CancelledError:
                        logging.info("Sleep interrupted, shutting down...")
                        break

                except Exception as e:
                    retry_count += 1
                    logging.error(f"Monitoring cycle failed (attempt {retry_count}/{self.max_retries}): {e}")

                    if retry_count >= self.max_retries:
                        logging.error("Max retries reached, stopping monitor")
                        break

                    # Exponential backoff with cancellation support
                    delay = min(self.retry_delay * (2 ** (retry_count - 1)), 300)
                    logging.info(f"Retrying in {delay} seconds...")
                    try:
                        await asyncio.sleep(delay)
                    except asyncio.CancelledError:
                        logging.info("Retry sleep interrupted, shutting down...")
                        break

        finally:
            if self.twitch_client:
                await self.twitch_client.close()
            logging.info("Twitch monitor stopped")

    def stop(self):
        """Stop the monitoring loop."""
        self.running = False


def setup_logging(log_level: str = 'INFO', log_file: Optional[Path] = None):
    """Setup logging configuration."""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        handlers=[]
    )

    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(log_format))
    logging.getLogger().addHandler(console_handler)

    # Add file handler if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(log_format))
        logging.getLogger().addHandler(file_handler)


async def setup_signal_handlers(monitor: TwitchMonitor, task: asyncio.Task):
    """Setup signal handlers for graceful shutdown using asyncio."""
    import signal
    import sys

    def signal_handler(signum):
        logging.info(f"Received signal {signum}, shutting down gracefully...")
        monitor.stop()
        # Cancel the main task to interrupt any sleep operations
        if not task.done():
            task.cancel()

    # Use asyncio's signal handling which works better on all platforms
    loop = asyncio.get_running_loop()

    try:
        # Only set up signal handlers on Unix-like systems
        if hasattr(signal, 'SIGINT') and sys.platform != 'win32':
            loop.add_signal_handler(signal.SIGINT, lambda: signal_handler(signal.SIGINT))
            logging.debug("SIGINT handler registered")
        if hasattr(signal, 'SIGTERM') and sys.platform != 'win32':
            loop.add_signal_handler(signal.SIGTERM, lambda: signal_handler(signal.SIGTERM))
            logging.debug("SIGTERM handler registered")
    except NotImplementedError:
        # Fallback to traditional signal handling if asyncio signal handling is not supported
        logging.warning("asyncio signal handling not supported, using traditional signal handling")

        def fallback_handler(signum, _):
            logging.info(f"Received signal {signum}, shutting down gracefully...")
            monitor.stop()
            if not task.done():
                task.cancel()

        signal.signal(signal.SIGINT, fallback_handler)
        signal.signal(signal.SIGTERM, fallback_handler)


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Twitch Stream Monitor with ntfy.sh notifications',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Use default config.yaml
  %(prog)s -c /path/to/config.yaml  # Use custom config file
  %(prog)s --log-level DEBUG        # Enable debug logging
  %(prog)s --log-file monitor.log   # Log to file
        """
    )

    parser.add_argument(
        '-c', '--config',
        type=Path,
        default=Path('config.yaml'),
        help='Configuration file path (default: config.yaml)'
    )

    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )

    parser.add_argument(
        '--log-file',
        type=Path,
        help='Log file path (default: console only)'
    )

    parser.add_argument(
        '--version',
        action='version',
        version='Twitch Monitor 1.0.0'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level, args.log_file)

    try:
        # Create and run monitor
        monitor = TwitchMonitor(args.config)

        # Get the current event loop
        loop = asyncio.get_running_loop()

        # Create a task for the monitor
        monitor_task = loop.create_task(monitor.run())

        # Setup signal handlers for graceful shutdown
        await setup_signal_handlers(monitor, monitor_task)

        # Wait for the monitor task to complete
        await monitor_task

    except TwitchMonitorError as e:
        logging.error(f"Configuration error: {e}")
        sys.exit(1)
    except asyncio.CancelledError:
        logging.info("Monitor cancelled, shutting down gracefully")
        sys.exit(0)
    except KeyboardInterrupt:
        logging.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    # Check Python version
    if sys.version_info < (3, 7):
        print("Error: Python 3.7 or higher is required", file=sys.stderr)
        sys.exit(1)

    # Run the async main function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
