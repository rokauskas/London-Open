# Security Policy

## Protecting Sensitive Information

This repository contains scripts that interact with external services (MongoDB, Telegram, etc.) and may use sensitive credentials. **Never commit credentials, API keys, or secrets to version control.**

## Sensitive Files

The following files should **NEVER** be committed to the repository:

### Configuration Files
- `etc/mongodb_config.json` - Contains MongoDB connection strings with passwords
- `etc/telegram_config.json` - Contains Telegram bot tokens and chat IDs
- `etc/ai_config.json` - May contain AI service API keys
- Any file ending in `_config.json` that contains credentials

### Environment Files
- `.env` - Environment variables file
- `.env.local`, `.env.*.local` - Local environment overrides
- `secrets.json`, `credentials.json` - Common secret storage files

### API Keys and Tokens
- Any file with `_key.json`, `_token.json`, `_secret.json`, or `_credentials.json` suffix

## How to Safely Use Configuration Files

### 1. Use Template Files

Template files (ending in `.template`) are safe to commit and should be used as examples:

```bash
# Copy template to create your local config
cp etc/mongodb_config.json.template etc/mongodb_config.json

# Edit the file and add your real credentials
# This file is gitignored and will not be committed
```

### 2. Use Environment Variables

As an alternative to config files, use environment variables:

**Linux/Mac:**
```bash
export TELEGRAM_BOT_TOKEN="123456789:ABCdef..."
export TELEGRAM_CHAT_ID="987654321"
```

**Windows PowerShell:**
```powershell
$env:TELEGRAM_BOT_TOKEN="123456789:ABCdef..."
$env:TELEGRAM_CHAT_ID="987654321"
```

The scripts will automatically check for environment variables if config files are not found.

### 3. Verify Before Committing

Always check what you're about to commit:

```bash
# Check which files are staged
git status

# Review changes
git diff

# If you see config files, DO NOT COMMIT
# Remove them from staging:
git reset HEAD etc/mongodb_config.json
```

## What to Do If Credentials Are Exposed

If you accidentally commit sensitive credentials:

### 1. Immediately Rotate Credentials
- **MongoDB**: Change your password immediately in Azure/MongoDB
- **Telegram Bot**: Revoke the bot token via @BotFather and create a new one
- **API Keys**: Revoke and regenerate through the service provider

### 2. Remove from Git History

Simply deleting the file in a new commit is **NOT** sufficient. The credentials remain in git history.

Use tools like `git-filter-repo` to remove sensitive data from history:

```bash
# Install git-filter-repo
pip install git-filter-repo

# Remove the sensitive file from all history
git filter-repo --path etc/mongodb_config.json --invert-paths

# Force push to update remote (WARNING: destructive operation)
git push origin --force --all
```

⚠️ **Warning**: This rewrites git history. Coordinate with all team members before doing this.

### 3. Report the Incident

If this is a shared repository:
1. Notify all collaborators about the exposure
2. Document what was exposed and for how long
3. Monitor for unauthorized access
4. Consider reporting to security@github.com for help removing sensitive data

## Gitignore Protection

The `.gitignore` file is configured to prevent committing sensitive files:

```gitignore
# Sensitive configuration files - DO NOT COMMIT
etc/mongodb_config.json
etc/telegram_config.json
etc/ai_config.json

# Environment variables and secrets
.env
.env.local
.env.*.local
*.env
secrets.json
credentials.json

# API keys and tokens
*_key.json
*_token.json
*_secret.json
*_credentials.json
```

## Security Best Practices

1. **Never hardcode credentials** in source code
2. **Use template files** as examples (safe to commit)
3. **Use environment variables** for credentials when possible
4. **Review all changes** before committing (`git diff`, `git status`)
5. **Use secure connections** (TLS/SSL) for all external services
6. **Regularly rotate credentials** as a preventive measure
7. **Limit credential permissions** to minimum required access
8. **Enable IP whitelisting** on services like MongoDB when possible

## Reporting Security Issues

If you discover a security vulnerability in this project:

1. **Do NOT** open a public issue
2. Email the maintainer privately with details
3. Allow reasonable time for the issue to be addressed
4. Coordinate on responsible disclosure timing

## Additional Resources

- [GitHub's guide on removing sensitive data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
- [git-filter-repo tool](https://github.com/newren/git-filter-repo)
- [OWASP Top 10 API Security Risks](https://owasp.org/www-project-api-security/)
