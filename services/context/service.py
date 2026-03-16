"""Deterministic context extraction service.

Purpose:
- Extract ExperimentalContext identity from ingested chunks.
- Instantiate real ExperimentalContext objects (not just string IDs).
- Build a ContextRegistry mapping context_id → ExperimentalContext.
- Propagate context within page scope: sentences on the same page
  as a dataset mention inherit that context if they have metric signals.

This implements SYSTEM_GUIDELINES §1.5.2:
  "ExperimentalContext is the primary identity carrier."
  "Claims are comparable only within identical experimental contexts."

Inputs/Outputs:
- Input: List[IngestionChunk]
- Output: ContextExtractionResult (registry + updated chunks)

Schema References:
- core.schemas.experimental_context
- services.ingestion.schemas

Failure Modes:
- Chunks with no detectable context → marked ctx_unknown
- Unknown metric direction → defaults to higher_is_better=True

Testing Strategy:
- Real PDF chunks produce real ExperimentalContext objects
- Page-scoped context propagation verified
- ctx_unknown chunks are preserved, not silently dropped
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from core.schemas.experimental_context import (
    ContextRegistry,
    EvaluationProtocol,
    ExperimentalContext,
    MetricDefinition,
    TaskType,
)
from services.ingestion.schemas import IngestionChunk


# Known dataset → task type mappings
_DATASET_TASK_MAP: Dict[str, TaskType] = {
    "wmt": TaskType.TRANSLATION,
    "glue": TaskType.CLASSIFICATION,
    "superglue": TaskType.CLASSIFICATION,
    "mnli": TaskType.CLASSIFICATION,
    "cola": TaskType.CLASSIFICATION,
    "sst-2": TaskType.CLASSIFICATION,
    "sst 2": TaskType.CLASSIFICATION,
    "mrpc": TaskType.CLASSIFICATION,
    "qqp": TaskType.CLASSIFICATION,
    "qnli": TaskType.CLASSIFICATION,
    "rte": TaskType.CLASSIFICATION,
    "wnli": TaskType.CLASSIFICATION,
    "squad": TaskType.QUESTION_ANSWERING,
    "imagenet": TaskType.CLASSIFICATION,
    "cifar-10": TaskType.CLASSIFICATION,
    "cifar 10": TaskType.CLASSIFICATION,
    "cifar-100": TaskType.CLASSIFICATION,
    "cifar 100": TaskType.CLASSIFICATION,
    "coco": TaskType.OTHER,
    "ms-coco": TaskType.OTHER,
    "ms coco": TaskType.OTHER,
    "pascal voc": TaskType.OTHER,
    "cnn": TaskType.SUMMARIZATION,
    "dailymail": TaskType.SUMMARIZATION,
    "xsum": TaskType.SUMMARIZATION,
    "samsum": TaskType.SUMMARIZATION,
    "penn treebank": TaskType.SEQUENCE_LABELING,
    "ptb": TaskType.SEQUENCE_LABELING,
    "conll": TaskType.SEQUENCE_LABELING,
    "librispeech": TaskType.OTHER,
    "mmlu": TaskType.QUESTION_ANSWERING,
    "truthfulqa": TaskType.QUESTION_ANSWERING,
    "hellaswag": TaskType.CLASSIFICATION,
    "arc": TaskType.CLASSIFICATION,
    "winogrande": TaskType.CLASSIFICATION,
    "gsm8k": TaskType.QUESTION_ANSWERING,
    "atari": TaskType.OTHER,
    "mujoco": TaskType.OTHER,
    "vtab": TaskType.CLASSIFICATION,
    "kitti": TaskType.OTHER,
    "cityscapes": TaskType.OTHER,
    "ade20k": TaskType.OTHER,
    "ms-marco": TaskType.QUESTION_ANSWERING,
    "ms marco": TaskType.QUESTION_ANSWERING,
    "natural questions": TaskType.QUESTION_ANSWERING,
    "triviaqa": TaskType.QUESTION_ANSWERING,
    "hotpotqa": TaskType.QUESTION_ANSWERING,
}

# Known metric → direction mappings
_METRIC_DIRECTION: Dict[str, bool] = {
    "accuracy": True,
    "f1": True,
    "f1-score": True,
    "f1-macro": True,
    "bleu": True,
    "rouge": True,
    "rouge-l": True,
    "rouge-1": True,
    "rouge-2": True,
    "map": True,
    "mrr": True,
    "auc": True,
    "precision": True,
    "recall": True,
    "wer": False,
    "cer": False,
    "latency": False,
    "perplexity": False,
    "loss": False,
    "error rate": False,
    "mse": False,
    "rmse": False,
    "mae": False,
    "psnr": True,
    "ssim": True,
    "fid": False,
    "meteor": True,
    "spice": True,
    "cider": True,
    "ndcg": True,
    "throughput": True,
    "fps": True,
    "reward": True,
    "return": True,
    "mean reward": True,
    "score": True,
    "em": True,
    "exact match": True,
    "iou": True,
    "dice": True,
    "top-1": True,
    "top-5": True,
    "sensitivity": True,
    "specificity": True,
}

# Dataset name detection
_DATASET_PATTERN = re.compile(
    r"\b(WMT(?:\s*20\d{2})?|GLUE|SuperGLUE|MNLI|CoLA|SQuAD|ImageNet|"
    r"CNN|DailyMail|Penn Treebank|CoNLL"
    r"|CIFAR[-\s]?10|CIFAR[-\s]?100|COCO|MS[-\s]?COCO|Pascal\s?VOC"
    r"|PTB|WikiText|C4|The Pile|CommonCrawl"
    r"|LibriSpeech|Common Voice|TIMIT|VoxCeleb"
    r"|ARC|HellaSwag|MMLU|TruthfulQA|Winogrande|GSM8K"
    r"|LAMBADA|StoryCloze|BoolQ|PIQA|OpenBookQA"
    r"|Atari|MuJoCo|HalfCheetah|Hopper|Walker|Humanoid|Ant|Reacher|Swimmer"
    r"|KITTI|Cityscapes|ADE20K|LSUN|CelebA|FFHQ"
    r"|VTAB|Oxford Flowers|Stanford Cars|SVHN"
    r"|MS[-\s]?MARCO|Natural Questions|TriviaQA|HotpotQA"
    r"|XSum|SAMSum"
    r"|SST[-\s]?2|MRPC|QQP|QNLI|RTE|WNLI|STS[-\s]?B)\b",
    re.IGNORECASE,
)

# Metric name detection
_METRIC_PATTERN = re.compile(
    r"\b(accuracy|f1-macro|f1-score|f1|bleu|rouge-l|rouge-1|rouge-2|rouge|map|mrr|auc|"
    r"precision|recall|wer|cer|perplexity|latency"
    r"|meteor|spice|cider|bertscore|sacrebleu|ter"
    r"|ndcg|hit rate"
    r"|mse|rmse|mae|psnr|ssim|fid"
    r"|loss|error rate|throughput|fps"
    r"|reward|return|mean reward|average reward|score"
    r"|top-1|top-5|iou|em|exact match"
    r"|spearman|pearson|correlation"
    r"|dice|jaccard|sensitivity|specificity)\b",
    re.IGNORECASE,
)

# Section header detection for results scope
_SECTION_HEADER_PATTERN = re.compile(
    r"^(?:\d+\.?\s+)?(Results|Experiments|Evaluation|Training|Ablation)",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass
class ContextExtractionResult:
    """Result of context extraction."""
    registry: ContextRegistry
    chunks: List[IngestionChunk]
    contexts_created: int
    unknown_chunks: int


class ContextExtractor:
    """
    Deterministic context extraction from ingested chunks.

    Scans chunk text for dataset mentions, task indicators, and metrics.
    Builds real ExperimentalContext objects and a ContextRegistry.
    Propagates context within page scope for improved coverage.
    """

    def extract_contexts(
        self, chunks: List[IngestionChunk]
    ) -> ContextExtractionResult:
        """
        Extract ExperimentalContext objects from chunks.

        Three-pass algorithm:
        1. Discovery: scan ALL chunks to find dataset mentions → build context specs
        2. Page propagation: for each page, propagate dataset context to
           metric-bearing chunks that don't mention a dataset themselves
        3. Assignment: assign context_id to each chunk, build registry
        """
        # Pass 1: discover contexts and dataset anchors
        context_specs, chunk_dataset_map = self._discover_contexts(chunks)

        # Pass 2: page-scoped propagation
        chunk_propagated_ctx = self._propagate_page_context(chunks, chunk_dataset_map)

        # Pass 3: build registry and assign
        return self._build_result(
            chunks, context_specs, chunk_dataset_map, chunk_propagated_ctx
        )

    def _discover_contexts(
        self, chunks: List[IngestionChunk]
    ) -> Tuple[Dict[str, Tuple[str, TaskType, str, bool]], Dict[int, str]]:
        """Pass 1: discover all unique contexts and map chunks to datasets."""
        context_specs: Dict[str, Tuple[str, TaskType, str, bool]] = {}
        chunk_dataset_map: Dict[int, str] = {}

        for i, chunk in enumerate(chunks):
            datasets = _DATASET_PATTERN.findall(chunk.text)
            if not datasets:
                continue

            metrics = _METRIC_PATTERN.findall(chunk.text)
            dataset_raw = datasets[0]
            dataset_normalized = re.sub(r"\s+", " ", dataset_raw.strip())
            dataset_key = dataset_normalized.lower()
            ctx_id = f"ctx_{dataset_key.replace(' ', '_')}"

            chunk_dataset_map[i] = ctx_id

            if ctx_id not in context_specs:
                first_word = dataset_key.split()[0]
                task = _DATASET_TASK_MAP.get(
                    dataset_key, _DATASET_TASK_MAP.get(first_word, TaskType.OTHER)
                )
                metric_name = metrics[0].strip().lower() if metrics else "unknown"
                higher = _METRIC_DIRECTION.get(metric_name, True)
                context_specs[ctx_id] = (dataset_normalized, task, metric_name, higher)

        return context_specs, chunk_dataset_map

    def _propagate_page_context(
        self,
        chunks: List[IngestionChunk],
        chunk_dataset_map: Dict[int, str],
    ) -> Dict[int, str]:
        """Pass 2: page-scoped context propagation."""
        page_groups: Dict[int, List[int]] = defaultdict(list)
        for i, chunk in enumerate(chunks):
            page_groups[chunk.page].append(i)

        propagated: Dict[int, str] = {}

        for _page, chunk_indices in page_groups.items():
            anchors = [
                (idx, chunk_dataset_map[idx])
                for idx in chunk_indices
                if idx in chunk_dataset_map
            ]
            if not anchors:
                continue

            self._propagate_anchors(
                chunks, chunk_indices, chunk_dataset_map, anchors, propagated
            )

        return propagated

    def _propagate_anchors(
        self,
        chunks: List[IngestionChunk],
        chunk_indices: List[int],
        chunk_dataset_map: Dict[int, str],
        anchors: List[Tuple[int, str]],
        propagated: Dict[int, str],
    ) -> None:
        """Propagate anchor contexts to signal-bearing chunks on the same page."""
        for idx in chunk_indices:
            if idx in chunk_dataset_map:
                continue
            chunk = chunks[idx]
            has_signal = bool(chunk.metric_names) or bool(chunk.numeric_strings)
            if not has_signal:
                continue
            best = self._find_nearest_anchor(idx, anchors)
            if best:
                propagated[idx] = best

    def _build_result(
        self,
        chunks: List[IngestionChunk],
        context_specs: Dict[str, Tuple[str, TaskType, str, bool]],
        chunk_dataset_map: Dict[int, str],
        chunk_propagated_ctx: Dict[int, str],
    ) -> ContextExtractionResult:
        """Pass 3: build registry, assign contexts, produce final result."""
        registry = ContextRegistry()

        for ctx_id, (dataset_name, task, metric_name, higher) in context_specs.items():
            ctx = ExperimentalContext(
                context_id=ctx_id,
                task=task,
                dataset=dataset_name,
                metric=MetricDefinition(
                    name=metric_name,
                    higher_is_better=higher,
                ),
                evaluation_protocol=EvaluationProtocol(split_type="test"),
            )
            registry.register(ctx)

        unknown_ctx = ExperimentalContext(
            context_id="ctx_unknown",
            task=TaskType.OTHER,
            dataset="unknown",
            metric=MetricDefinition(name="unknown", higher_is_better=True),
            evaluation_protocol=EvaluationProtocol(split_type="unknown"),
        )
        registry.register(unknown_ctx)

        updated_chunks: List[IngestionChunk] = []
        unknown_count = 0
        for i, chunk in enumerate(chunks):
            ctx_id = self._resolve_context(
                i, chunk, chunk_dataset_map, chunk_propagated_ctx, registry
            )
            if ctx_id == "ctx_unknown":
                unknown_count += 1
            updated_chunks.append(
                IngestionChunk(
                    chunk_id=chunk.chunk_id,
                    source_id=chunk.source_id,
                    page=chunk.page,
                    text=chunk.text,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    text_hash=chunk.text_hash,
                    context_id=ctx_id,
                    numeric_strings=chunk.numeric_strings,
                    unit_strings=chunk.unit_strings,
                    metric_names=chunk.metric_names,
                )
            )

        real_contexts = sum(
            1 for ctx_id in registry.contexts if ctx_id != "ctx_unknown"
        )

        return ContextExtractionResult(
            registry=registry,
            chunks=updated_chunks,
            contexts_created=real_contexts,
            unknown_chunks=unknown_count,
        )

    def _find_nearest_anchor(
        self, chunk_idx: int, anchors: List[Tuple[int, str]]
    ) -> Optional[str]:
        """Find the nearest anchor above a chunk, or the only anchor on the page."""
        if not anchors:
            return None

        # Find nearest anchor above (most recent anchor with index < chunk_idx)
        best = None
        for anchor_idx, ctx_id in anchors:
            if anchor_idx < chunk_idx:
                best = ctx_id
            elif anchor_idx > chunk_idx and best is None:
                # No anchor above — use the first anchor below as fallback
                best = ctx_id
                break

        # If only one anchor on page, always use it
        if best is None and len(anchors) == 1:
            best = anchors[0][1]

        return best

    def _resolve_context(
        self,
        idx: int,
        chunk: IngestionChunk,
        direct_map: Dict[int, str],
        propagated_map: Dict[int, str],
        registry: ContextRegistry,
    ) -> str:
        """Resolve final context_id for a chunk."""
        # Priority 1: direct dataset mention
        if idx in direct_map:
            return direct_map[idx]

        # Priority 2: page-scoped propagation
        if idx in propagated_map:
            return propagated_map[idx]

        # Priority 3: metric-only context from ingestion
        if (
            chunk.context_id != "ctx_unknown"
            and chunk.context_id.startswith("ctx_metric_")
        ):
            ctx_id = chunk.context_id
            if ctx_id not in registry.contexts:
                metric_name_raw = ctx_id.replace("ctx_metric_", "").replace("_", "-")
                higher = _METRIC_DIRECTION.get(metric_name_raw, True)
                metric_ctx = ExperimentalContext(
                    context_id=ctx_id,
                    task=TaskType.OTHER,
                    dataset="unknown",
                    metric=MetricDefinition(
                        name=metric_name_raw,
                        higher_is_better=higher,
                    ),
                    evaluation_protocol=EvaluationProtocol(split_type="unknown"),
                )
                registry.register(metric_ctx)
            return ctx_id

        return "ctx_unknown"
