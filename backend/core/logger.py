# backend/core/logger.py
import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

# ANSI color codes for terminal output
class ColoredFormatter(logging.Formatter):
    """Custom formatter with ANSI color codes for console output."""
    
    # Color codes
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    
    COLORS = {
        'INFO': GREEN,
        'WARNING': YELLOW,
        'ERROR': RED,
        'CRITICAL': RED,
        'DEBUG': BLUE,
    }
    
    def format(self, record):
        # Store original levelname
        original_levelname = record.levelname
        
        # Get the color for this log level
        color = self.COLORS.get(record.levelname, '')
        reset = self.RESET
        
        # Temporarily modify levelname for formatting
        record.levelname = f"{color}{original_levelname}{reset}"
        
        # Format the message
        formatted = super().format(record)
        
        # Restore original levelname (just in case)
        record.levelname = original_levelname
        
        return formatted


def setup_logging():
    """
    Configure centralized logging for the Apex backend.
    
    Sets up:
    - Color-coded console output (Green INFO, Yellow WARNING, Red ERROR)
    - Rotating file handler (logs/apex.log, 10MB max, 5 backups)
    - Format: [YYYY-MM-DD HH:MM:SS] [LEVEL] [COMPONENT] : Message
    """
    # Create logs directory if it doesn't exist
    logs_dir = "logs"
    os.makedirs(logs_dir, exist_ok=True)
    
    # Define log format
    log_format = "[%(asctime)s] [%(levelname)s] [%(name)s] : %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # Console Handler with colors
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = ColoredFormatter(log_format, datefmt=date_format)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File Handler with rotation
    log_file_path = os.path.join(logs_dir, "apex.log")
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    # File formatter without ANSI codes
    file_formatter = logging.Formatter(log_format, datefmt=date_format)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Return the root logger
    logger = logging.getLogger("Apex")
    logger.info("Logging system initialized - Console: colored | File: logs/apex.log")
    return logger
