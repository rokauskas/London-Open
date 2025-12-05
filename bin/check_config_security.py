#!/usr/bin/env python3
"""
Security Configuration Checker

Verifies that sensitive configuration files are properly set up and not tracked in git.
Run this before committing to ensure no sensitive data is exposed.

Usage:
    python bin/check_config_security.py
"""
import sys
from pathlib import Path
import subprocess
import json
import re

# Add project root to Python path
project_root = Path(__file__).parent.parent.resolve()

# Define sensitive files that should NOT be tracked
SENSITIVE_FILES = [
    'etc/mongodb_config.json',
    'etc/telegram_config.json',
    'etc/ai_config.json',
    '.env',
    '.env.local',
]

# Define template files that SHOULD exist
TEMPLATE_FILES = [
    'etc/mongodb_config.json.template',
    'etc/telegram_config.json.template',
]


def check_git_tracking():
    """Check if any sensitive files are tracked by git"""
    print("🔍 Checking for tracked sensitive files...")
    
    issues = []
    
    for sensitive_file in SENSITIVE_FILES:
        file_path = project_root / sensitive_file
        
        # Check if file is tracked by git
        try:
            result = subprocess.run(
                ['git', 'ls-files', '--error-unmatch', sensitive_file],
                cwd=project_root,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                issues.append(f"❌ CRITICAL: {sensitive_file} is tracked by git!")
                print(f"   ⚠️  {sensitive_file} is tracked by git (DANGEROUS!)")
            else:
                if file_path.exists():
                    print(f"   ✓ {sensitive_file} exists and is properly ignored")
                else:
                    print(f"   ℹ️  {sensitive_file} does not exist (will be ignored when created)")
        except Exception as e:
            print(f"   ⚠️  Error checking {sensitive_file}: {e}")
    
    return issues


def check_template_files():
    """Check if template files exist"""
    print("\n🔍 Checking for template files...")
    
    issues = []
    
    for template_file in TEMPLATE_FILES:
        file_path = project_root / template_file
        
        if file_path.exists():
            print(f"   ✓ {template_file} exists")
        else:
            issues.append(f"⚠️  WARNING: {template_file} is missing")
            print(f"   ⚠️  {template_file} is missing")
    
    return issues


def check_gitignore():
    """Check if .gitignore has proper entries"""
    print("\n🔍 Checking .gitignore configuration...")
    
    gitignore_path = project_root / '.gitignore'
    
    if not gitignore_path.exists():
        print("   ❌ CRITICAL: .gitignore file not found!")
        return [".gitignore file is missing"]
    
    try:
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            gitignore_content = f.read()
    except UnicodeDecodeError as e:
        print(f"   ❌ ERROR: .gitignore has encoding issues: {e}")
        return [f".gitignore has encoding issues: {e}"]
    except Exception as e:
        print(f"   ❌ ERROR: Could not read .gitignore: {e}")
        return [f"Could not read .gitignore: {e}"]
    
    issues = []
    required_patterns = [
        'mongodb_config.json',
        'telegram_config.json',
        '.env',
    ]
    
    for pattern in required_patterns:
        if pattern in gitignore_content:
            print(f"   ✓ .gitignore includes pattern: {pattern}")
        else:
            issues.append(f"⚠️  WARNING: .gitignore missing pattern: {pattern}")
            print(f"   ⚠️  .gitignore missing pattern: {pattern}")
    
    return issues


def check_config_content():
    """Check if config files contain placeholder values"""
    print("\n🔍 Checking configuration file content...")
    
    warnings = []
    
    # Common placeholder patterns (case-insensitive)
    placeholder_patterns = [
        r'your[_-]?',           # your-, your_, your
        r'placeholder',         # placeholder
        r'replace[_-]?this',    # replace-this, replace_this
        r'example',             # example
        r'test[_-]?',          # test-, test_
        r'username:password',   # generic username:password
        r'<[^>]+>',            # <anything>
        r'\[.*\]',             # [anything]
        r'xxx+',               # xxx, xxxx, etc.
    ]
    
    def contains_placeholder(text):
        """Check if text contains common placeholder patterns"""
        if not text or text.strip() == '':
            return True
        text_lower = text.lower()
        for pattern in placeholder_patterns:
            if re.search(pattern, text_lower):
                return True
        return False
    
    # Check MongoDB config
    mongodb_config = project_root / 'etc' / 'mongodb_config.json'
    if mongodb_config.exists():
        try:
            with open(mongodb_config, 'r', encoding='utf-8') as f:
                config = json.load(f)
                conn_str = config.get('connection_string', '')
                
                if contains_placeholder(conn_str):
                    print("   ⚠️  MongoDB config contains placeholder credentials")
                    warnings.append("MongoDB config may contain placeholder values")
                elif conn_str:
                    print("   ✓ MongoDB config appears to be configured")
                else:
                    print("   ⚠️  MongoDB config is empty")
        except Exception as e:
            print(f"   ⚠️  Could not parse MongoDB config: {e}")
    
    # Check Telegram config
    telegram_config = project_root / 'etc' / 'telegram_config.json'
    if telegram_config.exists():
        try:
            with open(telegram_config, 'r', encoding='utf-8') as f:
                config = json.load(f)
                bot_token = config.get('bot_token', '')
                chat_id = config.get('chat_id', '')
                
                # Telegram bot tokens should match format: digits:alphanumeric+underscore
                # Example: 123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
                telegram_token_pattern = r'^\d+:[A-Za-z0-9_]+$'
                
                if contains_placeholder(bot_token):
                    print("   ⚠️  Telegram config contains placeholder bot token")
                    warnings.append("Telegram config may contain placeholder values")
                elif bot_token and not re.match(telegram_token_pattern, bot_token):
                    print("   ⚠️  Telegram bot token format looks suspicious")
                    warnings.append("Telegram bot token may not be valid")
                elif bot_token and chat_id:
                    print("   ✓ Telegram config appears to be configured")
                else:
                    print("   ⚠️  Telegram config is incomplete")
        except Exception as e:
            print(f"   ⚠️  Could not parse Telegram config: {e}")
    
    return warnings


def main():
    """Main security check function"""
    print("=" * 60)
    print("🔒 Configuration Security Checker")
    print("=" * 60)
    print()
    
    all_issues = []
    
    # Run all checks
    all_issues.extend(check_git_tracking())
    all_issues.extend(check_template_files())
    all_issues.extend(check_gitignore())
    warnings = check_config_content()
    
    # Print summary
    print("\n" + "=" * 60)
    print("📋 Summary")
    print("=" * 60)
    
    if all_issues:
        print("\n❌ ISSUES FOUND:")
        for issue in all_issues:
            print(f"  {issue}")
        
        if any('CRITICAL' in issue for issue in all_issues):
            print("\n🚨 CRITICAL ISSUES DETECTED!")
            print("   DO NOT COMMIT until these are resolved!")
            sys.exit(1)
    else:
        print("\n✅ No critical security issues found!")
    
    if warnings:
        print("\n⚠️  WARNINGS:")
        for warning in warnings:
            print(f"  {warning}")
    
    print("\n💡 Tips:")
    print("  • Always run 'git status' before committing")
    print("  • Never commit files containing real credentials")
    print("  • Use environment variables as an alternative to config files")
    print("  • See SECURITY.md for more information")
    print()


if __name__ == "__main__":
    main()
