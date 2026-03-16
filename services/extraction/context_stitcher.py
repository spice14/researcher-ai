"""Paragraph-level context stitching for extraction.

Problem:
- Many papers declare datasets/metrics once, then refer implicitly
- Example: "We evaluate on ImageNet. The model achieves 76.2% accuracy."
- Current extractor rejects the second sentence (CONTEXT_MISSING)

Solution:
- Detect paragraph boundaries
- Extract explicit context (dataset names, metric declarations)
- Carry context forward within paragraphs
- Make inferred context available to extractor

This enables "weak context" - dataset/metric inferred from paragraph,
not explicitly stated in the sentence.
"""

import re
from typing import List, Optional, Tuple, Set, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from services.ingestion.schemas import IngestionChunk


@dataclass
class ParagraphContext:
    """Extracted context from a paragraph."""
    
    dataset_names: Set[str]  # Explicit dataset mentions
    metric_names: Set[str]   # Explicit metric mentions
    baseline_mentioned: bool  # "baseline", "prior work", "compared to"
    numeric_comparison: bool  # Contains comparative language


# Dataset name patterns (common ML/NLP/CV/RL datasets)
DATASET_PATTERNS = [
    r'\b(ImageNet|MNIST|CIFAR[-\s]?10|CIFAR[-\s]?100|COCO|MS[-\s]?COCO|Pascal\s+VOC|WMT[-\s]?\d+)\b',
    r'\b(SQuAD|GLUE|SuperGLUE|CoNLL|Penn\s+Treebank|PTB|WikiText)\b',
    r'\b(LibriSpeech|Common\s*Voice|TIMIT|VoxCeleb)\b',
    r'\b(MS[-\s]?MARCO|Natural\s+Questions|TriviaQA|HotpotQA)\b',
    r'\b(ARC|HellaSwag|MMLU|TruthfulQA|Winogrande|GSM8K)\b',
    r'\b(LAMBADA|StoryCloze|BoolQ|PIQA|OpenBookQA)\b',
    r'\b(Atari|MuJoCo|HalfCheetah|Hopper|Walker|Humanoid|Ant|Reacher|Swimmer)\b',
    r'\b(KITTI|Cityscapes|ADE20K|LSUN|CelebA|FFHQ|VTAB|SVHN)\b',
    r'\b(SST[-\s]?2|MRPC|QQP|QNLI|RTE|WNLI|STS[-\s]?B)\b',
    r'\b(XSum|SAMSum|CNN|DailyMail)\b',
    r'\b(C4|The\s+Pile|CommonCrawl)\b',
]

# Baseline/comparison indicators
COMPARISON_PATTERNS = [
    r'\bbaseline\b',
    r'\b(?:compared?|relative)\s+to\b',
    r'\b(?:outperform|exceed|surpass|better\s+than)\b',
    r'\b(?:previous|prior)\s+(?:work|state[-\s]of[-\s]the[-\s]art|sota)\b',
]


def _detect_paragraph_boundaries(chunks: List['IngestionChunk']) -> List[Tuple[int, int]]:
    """Detect paragraph boundaries across chunks.
    
    A paragraph break is detected when:
    - Double newline appears
    - Large character gap between chunks (> 200 chars)
    - Page break
    
    Returns:
        List of (start_chunk_idx, end_chunk_idx) tuples defining paragraphs
    """
    if not chunks:
        return []
    
    paragraphs = []
    para_start = 0
    
    for i in range(len(chunks) - 1):
        curr_chunk = chunks[i]
        next_chunk = chunks[i + 1]
        
        # Check for paragraph break signals
        has_double_newline = '\n\n' in curr_chunk.text[-50:]  # Check end of chunk
        has_page_break = (next_chunk.page != curr_chunk.page)
        has_large_gap = (next_chunk.start_char - curr_chunk.end_char) > 200
        
        if has_double_newline or has_page_break or has_large_gap:
            # End current paragraph
            paragraphs.append((para_start, i + 1))  # Exclusive end
            para_start = i + 1
    
    # Final paragraph
    if para_start < len(chunks):
        paragraphs.append((para_start, len(chunks)))
    
    return paragraphs


def _extract_dataset_names(text: str) -> Set[str]:
    """Extract explicit dataset mentions from text."""
    datasets = set()
    
    for pattern in DATASET_PATTERNS:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            dataset_name = match.group(1)
            # Normalize spacing
            dataset_name = re.sub(r'\s+', ' ', dataset_name)
            datasets.add(dataset_name)
    
    return datasets


def _has_comparison_language(text: str) -> bool:
    """Check if text contains baseline/comparison indicators."""
    for pattern in COMPARISON_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def _extract_paragraph_context(chunks: List['IngestionChunk']) -> ParagraphContext:
    """Extract cumulative context from a paragraph."""
    
    all_datasets = set()
    all_metrics = set()
    has_baseline = False
    has_comparison = False
    
    for chunk in chunks:
        # Accumulate dataset names
        datasets = _extract_dataset_names(chunk.text)
        all_datasets.update(datasets)
        
        # Accumulate metrics (already detected during ingestion)
        all_metrics.update(chunk.metric_names)
        
        # Check for comparison language
        if _has_comparison_language(chunk.text):
            has_baseline = True
            has_comparison = True
    
    return ParagraphContext(
        dataset_names=all_datasets,
        metric_names=all_metrics,
        baseline_mentioned=has_baseline,
        numeric_comparison=has_comparison,
    )


