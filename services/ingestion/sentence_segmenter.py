"""Deterministic sentence segmenter for Model B ingestion.

Purpose:
- Split PyMuPDF blocks into sentence-level chunks for extraction
- Restore semantic topology expected by extraction engine
- Maintain 100% determinism (no ML, no external tokenizers)

Rules:
- Regex-based splitting only
- Preserve decimal numbers (3.14, 28.4, 0.95)
- Preserve abbreviations (e.g., i.e., et al., Fig., etc.)
- Preserve scientific notation (1e-3, 2.5e-4)
- Pure function (no randomness, no state)

Testing:
- 5-run hash identity test
- Abbreviation preservation test
- Decimal preservation test
- Empty sentence removal test
"""

import re
from typing import List


# Known abbreviations that should not trigger sentence breaks
ABBREVIATIONS = {
    "e.g.", "i.e.", "et al.", "Fig.", "fig.", "Sec.", "sec.", 
    "Eq.", "eq.", "Tab.", "tab.", "Dr.", "dr.", "Mr.", "mr.", 
    "Ms.", "ms.", "Mrs.", "mrs.", "Prof.", "prof.", "Inc.", "inc.",
    "vs.", "Vol.", "vol.", "No.", "no.", "al.", "cf.", "Cf.",
}


# Placeholder for abbreviations (unlikely to appear in text)
_ABBREV_PLACEHOLDER = "<!ABBREV_{:04d}!>"


def _normalize_whitespace(text: str) -> str:
    """Normalize whitespace while preserving paragraph structure.
    
    Args:
        text: Input text
    
    Returns:
        Text with normalized whitespace
    """
    # Replace multiple spaces (but not newlines) with single space
    text = re.sub(r' +', ' ', text)
    # Preserve double newlines (paragraph breaks) but normalize triple+ newlines to double
    text = re.sub(r'\n\n+', '\n\n', text)
    # Remove leading/trailing whitespace
    text = text.strip()
    return text


def _protect_abbreviations(text: str) -> tuple[str, dict[str, str]]:
    """Replace abbreviations with placeholders to protect them during splitting.
    
    Args:
        text: Input text
    
    Returns:
        (protected_text, replacement_map)
    """
    protected = text
    replacement_map = {}
    
    # Sort abbreviations by length (descending) to handle longer ones first
    sorted_abbrevs = sorted(ABBREVIATIONS, key=len, reverse=True)
    
    for idx, abbrev in enumerate(sorted_abbrevs):
        placeholder = _ABBREV_PLACEHOLDER.format(idx)
        if abbrev in protected:
            replacement_map[placeholder] = abbrev
            protected = protected.replace(abbrev, placeholder)
    
    return protected, replacement_map


def _restore_abbreviations(text: str, replacement_map: dict[str, str]) -> str:
    """Restore abbreviations from placeholders.
    
    Args:
        text: Text with placeholders
        replacement_map: Mapping from placeholder to original abbreviation
    
    Returns:
        Text with abbreviations restored
    """
    restored = text
    for placeholder, abbrev in replacement_map.items():
        restored = restored.replace(placeholder, abbrev)
    return restored


def _is_decimal_boundary(text: str, pos: int) -> bool:
    """Check if period at position is part of a decimal number.
    
    Args:
        text: Input text
        pos: Position of period
    
    Returns:
        True if period is part of decimal number
    """
    if pos == 0 or pos >= len(text) - 1:
        return False
    
    # Check if surrounded by digits
    return text[pos - 1].isdigit() and text[pos + 1].isdigit()


