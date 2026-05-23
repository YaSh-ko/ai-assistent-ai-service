import re
from typing import Any, Dict, List

class PIIService:
    """
    Service for sanitizing Personally Identifiable Information (PII) from text and data structures.
    Uses regex-based heuristics to replace names, emails, and phone numbers.
    """
    
    # Regex patterns for PII
    EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    PHONE_PATTERN = r'\b(?:\+?(\d{1,3}))?[-. (]*(\d{3})[-. )]*(\d{3})[-. ]*(\d{4})\b'
    # Simple name pattern (capitalized words, simplistic) - use with caution or NLP in production
    # For now, we'll focus on emails and phones as they are most critical and easier to regex
    
    def anonymize_text(self, text: str) -> str:
        """
        Anonymize PII in the given text.
        """
        if not text:
            return text
            
        # Replace emails
        text = re.sub(self.EMAIL_PATTERN, '[EMAIL]', text)
        
        # Replace phones
        text = re.sub(self.PHONE_PATTERN, '[PHONE]', text)
        
        return text

    def anonymize_structure(self, data: Dict | List | str) -> Dict | List | str:
        """
        Recursively anonymize PII in a data structure (dict, list, or string).
        """
        if isinstance(data, str):
            return self.anonymize_text(data)
        elif isinstance(data, dict):
            return {k: self.anonymize_structure(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.anonymize_structure(item) for item in data]
        else:
            return data
