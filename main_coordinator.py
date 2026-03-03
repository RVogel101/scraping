"""
Main Coordinator Script for CWAS Facebook Image Processing Pipeline

This script coordinates the full pipeline:
1. Runs the Facebook scraper to download new images
2. Processes new images through extraction pipeline  
3. Generates updated CSV and pickle files with extracted data
"""

import os
import sys
import subprocess
import time
import logging
import json
import pandas as pd
import pickle
from datetime import datetime
from pathlib import Path

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRAPER_SCRIPT = os.path.join(SCRIPT_DIR, "scrape_fb_images.py")
IMAGES_DIR = os.path.join(SCRIPT_DIR, "FB-UK-CWAS-Content")
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "cwas_extracted_data.csv")
OUTPUT_PICKLE = os.path.join(SCRIPT_DIR, "cwas_extracted_data.pkl")
PROCESSING_LOG = os.path.join(SCRIPT_DIR, "processing_log.json")

def setup_logging():
    """Set up enhanced logging for the coordinator."""
    try:
        from logging_config import setup_enhanced_logging, log_system_info, create_session_logger
        logger = setup_enhanced_logging("coordinator", enable_debug_file=True)
        
        # Log system info for diagnostics
        log_system_info()
        
        return logger
        
    except ImportError:
        # Fallback to basic logging if logging_config is not available
        log_file = os.path.join(SCRIPT_DIR, "coordinator.log")
        
        # Create a custom formatter for more detailed logging
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s'
        )
        
        # File handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        
        # Console handler  
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        
        # Configure root logger
        logging.basicConfig(
            level=logging.DEBUG,
            handlers=[file_handler, console_handler]
        )
        
        logger = logging.getLogger(__name__)
        logger.info(f"Coordinator logging initialized - log file: {log_file}")
        return logger

def get_existing_images():
    """Get list of existing CWAS images before scraping."""
    logger = logging.getLogger(__name__)
    logger.debug(f"Scanning for existing images in: {IMAGES_DIR}")
    
    existing = set()
    if os.path.exists(IMAGES_DIR):
        try:
            files = os.listdir(IMAGES_DIR)
            logger.debug(f"Found {len(files)} total files in images directory")
            
            for filename in files:
                if filename.upper().startswith('CWAS_') and filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                    existing.add(filename)
                    logger.debug(f"Found existing CWAS image: {filename}")
            
            logger.info(f"Found {len(existing)} existing CWAS images")
        except Exception as e:
            logger.error(f"Error scanning images directory: {e}")
    else:
        logger.warning(f"Images directory does not exist: {IMAGES_DIR}")
    
    return existing