def _split_on_sentence_boundaries(text: str) -> List[str]:
    """Split text on sentence boundaries using regex patterns.
    
    Splits on:
    - period + space + uppercase letter
    - period + newline + uppercase letter
    - question mark + space
    - exclamation + space
    - newline + newline (paragraph breaks)
    
    Args:
        text: Input text with abbreviations protected
    
    Returns:
        List of sentence strings
    """
    sentences = []
    current = []
    i = 0
    
    while i < len(text):
        char = text[i]
        current.append(char)
        
        # Check for sentence boundaries
        is_boundary = False
        
        # Double newline (paragraph break) - check first
        if char == '\n' and i + 1 < len(text) and text[i + 1] == '\n':
            is_boundary = True
            # Skip the second newline
            i += 1
        
        # Period followed by space and uppercase letter
        elif char == '.' and i + 2 < len(text):
            if not _is_decimal_boundary(text, i):
                next_char = text[i + 1]
                next_next_char = text[i + 2] if i + 2 < len(text) else ''
                
                # Period + space + uppercase
                if next_char == ' ' and next_next_char.isupper():
                    is_boundary = True
                # Period + newline + uppercase
                elif next_char == '\n' and next_next_char.isupper():
                    is_boundary = True
        
        # Question mark or exclamation followed by space
        elif char in '?!' and i + 1 < len(text):
            next_char = text[i + 1]
            if next_char in ' \n':
                is_boundary = True
        
        if is_boundary:
            # Save current sentence
            sentence = ''.join(current).strip()
            if sentence:
                sentences.append(sentence)
            current = []
        
        i += 1
    
    # Add remaining text as final sentence
    if current:
        sentence = ''.join(current).strip()
        if sentence:
            sentences.append(sentence)
    
    return sentences


def split_into_sentences(text: str) -> List[str]:
    """Split text into sentences using deterministic rules.
    
    This is the main entry point for sentence segmentation.
    
    Process:
    1. Normalize whitespace
    2. Protect abbreviations (replace with placeholders)
    3. Split on sentence boundaries
    4. Restore abbreviations
    5. Filter empty sentences
    
    Args:
        text: Input text (typically a PyMuPDF block)
    
    Returns:
        List of sentence strings in original order
    
    Examples:
        >>> split_into_sentences("This is sentence 1. This is sentence 2.")
        ['This is sentence 1.', 'This is sentence 2.']
        
        >>> split_into_sentences("The model achieves 28.4 BLEU. This is new.")
        ['The model achieves 28.4 BLEU.', 'This is new.']
        
        >>> split_into_sentences("See Fig. 1 for details. This is important.")
        ['See Fig. 1 for details.', 'This is important.']
    """
    # Step 1: Normalize whitespace
    normalized = _normalize_whitespace(text)
    
    # Step 2: Protect abbreviations
    protected, replacement_map = _protect_abbreviations(normalized)
    
    # Step 3: Split on sentence boundaries
    sentences = _split_on_sentence_boundaries(protected)
    
    # Step 4: Restore abbreviations in each sentence
    restored_sentences = [
        _restore_abbreviations(sent, replacement_map)
        for sent in sentences
    ]
    
    # Step 5: Filter empty sentences and strip whitespace
    final_sentences = [
        sent.strip()
        for sent in restored_sentences
        if sent.strip()
    ]
    
    return final_sentences


def split_block_into_sentence_chunks(
    block_text: str,
    block_id: str,
    page: int,
    source_id: str,
    block_type: str = "BODY"
) -> List[dict]:
    """Split a PyMuPDF block into sentence-level chunk metadata.
    
    Convenience function for Model B ingestion service.
    
    Args:
        block_text: Text content of the block
        block_id: Block identifier
        page: Page number
        source_id: Source document identifier
        block_type: Type of block (BODY or TABLE)
    
    Returns:
        List of chunk metadata dicts suitable for IngestionChunk construction
    """
    sentences = split_into_sentences(block_text)
    
    chunks = []
    for sent_idx, sentence in enumerate(sentences):
        chunk_meta = {
            'text': sentence,
            'block_id': f"{block_id}_s{sent_idx}",
            'page': page,
            'source_id': source_id,
            'block_type': block_type,
            'sentence_index': sent_idx,
        }
        chunks.append(chunk_meta)
    
    return chunks
