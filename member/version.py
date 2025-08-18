#!/usr/bin/env python3
"""
Version utilities for Netring
"""
import os
import logging

logger = logging.getLogger(__name__)

def get_version():
    """Get version from VERSION file"""
    try:
        # Get the directory containing this file (member/)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up one level to the project root
        project_root = os.path.dirname(current_dir)
        version_file = os.path.join(project_root, 'VERSION')
        
        if os.path.exists(version_file):
            with open(version_file, 'r') as f:
                version = f.read().strip()
                logger.debug(f"Read version {version} from {version_file}")
                return version
        else:
            logger.warning(f"VERSION file not found at {version_file}")
            return "unknown"
    except Exception as e:
        logger.error(f"Failed to read version: {e}")
        return "unknown"

# Cache the version to avoid repeated file reads
_cached_version = None

def get_cached_version():
    """Get cached version or read from file if not cached"""
    global _cached_version
    if _cached_version is None:
        _cached_version = get_version()
    return _cached_version