#!/usr/bin/env python3
"""
Telegram Notification Service

Sends analysis results to Telegram including:
- Session average price analysis
- VWAP calculations
- Price chart image
- Trading statistics

Configuration:
    Credentials stored in etc/telegram_config.json:
    {
        "bot_token": "123456789:ABCdef...",
        "chat_id": "987654321"
    }

Usage:
    python bin/send_telegram_notification.py

Requires:
    - requests library (pip install requests)
    - Valid Telegram bot token and chat ID
    - Analysis output in var/output/session_average_analysis.json
"""
import sys
from pathlib import Path
import json
import os

# Add project root to Python path
project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def send_telegram_photo(photo_path, caption, bot_token, chat_id):
    """
    Send photo with caption via Telegram Bot API.
    
    Args:
        photo_path (str): Path to image file to send
        caption (str): Message caption (supports Markdown formatting)
        bot_token (str): Telegram bot API token
        chat_id (str): Telegram chat ID to send to
    
    Returns:
        bool: True if photo sent successfully, False otherwise
    
    Raises:
        requests.exceptions.RequestException: If API call fails
    """
    try:
        import requests
    except ImportError:
        print("Error: 'requests' library not installed")
        return False
    
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    
    try:
        with open(photo_path, 'rb') as photo:
            files = {'photo': photo}
            data = {
                'chat_id': chat_id,
                'caption': caption,
                'parse_mode': 'Markdown'
            }
            response = requests.post(url, data=data, files=files, timeout=30)
            response.raise_for_status()
            return True
    except Exception as e:
        print(f"Error sending photo: {e}")
        return False


def send_telegram_message(message, photo_path=None):
    """
    Send message via Telegram Bot API, optionally with attached photo.
    
    Attempts to load credentials from etc/telegram_config.json first,
    then falls back to environment variables TELEGRAM_BOT_TOKEN and
    TELEGRAM_CHAT_ID.
    
    Args:
        message (str): Message text to send (Markdown format supported)
        photo_path (str, optional): Path to image file to attach
    
    Returns:
        bool: True if message sent successfully, False otherwise
    
    Example:
        send_telegram_message(
            "*Session Analysis*\\nAverage: 23795.98",
            photo_path="var/output/price_chart.png"
        )
    """
    try:
        import requests
    except ImportError:
        print("Error: 'requests' library not installed. Install with: pip install requests")
        return False
    
    # Try to get credentials from config file first, then environment variables
    bot_token = None
    chat_id = None
    
    config_file = project_root / "etc" / "telegram_config.json"
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                bot_token = config.get('bot_token')
                chat_id = config.get('chat_id')
                
                # Check if they're placeholder values
                if bot_token == "YOUR_BOT_TOKEN_HERE" or chat_id == "YOUR_CHAT_ID_HERE":
                    bot_token = None
                    chat_id = None
        except Exception as e:
            print(f"Warning: Could not read config file: {e}")
    
    # Fallback to environment variables
    if not bot_token:
        bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not chat_id:
        chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        print("Error: Telegram credentials not configured")
        print(f"\nOption 1: Edit the config file at:")
        print(f"  {config_file}")
        print("  Set your bot_token and chat_id")
        print("\nOption 2: Set environment variables:")
        print("  Windows PowerShell:")
        print("    $env:TELEGRAM_BOT_TOKEN='your_bot_token'")
        print("    $env:TELEGRAM_CHAT_ID='your_chat_id'")
        print("\n  Linux/Mac:")
        print("    export TELEGRAM_BOT_TOKEN='your_bot_token'")
        print("    export TELEGRAM_CHAT_ID='your_chat_id'")
        print("\nGet bot token from @BotFather on Telegram")
        print("Get chat ID by messaging your bot and visiting:")
        print("  https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates")
        return False
    
    # If photo provided, send photo with caption
    if photo_path and Path(photo_path).exists():
        success = send_telegram_photo(photo_path, message, bot_token, chat_id)
        if success:
            print("✓ Telegram photo with analysis sent successfully!")
            return True
        else:
            print("Warning: Failed to send photo, falling back to text message")
    
    # Send text message
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    data = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'Markdown'
    }
    
    try:
        response = requests.post(url, data=data, timeout=10)
        response.raise_for_status()
        print("✓ Telegram message sent successfully!")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error sending Telegram message: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"API Error Details: {error_detail}")
                if 'description' in error_detail:
                    print(f"Description: {error_detail['description']}")
            except:
                pass
        print("\nTroubleshooting:")
        print("1. Verify your chat_id is a NUMBER (not bot username)")
        print("2. Send a message to your bot first")
        print(f"3. Visit: https://api.telegram.org/bot{bot_token[:20]}***/getUpdates")
        print("4. Look for 'chat':{'id': NUMBER} and use that number")
        return False


def format_analysis_message(analysis_file):
    """
    Format session average analysis as Telegram message
    """
    try:
        with open(analysis_file, 'r') as f:
            data = json.load(f)
        
        message = f"""
🔔 *London Open Session Analysis*

📊 *Price Levels:*
• Session Average: `{data['session_average']:.2f}`
• VWAP: `{data['vwap']:.2f}`

⏱️ *Time at Average (±{data['tolerance_points']:.1f} pts):*
• Duration: `{data['time_at_avg_seconds']}s` ({data['time_at_avg_minutes']:.1f} min)
• Percentage: `{data['time_at_avg_pct']:.2f}%` of session
• Price crosses: `{data['price_crosses']}` times

💡 *Trading Insight:*
{"High mean-reversion activity" if data['price_crosses'] > 50 else "Low mean-reversion activity"}
"""
        return message
    except Exception as e:
        print(f"Error reading analysis file: {e}")
        return None


def main():
    """
    Main function to send Telegram notification
    """
    # Find the most recent session_average_analysis.json
    output_dir = project_root / "var" / "output"
    analysis_file = output_dir / "session_average_analysis.json"
    
    if not analysis_file.exists():
        print(f"Error: Analysis file not found: {analysis_file}")
        print("Run analyze_london_open.py first to generate the analysis.")
        sys.exit(1)
    
    print(f"Reading analysis from: {analysis_file}")
    
    # Find the most recent chart image
    chart_image = None
    chart_files = list(output_dir.glob("price_chart_*.png"))
    if chart_files:
        # Get the most recent one
        chart_image = max(chart_files, key=lambda p: p.stat().st_mtime)
        print(f"Found chart image: {chart_image.name}")
    
    message = format_analysis_message(analysis_file)
    if message:
        send_telegram_message(message, photo_path=chart_image)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
