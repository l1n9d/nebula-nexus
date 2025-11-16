"""Query preprocessing utilities for improving search quality.

This module provides query enhancement through:
- Conference/venue name normalization and expansion
- Temporal query handling
- Common abbreviation expansion
"""

import re
from datetime import datetime
from typing import Dict, List, Tuple


class QueryPreprocessor:
    """Preprocesses queries to improve search quality."""

    # Major CS conference mappings (name -> aliases)
    CONFERENCE_ALIASES: Dict[str, List[str]] = {
        "NeurIPS": ["NIPS", "Neural Information Processing Systems"],
        "ICML": ["International Conference on Machine Learning"],
        "ICLR": ["International Conference on Learning Representations"],
        "CVPR": ["Conference on Computer Vision and Pattern Recognition"],
        "ICCV": ["International Conference on Computer Vision"],
        "ECCV": ["European Conference on Computer Vision"],
        "ACL": ["Association for Computational Linguistics"],
        "EMNLP": ["Empirical Methods in Natural Language Processing"],
        "NAACL": ["North American Chapter of the ACL"],
        "AAAI": ["Association for the Advancement of Artificial Intelligence"],
        "IJCAI": ["International Joint Conference on Artificial Intelligence"],
        "KDD": ["Knowledge Discovery and Data Mining"],
        "WWW": ["World Wide Web Conference", "TheWebConf"],
        "SIGIR": ["Special Interest Group on Information Retrieval"],
        "ICRA": ["International Conference on Robotics and Automation"],
        "IROS": ["Intelligent Robots and Systems"],
        "RSS": ["Robotics: Science and Systems"],
    }

    # Common CS abbreviations
    ABBREVIATION_EXPANSIONS: Dict[str, str] = {
        "ML": "machine learning",
        "DL": "deep learning",
        "NLP": "natural language processing",
        "CV": "computer vision",
        "RL": "reinforcement learning",
        "GAN": "generative adversarial network",
        "CNN": "convolutional neural network",
        "RNN": "recurrent neural network",
        "LSTM": "long short-term memory",
        "GPT": "generative pre-trained transformer",
        "BERT": "bidirectional encoder representations from transformers",
    }

    def __init__(self):
        """Initialize the query preprocessor."""
        self.current_year = datetime.now().year

    def preprocess(self, query: str) -> str:
        """Apply all preprocessing steps to a query.

        Args:
            query: Raw user query

        Returns:
            Preprocessed query string
        """
        # Step 1: Normalize whitespace
        query = self._normalize_whitespace(query)

        # Step 2: Expand conference aliases
        query = self._expand_conference_names(query)

        # Step 3: Handle temporal queries
        query = self._handle_temporal_queries(query)

        # Step 4: Optionally expand common abbreviations (commented by default to avoid over-expansion)
        # query = self._expand_abbreviations(query)

        return query.strip()

    def _normalize_whitespace(self, query: str) -> str:
        """Normalize whitespace in query."""
        return re.sub(r"\s+", " ", query).strip()

    def _expand_conference_names(self, query: str) -> str:
        """Expand conference names to include aliases.

        Example: "NeurIPS" -> "(NeurIPS OR NIPS OR Neural Information Processing Systems)"
        """
        for primary_name, aliases in self.CONFERENCE_ALIASES.items():
            all_names = [primary_name] + aliases

            # Check if any variant appears in the query (case-insensitive)
            for name in all_names:
                # Use word boundaries to avoid partial matches
                pattern = rf"\b{re.escape(name)}\b"
                if re.search(pattern, query, re.IGNORECASE):
                    # Replace with expanded OR clause
                    or_clause = " OR ".join(f'"{n}"' for n in all_names)
                    expanded = f"({or_clause})"

                    # Replace the matched name with expanded clause
                    query = re.sub(pattern, expanded, query, flags=re.IGNORECASE, count=1)
                    break  # Only expand once per conference

        return query

    def _handle_temporal_queries(self, query: str) -> str:
        """Handle temporal queries like 'recent', 'latest', specific years.

        Note: For 'recent' and 'latest', we remove them and rely on date sorting.
        For specific years, we keep them for BM25 matching.
        """
        # Remove temporal adjectives (rely on sorting instead)
        temporal_patterns = [
            (r"\b(recent|latest|newest|current)\s+(papers?|work|research|studies?)\b", ""),
            (r"\b(recent|latest|newest|current)\b", ""),
        ]

        for pattern, replacement in temporal_patterns:
            query = re.sub(pattern, replacement, query, flags=re.IGNORECASE)

        # Keep specific years for BM25 matching (e.g., "2024 papers" stays as is)
        # No action needed - years are already good for BM25

        return query

    def _expand_abbreviations(self, query: str) -> str:
        """Expand common CS abbreviations.

        Note: This is aggressive and can change query intent.
        Use carefully and only for specific abbreviations.
        """
        for abbrev, expansion in self.ABBREVIATION_EXPANSIONS.items():
            # Only expand if it's a standalone word (not part of another word)
            pattern = rf"\b{re.escape(abbrev)}\b"
            if re.search(pattern, query):
                # Create OR clause: "ML" -> "(ML OR machine learning)"
                expanded = f'({abbrev} OR "{expansion}")'
                query = re.sub(pattern, expanded, query, count=1)

        return query

    def analyze_query_type(self, query: str) -> Dict[str, bool]:
        """Analyze query type for potential weight adjustments.

        Returns:
            Dictionary with query characteristics
        """
        query_lower = query.lower()

        return {
            "has_conference": any(
                re.search(rf"\b{re.escape(name)}\b", query, re.IGNORECASE)
                for names in self.CONFERENCE_ALIASES.values()
                for name in names
            ),
            "has_year": bool(re.search(r"\b(19|20)\d{2}\b", query)),
            "is_temporal": bool(re.search(r"\b(recent|latest|newest|current|new)\b", query_lower)),
            "is_comparison": bool(
                re.search(r"\b(vs|versus|compared? to|difference between|compare)\b", query_lower)
            ),
            "is_implementation": bool(
                re.search(r"\b(how to|implement|code for|tutorial|example)\b", query_lower)
            ),
        }


# Global preprocessor instance
_preprocessor = QueryPreprocessor()


def preprocess_query(query: str) -> str:
    """Convenience function to preprocess a query.

    Args:
        query: Raw user query

    Returns:
        Preprocessed query string
    """
    return _preprocessor.preprocess(query)


def analyze_query(query: str) -> Dict[str, bool]:
    """Convenience function to analyze query type.

    Args:
        query: User query

    Returns:
        Dictionary with query characteristics
    """
    return _preprocessor.analyze_query_type(query)

