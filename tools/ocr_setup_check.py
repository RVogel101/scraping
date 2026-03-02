"""
Test OCR Setup - Quick Test Script
Tests OCR functionality with a few sample images before running the full extraction.
"""

import os
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test if required packages are installed."""
    print("Testing package imports...")
    
    packages = {
        'cv2': 'opencv-python',
        'PIL': 'pillow', 
        'numpy': 'numpy',
        'pytesseract': 'pytesseract',
        'pandas': 'pandas'
    }
    
    missing = []
    for package, install_name in packages.items():
        try:
            if package == 'PIL':
                from PIL import Image
            elif package == 'cv2':
                import cv2
            else:
                __import__(package)
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ❌ {package} (install with: pip install {install_name})")
            missing.append(install_name)
    
    return missing

def test_tesseract():
    """Test Tesseract OCR installation."""
    print("\nTesting Tesseract OCR...")
    
    try:
        import pytesseract
        
        # Try to find Tesseract executable in common Windows locations
        common_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            r"C:\Tesseract-OCR\tesseract.exe"
        ]
        
        tesseract_found = False
        for path in common_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                print(f"  ✓ Found Tesseract at: {path}")
                tesseract_found = True
                break
        
        if not tesseract_found:
            print("  ⚠️  Trying default Tesseract path...")
        
        version = pytesseract.get_tesseract_version()
        print(f"  ✓ Tesseract version: {version}")
        
        # Test supported languages
        try:
            langs = pytesseract.get_languages()
            print(f"  ✓ Available languages: {', '.join(langs)}")
            
            # Check for Armenian language support
            armenian_support = []
            if 'hy' in langs:
                armenian_support.append('Standard Armenian (hy)')
            if 'hye' in langs:
                armenian_support.append('Enhanced Armenian (hye)')
                
            if armenian_support:
                print(f"  ✓ Armenian support: {', '.join(armenian_support)}")
            else:
                print("  ⚠️  No Armenian language support found")
                print("     Install: tesseract-ocr-arm + hye-tesseract model")
                
        except Exception as e:
            print(f"  ⚠️  Could not get language list: {e}")
            
        return True
        
    except Exception as e:
        print(f"  ❌ Tesseract not found: {e}")
        print("  Install from: https://github.com/UB-Mannheim/tesseract/wiki")
        return False

def test_sample_images():
    """Test OCR on a few sample images."""
    print("\nTesting OCR on sample images...")
    
    from extract_image_text_simple import process_image
    
    input_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "FB-UK-CWAS-Content")
    
    if not os.path.exists(input_dir):
        print(f"  ❌ Input directory not found: {input_dir}")
        return False
    
    # Get first 3 image files for testing
    image_files = []
    for filename in sorted(os.listdir(input_dir))[:10]:  # Check first 10 files
        if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            image_files.append(os.path.join(input_dir, filename))
            if len(image_files) >= 3:  # Test with 3 images
                break
    
    if not image_files:
        print("  ❌ No image files found for testing")
        return False
    
    print(f"  Testing with {len(image_files)} sample images...")
    
    success_count = 0
    for filepath in image_files:
        filename = os.path.basename(filepath)
        print(f"    Processing: {filename}")
        
        try:
            result = process_image(filepath)
            
            if result.get('error'):
                print(f"      ❌ Error: {result['error']}")
            else:
                text = result.get('text', '').strip()
                confidence = result.get('confidence', 0)
                char_count = len(text)
                
                if char_count > 0:
                    print(f"      ✓ Extracted {char_count} characters (confidence: {confidence:.1f}%)")
                    print(f"      Sample text: {text[:100]}{'...' if len(text) > 100 else ''}")
                    success_count += 1
                else:
                    print(f"      ⚠️  No text extracted")
                    
        except Exception as e:
            print(f"      ❌ Processing failed: {e}")
    
    print(f"  Result: {success_count}/{len(image_files)} images processed successfully")
    return success_count > 0

def main():
    """Main test function."""
    print("🧪 OCR Setup Test")
    print("=" * 40)
    
    # Test 1: Package imports
    missing_packages = test_imports()
    if missing_packages:
        print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
        print(f"Install with: pip install {' '.join(missing_packages)}")
        return False
    
    # Test 2: Tesseract
    if not test_tesseract():
        print("\n❌ Tesseract OCR is not properly installed")
        return False
    
    # Test 3: Sample image processing
    if not test_sample_images():
        print("\n❌ Sample image processing failed")
        return False
    
    print("\n✅ All tests passed! OCR setup is working correctly.")
    print("\nYou can now run:")
    print("  python extract_image_text_simple.py  (for simple extraction)")
    print("  python extract_image_text.py         (for advanced multi-engine extraction)")
    
    return True

if __name__ == "__main__":
    main()