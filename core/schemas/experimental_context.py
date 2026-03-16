"""
Experimental Context Schema.

Defines the first-class representation of an experimental world that determines
claim comparability.

This is the missing primitive that enables:
- Accurate contradiction detection
- Confidence calibration with physics
- Unit normalization with semantic anchors
- Consensus analysis over shared contexts

Without ExperimentalContext, claims are just statements.
With it, claims become observations within defined experimental worlds.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class TaskType(str, Enum):
    """Canonical task types in ML/AI research."""
    
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    SEQUENCE_LABELING = "sequence_labeling"
    GENERATION = "generation"
    QUESTION_ANSWERING = "question_answering"
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"
    INFORMATION_EXTRACTION = "information_extraction"
    REASONING = "reasoning"
    OTHER = "other"


class MetricDefinition(BaseModel):
    """
    Formal definition of an evaluation metric.
    
    Two claims are only comparable if they use the same metric definition,
    not just the same metric name.
    """
    
    name: str = Field(..., description="Canonical metric name (e.g., 'accuracy', 'F1', 'BLEU')", min_length=1)
    unit: Optional[str] = Field(None, description="Unit of measurement (e.g., '%', 'seconds', 'GB')")
    higher_is_better: bool = Field(..., description="Whether higher values indicate better performance")
    range_min: Optional[float] = Field(None, description="Minimum possible value")
    range_max: Optional[float] = Field(None, description="Maximum possible value")
    aggregation_method: Optional[str] = Field(
        None,
        description="How metric is aggregated (e.g., 'macro', 'micro', 'weighted')"
    )
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure metric name is non-empty."""
        if len(v.strip()) == 0:
            raise ValueError("Metric name must be non-empty")
        return v.strip().lower()
    
    def is_compatible_with(self, other: "MetricDefinition") -> bool:
        """
        Check if two metric definitions are compatible for comparison.
        
        Metrics are compatible if they measure the same thing in the same way.
        """
        return (
            self.name == other.name
            and self.unit == other.unit
            and self.higher_is_better == other.higher_is_better
            and self.aggregation_method == other.aggregation_method
        )


class EvaluationProtocol(BaseModel):
    """
    Defines how an experiment was evaluated.
    
    Critical for determining if two results are comparable.
    """
    
    split_type: str = Field(
        ...,
        description="Type of data split (e.g., 'train/test', 'k-fold', 'leave-one-out')",
        min_length=1
    )
    test_set_size: Optional[int] = Field(None, ge=1, description="Number of test examples")
    cross_validation_folds: Optional[int] = Field(None, ge=2, description="Number of CV folds if applicable")
    random_seed: Optional[int] = Field(None, description="Random seed for reproducibility")
    evaluation_runs: int = Field(1, ge=1, description="Number of evaluation runs")
    
    @field_validator("split_type")
    @classmethod
    def validate_split_type(cls, v: str) -> str:
        """Normalize split type."""
        return v.strip().lower()


