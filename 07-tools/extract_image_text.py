"""
Simple Image Text Extractor - Quick Version
A simpler version using only Tesseract OCR for quick testing.
"""

import os
import json
import csv
import re
import time
import logging
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Basic imports
try:
    import cv2
    import numpy as np
    from PIL import Image
    import pytesseract
    import pandas as pd
except ImportError as e:
    print(f"Missing package: {e}")
    print("Install with: pip install pillow opencv-python pytesseract pandas")
    exit(1)

# Configuration
INPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "FB-UK-CWAS-Content")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extracted_text_simple")
MAX_WORKERS = 19  # Number of parallel processing threads

def setup_tesseract():
    """Setup Tesseract path for Windows."""
    import pytesseract
    
    # Try to find Tesseract executable in common Windows locations
    common_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe", 
        r"C:\Tesseract-OCR\tesseract.exe"
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            print(f"✓ Using Tesseract at: {path}")
            return True
    
    return False

def setup_logging():
    """Setup logging."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(OUTPUT_DIR, "extraction.log")),
            logging.StreamHandler()
        ]
    )

def parse_filename(filename: str) -> Tuple[str, str]:
    """Extract CWAS number and date from filename."""
    match = re.match(r'CWAS_(\d+)_(\d{4}-\d{2}-\d{2})', filename)
    if match:
        return match.group(1), match.group(2)
    return "", ""

def preprocess_image(image: np.ndarray) -> List[np.ndarray]:
    """Enhanced image preprocessing with multiple variants for better OCR."""
    variants = []
    
    # Convert to grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    
    # Upscale image if too small — Tesseract works best at ~300 DPI
    # (small text and special chars like + and quotes get lost otherwise)
    h, w = gray.shape[:2]
    if max(h, w) < 2000:
        scale = 2.0
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    
    # Original grayscale
    variants.append(gray)
    
    # Denoised version
    denoised = cv2.medianBlur(gray, 3)
    variants.append(denoised)
    
    # High contrast binary
    _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(binary)
    
    # Adaptive threshold (better for varying lighting)
    adaptive = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    variants.append(adaptive)
    
    # Morphological operations to clean up text
    kernel = np.ones((2,2), np.uint8)
    morph = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    variants.append(morph)
    
    # Enhanced contrast
    enhanced = cv2.convertScaleAbs(denoised, alpha=1.5, beta=20)
    variants.append(enhanced)
    
    # Sharpened version (helps with blurry + signs and quotes)
    sharpen_kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    sharpened = cv2.filter2D(denoised, -1, sharpen_kernel)
    variants.append(sharpened)
    
    return variants

def correct_armenian_ocr(text: str) -> str:
    """Fix known Tesseract OCR misreads for Armenian text."""
    # OCR misreads ով (ov: vo+vew) as delays ounds oundsуounds oundsv (ouv: vo+yiwn+vew) by inserting extra yiwn (U+0582)
    text = text.replace('\u0578\u0582\u057E', '\u0578\u057E')
    return text

def extract_text_tesseract(image: np.ndarray) -> Dict:
    """Enhanced OCR with multiple preprocessing variants and PSM modes."""
    try:
        # Get multiple preprocessed versions
        image_variants = preprocess_image(image)
        
        # Different Page Segmentation Modes (PSM)
        psm_modes = [
            (6, "Uniform block of text"),
            (8, "Single word"),
            (7, "Single text line"),
            (11, "Sparse text"),
            (13, "Raw line. Treat as single text line")
        ]
        
        # Language configurations
        lang_configs = [
            ('eng+hye', 'English + Enhanced Armenian')
        ]
        
        all_results = []
        
        for img_idx, processed_img in enumerate(image_variants):
            for lang_config, lang_desc in lang_configs:
                for psm_mode, psm_desc in psm_modes:
                    try:
                        # Convert to PIL
                        pil_image = Image.fromarray(processed_img)
                        
                        # Custom config with PSM mode + preserve special chars
                        custom_config = f'--oem 3 --psm {psm_mode} -c preserve_interword_spaces=1'
                        
                        # Get text with confidence
                        data = pytesseract.image_to_data(
                            pil_image, 
                            lang=lang_config, 
                            config=custom_config,
                            output_type=pytesseract.Output.DICT
                        )
                        
                        # Filter confident text
                        confident_text = []
                        confidences = []
                        
                        # Characters that are meaningful even as singles
                        special_singles = set('+-=()[]{}"\'/,.:;!?&@#%*')
                        
                        for i, conf in enumerate(data['conf']):
                            if int(conf) > 15:  # Lowered threshold for better recall
                                text = data['text'][i].strip()
                                if not text:
                                    continue
                                # Allow single chars if they're special/meaningful
                                if len(text) == 1 and text not in special_singles and not text.isalpha():
                                    continue
                                confident_text.append(text)
                                confidences.append(int(conf))
                        
                        if confident_text:
                            full_text = ' '.join(confident_text)
                            avg_confidence = sum(confidences) / len(confidences)
                            
                            all_results.append({
                                'text': full_text,
                                'confidence': avg_confidence,
                                'word_count': len(confident_text),
                                'language': lang_config,
                                'psm_mode': psm_mode,
                                'preprocessing': img_idx,
                                'description': f"{lang_desc} | {psm_desc} | Variant {img_idx}"
                            })
                            
                    except Exception as e:
                        continue
        
        # Return best result based on confidence and text length
        if all_results:
            # Score based on confidence and text length
            for result in all_results:
                text_score = min(len(result['text']) / 100, 1.0)  # Normalize text length
                conf_score = result['confidence'] / 100
                # Bonus for results that contain special chars (+, quotes)
                special_bonus = 0.05 if any(c in result['text'] for c in '+-="\'') else 0
                # Bonus for mixed-language results (likely has the English explanation)
                has_latin = any(c.isascii() and c.isalpha() for c in result['text'])
                has_armenian = any('\u0530' <= c <= '\u058F' for c in result['text'])
                mixed_bonus = 0.1 if (has_latin and has_armenian) else 0
                result['combined_score'] = (text_score * 0.5) + (conf_score * 0.3) + special_bonus + mixed_bonus
            
            best_result = max(all_results, key=lambda x: x['combined_score'])
            
            # Try to merge: if a different lang config found significantly more text,
            # combine them (e.g. eng finds English explanation, hye finds Armenian)
            best_eng = max((r for r in all_results if r['language'] == 'eng'), 
                          key=lambda x: x['combined_score'], default=None)
            best_hye = max((r for r in all_results if r['language'] == 'hye'), 
                          key=lambda x: x['combined_score'], default=None)
            
            # If the best overall is Armenian but English found substantial extra text
            if (best_result['language'] == 'hye' and best_eng 
                and len(best_eng['text']) > len(best_result['text']) * 0.5
                and best_eng['text'] not in best_result['text']):
                # Use eng+hye result instead, or merge
                best_mixed = max((r for r in all_results if r['language'] == 'eng+hye'), 
                                key=lambda x: x['combined_score'], default=None)
                if best_mixed and len(best_mixed['text']) >= len(best_result['text']):
                    best_result = best_mixed
            
            return {
                'text': correct_armenian_ocr(best_result['text']),
                'confidence': best_result['confidence'],
                'language': best_result['language'],
                'psm_mode': best_result['psm_mode'],
                'preprocessing_variant': best_result['preprocessing'],
                'combined_score': best_result['combined_score'],
                'all_results': all_results
            }
        else:
            return {'text': '', 'confidence': 0, 'language': '', 'all_results': []}
            
    except Exception as e:
        return {'text': '', 'confidence': 0, 'language': '', 'error': str(e)}

def process_image(filepath: str) -> Dict:
    """Process a single image."""
    filename = os.path.basename(filepath)
    cwas_number, date = parse_filename(filename)
    
    start_time = time.time()
    
    try:
        # Load image
        image = cv2.imread(filepath)
        if image is None:
            raise Exception("Could not load image")
        
        # Get image info
        height, width = image.shape[:2]
        file_size = os.path.getsize(filepath)
        
        # Extract text with enhanced preprocessing
        ocr_result = extract_text_tesseract(image)
        
        processing_time = time.time() - start_time
        
        result = {
            'filename': filename,
            'cwas_number': cwas_number,
            'date': date,
            'text': ocr_result.get('text', ''),
            'confidence': ocr_result.get('confidence', 0),
            'language': ocr_result.get('language', ''),
            'psm_mode': ocr_result.get('psm_mode', ''),
            'preprocessing_variant': ocr_result.get('preprocessing_variant', ''),
            'combined_score': ocr_result.get('combined_score', 0),
            'processing_time': processing_time,
            'file_size': file_size,
            'dimensions': f"{width}x{height}",
            'character_count': len(ocr_result.get('text', '')),
            'timestamp': datetime.now().isoformat()
        }
        
        if 'error' in ocr_result:
            result['error'] = ocr_result['error']
        
        return result
        
    except Exception as e:
        return {
            'filename': filename,
            'cwas_number': cwas_number,
            'date': date,
            'text': '',
            'confidence': 0,
            'error': str(e),
            'processing_time': time.time() - start_time,
            'timestamp': datetime.now().isoformat()
        }

def main():
    """Main function."""
    setup_logging()
    
    print("🔍 Simple Image Text Extractor (Tesseract Only)")
    print("="*50)
    
    # Setup Tesseract path
    if not setup_tesseract():
        print("⚠️  Tesseract not found in common locations, trying default...")
    
    # Check if Tesseract is available
    try:
        version = pytesseract.get_tesseract_version()
        print(f"✓ Tesseract version: {version}")
    except Exception as e:
        print(f"❌ Tesseract not found: {e}")
        print("Install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki")
        print("\nFor Windows:")
        print("1. Download installer from the link above")
        print("2. Run as administrator")
        print("3. Make sure to install language packs (including Armenian)")
        print("4. Restart your terminal after installation")
        return
    
    # Get image files
    print(f"🔍 Scanning directory: {INPUT_DIR}")
    if not os.path.exists(INPUT_DIR):
        print(f"❌ Input directory not found: {INPUT_DIR}")
        return
    
    # Count all files first
    all_files = os.listdir(INPUT_DIR)
    print(f"📂 Total files in directory: {len(all_files)}")
    
    # Find image files with comprehensive extensions
    image_extensions = ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff', '.tif')
    image_files = []
    
    for filename in all_files:
        if filename.lower().endswith(image_extensions):
            image_files.append(os.path.join(INPUT_DIR, filename))
    
    # Show what we found
    print(f"🖼️  Image files found: {len(image_files)}")
    if len(image_files) > 0:
        print(f"    Extensions found: {set(os.path.splitext(f)[1].lower() for f in all_files if os.path.splitext(f)[1].lower() in image_extensions)}")
        print(f"    First few files: {[os.path.basename(f) for f in image_files[:3]]}")
        if len(image_files) > 3:
            print(f"    ... and {len(image_files) - 3} more")
    
    if not image_files:
        print("❌ No image files found!")
        print(f"    Looking for extensions: {image_extensions}")
        print(f"    Sample files in directory: {all_files[:5] if all_files else 'None'}")
        return
    
    print(f"📊 Found {len(image_files)} images")
    
    # Ask for confirmation
    response = input(f"\nProcess all {len(image_files)} images? (y/N): ").strip().lower()
    if response != 'y':
        print("Cancelled.")
        return
    
    # Process images in parallel
    results = []
    start_time = time.time()
    completed = 0
    
    print(f"🚀 Starting parallel processing with {MAX_WORKERS} workers...")
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all jobs
        future_to_file = {executor.submit(process_image, filepath): filepath for filepath in image_files}
        
        # Process completed jobs
        for future in as_completed(future_to_file):
            filepath = future_to_file[future]
            filename = os.path.basename(filepath)
            
            try:
                result = future.result()
                results.append(result)
                completed += 1
                
                # Progress update
                if completed % 50 == 0 or completed == len(image_files):
                    print(f"✓ Completed {completed}/{len(image_files)}: {filename}")
                    
            except Exception as e:
                print(f"❌ Error processing {filename}: {e}")
                # Add error result
                results.append({
                    'filename': filename,
                    'cwas_number': '', 
                    'date': '',
                    'text': '',
                    'confidence': 0,
                    'error': str(e),
                    'processing_time': 0,
                    'timestamp': datetime.now().isoformat()
                })
                completed += 1
        
        # Progress update (final)
        if completed % 50 != 0:
            elapsed = time.time() - start_time
            print(f"  ✓ Final: {completed}/{len(image_files)} completed in {elapsed/60:.1f}min")
    
    total_time = time.time() - start_time
    print(f"\n✅ Processing completed in {total_time/60:.1f} minutes!")
    
    # Export results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create DataFrame
    df = pd.DataFrame(results)
    
    # Add is_coined column
    coined_phrase = "this word was coined by the centre for western armenian studies"
    df['is_coined'] = df['text'].str.lower().str.contains(coined_phrase, na=False).map({True: 'yes', False: 'no'})
    
    # CSV export
    csv_file = os.path.join(OUTPUT_DIR, f"extracted_text_{timestamp}.csv")
    df.to_csv(csv_file, index=False, encoding='utf-8')
    print(f"📄 CSV exported: {csv_file}")
    
    # Pickle export (DataFrame)
    pickle_file = os.path.join(OUTPUT_DIR, f"extracted_text_dataframe_{timestamp}.pkl")
    df.to_pickle(pickle_file)
    print(f"🥒 Pickle DataFrame exported: {pickle_file}")
    
    # JSON export
    json_file = os.path.join(OUTPUT_DIR, f"extracted_text_{timestamp}.json")
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"📄 JSON exported: {json_file}")
    
    # Text summary
    successful = [r for r in results if r.get('text', '').strip()]
    total_chars = sum(len(r.get('text', '')) for r in results)
    avg_confidence = sum(r.get('confidence', 0) for r in results) / len(results)
    
    print(f"\n📈 Summary:")
    print(f"  ✓ Successful extractions: {len(successful)}/{len(results)}")
    print(f"  ✓ Total characters extracted: {total_chars:,}")
    print(f"  ✓ Average confidence: {avg_confidence:.1f}%")
    print(f"  📁 Results saved to: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
