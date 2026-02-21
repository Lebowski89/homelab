"""Secret utilities for Infisical Ansible Collection.

This module provides helper functions for working with secrets.
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type


# Fields to exclude from secret responses (internal fields that are not relevant to the user or deprecated, duplicates of other fields)
EXCLUDED_SECRET_FIELDS = ('_id', 'metadata')

def clean_secret_dict(secret_dict):
    """Remove deprecated fields from a secret dictionary.
    
    Args:
        secret_dict: A dictionary from secret.to_dict()
        
    Returns:
        A new dictionary with deprecated fields removed
    """
    return {k: v for k, v in secret_dict.items() if k not in EXCLUDED_SECRET_FIELDS}