class ExperimentalContext(BaseModel):
    """
    First-class representation of an experimental world.
    
    This schema answers the question: "Under what conditions was this claim observed?"
    
    Two claims can only contradict if they share the same experimental context.
    Confidence can only be calibrated by counting independent contexts.
    Consensus can only be built within shared contexts.
    
    This is the missing primitive that enables epistemic rigor.
    
    Attributes:
        context_id: Unique identifier for this experimental context
        task: What task is being performed
        dataset: Which dataset is used
        dataset_version: Version or split of the dataset
        metric: How performance is measured
        model_class: Category of model (e.g., 'transformer', 'CNN', 'ensemble')
        training_regime: How the model was trained
        evaluation_protocol: How evaluation was conducted
        domain: Scientific domain or field
        additional_constraints: Any other constraints that affect comparability
    """
    
    context_id: str = Field(..., description="Unique identifier for this context", min_length=1)
    
    # Core experimental identity
    task: TaskType = Field(..., description="Task being performed")
    dataset: str = Field(..., description="Dataset name", min_length=1)
    dataset_version: Optional[str] = Field(None, description="Dataset version or split (e.g., 'v2', 'test')")
    
    # Measurement definition
    metric: MetricDefinition = Field(..., description="How performance is measured")
    
    # Model constraints
    model_class: Optional[str] = Field(
        None,
        description="Category of model (e.g., 'transformer', 'CNN', 'RNN', 'ensemble')"
    )
    
    # Experimental setup
    training_regime: Optional[str] = Field(
        None,
        description="Training approach (e.g., 'supervised', 'few-shot', 'zero-shot', 'fine-tuned')"
    )
    evaluation_protocol: EvaluationProtocol = Field(..., description="Evaluation methodology")
    
    # Broader context
    domain: Optional[str] = Field(None, description="Scientific domain (e.g., 'NLP', 'Computer Vision')")
    
    # Extensibility
    additional_constraints: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional constraints that affect comparability"
    )
    
    @field_validator("context_id", "dataset")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        """Ensure required strings are non-empty."""
        if len(v.strip()) == 0:
            raise ValueError("Required string fields must be non-empty")
        return v
    
    def is_comparable_to(self, other: "ExperimentalContext") -> bool:
        """
        Determine if two experimental contexts are comparable.
        
        Contexts are comparable if they represent the same experimental world:
        - Same task
        - Same dataset (and version)
        - Same metric definition
        - Compatible evaluation protocol
        
        Returns:
            True if claims from these contexts can be compared
        """
        # Must be same task
        if self.task != other.task:
            return False
        
        # Must be same dataset
        if self.dataset.lower() != other.dataset.lower():
            return False
        
        # If versions specified, must match
        if self.dataset_version and other.dataset_version:
            if self.dataset_version.lower() != other.dataset_version.lower():
                return False
        
        # Metrics must be compatible
        if not self.metric.is_compatible_with(other.metric):
            return False
        
        # Evaluation protocol should be similar
        # (This is a softer constraint - log warning but allow comparison)
        if self.evaluation_protocol.split_type != other.evaluation_protocol.split_type:
            # Could be compared but with caveats
            pass
        
        return True
    
    def get_identity_key(self) -> str:
        """
        Generate a canonical identity key for this context.
        
        Used for grouping claims by comparable contexts.
        """
        parts = [
            self.task.value,
            self.dataset.lower(),
            self.dataset_version.lower() if self.dataset_version else "default",
            self.metric.name,
            self.metric.unit or "dimensionless",
        ]
        return ":".join(parts)


class ContextRegistry(BaseModel):
    """
    Registry of experimental contexts.
    
    Maintains the set of known experimental worlds and provides
    lookup and comparison services.
    """
    
    contexts: Dict[str, ExperimentalContext] = Field(
        default_factory=dict,
        description="Map of context_id to ExperimentalContext"
    )
    
    def register(self, context: ExperimentalContext) -> None:
        """Register a new experimental context."""
        if context.context_id in self.contexts:
            raise ValueError(f"Context {context.context_id} already registered")
        self.contexts[context.context_id] = context
    
    def get(self, context_id: str) -> Optional[ExperimentalContext]:
        """Retrieve a context by ID."""
        return self.contexts.get(context_id)
    
    def find_comparable_contexts(self, context_id: str) -> List[str]:
        """
        Find all contexts comparable to the given context.
        
        Returns list of context IDs that represent the same experimental world.
        """
        target = self.contexts.get(context_id)
        if not target:
            return []
        
        comparable = []
        for cid, ctx in self.contexts.items():
            if cid != context_id and target.is_comparable_to(ctx):
                comparable.append(cid)
        
        return comparable
    
    def group_by_comparability(self) -> Dict[str, List[str]]:
        """
        Group all contexts into equivalence classes.
        
        Returns a dict mapping identity keys to lists of context IDs.
        """
        groups: Dict[str, List[str]] = {}
        
        for context_id, context in self.contexts.items():
            key = context.get_identity_key()
            if key not in groups:
                groups[key] = []
            groups[key].append(context_id)
        
        return groups
