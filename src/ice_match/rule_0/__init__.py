"""Rule 0: Position Decomposition Analyzer.

A standalone tool for breaking down complex products into base components
and analyzing positions across trader and exchange data.
"""

from src.ice_match.rule_0.display import PositionDisplay
from src.ice_match.rule_0.matrix_comparator import MatrixComparator
from src.ice_match.rule_0.position_matrix import PositionMatrix
from src.ice_match.rule_0.product_decomposer import ProductDecomposer

__all__ = [
    "MatrixComparator",
    "PositionDisplay",
    "PositionMatrix",
    "ProductDecomposer",
]