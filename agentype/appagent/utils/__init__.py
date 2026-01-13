"""
agentype - App Agent 工具模块
Author: cuilei
Version: 1.0
"""

from .common import (
    GlobalTimestampManager,
    safe_json_load,
    safe_json_save,
    calculate_file_hash,
    format_file_size,
    get_file_info,
    ensure_directory,
    clean_filename,
    validate_file_extension,
    merge_configs,
    setup_logging,
    ProgressTracker
)

from .i18n import (
    set_language,
    get_language,
    _,
    add_translation,
    get_available_languages,
    translate_dict
)

__all__ = [
    # common.py exports
    'GlobalTimestampManager',
    'safe_json_load',
    'safe_json_save', 
    'calculate_file_hash',
    'format_file_size',
    'get_file_info',
    'ensure_directory',
    'clean_filename',
    'validate_file_extension',
    'merge_configs',
    'setup_logging',
    'ProgressTracker',
    
    # i18n.py exports
    'set_language',
    'get_language',
    '_',
    'add_translation',
    'get_available_languages',
    'translate_dict'
]