"""
PDF Text Extraction Service

This module provides hybrid PDF text extraction using pdfplumber and OCR fallback.
It automatically detects PDF quality and selects the best extraction method.
"""

import os
import time
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from PIL import Image

# Configure logging
logger = logging.getLogger(__name__)

# Timeout configuration
EXTRACTION_TIMEOUT = 15  # seconds
OCR_DPI = 300  # DPI for PDF to image conversion


def _clean_text(text: str) -> str:
    """
    Clean extracted text by removing extra whitespace and normalizing encoding.
    
    Args:
        text: Raw extracted text
        
    Returns:
        str: Cleaned text
    """
    if not text:
        return ""
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove null bytes and other control characters
    text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', text)
    
    # Normalize encoding - replace common problematic characters
    text = text.encode('utf-8', errors='ignore').decode('utf-8')
    
    # Remove multiple consecutive spaces
    text = re.sub(r' {2,}', ' ', text)
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    return text


def extract_with_pdfplumber(pdf_path: str) -> Dict:
    """
    Extract text from PDF using pdfplumber.
    
    This method works best for PDFs with embedded text (digital PDFs).
    It's fast and accurate for properly formatted PDFs.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Dict containing:
            - text: Extracted text
            - method: "pdfplumber"
            - confidence: 0.95
            - page_count: Number of pages processed
            - char_count: Character count of extracted text
            
    Raises:
        FileNotFoundError: If PDF file doesn't exist
        Exception: For other PDF processing errors
    """
    start_time = time.time()
    
    if not os.path.exists(pdf_path):
        logger.error(f"PDF file not found: {pdf_path}")
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    try:
        logger.info(f"Extracting text from '{pdf_path}' using pdfplumber...")
        
        all_text = []
        page_count = 0
        
        with pdfplumber.open(pdf_path) as pdf:
            page_count = len(pdf.pages)
            
            for page_num, page in enumerate(pdf.pages, 1):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        all_text.append(page_text)
                    logger.debug(f"Extracted text from page {page_num}/{page_count}")
                except Exception as e:
                    logger.warning(f"Failed to extract text from page {page_num}: {str(e)}")
                    continue
        
        # Concatenate and clean text
        raw_text = '\n'.join(all_text)
        cleaned_text = _clean_text(raw_text)
        char_count = len(cleaned_text)
        
        processing_time = time.time() - start_time
        
        logger.info(
            f"pdfplumber extraction completed - "
            f"Pages: {page_count}, Chars: {char_count}, "
            f"Time: {processing_time:.2f}s"
        )
        
        return {
            "text": cleaned_text,
            "method": "pdfplumber",
            "confidence": 0.95,
            "page_count": page_count,
            "char_count": char_count,
            "processing_time": round(processing_time, 2)
        }
        
    except FileNotFoundError:
        raise
    except Exception as e:
        logger.error(f"pdfplumber extraction failed: {str(e)}")
        raise Exception(f"Failed to extract text with pdfplumber: {str(e)}")


def extract_with_ocr(pdf_path: str) -> Dict:
    """
    Extract text from PDF using OCR (pytesseract).
    
    This method converts PDF pages to images and uses OCR to extract text.
    Best for scanned PDFs or PDFs without embedded text.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Dict containing:
            - text: Extracted text
            - method: "ocr"
            - confidence: 0.78
            - page_count: Number of pages processed
            - char_count: Character count of extracted text
            
    Raises:
        FileNotFoundError: If PDF file doesn't exist
        Exception: For OCR processing errors
    """
    start_time = time.time()
    
    if not os.path.exists(pdf_path):
        logger.error(f"PDF file not found: {pdf_path}")
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    try:
        logger.info(f"Extracting text from '{pdf_path}' using OCR...")
        
        # Convert PDF to images
        logger.debug(f"Converting PDF to images at {OCR_DPI} DPI...")
        images = convert_from_path(pdf_path, dpi=OCR_DPI)
        page_count = len(images)
        
        logger.info(f"Converting {page_count} pages to images completed")
        
        all_text = []
        
        # Extract text from each image
        for page_num, image in enumerate(images, 1):
            try:
                logger.debug(f"Performing OCR on page {page_num}/{page_count}")
                page_text = pytesseract.image_to_string(image, lang='eng')
                if page_text:
                    all_text.append(page_text)
            except Exception as e:
                logger.warning(f"OCR failed for page {page_num}: {str(e)}")
                continue
        
        # Concatenate and clean text
        raw_text = '\n'.join(all_text)
        cleaned_text = _clean_text(raw_text)
        char_count = len(cleaned_text)
        
        processing_time = time.time() - start_time
        
        logger.info(
            f"OCR extraction completed - "
            f"Pages: {page_count}, Chars: {char_count}, "
            f"Time: {processing_time:.2f}s"
        )
        
        return {
            "text": cleaned_text,
            "method": "ocr",
            "confidence": 0.78,
            "page_count": page_count,
            "char_count": char_count,
            "processing_time": round(processing_time, 2)
        }
        
    except FileNotFoundError:
        raise
    except Exception as e:
        logger.error(f"OCR extraction failed: {str(e)}")
        raise Exception(f"Failed to extract text with OCR: {str(e)}")