def run_scraper(mode='update'):
    """
    Run the Facebook scraper script.
    
    Args:
        mode (str): 'update' for incremental or 'refresh' for complete refresh
        
    Returns:
        bool: True if scraper ran successfully
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Starting Facebook scraper in {mode} mode...")
    
    # Validate scraper script exists
    if not os.path.exists(SCRAPER_SCRIPT):
        error_msg = f"Scraper script not found: {SCRAPER_SCRIPT}"
        logger.error(error_msg)
        return False
    
    try:
        # Import and run the scraper directly
        logger.debug("Importing scrape_fb_images module")
        import scrape_fb_images
        logger.info("Successfully imported scraper module")
        
        # Monkey patch the get_run_mode function to return our choice
        logger.debug(f"Setting up monkey patch for run mode: {mode}")
        original_get_run_mode = scrape_fb_images.get_run_mode
        scrape_fb_images.get_run_mode = lambda: mode
        
        # Run the main scraper function
        logger.info("Executing scraper main() function")
        scraper_start_time = time.time()
        
        scrape_fb_images.main()
        
        scraper_duration = time.time() - scraper_start_time
        logger.info(f"Scraper execution completed in {scraper_duration:.1f}s")
        
        # Restore original function
        logger.debug("Restoring original get_run_mode function")
        scrape_fb_images.get_run_mode = original_get_run_mode
        
        logger.info("Facebook scraper completed successfully")
        return True
        
    except ImportError as e:
        logger.error(f"Failed to import scraper module: {e}")
        return False
    except Exception as e:
        logger.error(f"Facebook scraper failed with exception: {e}")
        logger.debug(f"Scraper exception details", exc_info=True)
        return False

def get_new_images(existing_before):
    """Get list of newly downloaded images."""
    current_images = get_existing_images()
    new_images = current_images - existing_before
    return sorted(list(new_images))

def extract_image_metadata(image_path):
    """
    Extract metadata and features from a single image.
    
    Args:
        image_path (str): Path to the image file
        
    Returns:
        dict: Extracted metadata and features
    """
    import re
    from PIL import Image
    from PIL.ExifTags import TAGS
    
    metadata = {
        'filename': os.path.basename(image_path),
        'filepath': image_path,
        'filesize_kb': os.path.getsize(image_path) / 1024,
        'processing_date': datetime.now().isoformat()
    }
    
    # Parse filename for CWAS number and date
    filename = os.path.basename(image_path)
    cwas_match = re.match(r'CWAS_(\d{4})', filename)
    if cwas_match:
        metadata['cwas_number'] = int(cwas_match.group(1))
    
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
    if date_match:
        metadata['post_date'] = date_match.group(1)
    
    try:
        # Get image dimensions and basic info
        with Image.open(image_path) as img:
            metadata['width'] = img.width
            metadata['height'] = img.height
            metadata['format'] = img.format
            metadata['mode'] = img.mode
            metadata['aspect_ratio'] = round(img.width / img.height, 2)
            
            # Extract EXIF data if available
            if hasattr(img, '_getexif') and img._getexif():
                exif_data = {}
                for tag_id, value in img._getexif().items():
                    tag = TAGS.get(tag_id, tag_id)
                    exif_data[tag] = str(value) if not isinstance(value, (int, float, str)) else value
                metadata['exif'] = exif_data
                
    except Exception as e:
        logging.warning(f"Could not process image {image_path}: {e}")
        metadata['processing_error'] = str(e)
    
    return metadata

def process_new_images(new_image_files):
    """
    Process new images through the extraction pipeline.
    
    Args:
        new_image_files (list): List of new image filenames
        
    Returns:
        list: List of extracted metadata dictionaries
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Processing {len(new_image_files)} new images...")
    
    extracted_data = []
    
    for i, filename in enumerate(new_image_files, 1):
        image_path = os.path.join(IMAGES_DIR, filename)
        logger.info(f"Processing {i}/{len(new_image_files)}: {filename}")
        
        try:
            metadata = extract_image_metadata(image_path)
            extracted_data.append(metadata)
        except Exception as e:
            logger.error(f"Failed to process {filename}: {e}")
            # Still add basic info for failed images
            extracted_data.append({
                'filename': filename,
                'filepath': image_path,
                'processing_error': str(e),
                'processing_date': datetime.now().isoformat()
            })
    
    logger.info(f"Completed processing {len(extracted_data)} images")
    return extracted_data

def load_existing_data():
    """Load existing extracted data if available."""
    logger = logging.getLogger(__name__)
    logger.debug(f"Attempting to load existing data from: {OUTPUT_CSV}")
    
    existing_df = pd.DataFrame()
    
    if os.path.exists(OUTPUT_CSV):
        try:
            file_size = os.path.getsize(OUTPUT_CSV)
            logger.debug(f"CSV file found, size: {file_size} bytes")
            
            load_start = time.time()
            existing_df = pd.read_csv(OUTPUT_CSV)
            load_time = time.time() - load_start
            
            logger.info(f"Loaded {len(existing_df)} existing records from CSV in {load_time:.2f}s")
            if len(existing_df) > 0:
                logger.debug(f"CSV columns: {list(existing_df.columns)}")
            
        except Exception as e:
            logger.warning(f"Could not load existing CSV: {e}")
            logger.debug("CSV load error details", exc_info=True)
    else:
        logger.info(f"No existing CSV file found at {OUTPUT_CSV}")
    
    return existing_df

