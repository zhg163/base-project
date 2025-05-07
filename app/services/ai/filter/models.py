from typing import Optional
from dataclasses import dataclass

@dataclass
class FilterDecision:
    """过滤决策结果"""
    action: str  # "pass", "warn", "block"
    reason: Optional[str] = None 