#!/usr/bin/env python3
"""
Test script for Twitch Stream Monitor setup
Verifies configuration and connectivity before running the main monitor.
"""

import asyncio
import sys
from pathlib import Path

import requests
import yaml
from twitchAPI.twitch import Twitch


def test_config_file(config_path: Path) -> dict:
    """Test if configuration file exists and is valid."""
    print("🔧 Testing configuration file...")
    
    if not config_path.exists():
        print(f"❌ Configuration file not found: {config_path}")
        return None
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        print("✅ Configuration file loaded successfully")
        return config
    except yaml.YAMLError as e:
        print(f"❌ Invalid YAML configuration: {e}")
        return None
    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")
        return None


def test_config_values(config: dict) -> bool:
    """Test if required configuration values are present."""
    print("\n🔍 Testing configuration values...")
    
    success = True
    
    # Check Twitch config
    twitch_config = config.get('twitch', {})
    if not twitch_config.get('client_id'):
        print("❌ Missing twitch.client_id")
        success = False
    else:
        print("✅ Twitch client_id present")
    
    if not twitch_config.get('client_secret'):
        print("❌ Missing twitch.client_secret")
        success = False
    else:
        print("✅ Twitch client_secret present")
    
    # Check ntfy config
    ntfy_config = config.get('ntfy', {})
    if not ntfy_config.get('topic'):
        print("❌ Missing ntfy.topic")
        success = False
    else:
        print("✅ ntfy topic present")
    
    # Check streamers
    streamers = config.get('streamers', [])
    if not streamers:
        print("❌ No streamers configured")
        success = False
    else:
        print(f"✅ {len(streamers)} streamers configured")
    
    return success


async def test_twitch_api(config: dict) -> bool:
    """Test Twitch API connectivity and credentials."""
    print("\n🎮 Testing Twitch API...")
    
    try:
        twitch_config = config['twitch']
        client = await Twitch(
            twitch_config['client_id'],
            twitch_config['client_secret']
        )
        
        # Test by getting a popular streamer's info
        users = []
        async for user in client.get_users(logins=['ninja']):
            users.append(user)

        if users:
            print("✅ Twitch API connection successful")
            await client.close()
            return True
        else:
            print("❌ Twitch API returned no data")
            await client.close()
            return False
            
    except Exception as e:
        print(f"❌ Twitch API test failed: {e}")
        return False


def test_ntfy_connectivity(config: dict) -> bool:
    """Test ntfy.sh connectivity."""
    print("\n📱 Testing ntfy.sh connectivity...")
    
    try:
        ntfy_config = config['ntfy']
        server = ntfy_config.get('server', 'https://ntfy.sh')
        topic = ntfy_config['topic']
        
        # Send a test notification
        url = f"{server}/{topic}"
        headers = {
            'Title': 'Twitch Monitor Test',
            'Tags': 'test,setup',
            'Priority': 'low'
        }
        
        response = requests.post(
            url,
            data="Test notification from Twitch Monitor setup",
            headers=headers,
            timeout=10
        )
        
        response.raise_for_status()
        print("✅ ntfy.sh test notification sent successfully")
        print(f"📱 Check your ntfy app for topic: {topic}")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ ntfy.sh connectivity test failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error testing ntfy.sh: {e}")
        return False


async def test_streamer_lookup(config: dict) -> bool:
    """Test looking up configured streamers."""
    print("\n👥 Testing streamer lookup...")
    
    try:
        twitch_config = config['twitch']
        streamers = config['streamers']
        
        client = await Twitch(
            twitch_config['client_id'],
            twitch_config['client_secret']
        )
        
        # Look up all configured streamers
        users = []
        async for user in client.get_users(logins=streamers):
            users.append(user)

        found_users = {user.login.lower() for user in users}
        
        success = True
        for streamer in streamers:
            if streamer.lower() in found_users:
                print(f"✅ Found streamer: {streamer}")
            else:
                print(f"❌ Streamer not found: {streamer}")
                success = False
        
        await client.close()
        return success
        
    except Exception as e:
        print(f"❌ Streamer lookup test failed: {e}")
        return False


def test_dependencies() -> bool:
    """Test if required dependencies are installed."""
    print("📦 Testing dependencies...")
    
    success = True
    dependencies = [
        ('requests', 'requests'),
        ('yaml', 'PyYAML'),
        ('twitchAPI', 'twitchAPI'),
    ]
    
    for module, package in dependencies:
        try:
            __import__(module)
            print(f"✅ {package} is installed")
        except ImportError:
            print(f"❌ {package} is not installed")
            success = False
    
    return success


async def main():
    """Main test function."""
    print("🧪 Twitch Stream Monitor Setup Test")
    print("=" * 40)
    
    # Test dependencies first
    if not test_dependencies():
        print("\n❌ Dependency test failed. Install requirements with:")
        print("pip3 install -r requirements.txt")
        return False
    
    # Load and test configuration
    config_path = Path('config.yaml')
    config = test_config_file(config_path)
    if not config:
        return False
    
    if not test_config_values(config):
        print("\n❌ Configuration validation failed")
        print("Please check your config.yaml file")
        return False
    
    # Test external connectivity
    tests = [
        test_twitch_api(config),
        test_ntfy_connectivity(config),
        test_streamer_lookup(config)
    ]
    
    results = await asyncio.gather(*tests, return_exceptions=True)
    
    # Check results
    all_passed = True
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"❌ Test {i+1} failed with exception: {result}")
            all_passed = False
        elif not result:
            all_passed = False
    
    print("\n" + "=" * 40)
    if all_passed:
        print("🎉 All tests passed! Your setup is ready.")
        print("\nYou can now run the monitor with:")
        print("python3 twitch_monitor.py")
    else:
        print("❌ Some tests failed. Please fix the issues above.")
    
    return all_passed


if __name__ == '__main__':
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        sys.exit(1)
