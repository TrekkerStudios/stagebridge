import gzip
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional, Dict, Tuple
import copy
import shutil
import re

from models import Marker, TempoChange, TimeSignatureChange
from audio import AudioFileMapper


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
        self.audio_tracks = {}
        self.template_audio_clip = None

    def load(self):
        """Load and parse the .als file"""
        try:
            with gzip.open(self.als_file, "rt", encoding="utf-8") as f:
                content = f.read()

            self.tree = ET.ElementTree(ET.fromstring(content))
            self.root = self.tree.getroot()

            # Find and extract template MIDI clip
            self._find_template_clip()

            # Find OSC track and template clip
            self._find_osc_template_clip()

            # Find audio tracks
            self._find_audio_tracks()

        except Exception as e:
            raise ValueError(f"Could not load .als file: {e}")

    def _find_template_clip(self):
        """Find a template MIDI clip and its container"""
        # Look for any existing MidiClip to use as template
        midi_clips = self.root.findall(".//MidiClip")

        if not midi_clips:
            raise ValueError(
                "No MIDI clips found in .als file to use as template"
            )

        # Use the first MIDI clip as template
        self.template_clip = midi_clips[0]

        # Find the container by searching for the parent that contains this clip
        self.clips_container = self._find_clips_container()

        print(
            f"Using MIDI clip '{self._get_clip_name(self.template_clip)}' as template"
        )

    def _find_osc_template_clip(self):
        """Find the OSC track and its template MIDI clip"""
        # Find all MIDI tracks
        midi_tracks = self.root.findall(".//MidiTrack")

        osc_track = None
        for track in midi_tracks:
            # Look for track name containing "External +OSC"
            name_elem = track.find(".//Name/EffectiveName")
            if (
                name_elem is not None
                and "External +OSC" in name_elem.get("Value", "")
            ):
                osc_track = track
                break

        if osc_track is None:
            print(
                "Warning: No 'External +OSC' track found, skipping OSC clip creation"
            )
            return

        # Find MIDI clips in this track
        osc_clips = osc_track.findall(".//MidiClip")

        if not osc_clips:
            print(
                "Warning: No MIDI clips found in OSC track, skipping OSC clip creation"
            )
            return

        # Use the first MIDI clip as template
        self.osc_template_clip = osc_clips[0]

        # Find the container for OSC clips
        self.osc_clips_container = self._find_osc_clips_container(osc_track)

        print(
            f"Found OSC track with template clip '{self._get_clip_name(self.osc_template_clip)}'"
        )

    def _find_audio_tracks(self):
        """Find audio tracks and store them for later use"""
        audio_tracks = self.root.findall(".//AudioTrack")

        for track in audio_tracks:
            name_elem = track.find(".//Name/EffectiveName")
            if name_elem is not None:
                track_name = name_elem.get("Value", "")
                if track_name in AudioFileMapper.TRACK_MAPPINGS:
                    self.audio_tracks[track_name] = track
                    print(f"Found audio track: '{track_name}'")

                    # Find template audio clip if we don't have one yet
                    if self.template_audio_clip is None:
                        audio_clips = track.findall(".//AudioClip")
                        if audio_clips:
                            self.template_audio_clip = audio_clips[0]
                            print(
                                f"Using audio clip from '{track_name}' as template"
                            )

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
        events_container = osc_track.find(".//ArrangerAutomation/Events")
        if events_container is None:
            print("Warning: Could not find OSC clips container")
            return None

        return events_container

    def _get_clip_name(self, clip_element) -> str:
        """Get the name of a MIDI clip"""
        name_elem = clip_element.find(".//Name")
        return (
            name_elem.get("Value", "Unnamed")
            if name_elem is not None
            else "Unnamed"
        )

    def _normalize_name(self, name: str) -> str:
        """Normalize name to lowercase with underscores."""
        # Remove special characters and replace spaces with underscores
        normalized = re.sub(r"[^\w\s-]", "", name.lower())
        normalized = re.sub(r"[-\s]+", "_", normalized)
        return normalized.strip("_")

    def _calculate_clip_durations(
        self, markers: List[Marker], session_end_beat: Optional[float] = None
    ) -> List[Tuple[Marker, float]]:
        """Calculate duration for each clip based on distance to next marker or session end"""
        clips_with_durations = []

        for i, marker in enumerate(markers):
            if i < len(markers) - 1:
                # Duration is the distance to the next marker
                next_marker = markers[i + 1]
                duration = next_marker.beat_position - marker.beat_position
            else:
                # For the last marker, calculate duration to session end or use default
                if (
                    session_end_beat is not None
                    and session_end_beat > marker.beat_position
                ):
                    duration = session_end_beat - marker.beat_position
                    # Cap the final section at 4 beats maximum
                    duration = min(duration, 4.0)
                else:
                    # Fallback to 4 beats if no session end found
                    duration = 4.0

            # Ensure minimum duration of 1 beat
            duration = max(duration, 1.0)

            clips_with_durations.append((marker, duration))
            print(
                f"Clip '{marker.name}': {duration} beats (from beat {marker.beat_position} to {marker.beat_position + duration})"
            )

        return clips_with_durations

    def create_midi_clips_from_markers(
        self, markers: List[Marker], session_end_beat: Optional[float] = None
    ):
        """Create MIDI clips from markers"""
        if not self.template_clip or not self.clips_container:
            raise ValueError("No template clip or container available")

        # Calculate durations for each clip
        clips_with_durations = self._calculate_clip_durations(
            markers, session_end_beat
        )

        # Remove existing clips except the template
        clips_to_remove = [
            clip
            for clip in self.clips_container.findall("MidiClip")
            if clip != self.template_clip
        ]
        for clip in clips_to_remove:
            self.clips_container.remove(clip)

        # Create new clips from markers
        for i, (marker, duration) in enumerate(clips_with_durations):
            new_clip = self._create_clip_from_marker(marker, duration, i)
            self.clips_container.append(new_clip)

        # Remove the template clip
        self.clips_container.remove(self.template_clip)

        print(f"Created {len(markers)} MIDI clips")

    def create_osc_clips_from_markers(
        self,
        markers: List[Marker],
        song_name: str,
        session_end_beat: Optional[float] = None,
    ):
        """Create OSC MIDI clips from markers"""
        if not self.osc_template_clip or not self.osc_clips_container:
            print(
                "Warning: No OSC template clip or container available, skipping OSC clip creation"
            )
            return

        # Calculate durations for each clip
        clips_with_durations = self._calculate_clip_durations(
            markers, session_end_beat
        )

        # Remove existing OSC clips except the template
        clips_to_remove = [
            clip
            for clip in self.osc_clips_container.findall("MidiClip")
            if clip != self.osc_template_clip
        ]
        for clip in clips_to_remove:
            self.osc_clips_container.remove(clip)

        # Create new OSC clips from markers
        for i, (marker, duration) in enumerate(clips_with_durations):
            # Create OSC formatted name
            normalized_song = self._normalize_name(song_name)
            normalized_section = self._normalize_name(marker.name)
            osc_name = f"/ableton/{normalized_song}/{normalized_section}"

            new_clip = self._create_osc_clip_from_marker(
                marker, duration, i, osc_name
            )
            self.osc_clips_container.append(new_clip)

        # Remove the OSC template clip
        self.osc_clips_container.remove(self.osc_template_clip)

        print(f"Created {len(markers)} OSC MIDI clips")

    def add_audio_files(
        self, audio_mapper: AudioFileMapper, project_samples_dir: Path
    ):
        """Add audio files to their respective tracks"""
        if not self.template_audio_clip:
            print(
                "Warning: No template audio clip found, skipping audio file addition"
            )
            return

        added_count = 0

        for track_name, track_element in self.audio_tracks.items():
            audio_file = audio_mapper.get_audio_file(track_name)

            if audio_file:
                # Copy audio file to project samples directory
                dest_file = project_samples_dir / audio_file.name
                try:
                    shutil.copy2(audio_file, dest_file)
                    print(
                        f"Copied '{audio_file.name}' to project samples"
                    )

                    # Get audio duration
                    duration = audio_mapper.get_audio_duration(track_name)

                    # Add audio clip to track
                    self._add_audio_clip_to_track(
                        track_element,
                        dest_file,
                        audio_file.name,
                        duration,
                    )
                    added_count += 1

                except Exception as e:
                    print(
                        f"Error copying audio file '{audio_file.name}': {e}"
                    )
            else:
                print(f"No audio file found for track '{track_name}'")

        print(f"Added {added_count} audio files to tracks")

    def _add_audio_clip_to_track(
        self,
        track_element: ET.Element,
        audio_file_path: Path,
        clip_name: str,
        duration_seconds: float,
    ):
        """Add an audio clip to a track with full file duration"""
        # Find the Sample/ArrangerAutomation/Events container
        events_container = track_element.find(
            ".//Sample/ArrangerAutomation/Events"
        )

        if events_container is None:
            print(f"Warning: Could not find events container for track")
            return

        # Remove existing audio clips
        existing_clips = events_container.findall("AudioClip")
        for clip in existing_clips:
            events_container.remove(clip)

        # Create new audio clip based on template
        new_clip = copy.deepcopy(self.template_audio_clip)

        # Update clip properties
        new_clip.set("Id", "0")
        new_clip.set("Time", "0")

        # Update clip name
        name_elem = new_clip.find(".//Name")
        if name_elem is not None:
            name_elem.set("Value", clip_name.replace(".wav", ""))

        # Update clip timing to match full audio file duration
        current_end_elem = new_clip.find(".//CurrentEnd")
        if current_end_elem is not None:
            # Convert seconds to beats (assuming 120 BPM for now - this could be improved)
            # At 120 BPM, 1 beat = 0.5 seconds, so beats = seconds * 2
            duration_beats = (
                duration_seconds * 2
            )  # This is a simplification
            current_end_elem.set("Value", str(duration_beats))

        # Update loop settings to match full duration
        loop_elem = new_clip.find(".//Loop")
        if loop_elem is not None:
            loop_end_elem = loop_elem.find(".//LoopEnd")
            out_marker_elem = loop_elem.find(".//OutMarker")

            if loop_end_elem is not None:
                loop_end_elem.set("Value", str(duration_beats))
            if out_marker_elem is not None:
                out_marker_elem.set("Value", str(duration_beats))

        # Update file reference
        file_ref = new_clip.find(".//SampleRef/FileRef")
        if file_ref is not None:
            relative_path_string = f"Samples/Imported/{audio_file_path.name}"

            # Update relative path
            relative_path_elem = file_ref.find("RelativePath")
            if relative_path_elem is not None:
                relative_path_elem.set("Value", relative_path_string)

            # Update absolute path to also be relative from the project root
            path_elem = file_ref.find("Path")
            if path_elem is not None:
                path_elem.set("Value", relative_path_string)

        # Add the clip to the events container
        events_container.append(new_clip)

        print(
            f"Added audio clip '{clip_name}' to track (duration: {duration_seconds:.3f}s)"
        )

    def apply_tempo_changes(self, tempo_changes: List[TempoChange]):
        """Apply tempo changes to the master track automation"""
        if not tempo_changes:
            print("No tempo changes to apply")
            return

        # Recreate the tempo automation envelope to ensure it's clean
        tempo_envelope = self._recreate_tempo_envelope()
        events_container = tempo_envelope.find(".//Events")

        # Create tempo events with proper interpolation prevention
        event_id = 0

        # Add initial tempo event at the very beginning
        if tempo_changes[0].beat_position > 0:
            # Use first tempo change value as initial tempo
            initial_event = ET.SubElement(events_container, "FloatEvent")
            initial_event.set("Id", str(event_id))
            initial_event.set(
                "Time", "-63072000"
            )  # Very beginning of timeline
            initial_event.set("Value", str(tempo_changes[0].tempo))
            event_id += 1

        # Add tempo change events
        for i, tempo_change in enumerate(tempo_changes):
            # If this isn't the first tempo change, add a "hold" event just before
            # the new tempo to prevent interpolation
            if i > 0:
                prev_tempo = tempo_changes[i - 1].tempo
                hold_time = (
                    tempo_change.beat_position - 0.001
                )  # Just before the change

                hold_event = ET.SubElement(events_container, "FloatEvent")
                hold_event.set("Id", str(event_id))
                hold_event.set("Time", str(hold_time))
                hold_event.set("Value", str(prev_tempo))
                event_id += 1

            # Add the actual tempo change event
            tempo_event = ET.SubElement(events_container, "FloatEvent")
            tempo_event.set("Id", str(event_id))
            tempo_event.set("Time", str(tempo_change.beat_position))
            tempo_event.set("Value", str(tempo_change.tempo))
            event_id += 1

            print(
                f"Added tempo change: {tempo_change.tempo} BPM at beat {tempo_change.beat_position}"
            )

        print(f"Applied {len(tempo_changes)} tempo changes")

    def apply_time_signature_changes(
        self, time_signature_changes: List[TimeSignatureChange]
    ):
        """Apply time signature changes to the master track automation"""
        if not time_signature_changes:
            print("No time signature changes to apply")
            return

        # Recreate the time signature automation envelope to ensure it's clean
        time_sig_envelope = self._recreate_time_signature_envelope()
        events_container = time_sig_envelope.find(".//Events")

        # Create time signature events
        event_id = 0

        # Add initial time signature event at the very beginning
        if time_signature_changes[0].beat_position > 0:
            # Use first time signature change value as initial
            initial_event = ET.SubElement(events_container, "EnumEvent")
            initial_event.set("Id", str(event_id))
            initial_event.set(
                "Time", "-63072000"
            )  # Very beginning of timeline
            initial_event.set(
                "Value", str(time_signature_changes[0].ableton_value)
            )
            event_id += 1

        # Add time signature change events
        for i, time_sig_change in enumerate(time_signature_changes):
            # If this isn't the first time signature change, add a "hold" event just before
            # the new time signature to prevent interpolation
            if i > 0:
                prev_time_sig = time_signature_changes[i - 1].ableton_value
                hold_time = (
                    time_sig_change.beat_position - 0.001
                )  # Just before the change

                hold_event = ET.SubElement(events_container, "EnumEvent")
                hold_event.set("Id", str(event_id))
                hold_event.set("Time", str(hold_time))
                hold_event.set("Value", str(prev_time_sig))
                event_id += 1

            # Add the actual time signature change event
            time_sig_event = ET.SubElement(events_container, "EnumEvent")
            time_sig_event.set("Id", str(event_id))
            time_sig_event.set("Time", str(time_sig_change.beat_position))
            time_sig_event.set("Value", str(time_sig_change.ableton_value))
            event_id += 1

            print(
                f"Added time signature change: {time_sig_change.numerator}/{time_sig_change.denominator} at beat {time_sig_change.beat_position}"
            )

        print(f"Applied {len(time_signature_changes)} time signature changes")

    def _recreate_tempo_envelope(self):
        """Deletes any existing tempo envelope and creates a new, clean one."""
        # Find master track
        master_track = self.root.find(".//MasterTrack")
        if master_track is None:
            raise ValueError("Could not find master track")

        # Find automation envelopes container
        envelopes_container = master_track.find(
            ".//AutomationEnvelopes/Envelopes"
        )
        if envelopes_container is None:
            raise ValueError("Could not find automation envelopes container")

        # Find and remove existing tempo envelope (PointeeId="8")
        for envelope in list(
            envelopes_container.findall("AutomationEnvelope")
        ):
            target = envelope.find(".//EnvelopeTarget/PointeeId")
            if target is not None and target.get("Value") == "8":
                envelopes_container.remove(envelope)
                print("Removed existing tempo automation envelope.")

        # Create a new, clean tempo envelope
        print("Creating new tempo automation envelope.")
        tempo_envelope = ET.SubElement(
            envelopes_container, "AutomationEnvelope"
        )
        tempo_envelope.set("Id", str(len(envelopes_container)))

        # Create envelope target
        envelope_target = ET.SubElement(tempo_envelope, "EnvelopeTarget")
        pointee_id = ET.SubElement(envelope_target, "PointeeId")
        pointee_id.set("Value", "8")  # Tempo parameter ID

        # Create automation container
        automation = ET.SubElement(tempo_envelope, "Automation")
        ET.SubElement(automation, "Events")

        # Create automation transform view state
        transform_state = ET.SubElement(
            automation, "AutomationTransformViewState"
        )
        is_pending = ET.SubElement(transform_state, "IsTransformPending")
        is_pending.set("Value", "false")
        ET.SubElement(transform_state, "TimeAndValueTransforms")

        return tempo_envelope

    def _recreate_time_signature_envelope(self):
        """Deletes any existing time signature envelope and creates a new, clean one."""
        # Find master track
        master_track = self.root.find(".//MasterTrack")
        if master_track is None:
            raise ValueError("Could not find master track")

        # Find automation envelopes container
        envelopes_container = master_track.find(
            ".//AutomationEnvelopes/Envelopes"
        )
        if envelopes_container is None:
            raise ValueError("Could not find automation envelopes container")

        # Find and remove existing time signature envelope (PointeeId="10")
        for envelope in list(
            envelopes_container.findall("AutomationEnvelope")
        ):
            target = envelope.find(".//EnvelopeTarget/PointeeId")
            if target is not None and target.get("Value") == "10":
                envelopes_container.remove(envelope)
                print("Removed existing time signature automation envelope.")

        # Create a new, clean time signature envelope
        print("Creating new time signature automation envelope.")
        time_sig_envelope = ET.SubElement(
            envelopes_container, "AutomationEnvelope"
        )
        time_sig_envelope.set("Id", str(len(envelopes_container)))

        # Create envelope target
        envelope_target = ET.SubElement(time_sig_envelope, "EnvelopeTarget")
        pointee_id = ET.SubElement(envelope_target, "PointeeId")
        pointee_id.set("Value", "10")  # Time signature parameter ID

        # Create automation container
        automation = ET.SubElement(time_sig_envelope, "Automation")
        ET.SubElement(automation, "Events")

        # Create automation transform view state
        transform_state = ET.SubElement(
            automation, "AutomationTransformViewState"
        )
        is_pending = ET.SubElement(transform_state, "IsTransformPending")
        is_pending.set("Value", "false")
        ET.SubElement(transform_state, "TimeAndValueTransforms")

        return time_sig_envelope

    def _create_clip_from_marker(
        self, marker: Marker, duration: float, clip_id: int
    ) -> ET.Element:
        """Create a new MIDI clip from a marker with specified duration"""
        # Deep copy the template clip
        new_clip = copy.deepcopy(self.template_clip)

        # Update clip properties
        new_clip.set("Id", str(clip_id))
        new_clip.set("Time", str(marker.beat_position))

        # Calculate end position
        end_position = marker.beat_position + duration

        # Update internal elements
        self._update_clip_element(new_clip, "LomId", str(clip_id))
        self._update_clip_element(new_clip, "LomIdView", str(clip_id))
        self._update_clip_element(
            new_clip, "CurrentStart", str(marker.beat_position)
        )
        self._update_clip_element(new_clip, "CurrentEnd", str(end_position))
        self._update_clip_element(new_clip, "Name", marker.name)

        # Update loop settings
        loop_elem = new_clip.find(".//Loop")
        if loop_elem is not None:
            self._update_element_in_container(loop_elem, "LoopStart", "0")
            self._update_element_in_container(
                loop_elem, "LoopEnd", str(duration)
            )
            self._update_element_in_container(
                loop_elem, "OutMarker", str(duration)
            )

        # Clear any existing notes
        self._clear_clip_notes(new_clip)

        print(
            f"Created clip: '{marker.name}' at beat {marker.beat_position} with duration {duration}"
        )

        return new_clip

    def _create_osc_clip_from_marker(
        self, marker: Marker, duration: float, clip_id: int, osc_name: str
    ) -> ET.Element:
        """Create a new OSC MIDI clip from a marker with specified duration and OSC name"""
        # Deep copy the OSC template clip
        new_clip = copy.deepcopy(self.osc_template_clip)

        # Update clip properties
        new_clip.set("Id", str(clip_id))
        new_clip.set("Time", str(marker.beat_position))

        # Calculate end position
        end_position = marker.beat_position + duration

        # Update internal elements
        self._update_clip_element(new_clip, "LomId", str(clip_id))
        self._update_clip_element(new_clip, "LomIdView", str(clip_id))
        self._update_clip_element(
            new_clip, "CurrentStart", str(marker.beat_position)
        )
        self._update_clip_element(new_clip, "CurrentEnd", str(end_position))
        self._update_clip_element(new_clip, "Name", osc_name)

        # Update loop settings
        loop_elem = new_clip.find(".//Loop")
        if loop_elem is not None:
            self._update_element_in_container(loop_elem, "LoopStart", "0")
            self._update_element_in_container(
                loop_elem, "LoopEnd", str(duration)
            )
            self._update_element_in_container(
                loop_elem, "OutMarker", str(duration)
            )

        # Clear any existing notes
        self._clear_clip_notes(new_clip)

        print(
            f"Created OSC clip: '{osc_name}' at beat {marker.beat_position} with duration {duration}"
        )

        return new_clip

    def _update_clip_element(
        self, clip: ET.Element, tag_name: str, value: str
    ):
        """Update a direct child element of the clip"""
        elem = clip.find(f".//{tag_name}")
        if elem is not None:
            elem.set("Value", value)

    def _update_element_in_container(
        self, container: ET.Element, tag_name: str, value: str
    ):
        """Update an element within a container"""
        elem = container.find(f".//{tag_name}")
        if elem is not None:
            elem.set("Value", value)

    def _clear_clip_notes(self, clip: ET.Element):
        """Clear all notes from a MIDI clip"""
        notes_elem = clip.find(".//Notes")
        if notes_elem is not None:
            # Clear KeyTracks and EventLists
            key_tracks = notes_elem.find(".//KeyTracks")
            if key_tracks is not None:
                key_tracks.clear()

            event_store = notes_elem.find(".//PerNoteEventStore")
            if event_store is not None:
                event_lists = event_store.find(".//EventLists")
                if event_lists is not None:
                    event_lists.clear()

    def save(self, output_file: Path):
        """Save the modified .als file"""
        try:
            # Properly format the XML with declaration
            ET.register_namespace("", "http://www.ableton.com/live")

            # Convert tree back to string with proper formatting
            xml_str = ET.tostring(
                self.root, encoding="unicode", xml_declaration=False
            )

            # Add XML declaration manually
            xml_content = (
                '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str
            )

            # Write compressed XML
            with gzip.open(output_file, "wt", encoding="utf-8") as f:
                f.write(xml_content)

            print(f"Saved modified project to: {output_file}")

        except Exception as e:
            raise ValueError(f"Could not save .als file: {e}")