from typing import Optional


class Marker:
    """Represents a marker from Pro Tools session"""
    
    def __init__(self, location: str, time_reference: str, name: str, tempo: Optional[float] = None):
        self.location = location
        self.time_reference = time_reference
        self.name = name
        self.tempo = tempo
        self.beat_position = self._parse_time_reference(time_reference)
    
    def _parse_time_reference(self, time_reference: str) -> float:
        """Convert Pro Tools time reference (e.g., '3|1', '34|3') to beat position"""
        try:
            if '|' in time_reference:
                bar, beat = time_reference.split('|')
                # Convert to 0-based beat position (bar-1)*4 + (beat-1)
                return (int(bar) - 1) * 4 + (int(beat) - 1)
            else:
                # If it's just a number, treat it as already a beat position
                return float(time_reference)
        except (ValueError, IndexError):
            print(f"Warning: Could not parse time reference '{time_reference}', using 0")
            return 0.0
    
    def __repr__(self):
        return f"Marker('{self.name}' @ {self.time_reference} -> beat {self.beat_position}, tempo={self.tempo})"