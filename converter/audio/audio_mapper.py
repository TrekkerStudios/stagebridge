from pathlib import Path
from typing import Dict, Optional
import wave
import struct


class AudioFileMapper:
    """Maps Pro Tools bounced files to Ableton track names"""
    
    # Mapping from Ableton track names to Pro Tools file patterns
    TRACK_MAPPINGS = {
        "VOX LIVE": ["GUITAR 1 LIVETRACKS", "VOX LIVETRACKS"],  # Try both patterns
        "VOX BT": ["TEMP VOX BACKTRACKS", "VOX BACKTRACKS"],
        "GTR 1": ["GUITAR 1 LIVETRACKS"],
        "GTR 2": ["GUITAR 2 LIVETRACKS"],
        "GTR BT": ["GUITAR BACKTRACKS"],
        "BASS": ["BASS TRACKS"],
        "INST BT": ["INSTRUMENT BACKTRACKS"],
        "SLATE": ["SLATE"]
    }
    
    def __init__(self, session_folder: Path):
        self.session_folder = session_folder
        self.bounced_files_folder = session_folder / "Bounced Files"
        self.audio_files = {}
        self.audio_durations = {}
        self._scan_audio_files()
    
    def _scan_audio_files(self):
        """Scan the Bounced Files folder for audio files"""
        if not self.bounced_files_folder.exists():
            print(f"Warning: Bounced Files folder not found: {self.bounced_files_folder}")
            return
        
        # Get all .wav files (ignore .asd files)
        wav_files = list(self.bounced_files_folder.glob("*.wav"))
        
        print(f"Found {len(wav_files)} audio files in {self.bounced_files_folder}")
        
        # Map files to tracks
        for track_name, patterns in self.TRACK_MAPPINGS.items():
            found_file = None
            
            for pattern in patterns:
                # Look for files containing the pattern
                for wav_file in wav_files:
                    if pattern.upper() in wav_file.name.upper():
                        found_file = wav_file
                        break
                
                if found_file:
                    break
            
            if found_file:
                self.audio_files[track_name] = found_file
                # Get audio duration
                duration = self._get_audio_duration(found_file)
                self.audio_durations[track_name] = duration
                print(f"Mapped '{track_name}' -> '{found_file.name}' (duration: {duration:.3f}s)")
            else:
                print(f"Warning: No audio file found for track '{track_name}'")
    
    def _get_audio_duration(self, audio_file: Path) -> float:
        """Get the duration of an audio file in seconds"""
        try:
            with wave.open(str(audio_file), 'rb') as wav_file:
                frames = wav_file.getnframes()
                sample_rate = wav_file.getframerate()
                duration = frames / float(sample_rate)
                return duration
        except Exception as e:
            print(f"Warning: Could not get duration for {audio_file.name}: {e}")
            return 0.0
    
    def get_audio_file(self, track_name: str) -> Optional[Path]:
        """Get the audio file for a given track name"""
        return self.audio_files.get(track_name)
    
    def get_audio_duration(self, track_name: str) -> float:
        """Get the duration of an audio file for a given track name"""
        return self.audio_durations.get(track_name, 0.0)
    
    def get_all_audio_files(self) -> Dict[str, Path]:
        """Get all mapped audio files"""
        return self.audio_files.copy()