def detect_pdf_quality(text: str) -> str:
    """
    Detect the quality of extracted PDF text.
    
    Analyzes the extracted text to determine if extraction was successful
    and if the PDF has good quality embedded text.
    
    Args:
        text: Extracted text to analyze
        
    Returns:
        str: Quality indicator
            - "poor_quality": Very little text extracted
            - "complex_layout": High percentage of non-ASCII characters
            - "good_quality": Good extraction with readable text
    """
    if not text:
        return "poor_quality"
    
    text_length = len(text)
    
    # Check for very short text
    if text_length < 50:
        logger.debug("PDF quality: poor_quality (text length < 50)")
        return "poor_quality"
    
    # Calculate non-ASCII character percentage
    non_ascii_chars = sum(1 for char in text if ord(char) > 127)
    non_ascii_percentage = (non_ascii_chars / text_length) * 100
    
    if non_ascii_percentage > 30:
        logger.debug(
            f"PDF quality: complex_layout "
            f"({non_ascii_percentage:.1f}% non-ASCII chars)"
        )
        return "complex_layout"
    
    logger.debug("PDF quality: good_quality")
    return "good_quality"


def _extract_with_timeout(
    extraction_func,
    pdf_path: str,
    timeout: int = EXTRACTION_TIMEOUT
) -> Dict:
    """
    Execute extraction function with timeout.
    
    Args:
        extraction_func: Function to execute
        pdf_path: Path to PDF file
        timeout: Timeout in seconds
        
    Returns:
        Dict: Extraction result
        
    Raises:
        TimeoutError: If extraction exceeds timeout
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(extraction_func, pdf_path)
        try:
            result = future.wait(timeout=timeout)
            return future.result()
        except FuturesTimeoutError:
            logger.warning(
                f"Extraction timed out after {timeout}s for '{pdf_path}'"
            )
            raise TimeoutError(
                f"PDF extraction exceeded timeout of {timeout} seconds"
            )


def extract_pdf_text(pdf_path: str) -> Dict:
    """
    Extract text from PDF using hybrid approach with automatic fallback.
    
    Main extraction pipeline:
    1. Try pdfplumber first (fast and accurate for digital PDFs)
    2. Check quality of extracted text
    3. If poor quality, fallback to OCR
    4. Return best result with comprehensive metadata
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Dict containing:
            - text: Extracted text
            - method: Extraction method used ("pdfplumber", "ocr", "hybrid")
            - confidence: Confidence score (0-1)
            - page_count: Number of pages
            - char_count: Character count
            - quality: Quality assessment
            - processing_time: Time taken in seconds
            - warnings: List of warnings (if any)
            
    Raises:
        FileNotFoundError: If PDF file doesn't exist
    """
    filename = Path(pdf_path).name
    logger.info(f"Starting PDF text extraction for: {filename}")
    
    if not os.path.exists(pdf_path):
        logger.error(f"PDF file not found: {pdf_path}")
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    warnings = []
    pdfplumber_result = None
    ocr_result = None
    
    # Try pdfplumber first
    try:
        logger.info("Attempting pdfplumber extraction...")
        pdfplumber_result = extract_with_pdfplumber(pdf_path)
        
        # Check quality
        quality = detect_pdf_quality(pdfplumber_result["text"])
        pdfplumber_result["quality"] = quality
        
        if quality == "good_quality":
            logger.info(
                f"Successfully extracted text using pdfplumber - "
                f"{pdfplumber_result['char_count']} characters"
            )
            return pdfplumber_result
        else:
            logger.warning(
                f"pdfplumber extraction quality is {quality}, "
                f"attempting OCR fallback..."
            )
            warnings.append(
                f"pdfplumber quality was {quality}, OCR fallback used"
            )
            
    except TimeoutError as e:
        logger.error(f"pdfplumber timed out: {str(e)}")
        warnings.append("pdfplumber extraction timed out")
    except Exception as e:
        logger.error(f"pdfplumber failed: {str(e)}")
        warnings.append(f"pdfplumber failed: {str(e)}")
    
    # Fallback to OCR
    try:
        logger.info("Attempting OCR extraction...")
        ocr_result = extract_with_ocr(pdf_path)
        
        quality = detect_pdf_quality(ocr_result["text"])
        ocr_result["quality"] = quality
        ocr_result["warnings"] = warnings
        
        # If we have both results, compare them
        if pdfplumber_result and pdfplumber_result["char_count"] > 0:
            logger.info("Using hybrid approach - combining results")
            
            # Choose the better result based on character count
            if ocr_result["char_count"] > pdfplumber_result["char_count"]:
                ocr_result["method"] = "hybrid"
                logger.info(
                    f"OCR produced more text ({ocr_result['char_count']} vs "
                    f"{pdfplumber_result['char_count']} chars), using OCR result"
                )
                return ocr_result
            else:
                pdfplumber_result["method"] = "hybrid"
                pdfplumber_result["warnings"] = warnings
                logger.info(
                    f"pdfplumber produced more text "
                    f"({pdfplumber_result['char_count']} vs "
                    f"{ocr_result['char_count']} chars), using pdfplumber result"
                )
                return pdfplumber_result
        
        logger.info(
            f"Successfully extracted text using OCR - "
            f"{ocr_result['char_count']} characters"
        )
        return ocr_result
        
    except TimeoutError as e:
        logger.error(f"OCR timed out: {str(e)}")
        warnings.append("OCR extraction timed out")
        
        # Return partial pdfplumber result if available
        if pdfplumber_result and pdfplumber_result["char_count"] > 0:
            pdfplumber_result["warnings"] = warnings
            pdfplumber_result["warnings"].append(
                "Returning partial pdfplumber result due to OCR timeout"
            )
            logger.warning("Returning partial pdfplumber result")
            return pdfplumber_result
            
        # Return error result
        return {
            "text": "",
            "method": "failed",
            "confidence": 0.0,
            "page_count": 0,
            "char_count": 0,
            "quality": "poor_quality",
            "processing_time": 0,
            "warnings": warnings + [str(e)],
            "error": "All extraction methods timed out"
        }
        
    except Exception as e:
        logger.error(f"OCR failed: {str(e)}")
        warnings.append(f"OCR failed: {str(e)}")
        
        # Return partial pdfplumber result if available
        if pdfplumber_result and pdfplumber_result["char_count"] > 0:
            pdfplumber_result["warnings"] = warnings
            pdfplumber_result["warnings"].append(
                "Returning partial pdfplumber result due to OCR failure"
            )
            logger.warning("Returning partial pdfplumber result")
            return pdfplumber_result
        
        # Return error result
        return {
            "text": "",
            "method": "failed",
            "confidence": 0.0,
            "page_count": 0,
            "char_count": 0,
            "quality": "poor_quality",
            "processing_time": 0,
            "warnings": warnings,
            "error": f"All extraction methods failed: {str(e)}"
        }


def extract_pdf_metadata(pdf_path: str) -> Dict:
    """
    Extract metadata from PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Dict containing PDF metadata (title, author, pages, etc.)
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            metadata = pdf.metadata or {}
            return {
                "title": metadata.get("Title", ""),
                "author": metadata.get("Author", ""),
                "subject": metadata.get("Subject", ""),
                "creator": metadata.get("Creator", ""),
                "producer": metadata.get("Producer", ""),
                "creation_date": metadata.get("CreationDate", ""),
                "modification_date": metadata.get("ModDate", ""),
                "page_count": len(pdf.pages)
            }
    except Exception as e:
        logger.error(f"Failed to extract PDF metadata: {str(e)}")
        return {"error": str(e)}