def save_extracted_data(all_data):
    """
    Save extracted data to CSV and pickle formats.
    
    Args:
        all_data (list): List of extracted metadata dictionaries
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Saving {len(all_data)} records to output files")
    
    if not all_data:
        logger.warning("No data to save")
        return pd.DataFrame()
    
    try:
        # Create DataFrame
        logger.debug("Converting data to DataFrame")
        df_start = time.time()
        df = pd.DataFrame(all_data)
        df_time = time.time() - df_start
        logger.debug(f"DataFrame created in {df_time:.3f}s, shape: {df.shape}")
        
        # Sort by CWAS number if available
        if 'cwas_number' in df.columns:
            logger.debug("Sorting by CWAS number")
            df = df.sort_values('cwas_number')
            logger.debug(f"Data sorted by CWAS number")
        
        # Save CSV
        logger.info(f"Saving CSV to: {OUTPUT_CSV}")
        csv_start = time.time()
        df.to_csv(OUTPUT_CSV, index=False)
        csv_time = time.time() - csv_start
        csv_size = os.path.getsize(OUTPUT_CSV)
        logger.info(f"Saved {len(df)} records to CSV ({csv_size} bytes) in {csv_time:.2f}s")
        
        # Save pickle
        logger.info(f"Saving pickle to: {OUTPUT_PICKLE}")
        pickle_start = time.time()
        with open(OUTPUT_PICKLE, 'wb') as f:
            pickle.dump(all_data, f)
        pickle_time = time.time() - pickle_start
        pickle_size = os.path.getsize(OUTPUT_PICKLE)
        logger.info(f"Saved {len(all_data)} records to pickle ({pickle_size} bytes) in {pickle_time:.2f}s")
        
        return df
        
    except Exception as e:
        logger.error(f"Failed to save extracted data: {e}")
        logger.debug("Save error details", exc_info=True)
        return pd.DataFrame()

def update_processing_log(stats):
    """Update the processing log with run statistics."""
    logger = logging.getLogger(__name__)
    logger.debug(f"Updating processing log with stats: {stats}")
    
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'stats': stats
    }
    
    processing_history = []
    if os.path.exists(PROCESSING_LOG):
        try:
            with open(PROCESSING_LOG, 'r') as f:
                processing_history = json.load(f)
            logger.debug(f"Loaded existing processing log with {len(processing_history)} entries")
        except Exception as e:
            logger.warning(f"Could not load existing processing log: {e}")
            processing_history = []
    else:
        logger.debug(f"No existing processing log found at {PROCESSING_LOG}")
    
    processing_history.append(log_entry)
    
    try:
        with open(PROCESSING_LOG, 'w') as f:
            json.dump(processing_history, f, indent=2)
        logger.info(f"Processing log updated - {len(processing_history)} total entries")
    except Exception as e:
        logger.error(f"Failed to update processing log: {e}")
    
    processing_history.append(log_entry)
    
    # Keep only last 50 runs
    processing_history = processing_history[-50:]
    
    with open(PROCESSING_LOG, 'w') as f:
        json.dump(processing_history, f, indent=2)

def print_summary(stats):
    """Print a summary of the processing run."""
    print("\n" + "="*70)
    print("  CWAS PROCESSING PIPELINE - SUMMARY")
    print("="*70)
    print(f"  Images before scraping: {stats['images_before']}")
    print(f"  Images after scraping:  {stats['images_after']}")
    print(f"  New images downloaded:  {stats['new_images']}")
    print(f"  Images processed:       {stats['processed_images']}")
    print(f"  Total records in CSV:   {stats['total_records']}")
    print(f"  Processing time:        {stats['processing_time']:.1f} seconds")
    print(f"\nOutput files:")
    print(f"  📊 CSV:    {OUTPUT_CSV}")
    print(f"  🥒 Pickle: {OUTPUT_PICKLE}")
    print(f"  📁 Images: {IMAGES_DIR}")
    print("="*70)

def main():
    """Main coordinator function."""
    start_time = time.time()
    logger = setup_logging()
    
    logger.info("="*80)
    logger.info("CWAS Facebook Image Processing Pipeline Started")
    logger.info(f"Working directory: {SCRIPT_DIR}")
    logger.info(f"Images directory: {IMAGES_DIR}")
    logger.info(f"Output CSV: {OUTPUT_CSV}")
    logger.info(f"Output pickle: {OUTPUT_PICKLE}")
    logger.info("="*80)
    
    print("="*70)
    print("  CWAS FACEBOOK IMAGE PROCESSING PIPELINE")  
    print("="*70)
    print("  This script will:")
    print("  1. Run Facebook scraper to download new images")
    print("  2. Extract metadata from new images") 
    print("  3. Update CSV and pickle files with new data")
    print("="*70)
    
    # Get user choice for scraper mode
    logger.info("Getting user input for scraper mode")
    while True:
        mode = input("\nScraper mode [1=update, 2=complete refresh]: ").strip()
        if mode == '1':
            scraper_mode = 'update'
            print("  → Selected: Update mode (new images only)")
            logger.info("User selected: Update mode (new images only)")
            break
        elif mode == '2':
            scraper_mode = 'refresh'
            print("  → Selected: Complete refresh (all images)")
            logger.info("User selected: Complete refresh (all images)")
            break
        else:
            print("  Please enter 1 or 2")
            logger.debug(f"Invalid user input: '{mode}'")
    
    # Initialize statistics
    stats = {
        'start_time': datetime.now().isoformat(),
        'scraper_mode': scraper_mode,
        'images_before': 0,
        'images_after': 0,
        'new_images_found': 0,
        'images_processed': 0,
        'processing_errors': 0,
        'total_runtime': 0
    }
    
    try:
        # Step 1: Get existing images before scraping
        logger.info("Step 1: Getting existing images before scraping")
        step1_start = time.time()
        images_before = get_existing_images()
        stats['images_before'] = len(images_before)
        step1_time = time.time() - step1_start
        logger.info(f"Step 1 complete: Found {stats['images_before']} existing images in {step1_time:.1f}s")
        
        # Step 2: Run the Facebook scraper
        logger.info(f"Step 2: Running Facebook scraper in {scraper_mode} mode")
        step2_start = time.time()
        scraper_success = run_scraper(scraper_mode)
        step2_time = time.time() - step2_start
        
        if not scraper_success:
            logger.error("Facebook scraper failed. Aborting pipeline.")
            stats['total_runtime'] = time.time() - start_time
            stats['pipeline_error'] = 'Scraper failed'
            update_processing_log(stats)
            return False
        
        logger.info(f"Step 2 complete: Scraper ran successfully in {step2_time:.1f}s")
        
        # Step 3: Identify new images
        logger.info("Step 3: Identifying new images...")
        images_after = get_existing_images()
        new_images = get_new_images(images_before)
        
        logger.info(f"Found {len(new_images)} new images to process")
        
        # Step 4: Process new images (or all if refresh mode)
        if scraper_mode == 'refresh':
            # In refresh mode, process all images
            images_to_process = sorted(list(images_after))
            logger.info(f"Refresh mode: Processing all {len(images_to_process)} images")
        else:
            # In update mode, process only new images
            images_to_process = new_images
        
        if not images_to_process:
            logger.info("No new images to process.")
            print("\n  ✅ No new images found - pipeline complete!")
            return True
        
        logger.info("Step 4: Processing images...")
        extracted_data = process_new_images(images_to_process)
        
        # Step 5: Merge with existing data (unless refresh mode)
        if scraper_mode == 'update':
            logger.info("Step 5: Merging with existing data...")
            existing_df = load_existing_data()
            if not existing_df.empty:
                existing_data = existing_df.to_dict('records')
                all_data = existing_data + extracted_data
            else:
                all_data = extracted_data
        else:
            # Refresh mode - use only newly extracted data
            all_data = extracted_data
        
        # Step 6: Save updated data
        logger.info("Step 6: Saving extracted data...")
        final_df = save_extracted_data(all_data)
        
        # Step 7: Update processing log and show summary
        processing_time = time.time() - start_time
        stats = {
            'images_before': len(images_before),
            'images_after': len(images_after), 
            'new_images': len(new_images),
            'processed_images': len(images_to_process),
            'total_records': len(final_df),
            'processing_time': processing_time,
            'scraper_mode': scraper_mode
        }
        
        update_processing_log(stats)
        print_summary(stats)
        
        logger.info("Pipeline completed successfully!")
        return True
        
    except KeyboardInterrupt:
        logger.info("Pipeline cancelled by user")
        return False
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)