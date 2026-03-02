"""
Logging Configuration for CWAS Facebook Image Processing Pipeline

This module provides centralized logging configuration for both the scraper
and coordinator scripts with different levels and output options.
"""

import logging
import logging.handlers
import os
from datetime import datetime

def setup_enhanced_logging(
    script_name="scraper",
    log_level=logging.INFO,
    enable_debug_file=True,
    max_log_size_mb=10,
    backup_count=5
):
    """
    Set up enhanced logging with multiple handlers and formatters.
    
    Args:
        script_name (str): Name of the script for log file naming
        log_level (int): Logging level for console output
        enable_debug_file (bool): Whether to create a separate debug log file
        max_log_size_mb (int): Maximum size of log files before rotation
        backup_count (int): Number of backup log files to keep
    """
    # Get the directory where this config file is located
    config_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(config_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    # Clear any existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)8s - [%(name)s:%(funcName)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Console handler (shows INFO and above)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(simple_formatter)
    
    # Main log file handler (shows INFO and above, with rotation)
    main_log_file = os.path.join(logs_dir, f"{script_name}.log")
    main_file_handler = logging.handlers.RotatingFileHandler(
        main_log_file,
        maxBytes=max_log_size_mb * 1024 * 1024,
        backupCount=backup_count
    )
    main_file_handler.setLevel(logging.INFO)
    main_file_handler.setFormatter(detailed_formatter)
    
    handlers = [console_handler, main_file_handler]
    
    # Debug file handler (shows DEBUG and above, separate file)
    if enable_debug_file:
        debug_log_file = os.path.join(logs_dir, f"{script_name}_debug.log")
        debug_file_handler = logging.handlers.RotatingFileHandler(
            debug_log_file,
            maxBytes=max_log_size_mb * 1024 * 1024,
            backupCount=backup_count
        )
        debug_file_handler.setLevel(logging.DEBUG)
        debug_file_handler.setFormatter(detailed_formatter)
        handlers.append(debug_file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG,  # Capture all levels, handlers will filter
        handlers=handlers,
        force=True
    )
    
    # Log the configuration
    logger = logging.getLogger(__name__)
    logger.info(f"Enhanced logging configured for {script_name}")
    logger.info(f"Main log: {main_log_file}")
    if enable_debug_file:
        logger.info(f"Debug log: {debug_log_file}")
    logger.info(f"Console level: {logging.getLevelName(log_level)}")
    logger.info(f"Log rotation: {max_log_size_mb}MB, {backup_count} backups")
    
    return logger

def log_performance_metrics(operation_name, start_time, end_time, additional_info=None):
    """
    Log performance metrics for operations.
    
    Args:
        operation_name (str): Name of the operation
        start_time (float): Start time (from time.time())
        end_time (float): End time (from time.time())
        additional_info (dict): Additional metrics to log
    """
    logger = logging.getLogger(__name__)
    duration = end_time - start_time
    
    log_msg = f"PERFORMANCE: {operation_name} took {duration:.2f}s"
    
    if additional_info:
        for key, value in additional_info.items():
            log_msg += f", {key}: {value}"
    
    logger.info(log_msg)

def log_system_info():
    """Log system information for debugging purposes."""
    import platform
    import psutil
    import sys
    
    logger = logging.getLogger(__name__)
    
    logger.info("=== SYSTEM INFORMATION ===")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Platform: {platform.platform()}")
    logger.info(f"Architecture: {platform.architecture()}")
    logger.info(f"Processor: {platform.processor()}")
    
    try:
        # Memory info
        memory = psutil.virtual_memory()
        logger.info(f"Total memory: {memory.total / (1024**3):.1f} GB")
        logger.info(f"Available memory: {memory.available / (1024**3):.1f} GB")
        
        # Disk info for the current directory
        disk = psutil.disk_usage('.')
        logger.info(f"Disk space total: {disk.total / (1024**3):.1f} GB")
        logger.info(f"Disk space free: {disk.free / (1024**3):.1f} GB")
        
    except Exception as e:
        logger.warning(f"Could not get system resource info: {e}")
    
    logger.info("=== END SYSTEM INFO ===")

def create_session_logger(session_id=None):
    """
    Create a session-specific logger for tracking a complete run.
    
    Args:
        session_id (str): Unique session identifier, auto-generated if not provided
        
    Returns:
        tuple: (logger, session_id)
    """
    if session_id is None:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create session-specific log file
    config_dir = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(config_dir, "logs", "sessions")
    os.makedirs(logs_dir, exist_ok=True)
    
    session_log_file = os.path.join(logs_dir, f"session_{session_id}.log")
    
    # Create session logger
    session_logger = logging.getLogger(f"session_{session_id}")
    session_logger.setLevel(logging.DEBUG)
    
    # Avoid duplicate handlers
    if not session_logger.handlers:
        handler = logging.FileHandler(session_log_file)
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        session_logger.addHandler(handler)
    
    session_logger.info(f"Session {session_id} started")
    session_logger.info(f"Session log: {session_log_file}")
    
    return session_logger, session_id