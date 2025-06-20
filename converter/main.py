#!/usr/bin/env python3
"""
Pro Tools to Ableton Live Marker Converter

Extracts markers from Pro Tools session text files and converts them to 
MIDI clips in Ableton Live .als project files. Also handles tempo and time signature changes.
Now also creates OSC clips for external control.
"""

import gzip
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import argparse
import copy


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


class TempoChange:
    """Represents a tempo change"""
    
    def __init__(self, beat_position: float, tempo: float):
        self.beat_position = beat_position
        self.tempo = tempo
    
    def __repr__(self):
        return f"TempoChange({self.tempo} BPM @ beat {self.beat_position})"


class TimeSignatureChange:
    """Represents a time signature change"""
    
    def __init__(self, beat_position: float, numerator: int, denominator: int):
        self.beat_position = beat_position
        self.numerator = numerator
        self.denominator = denominator
        self.ableton_value = self._calculate_ableton_value()
    
    def _calculate_ableton_value(self) -> int:
        """Calculate Ableton's internal time signature value"""
        # Ableton uses specific values for time signatures:
        # 4/4 = 201, 3/4 = 200, 2/4 = 199, etc.
        # Formula appears to be: (numerator - 1) * 100 + denominator + 97
        # But let's use known mappings for common time signatures
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


