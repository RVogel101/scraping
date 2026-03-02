# Enhanced Logging for CWAS Facebook Image Processing Pipeline

This document explains the enhanced logging system that has been added to improve diagnostics and troubleshooting capabilities.

## Overview

The logging system has been significantly enhanced across all scripts with:
- **Detailed diagnostic logging** throughout all major functions
- **Performance tracking** for timing critical operations  
- **Error logging** with full context and stack traces
- **Session tracking** for complete run monitoring
- **Log rotation** to prevent disk space issues
- **Multiple log levels** for different debugging needs

## Log Files Structure

### Main Log Files
- `logs/scraper.log` - Main scraper activity (INFO level and above)
- `logs/coordinator.log` - Main coordinator activity (INFO level and above)
- `logs/scraper_debug.log` - Detailed scraper debugging (DEBUG level)
- `logs/coordinator_debug.log` - Detailed coordinator debugging (DEBUG level)

### Session Logs
- `logs/sessions/session_YYYYMMDD_HHMMSS.log` - Complete session tracking for individual runs

## Log Levels and What They Track

### INFO Level (Main logs)
- Script startup and completion
- Phase transitions and major operations
- Success/failure of major components
- Performance summaries
- File operations (saves, loads)
- Statistics and final results

### DEBUG Level (Debug logs)  
- Function entry/exit points
- Variable states and decision points
- Detailed browser interactions
- Individual image processing steps  
- Network operations and retries
- Memory usage tracking
- Thread-specific operations

### WARNING/ERROR Levels
- Non-fatal issues that don't stop execution
- Failed operations with context
- System resource issues
- Configuration problems
- Full exception details with stack traces

## Key Features Added

### 1. Scraper Enhancements (`scrape_fb_images.py`)
- **Chrome WebDriver setup**: Detailed logging of profile copying, driver initialization
- **Page navigation**: Navigation timing and success/failure tracking
- **Scroll collection**: Progress tracking, link collection metrics, bookmark handling
- **Download workers**: Thread-specific logging with worker names, individual image processing
- **SharedDateExtractor**: Browser pool management, date extraction success/failure
- **Error handling**: Comprehensive exception logging with context

### 2. Coordinator Enhancements (`main_coordinator.py`)
- **Pipeline phases**: Detailed timing for each major phase
- **Image detection**: Before/after scraping comparisons, new image identification
- **Metadata extraction**: Per-image processing status, EXIF data extraction results
- **File operations**: CSV/pickle save timing and file sizes
- **Processing statistics**: Complete run metrics and performance data

### 3. System Diagnostics
- **System information**: Python version, platform, memory, disk space
- **Resource monitoring**: Memory usage tracking throughout execution
- **Performance metrics**: Timing for all major operations
- **Session tracking**: Unique session IDs for run correlation

## Usage

### Running with Enhanced Logging
Both scripts automatically use the enhanced logging system:

```bash
# Scraper (standalone)
python scrape_fb_images.py

# Coordinator (full pipeline)  
python main_coordinator.py
```

### Finding Information in Logs

#### For Debugging Scraper Issues:
1. Check `logs/scraper.log` for high-level flow and errors
2. Check `logs/scraper_debug.log` for detailed browser interactions
3. Look for specific thread names like `[Thread-1]` to track individual downloads

#### For Debugging Coordinator Issues:
1. Check `logs/coordinator.log` for pipeline flow and statistics
2. Check `logs/coordinator_debug.log` for detailed metadata extraction
3. Review session logs for complete run tracking

#### Common Debugging Scenarios:

**Duplicate Images Still Being Downloaded:**
- Search for "already exists" in scraper logs
- Check "URL normalization" entries in debug logs
- Look for "deduplication" entries to see what's being filtered

**Browser Problems:**
- Search for "Chrome WebDriver" and "driver" in logs
- Check for "Failed to initialize" or "browser launch" errors
- Review "SharedDateExtractor" entries for browser pool issues

**Performance Issues:**
- Look for "PERFORMANCE:" entries in logs
- Check timing for "Phase" operations
- Review memory usage entries

**Processing Errors:**
- Search for "ERROR" and "EXCEPTION" in logs
- Check "metadata extraction" entries for specific file issues
- Review "processing_error" in coordinator logs

## Log Rotation

Logs automatically rotate when they reach 10MB:
- 5 backup copies are kept (e.g., `scraper.log.1`, `scraper.log.2`, etc.)
- Older logs are automatically deleted to prevent disk space issues
- Session logs are not rotated (they're unique per run)

## Configuration

The logging configuration can be customized in `logging_config.py`:
- `log_level`: Console output level (DEBUG, INFO, WARNING, ERROR)
- `enable_debug_file`: Whether to create separate debug log files
- `max_log_size_mb`: Log file size before rotation (default: 10MB)
- `backup_count`: Number of backup files to keep (default: 5)

## Troubleshooting the Logging System

If logging isn't working properly:

1. **Check file permissions**: Ensure the script can write to the `logs/` directory
2. **Check disk space**: Ensure sufficient space for log files
3. **Import errors**: If `logging_config.py` import fails, scripts fall back to basic logging
4. **Missing dependencies**: The enhanced logging uses `psutil` for system info (optional)

## Performance Impact

The enhanced logging system has minimal performance impact:
- **File I/O**: Logs are written asynchronously where possible
- **Memory usage**: Logs are flushed regularly to prevent memory buildup
- **Debug logs**: Only written to files, don't slow console output
- **Rotation**: Prevents logs from consuming excessive disk space

The benefits for troubleshooting far outweigh the minimal performance overhead.