"""
Git utility functions for checking repository status.

This module provides utilities to check for uncommitted changes
before running data pipeline operations.
"""
import subprocess
import sys
from pathlib import Path


def check_uncommitted_changes(repo_path=None):
    """
    Check if there are uncommitted changes in the git repository.
    
    Args:
        repo_path (Path, optional): Path to git repository. Defaults to current directory.
    
    Returns:
        tuple: (has_changes: bool, changes_description: str)
    """
    if repo_path is None:
        repo_path = Path.cwd()
    
    try:
        # Check if we're in a git repository
        result = subprocess.run(
            ['git', 'rev-parse', '--git-dir'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            # Not a git repository
            return False, ""
        
        # Check for uncommitted changes (both staged and unstaged)
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            # Git command failed
            return False, ""
        
        changes = result.stdout.strip()
        if changes:
            return True, changes
        
        return False, ""
    
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        # Git not available or command failed
        return False, ""


def prompt_proceed_with_uncommitted_changes(changes_description):
    """
    Prompt user whether to proceed when uncommitted changes are detected.
    
    Args:
        changes_description (str): Description of uncommitted changes from git status
    
    Returns:
        bool: True if user wants to proceed, False otherwise
    """
    print("\n" + "="*70)
    print("⚠️  WARNING: Uncommitted changes detected")
    print("="*70)
    print("\nThe following files have uncommitted changes:\n")
    
    # Parse and display changes in a user-friendly format
    lines = changes_description.split('\n')
    for line in lines[:10]:  # Show first 10 files
        if line.strip():
            print(f"  {line}")
    
    if len(lines) > 10:
        print(f"  ... and {len(lines) - 10} more file(s)")
    
    print("\nRunning the pipeline may generate new files or modify existing ones.")
    print("It's recommended to commit or stash your changes first.")
    print("="*70)
    
    # Prompt user
    while True:
        response = input("\nDo you want to proceed anyway? (yes/no): ").strip().lower()
        if response in ['yes', 'y']:
            print("Proceeding with uncommitted changes...")
            return True
        elif response in ['no', 'n']:
            print("Aborted. Please commit or stash your changes before running.")
            return False
        else:
            print("Please enter 'yes' or 'no'")


def check_and_prompt_if_uncommitted(repo_path=None):
    """
    Check for uncommitted changes and prompt user if found.
    
    This is the main entry point for scripts to use.
    
    Args:
        repo_path (Path, optional): Path to git repository. Defaults to current directory.
    
    Returns:
        bool: True if should proceed (no changes or user confirmed), False if should abort
    """
    has_changes, changes = check_uncommitted_changes(repo_path)
    
    if not has_changes:
        # No uncommitted changes, proceed
        return True
    
    # Uncommitted changes detected, prompt user
    return prompt_proceed_with_uncommitted_changes(changes)