class ProToolsSessionParser:
    """Parses Pro Tools session text files"""
    
    def __init__(self, session_file: Path):
        self.session_file = session_file
        self.markers: List[Marker] = []
        self.tempo_changes: List[TempoChange] = []
        self.time_signature_changes: List[TimeSignatureChange] = []
        self.session_end_beat: Optional[float] = None
        self.song_name: Optional[str] = None
    
    def parse(self) -> Tuple[List[Marker], List[TempoChange], List[TimeSignatureChange], Optional[float], Optional[str]]:
        """Parse the Pro Tools session file and extract markers, tempo changes, time signature changes, session end, and song name"""
        with open(self.session_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract song name from session
        self.song_name = self._extract_song_name(content)
        
        # Find markers section
        markers_section = self._extract_markers_section(content)
        if not markers_section:
            raise ValueError("No markers section found in Pro Tools session file")
        
        # Parse markers, tempo changes, time signature changes, and session end
        self.markers, self.tempo_changes, self.time_signature_changes, self.session_end_beat = self._parse_markers_and_changes(markers_section)
        
        return self.markers, self.tempo_changes, self.time_signature_changes, self.session_end_beat, self.song_name
    
    def _extract_song_name(self, content: str) -> Optional[str]:
        """Extract song name from Pro Tools session file"""
        # Look for SESSION NAME line
        session_name_pattern = r'SESSION NAME:\s*(.+)'
        match = re.search(session_name_pattern, content)
        
        if match:
            session_name = match.group(1).strip()
            # Extract song name from session name (remove file extensions and extra info)
            # Pattern like "(.113.) Fat Lip - Sum 41 SD" -> "Fat Lip"
            
            # Try to extract song name from various patterns
            patterns = [
                r'\([^)]*\)\s*(.+?)\s*-\s*(.+?)\s*SD',  # "(.113.) Fat Lip - Sum 41 SD"
                r'\([^)]*\)\s*(.+?)\s*-\s*(.+)',        # "(.113.) Fat Lip - Sum 41"
                r'(.+?)\s*-\s*(.+?)\s*SD',              # "Fat Lip - Sum 41 SD"
                r'(.+?)\s*-\s*(.+)',                    # "Fat Lip - Sum 41"
                r'(.+)',                                # Fallback: entire name
            ]
            
            for pattern in patterns:
                match = re.match(pattern, session_name)
                if match:
                    song_name = match.group(1).strip()
                    print(f"Extracted song name: '{song_name}'")
                    return self._normalize_name(song_name)
            
        print("Warning: Could not extract song name from session file")
        return "unknown_song"
    
    def _normalize_name(self, name: str) -> str:
        """Normalize name to lowercase with underscores"""
        # Remove special characters and replace spaces with underscores
        normalized = re.sub(r'[^\w\s-]', '', name.lower())
        normalized = re.sub(r'[-\s]+', '_', normalized)
        return normalized.strip('_')
    
    def _extract_markers_section(self, content: str) -> str:
        """Extract the markers section from the session file"""
        start_pattern = r'M A R K E R S\s+L I S T I N G'
        start_match = re.search(start_pattern, content)
        
        if not start_match:
            return ""
        
        # Find the end of the markers section (next major section or end of file)
        start_pos = start_match.end()
        
        # Look for next major section header or end of file
        end_patterns = [
            r'\n[A-Z]\s+[A-Z].*L I S T I N G',
            r'\n[A-Z]\s+[A-Z].*I N F O R M A T I O N'
        ]
        
        end_pos = len(content)
        for pattern in end_patterns:
            match = re.search(pattern, content[start_pos:])
            if match:
                end_pos = start_pos + match.start()
                break
        
        return content[start_pos:end_pos]
    
    def _parse_markers_and_changes(self, markers_section: str) -> Tuple[List[Marker], List[TempoChange], List[TimeSignatureChange], Optional[float]]:
        """Parse individual markers, tempo changes, time signature changes, and session end from the markers section"""
        markers = []
        tempo_changes = []
        time_signature_changes = []
        session_end_beat = None
        
        # Split into lines and process each marker line
        lines = markers_section.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#') or 'LOCATION' in line:
                continue
            
            # Parse marker line using tab separation first, then multiple spaces
            parts = line.split('\t') if '\t' in line else re.split(r'\s{2,}', line)
            
            if len(parts) >= 6:  # Need at least 6 parts to get TIME REFERENCE
                try:
                    location = parts[1].strip()
                    time_reference = parts[2].strip()  # This is the TIME REFERENCE column
                    name = parts[4].strip()
                    
                    # Check if this is an END marker
                    if name.upper() == 'END':
                        session_end_beat = self._parse_time_reference_for_changes(time_reference)
                        print(f"Found session END at beat {session_end_beat}")
                        continue
                    
                    # Check if this is a tempo marker
                    if 'Tempo' in name or self._is_tempo_marker(name):
                        tempo_value = self._extract_tempo_from_name(name)
                        if tempo_value:
                            beat_pos = self._parse_time_reference_for_changes(time_reference)
                            
                            # Validate beat position is reasonable (not way beyond the session)
                            if beat_pos < 10000:  # Reasonable upper limit for beat position
                                tempo_changes.append(TempoChange(beat_pos, tempo_value))
                                print(f"Parsed tempo change: {tempo_value} BPM @ beat {beat_pos}")
                            else:
                                print(f"Warning: Tempo change at beat {beat_pos} is beyond reasonable range, skipping")
                        continue
                    
                    # Check if this is a time signature marker
                    time_sig = self._extract_time_signature_from_name(name)
                    if time_sig:
                        beat_pos = self._parse_time_reference_for_changes(time_reference)
                        
                        # Validate beat position is reasonable
                        if beat_pos < 10000:  # Reasonable upper limit for beat position
                            numerator, denominator = time_sig
                            time_signature_changes.append(TimeSignatureChange(beat_pos, numerator, denominator))
                            print(f"Parsed time signature change: {numerator}/{denominator} @ beat {beat_pos}")
                        else:
                            print(f"Warning: Time signature change at beat {beat_pos} is beyond reasonable range, skipping")
                        continue
                    
                    # Skip numeric-only names
                    if (name.replace('.', '').replace('-', '').isdigit() or
                        len(name.replace('.', '').replace('-', '')) == 0):
                        continue
                    
                    # Clean up marker name
                    name = self._clean_marker_name(name)
                    
                    if name and time_reference:
                        beat_pos = self._parse_time_reference_for_changes(time_reference)
                        
                        # Validate marker beat position is reasonable
                        if beat_pos < 10000:  # Reasonable upper limit
                            marker = Marker(location, time_reference, name)
                            markers.append(marker)
                            print(f"Parsed marker: {marker}")
                        else:
                            print(f"Warning: Marker '{name}' at beat {beat_pos} is beyond reasonable range, skipping")
                
                except (IndexError, ValueError) as e:
                    print(f"Warning: Could not parse marker line: {line} ({e})")
                    continue
        
        # Sort by beat position
        markers = sorted(markers, key=lambda m: m.beat_position)
        tempo_changes = sorted(tempo_changes, key=lambda t: t.beat_position)
        time_signature_changes = sorted(time_signature_changes, key=lambda ts: ts.beat_position)
        
        return markers, tempo_changes, time_signature_changes, session_end_beat
    
    def _is_tempo_marker(self, name: str) -> bool:
        """Check if a marker name indicates a tempo change"""
        try:
            # Clean the name first - remove any trailing backslashes or other non-numeric characters
            cleaned_name = name.rstrip('\\').strip()
            tempo = float(cleaned_name)
            
            # Validate that it's in a reasonable tempo range
            return 30 <= tempo <= 300
            
        except ValueError:
            return False
    
    def _extract_tempo_from_name(self, name: str) -> Optional[float]:
        """Extract tempo value from marker name"""
        try:
            # Clean the name first - remove any trailing backslashes or other non-numeric characters
            cleaned_name = name.rstrip('\\').strip()
            tempo = float(cleaned_name)
            
            # Validate that the tempo is within a reasonable range
            if 30 <= tempo <= 300:  # Reasonable BPM range
                return tempo
            else:
                print(f"Warning: Tempo {tempo} is outside reasonable range (30-300 BPM), skipping")
                return None
                
        except ValueError:
            return None
    
    def _extract_time_signature_from_name(self, name: str) -> Optional[Tuple[int, int]]:
        """Extract time signature from marker name"""
        # Look for patterns like "3/4", "4/4", "Duh 3/4", etc.
        time_sig_patterns = [
            r'(\d+)/(\d+)',  # Direct pattern like "3/4"
            r'(\d+)/(\d+)',  # In context like "Duh 3/4"
        ]
        
        for pattern in time_sig_patterns:
            match = re.search(pattern, name)
            if match:
                numerator = int(match.group(1))
                denominator = int(match.group(2))
                return (numerator, denominator)
        
        return None
    
    def _parse_time_reference_for_changes(self, time_reference: str) -> float:
        """Convert Pro Tools time reference to beat position for tempo/time signature changes"""
        try:
            if '|' in time_reference:
                bar, beat = time_reference.split('|')
                # Convert to 0-based beat position (bar-1)*4 + (beat-1)
                return (int(bar) - 1) * 4 + (int(beat) - 1)
            else:
                return float(time_reference)
        except (ValueError, IndexError):
            return 0.0
    
    def _clean_marker_name(self, name: str) -> str:
        """Clean up marker names"""
        # Remove quotes and extra whitespace
        name = name.strip('"\'').strip()
        
        # Skip empty names or pure numbers
        if not name or name.replace('.', '').replace('-', '').isdigit():
            return ""
        
        return name


class AbletonProjectEditor:
    """Edits Ableton Live .als project files"""
    
    def __init__(self, als_file: Path):
        self.als_file = als_file
        self.tree = None
        self.root = None
        self.template_clip = None
        self.clips_container = None
        self.osc_template_clip = None
        self.osc_clips_container = None
    
    def load(self):
        """Load and parse the .als file"""
        try:
            with gzip.open(self.als_file, 'rt', encoding='utf-8') as f:
                content = f.read()
            
            self.tree = ET.ElementTree(ET.fromstring(content))
            self.root = self.tree.getroot()
            
            # Find and extract template MIDI clip
            self._find_template_clip()
            
            # Find OSC track and template clip
            self._find_osc_template_clip()
            
        except Exception as e:
            raise ValueError(f"Could not load .als file: {e}")
    
    def _find_template_clip(self):
        """Find a template MIDI clip and its container"""
        # Look for any existing MidiClip to use as template
        midi_clips = self.root.findall('.//MidiClip')
        
        if not midi_clips:
            raise ValueError("No MIDI clips found in .als file to use as template")
        
        # Use the first MIDI clip as template
        self.template_clip = midi_clips[0]
        
        # Find the container by searching for the parent that contains this clip
        self.clips_container = self._find_clips_container()
        
        print(f"Using MIDI clip '{self._get_clip_name(self.template_clip)}' as template")
    
    def _find_osc_template_clip(self):
        """Find the OSC track and its template MIDI clip"""
        # Find all MIDI tracks
        midi_tracks = self.root.findall('.//MidiTrack')
        
        osc_track = None
        for track in midi_tracks:
            # Look for track name containing "External +OSC"
            name_elem = track.find('.//Name/EffectiveName')
            if name_elem is not None and 'External +OSC' in name_elem.get('Value', ''):
                osc_track = track
                break
        
        if osc_track is None:
            print("Warning: No 'External +OSC' track found, skipping OSC clip creation")
            return
        
        # Find MIDI clips in this track
        osc_clips = osc_track.findall('.//MidiClip')
        
        if not osc_clips:
            print("Warning: No MIDI clips found in OSC track, skipping OSC clip creation")
            return
        
        # Use the first MIDI clip as template
        self.osc_template_clip = osc_clips[0]
        
        # Find the container for OSC clips
        self.osc_clips_container = self._find_osc_clips_container(osc_track)
        
        print(f"Found OSC track with template clip '{self._get_clip_name(self.osc_template_clip)}'")
    
    def _find_clips_container(self):
        """Find the container that holds MIDI clips"""
        # Search through the XML tree to find the parent of our template clip
        def find_parent(element, target):
            for child in element:
                if child == target:
                    return element
                parent = find_parent(child, target)
                if parent is not None:
                    return parent
            return None
        
        container = find_parent(self.root, self.template_clip)
        if container is None:
            raise ValueError("Could not find container for MIDI clips")
        
        return container
    
    def _find_osc_clips_container(self, osc_track):
        """Find the container that holds OSC MIDI clips"""
        # Look for the ArrangerAutomation/Events container in the OSC track
        events_container = osc_track.find('.//ArrangerAutomation/Events')
        if events_container is None:
            print("Warning: Could not find OSC clips container")
            return None
        
        return events_container
    
    def _get_clip_name(self, clip_element) -> str:
        """Get the name of a MIDI clip"""
        name_elem = clip_element.find('.//Name')
        return name_elem.get('Value', 'Unnamed') if name_elem is not None else 'Unnamed'
    
    def _normalize_name(self, name: str) -> str:
        """Normalize name to lowercase with underscores"""
        # Remove special characters and replace spaces with underscores
        normalized = re.sub(r'[^\w\s-]', '', name.lower())
        normalized = re.sub(r'[-\s]+', '_', normalized)
        return normalized.strip('_')
    
    def _calculate_clip_durations(self, markers: List[Marker], session_end_beat: Optional[float] = None) -> List[Tuple[Marker, float]]:
        """Calculate duration for each clip based on distance to next marker or session end"""
        clips_with_durations = []
        
        for i, marker in enumerate(markers):
            if i < len(markers) - 1:
                # Duration is the distance to the next marker
                next_marker = markers[i + 1]
                duration = next_marker.beat_position - marker.beat_position
            else:
                # For the last marker, calculate duration to session end or use default
                if session_end_beat is not None and session_end_beat > marker.beat_position:
                    duration = session_end_beat - marker.beat_position
                    # Cap the final section at 4 beats maximum
                    duration = min(duration, 4.0)
                else:
                    # Fallback to 4 beats if no session end found
                    duration = 4.0
            
            # Ensure minimum duration of 1 beat
            duration = max(duration, 1.0)
            
            clips_with_durations.append((marker, duration))
            print(f"Clip '{marker.name}': {duration} beats (from beat {marker.beat_position} to {marker.beat_position + duration})")
        
        return clips_with_durations
    
    def create_midi_clips_from_markers(self, markers: List[Marker], session_end_beat: Optional[float] = None):
        """Create MIDI clips from markers"""
        if not self.template_clip or not self.clips_container:
            raise ValueError("No template clip or container available")
        
        # Calculate durations for each clip
        clips_with_durations = self._calculate_clip_durations(markers, session_end_beat)
        
        # Remove existing clips except the template
        clips_to_remove = [clip for clip in self.clips_container.findall('MidiClip') 
                          if clip != self.template_clip]
        for clip in clips_to_remove:
            self.clips_container.remove(clip)
        
        # Create new clips from markers
        for i, (marker, duration) in enumerate(clips_with_durations):
            new_clip = self._create_clip_from_marker(marker, duration, i)
            self.clips_container.append(new_clip)
        
        # Remove the template clip
        self.clips_container.remove(self.template_clip)
        
        print(f"Created {len(markers)} MIDI clips")
    
    def create_osc_clips_from_markers(self, markers: List[Marker], song_name: str, session_end_beat: Optional[float] = None):
        """Create OSC MIDI clips from markers"""
        if not self.osc_template_clip or not self.osc_clips_container:
            print("Warning: No OSC template clip or container available, skipping OSC clip creation")
            return
        
        # Calculate durations for each clip
        clips_with_durations = self._calculate_clip_durations(markers, session_end_beat)
        
        # Remove existing OSC clips except the template
        clips_to_remove = [clip for clip in self.osc_clips_container.findall('MidiClip') 
                          if clip != self.osc_template_clip]
        for clip in clips_to_remove:
            self.osc_clips_container.remove(clip)
        
        # Create new OSC clips from markers
        for i, (marker, duration) in enumerate(clips_with_durations):
            # Create OSC formatted name
            normalized_song = self._normalize_name(song_name)
            normalized_section = self._normalize_name(marker.name)
            osc_name = f"/ableton/{normalized_song}/{normalized_section}"
            
            new_clip = self._create_osc_clip_from_marker(marker, duration, i, osc_name)
            self.osc_clips_container.append(new_clip)
        
        # Remove the OSC template clip
        self.osc_clips_container.remove(self.osc_template_clip)
        
        print(f"Created {len(markers)} OSC MIDI clips")
    
    def apply_tempo_changes(self, tempo_changes: List[TempoChange]):
        """Apply tempo changes to the master track automation"""
        if not tempo_changes:
            print("No tempo changes to apply")
            return
        
        # Find the master track's tempo automation envelope
        tempo_envelope = self._find_or_create_tempo_envelope()
        
        # Clear existing tempo events
        events_container = tempo_envelope.find('.//Events')
        if events_container is not None:
            events_container.clear()
        
        # Create tempo events with proper interpolation prevention
        event_id = 0
        
        # Add initial tempo event at the very beginning
        if tempo_changes[0].beat_position > 0:
            # Use first tempo change value as initial tempo
            initial_event = ET.SubElement(events_container, 'FloatEvent')
            initial_event.set('Id', str(event_id))
            initial_event.set('Time', '-63072000')  # Very beginning of timeline
            initial_event.set('Value', str(tempo_changes[0].tempo))
            event_id += 1
        
        # Add tempo change events
        for i, tempo_change in enumerate(tempo_changes):
            # If this isn't the first tempo change, add a "hold" event just before
            # the new tempo to prevent interpolation
            if i > 0:
                prev_tempo = tempo_changes[i-1].tempo
                hold_time = tempo_change.beat_position - 0.001  # Just before the change
                
                hold_event = ET.SubElement(events_container, 'FloatEvent')
                hold_event.set('Id', str(event_id))
                hold_event.set('Time', str(hold_time))
                hold_event.set('Value', str(prev_tempo))
                event_id += 1
            
            # Add the actual tempo change event
            tempo_event = ET.SubElement(events_container, 'FloatEvent')
            tempo_event.set('Id', str(event_id))
            tempo_event.set('Time', str(tempo_change.beat_position))
            tempo_event.set('Value', str(tempo_change.tempo))
            event_id += 1
            
            print(f"Added tempo change: {tempo_change.tempo} BPM at beat {tempo_change.beat_position}")
        
        print(f"Applied {len(tempo_changes)} tempo changes")
    
    def apply_time_signature_changes(self, time_signature_changes: List[TimeSignatureChange]):
        """Apply time signature changes to the master track automation"""
        if not time_signature_changes:
            print("No time signature changes to apply")
            return
        
        # Find the master track's time signature automation envelope
        time_sig_envelope = self._find_or_create_time_signature_envelope()
        
        # Clear existing time signature events
        events_container = time_sig_envelope.find('.//Events')
        if events_container is not None:
            events_container.clear()
        
        # Create time signature events
        event_id = 0
        
        # Add initial time signature event at the very beginning
        if time_signature_changes[0].beat_position > 0:
            # Use first time signature change value as initial
            initial_event = ET.SubElement(events_container, 'EnumEvent')
            initial_event.set('Id', str(event_id))
            initial_event.set('Time', '-63072000')  # Very beginning of timeline
            initial_event.set('Value', str(time_signature_changes[0].ableton_value))
            event_id += 1
        
        # Add time signature change events
        for i, time_sig_change in enumerate(time_signature_changes):
            # If this isn't the first time signature change, add a "hold" event just before
            # the new time signature to prevent interpolation
            if i > 0:
                prev_time_sig = time_signature_changes[i-1].ableton_value
                hold_time = time_sig_change.beat_position - 0.001  # Just before the change
                
                hold_event = ET.SubElement(events_container, 'EnumEvent')
                hold_event.set('Id', str(event_id))
                hold_event.set('Time', str(hold_time))
                hold_event.set('Value', str(prev_time_sig))
                event_id += 1
            
            # Add the actual time signature change event
            time_sig_event = ET.SubElement(events_container, 'EnumEvent')
            time_sig_event.set('Id', str(event_id))
            time_sig_event.set('Time', str(time_sig_change.beat_position))
            time_sig_event.set('Value', str(time_sig_change.ableton_value))
            event_id += 1
            
            print(f"Added time signature change: {time_sig_change.numerator}/{time_sig_change.denominator} at beat {time_sig_change.beat_position}")
        
        print(f"Applied {len(time_signature_changes)} time signature changes")
    
    def _find_or_create_tempo_envelope(self):
        """Find or create the tempo automation envelope in the master track"""
        # Find master track
        master_track = self.root.find('.//MasterTrack')
        if master_track is None:
            raise ValueError("Could not find master track")
        
        # Find automation envelopes
        envelopes_container = master_track.find('.//AutomationEnvelopes/Envelopes')
        if envelopes_container is None:
            raise ValueError("Could not find automation envelopes container")
        
        # Look for existing tempo envelope (PointeeId="8" based on your example)
        for envelope in envelopes_container.findall('AutomationEnvelope'):
            target = envelope.find('.//EnvelopeTarget/PointeeId')
            if target is not None and target.get('Value') == '8':
                print("Found existing tempo automation envelope")
                return envelope
        
        # Create new tempo envelope if not found
        print("Creating new tempo automation envelope")
        tempo_envelope = ET.SubElement(envelopes_container, 'AutomationEnvelope')
        tempo_envelope.set('Id', str(len(envelopes_container)))
        
        # Create envelope target
        envelope_target = ET.SubElement(tempo_envelope, 'EnvelopeTarget')
        pointee_id = ET.SubElement(envelope_target, 'PointeeId')
        pointee_id.set('Value', '8')  # Tempo parameter ID
        
        # Create automation container
        automation = ET.SubElement(tempo_envelope, 'Automation')
        events = ET.SubElement(automation, 'Events')
        
        # Create automation transform view state
        transform_state = ET.SubElement(automation, 'AutomationTransformViewState')
        is_pending = ET.SubElement(transform_state, 'IsTransformPending')
        is_pending.set('Value', 'false')
        transforms = ET.SubElement(transform_state, 'TimeAndValueTransforms')
        
        return tempo_envelope
    
    def _find_or_create_time_signature_envelope(self):
        """Find or create the time signature automation envelope in the master track"""
        # Find master track
        master_track = self.root.find('.//MasterTrack')
        if master_track is None:
            raise ValueError("Could not find master track")
        
        # Find automation envelopes
        envelopes_container = master_track.find('.//AutomationEnvelopes/Envelopes')
        if envelopes_container is None:
            raise ValueError("Could not find automation envelopes container")
        
        # Look for existing time signature envelope (PointeeId="10" based on your example)
        for envelope in envelopes_container.findall('AutomationEnvelope'):
            target = envelope.find('.//EnvelopeTarget/PointeeId')
            if target is not None and target.get('Value') == '10':
                print("Found existing time signature automation envelope")
                return envelope
        
        # Create new time signature envelope if not found
        print("Creating new time signature automation envelope")
        time_sig_envelope = ET.SubElement(envelopes_container, 'AutomationEnvelope')
        time_sig_envelope.set('Id', str(len(envelopes_container)))
        
        # Create envelope target
        envelope_target = ET.SubElement(time_sig_envelope, 'EnvelopeTarget')
        pointee_id = ET.SubElement(envelope_target, 'PointeeId')
        pointee_id.set('Value', '10')  # Time signature parameter ID
        
        # Create automation container
        automation = ET.SubElement(time_sig_envelope, 'Automation')
        events = ET.SubElement(automation, 'Events')
        
        # Create automation transform view state
        transform_state = ET.SubElement(automation, 'AutomationTransformViewState')
        is_pending = ET.SubElement(transform_state, 'IsTransformPending')
        is_pending.set('Value', 'false')
        transforms = ET.SubElement(transform_state, 'TimeAndValueTransforms')
        
        return time_sig_envelope
    
    def _create_clip_from_marker(self, marker: Marker, duration: float, clip_id: int) -> ET.Element:
        """Create a new MIDI clip from a marker with specified duration"""
        # Deep copy the template clip
        new_clip = copy.deepcopy(self.template_clip)
        
        # Update clip properties
        new_clip.set('Id', str(clip_id))
        new_clip.set('Time', str(marker.beat_position))
        
        # Calculate end position
        end_position = marker.beat_position + duration
        
        # Update internal elements
        self._update_clip_element(new_clip, 'LomId', str(clip_id))
        self._update_clip_element(new_clip, 'LomIdView', str(clip_id))
        self._update_clip_element(new_clip, 'CurrentStart', str(marker.beat_position))
        self._update_clip_element(new_clip, 'CurrentEnd', str(end_position))
        self._update_clip_element(new_clip, 'Name', marker.name)
        
        # Update loop settings
        loop_elem = new_clip.find('.//Loop')
        if loop_elem is not None:
            self._update_element_in_container(loop_elem, 'LoopStart', '0')
            self._update_element_in_container(loop_elem, 'LoopEnd', str(duration))
            self._update_element_in_container(loop_elem, 'OutMarker', str(duration))
        
        # Clear any existing notes
        self._clear_clip_notes(new_clip)
        
        print(f"Created clip: '{marker.name}' at beat {marker.beat_position} with duration {duration}")
        
        return new_clip
    
    def _create_osc_clip_from_marker(self, marker: Marker, duration: float, clip_id: int, osc_name: str) -> ET.Element:
        """Create a new OSC MIDI clip from a marker with specified duration and OSC name"""
        # Deep copy the OSC template clip
        new_clip = copy.deepcopy(self.osc_template_clip)
        
        # Update clip properties
        new_clip.set('Id', str(clip_id))
        new_clip.set('Time', str(marker.beat_position))
        
        # Calculate end position
        end_position = marker.beat_position + duration
        
        # Update internal elements
        self._update_clip_element(new_clip, 'LomId', str(clip_id))
        self._update_clip_element(new_clip, 'LomIdView', str(clip_id))
        self._update_clip_element(new_clip, 'CurrentStart', str(marker.beat_position))
        self._update_clip_element(new_clip, 'CurrentEnd', str(end_position))
        self._update_clip_element(new_clip, 'Name', osc_name)
        
        # Update loop settings
        loop_elem = new_clip.find('.//Loop')
        if loop_elem is not None:
            self._update_element_in_container(loop_elem, 'LoopStart', '0')
            self._update_element_in_container(loop_elem, 'LoopEnd', str(duration))
            self._update_element_in_container(loop_elem, 'OutMarker', str(duration))
        
        # Clear any existing notes
        self._clear_clip_notes(new_clip)
        
        print(f"Created OSC clip: '{osc_name}' at beat {marker.beat_position} with duration {duration}")
        
        return new_clip
    
    def _update_clip_element(self, clip: ET.Element, tag_name: str, value: str):
        """Update a direct child element of the clip"""
        elem = clip.find(f'.//{tag_name}')
        if elem is not None:
            elem.set('Value', value)
    
    def _update_element_in_container(self, container: ET.Element, tag_name: str, value: str):
        """Update an element within a container"""
        elem = container.find(f'.//{tag_name}')
        if elem is not None:
            elem.set('Value', value)
    
    def _clear_clip_notes(self, clip: ET.Element):
        """Clear all notes from a MIDI clip"""
        notes_elem = clip.find('.//Notes')
        if notes_elem is not None:
            # Clear KeyTracks and EventLists
            key_tracks = notes_elem.find('.//KeyTracks')
            if key_tracks is not None:
                key_tracks.clear()
            
            event_store = notes_elem.find('.//PerNoteEventStore')
            if event_store is not None:
                event_lists = event_store.find('.//EventLists')
                if event_lists is not None:
                    event_lists.clear()
    
    def save(self, output_file: Path):
        """Save the modified .als file"""
        try:
            # Properly format the XML with declaration
            ET.register_namespace('', 'http://www.ableton.com/live')
            
            # Convert tree back to string with proper formatting
            xml_str = ET.tostring(self.root, encoding='unicode', xml_declaration=False)
            
            # Add XML declaration manually
            xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str
            
            # Write compressed XML
            with gzip.open(output_file, 'wt', encoding='utf-8') as f:
                f.write(xml_content)
            
            print(f"Saved modified project to: {output_file}")
            
        except Exception as e:
            raise ValueError(f"Could not save .als file: {e}")


def process_single_file(session_file: Path, skeleton_file: Path, output_dir: Path):
    """Process a single Pro Tools session file"""
    try:
        # Parse Pro Tools session
        print(f"\nProcessing: {session_file.name}")
        print(f"Parsing Pro Tools session: {session_file}")
        session_parser = ProToolsSessionParser(session_file)
        markers, tempo_changes, time_signature_changes, session_end_beat, song_name = session_parser.parse()
        
        print(f"Found {len(markers)} valid markers")
        print(f"Found {len(tempo_changes)} tempo changes")
        print(f"Found {len(time_signature_changes)} time signature changes")
        if session_end_beat:
            print(f"Session ends at beat {session_end_beat}")
        if song_name:
            print(f"Song name: '{song_name}'")
        
        # Load and modify Ableton project
        print(f"Loading skeleton project: {skeleton_file}")
        editor = AbletonProjectEditor(skeleton_file)
        editor.load()
        
        # Create MIDI clips from markers
        print("Creating MIDI clips from markers...")
        editor.create_midi_clips_from_markers(markers, session_end_beat)
        
        # Create OSC clips from markers
        print("Creating OSC clips from markers...")
        editor.create_osc_clips_from_markers(markers, song_name or "unknown_song", session_end_beat)
        
        # Apply tempo changes
        print("Applying tempo changes...")
        editor.apply_tempo_changes(tempo_changes)
        
        # Apply time signature changes
        print("Applying time signature changes...")
        editor.apply_time_signature_changes(time_signature_changes)
        
        # Create output filename based on input filename
        output_file = output_dir / f"{session_file.stem}.als"
        
        # Save modified project
        editor.save(output_file)
        
        print(f"Success! Created {len(markers)} MIDI clips, {len(markers)} OSC clips, {len(tempo_changes)} tempo changes, and {len(time_signature_changes)} time signature changes in {output_file}")
        
        return True
        
    except Exception as e:
        print(f"Error processing {session_file.name}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Convert Pro Tools markers to Ableton Live MIDI clips with tempo and time signature changes"
    )
    parser.add_argument('input_folder', type=Path, 
                       help='Folder containing Pro Tools session text files (.txt)')
    
    args = parser.parse_args()
    
    # Hardcoded paths
    skeleton_file = Path("./utils/skeleton.als")
    output_dir = Path("./output")
    
    # Validate input folder
    if not args.input_folder.exists() or not args.input_folder.is_dir():
        print(f"Error: Input folder not found or not a directory: {args.input_folder}")
        return 1
    
    # Validate skeleton file
    if not skeleton_file.exists():
        print(f"Error: Skeleton file not found: {skeleton_file}")
        return 1
    
    # Create output directory if it doesn't exist
    output_dir.mkdir(exist_ok=True)
    print(f"Output directory: {output_dir.absolute()}")
    
    # Find all .txt files in the input folder
    txt_files = list(args.input_folder.glob("*.txt"))
    
    if not txt_files:
        print(f"No .txt files found in {args.input_folder}")
        return 1
    
    print(f"Found {len(txt_files)} .txt files to process")
    
    # Process each file
    successful = 0
    failed = 0
    
    for txt_file in txt_files:
        if process_single_file(txt_file, skeleton_file, output_dir):
            successful += 1
        else:
            failed += 1
    
    print(f"\n=== Processing Complete ===")
    print(f"Successfully processed: {successful} files")
    print(f"Failed to process: {failed} files")
    print(f"Output files saved to: {output_dir.absolute()}")
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    exit(main())