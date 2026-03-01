"""Weak claim tier validation and classification.

Validates and marks claims as strong (explicit context) or weak (inferred context).
"""

import re
from enum import Enum
from typing import Tuple, Optional


class ClaimTier(str, Enum):
    """Hierarchical claim acceptance tiers."""
    STRONG = "strong"      # Explicit dataset + metric context
    WEAK = "weak"          # Inferred context (quantitative delta + property)
    REJECTED = "rejected"  # Does not meet criteria


class WeakClaimValidator:
    """Validates and extracts weak-tier claims.
    
    Weak claims accept quantitative deltas without explicit dataset names.
    Examples:
    - "Latency improved by 34%"
    - "Error reduced from 0.54 to 0.31"
    - "2.3x improvement over baseline"
    - "Accuracy increase (p < 0.01)"
    
    Key constraint: Must be quantitative (data-backed), not hedged.
    """
    
    # Measurable property patterns (regex)
    METRICS_PATTERN = r'\b(accuracy|precision|recall|f1|f-1|bleu|rouge|loss|error|latency|throughput|memory|energy|cost|time|speed|efficiency|benchmark|score|rate|percentage|percent|yield|torque|force|strength|pressure|temperature|conductivity|resistance|velocity|density|wavelength|frequency|power|voltage|current|impedance|gain|decibel|db|snr|psnr|quality|reliability|availability|bandwidth|delay|qos|sla|slo|cpu|gpu|tpu|flops|operations|instruction|cycle|cache|tps|qps|ops|iops|p50|p99|p99\.9|percentile|min|max|avg|mean|median|std|stddev|sigma|variance|entropy|kl|divergence|wasserstein|cosine|similarity|distance|correlation|coefficient|likelihood|probability|confidence|credibility|evidence|certainty|weight|count|size|dimension|ratio|multiple|fold|factor|increase|decrease|improvement|degradation|gain|loss|reduction|growth|decline|regression|progression|advancement|enhancement|boost|surge|spike|drop|crash|failure|success|efficiency|effectiveness|margin|difference|delta|shift|change|variation|range|spread|distribution|histogram|quantile|bin|bucket|gradient|derivation|integral|slope|curvature|amplitude|frequency|phase|modulation|noise|signal|resolution|pixel|frame|fps|hz|baud|bits|bytes|kb|mb|gb|tb|pb)\b'
    
    # Quantitative delta patterns (regex)
    DELTA_PATTERNS = [
        r'(?:increased|improved|enhanced|boosted|accelerated|reduced|decreased|lowered|minimized|optimized|expanded|growing|climbing|rising)\s+(?:by|at|of)?\s*(\d+\.?\d*)\s*(?:%|percent|times|x|fold)',
        r'(?:from|between)\s+(\d+\.?\d*)\s+(?:to|and)\s+(\d+\.?\d*)',
        r'(\d+\.?\d*)\s*(?:x|times|fold)\s+(?:improvement|better|faster|slower|larger|smaller)',
        r'(?:baseline|baseline).*?(\d+\.?\d*)\s*(?:%|percent)',
        r'(?:p\s*[<>]|p-value)\s*(?:[<>=]+)?\s*(\d+\.?\d*)',
    ]
    
    # Hedging patterns that disqualify (regex)
    HEDGE_PATTERNS = [
        r'\b(?:may|might|could|should|appears|suggests|indicates|hypothesized|theoretical|estimated|approximate|roughly|approximately|about|around|perhaps|allegedly|purportedly|ostensibly|seemingly|arguably)\b',
    ]
    
    # Compound patterns that disqualify (regex)
    COMPOUND_PATTERNS = [
        r'(?:dataset|metric|dataset)\s+(?:a|1)\s+(?:and|or)\s+(?:dataset|metric|dataset)\s+(?:b|2)',
        r'(?:or|and)\s+(?:dataset|metric)\s+(?:[a-z0-9]+)',
    ]
    
    @classmethod
    def is_quantitative_delta(cls, text: str) -> bool:
        """Check if text contains quantitative delta pattern."""
        text_lower = text.lower()
        for pattern in cls.DELTA_PATTERNS:
            if re.search(pattern, text_lower):
                return True
        return False
    
    @classmethod
    def has_measurable_property(cls, text: str) -> bool:
        """Check if text mentions a measurable metric/property."""
        text_lower = text.lower()
        # Check for p-value pattern separately (more robust)
        if re.search(r'\bp\s*[<>=]', text_lower) or 'p-value' in text_lower:
            return True
        # Check for other metrics
        return bool(re.search(cls.METRICS_PATTERN, text_lower))
    
    @classmethod
    def is_hedged(cls, text: str) -> bool:
        """Check if text contains hedging language."""
        for pattern in cls.HEDGE_PATTERNS:
            if re.search(pattern, text.lower()):
                return True
        return False
    
    @classmethod
    def is_compound(cls, text: str) -> bool:
        """Check if text contains compound measurement (multiple datasets/metrics)."""
        for pattern in cls.COMPOUND_PATTERNS:
            if re.search(pattern, text.lower()):
                return True
        return False
    
    @classmethod
    def validate(cls, text: str) -> Tuple[bool, Optional[str]]:
        """Validate if text can be accepted as weak claim.
        
        Returns:
            (is_valid, rejection_reason)
        """
        
        if cls.is_hedged(text):
            return False, "HEDGED_STATEMENT"
        
        if cls.is_compound(text):
            return False, "COMPOUND_METRIC"
        
        if not cls.is_quantitative_delta(text):
            return False, "NOT_QUANTITATIVE_DELTA"
        
        if not cls.has_measurable_property(text):
            return False, "NO_MEASURABLE_PROPERTY"
        
        return True, None
    
    @classmethod
    def extract_quantitative_value(cls, text: str) -> Optional[float]:
        """Try to extract primary numeric value from text."""
        matches = re.findall(r'(\d+\.?\d*)', text)
        if matches:
            try:
                # Return largest numeric value found
                return max(float(m) for m in matches)
            except ValueError:
                pass
        return None


if __name__ == "__main__":
    # Self-test
    test_cases = [
        ("Latency improved by 34%", True, "weak delta + metric"),
        ("Error reduced from 0.54 to 0.31", True, "absolute change + metric"),
        ("2.3x improvement over baseline", True, "multiplication factor"),
        ("Accuracy may increase", False, "hedged"),
        ("Accuracy on Dataset A or Dataset B", False, "compound"),
        ("The model is good", False, "not quantitative"),
        ("Throughput increased by 15%", True, "weak delta"),
        ("p < 0.01", True, "statistical significance"),
    ]
    
    print("WeakClaimValidator Self-Test:\n")
    for text, expected, description in test_cases:
        valid, reason = WeakClaimValidator.validate(text)
        status = "✓" if valid == expected else "✗"
        print(f"{status} '{text}'")
        print(f"  {description} → {valid} {f'({reason})' if reason else ''}\n")