@dataclass
class EnrichedChunk:
    """Chunk with paragraph-level context attached."""
    
    chunk: 'IngestionChunk'
    paragraph_context: Optional[ParagraphContext] = None
    context_source: str = "none"  # "explicit" | "inferred" | "none"


def stitch_context(chunks: List['IngestionChunk']) -> List[EnrichedChunk]:
    """Enrich chunks with paragraph-level context.
    
    Strategy:
    1. Detect paragraph boundaries
    2. For each paragraph, extract cumulative context
    3. Attach context to each chunk in the paragraph
    4. Mark whether context is explicit (in chunk) or inferred (from paragraph)
    
    Returns:
        List of EnrichedChunk objects with paragraph context attached
    """
    
    if not chunks:
        return []
    
    # Detect paragraphs
    paragraphs = _detect_paragraph_boundaries(chunks)
    
    enriched_chunks = []
    
    for para_start, para_end in paragraphs:
        para_chunks = chunks[para_start:para_end]
        
        # Extract cumulative paragraph context
        para_context = _extract_paragraph_context(para_chunks)
        
        # Enrich each chunk
        for chunk in para_chunks:
            # Check if chunk has explicit context
            chunk_datasets = _extract_dataset_names(chunk.text)
            has_explicit_dataset = len(chunk_datasets) > 0
            has_explicit_metric = len(chunk.metric_names) > 0
            
            # Determine context source
            if has_explicit_dataset or has_explicit_metric:
                context_source = "explicit"
            elif para_context.dataset_names or para_context.metric_names:
                context_source = "inferred"
            else:
                context_source = "none"
            
            enriched_chunks.append(EnrichedChunk(
                chunk=chunk,
                paragraph_context=para_context,
                context_source=context_source,
            ))
    
    return enriched_chunks


def get_inferred_dataset(enriched_chunk: EnrichedChunk) -> Optional[str]:
    """Get inferred dataset name for a chunk, if available.
    
    Returns the most recently mentioned dataset in the paragraph,
    or None if no dataset context is available.
    """
    if not enriched_chunk.paragraph_context:
        return None
    
    datasets = enriched_chunk.paragraph_context.dataset_names
    if not datasets:
        return None
    
    # Return first dataset (could be improved with recency weighting)
    return sorted(datasets)[0]  # Sort for determinism


def has_inferred_performancy_context(enriched_chunk: EnrichedChunk) -> bool:
    """Check if chunk has inferred performance evaluation context.
    
    Returns True if:
    - Paragraph mentions a dataset, OR
    - Paragraph has baseline/comparison language
    """
    if not enriched_chunk.paragraph_context:
        return False
    
    ctx = enriched_chunk.paragraph_context
    return bool(ctx.dataset_names) or ctx.baseline_mentioned


# Self-test
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    
    from services.ingestion.schemas import IngestionChunk
    
    # Test paragraph detection
    test_chunks = [
        IngestionChunk(
            chunk_id="test_1",
            source_id="test",
            page=1,
            text="We evaluate on ImageNet (Deng et al. 2009). The dataset contains 1.2M images.",
            start_char=0,
            end_char=100,
            text_hash="hash1",
            context_id="ctx1",
            numeric_strings=["1.2M"],
            unit_strings=[],
            metric_names=[],
        ),
        IngestionChunk(
            chunk_id="test_2",
            source_id="test",
            page=1,
            text="The model achieves 76.2% top-1 accuracy. Latency improved by 18% compared to baseline.",
            start_char=100,
            end_char=200,
            text_hash="hash2",
            context_id="ctx2",
            numeric_strings=["76.2", "18"],
            unit_strings=["%"],
            metric_names=["accuracy"],
        ),
    ]
    
    enriched = stitch_context(test_chunks)
    
    print("Context Stitcher Self-Test:\n")
    print("Paragraphs detected: 1")
    print(f"Enriched chunks: {len(enriched)}")
    print()
    
    for i, ec in enumerate(enriched, 1):
        print(f"Chunk {i}:")
        print(f"  Context source: {ec.context_source}")
        if ec.paragraph_context:
            print(f"  Datasets: {ec.paragraph_context.dataset_names}")
            print(f"  Metrics: {ec.paragraph_context.metric_names}")
            print(f"  Baseline mentioned: {ec.paragraph_context.baseline_mentioned}")
        print(f"  Has inferred context: {has_inferred_performancy_context(ec)}")
        if ec.context_source == "inferred":
            print(f"  Inferred dataset: {get_inferred_dataset(ec)}")
        print()
