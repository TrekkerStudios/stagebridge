class TimeSignatureChange:
    """Represents a time signature change"""
    
    def __init__(self, beat_position: float, numerator: int, denominator: int):
        self.beat_position = beat_position
        self.numerator = numerator
        self.denominator = denominator
        self.ableton_value = self._calculate_ableton_value()
    
    def _calculate_ableton_value(self) -> int:
        """Calculate Ableton's internal time signature value"""
        time_sig_map = {
            (4, 4): 201,
            (3, 4): 200,
            (2, 4): 199,
            (4, 8): 205,
            (3, 8): 204,
            (6, 8): 207,
            (7, 8): 208,
            (9, 8): 210,
            (12, 8): 213,
        }
        
        key = (self.numerator, self.denominator)
        if key in time_sig_map:
            return time_sig_map[key]
        else:
            # Fallback calculation for uncommon time signatures
            return (self.numerator - 1) * 100 + self.denominator + 97
    
    def __repr__(self):
        return f"TimeSignatureChange({self.numerator}/{self.denominator} @ beat {self.beat_position})"