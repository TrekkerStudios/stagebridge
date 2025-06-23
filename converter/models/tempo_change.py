class TempoChange:
    """Represents a tempo change"""
    
    def __init__(self, beat_position: float, tempo: float):
        self.beat_position = beat_position
        self.tempo = tempo
    
    def __repr__(self):
        return f"TempoChange({self.tempo} BPM @ beat {self.beat_position})"