import re
from pathlib import Path
from typing import List, Tuple, Optional

from models import Marker, TempoChange, TimeSignatureChange


class ProToolsSessionParser:
    """Parses Pro Tools session text files"""

    def __init__(self, session_file: Path):
        self.session_file = session_file
        self.markers: List[Marker] = []
        self.tempo_changes: List[TempoChange] = []
        self.time_signature_changes: List[TimeSignatureChange] = []
        self.session_end_beat: Optional[float] = None
        self.song_name: Optional[
            str
        ] = None  # This will be the normalized name
        self.original_song_name: Optional[str] = None

    def parse(
        self,
    ) -> Tuple[
        List[Marker],
        List[TempoChange],
        List[TimeSignatureChange],
        Optional[float],
    ]:
        """Parse the Pro Tools session file and extract markers, tempo changes, time signature changes, and session end."""
        with open(self.session_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract song name from session
        self._extract_song_name(content)

        # Find markers section
        markers_section = self._extract_markers_section(content)
        if not markers_section:
            raise ValueError(
                "No markers section found in Pro Tools session file"
            )

        # Parse markers, tempo changes, time signature changes, and session end
        (
            self.markers,
            self.tempo_changes,
            self.time_signature_changes,
            self.session_end_beat,
        ) = self._parse_markers_and_changes(markers_section)

        return (
            self.markers,
            self.tempo_changes,
            self.time_signature_changes,
            self.session_end_beat,
        )

    def _extract_song_name(self, content: str):
        """Extracts and sets the original and normalized song names from the Pro Tools session file."""
        # Look for SESSION NAME line
        session_name_pattern = r"SESSION NAME:\s*(.+)"
        match = re.search(session_name_pattern, content)

        if match:
            session_name = match.group(1).strip()
            # Extract song name from session name (remove file extensions and extra info)
            # Pattern like "(.113.) Fat Lip - Sum 41 SD" -> "Fat Lip"

            # Try to extract song name from various patterns
            patterns = [
                r"\([^)]*\)\s*(.+?)\s*-\s*(.+?)\s*SD",  # "(.113.) Fat Lip - Sum 41 SD"
                r"\([^)]*\)\s*(.+?)\s*-\s*(.+)",  # "(.113.) Fat Lip - Sum 41"
                r"(.+?)\s*-\s*(.+?)\s*SD",  # "Fat Lip - Sum 41 SD"
                r"(.+?)\s*-\s*(.+)",  # "Fat Lip - Sum 41"
                r"(.+)",  # Fallback: entire name
            ]

            for pattern in patterns:
                match = re.match(pattern, session_name)
                if match:
                    original_name = match.group(1).strip()
                    self.original_song_name = original_name
                    self.song_name = self.normalize_name(original_name)
                    print(
                        f"Extracted song name: '{self.original_song_name}'"
                    )
                    return

        print("Warning: Could not extract song name from session file")
        self.original_song_name = None
        self.song_name = "unknown_song"

    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize name to lowercase with underscores."""
        # Remove special characters and replace spaces with underscores
        normalized = re.sub(r"[^\w\s-]", "", name.lower())
        normalized = re.sub(r"[-\s]+", "_", normalized)
        return normalized.strip("_")

    def _extract_markers_section(self, content: str) -> str:
        """Extract the markers section from the session file"""
        start_pattern = r"M A R K E R S\s+L I S T I N G"
        start_match = re.search(start_pattern, content)

        if not start_match:
            return ""

        # Find the end of the markers section (next major section or end of file)
        start_pos = start_match.end()

        # Look for next major section header or end of file
        end_patterns = [
            r"\n[A-Z]\s+[A-Z].*L I S T I N G",
            r"\n[A-Z]\s+[A-Z].*I N F O R M A T I O N",
        ]

        end_pos = len(content)
        for pattern in end_patterns:
            match = re.search(pattern, content[start_pos:])
            if match:
                end_pos = start_pos + match.start()
                break

        return content[start_pos:end_pos]

    def _parse_markers_and_changes(
        self, markers_section: str
    ) -> Tuple[
        List[Marker],
        List[TempoChange],
        List[TimeSignatureChange],
        Optional[float],
    ]:
        """Parse individual markers, tempo changes, time signature changes, and session end from the markers section"""
        markers = []
        tempo_changes = []
        time_signature_changes = []
        session_end_beat = None

        # Split into lines and process each marker line
        lines = markers_section.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or "LOCATION" in line:
                continue

            # Parse marker line using tab separation first, then multiple spaces
            parts = (
                line.split("\t")
                if "\t" in line
                else re.split(r"\s{2,}", line)
            )

            if (
                len(parts) >= 6
            ):  # Need at least 6 parts to get TIME REFERENCE
                try:
                    location = parts[1].strip()
                    time_reference = parts[2].strip()  # This is the TIME REFERENCE column
                    name = parts[4].strip()

                    # Check if this is an END marker
                    if name.upper() == "END":
                        session_end_beat = self._parse_time_reference_for_changes(
                            time_reference
                        )
                        print(
                            f"Found session END at beat {session_end_beat}"
                        )
                        continue

                    # Check if this is a tempo marker
                    if "Tempo" in name or self._is_tempo_marker(name):
                        tempo_value = self._extract_tempo_from_name(name)
                        if tempo_value:
                            beat_pos = self._parse_time_reference_for_changes(
                                time_reference
                            )

                            # Validate beat position is reasonable (not way beyond the session)
                            if (
                                beat_pos < 10000
                            ):  # Reasonable upper limit for beat position
                                tempo_changes.append(
                                    TempoChange(beat_pos, tempo_value)
                                )
                                print(
                                    f"Parsed tempo change: {tempo_value} BPM @ beat {beat_pos}"
                                )
                            else:
                                print(
                                    f"Warning: Tempo change at beat {beat_pos} is beyond reasonable range, skipping"
                                )
                        continue

                    # Check if this is a time signature marker
                    time_sig = self._extract_time_signature_from_name(name)
                    if time_sig:
                        beat_pos = self._parse_time_reference_for_changes(
                            time_reference
                        )

                        # Validate beat position is reasonable
                        if (
                            beat_pos < 10000
                        ):  # Reasonable upper limit for beat position
                            numerator, denominator = time_sig
                            time_signature_changes.append(
                                TimeSignatureChange(
                                    beat_pos, numerator, denominator
                                )
                            )
                            print(
                                f"Parsed time signature change: {numerator}/{denominator} @ beat {beat_pos}"
                            )
                        else:
                            print(
                                f"Warning: Time signature change at beat {beat_pos} is beyond reasonable range, skipping"
                            )
                        continue

                    # Skip numeric-only names
                    if (
                        name.replace(".", "").replace("-", "").isdigit()
                        or len(name.replace(".", "").replace("-", "")) == 0
                    ):
                        continue

                    # Clean up marker name
                    name = self._clean_marker_name(name)

                    if name and time_reference:
                        beat_pos = self._parse_time_reference_for_changes(
                            time_reference
                        )

                        # Validate marker beat position is reasonable
                        if beat_pos < 10000:  # Reasonable upper limit
                            marker = Marker(location, time_reference, name)
                            markers.append(marker)
                            print(f"Parsed marker: {marker}")
                        else:
                            print(
                                f"Warning: Marker '{name}' at beat {beat_pos} is beyond reasonable range, skipping"
                            )

                except (IndexError, ValueError) as e:
                    print(
                        f"Warning: Could not parse marker line: {line} ({e})"
                    )
                    continue

        # Sort by beat position
        markers = sorted(markers, key=lambda m: m.beat_position)
        tempo_changes = sorted(tempo_changes, key=lambda t: t.beat_position)
        time_signature_changes = sorted(
            time_signature_changes, key=lambda ts: ts.beat_position
        )

        return (
            markers,
            tempo_changes,
            time_signature_changes,
            session_end_beat,
        )

    def _is_tempo_marker(self, name: str) -> bool:
        """Check if a marker name indicates a tempo change"""
        try:
            # Clean the name first - remove any trailing backslashes or other non-numeric characters
            cleaned_name = name.rstrip("\\").strip()
            tempo = float(cleaned_name)

            # Validate that it's in a reasonable tempo range
            return 30 <= tempo <= 300

        except ValueError:
            return False

    def _extract_tempo_from_name(self, name: str) -> Optional[float]:
        """Extract tempo value from marker name"""
        try:
            # Clean the name first - remove any trailing backslashes or other non-numeric characters
            cleaned_name = name.rstrip("\\").strip()
            tempo = float(cleaned_name)

            # Validate that the tempo is within a reasonable range
            if 30 <= tempo <= 300:  # Reasonable BPM range
                return tempo
            else:
                print(
                    f"Warning: Tempo {tempo} is outside reasonable range (30-300 BPM), skipping"
                )
                return None

        except ValueError:
            return None

    def _extract_time_signature_from_name(
        self, name: str
    ) -> Optional[Tuple[int, int]]:
        """Extract time signature from marker name"""
        # Look for patterns like "3/4", "4/4", "Duh 3/4", etc.
        time_sig_patterns = [
            r"(\d+)/(\d+)",  # Direct pattern like "3/4"
            r"(\d+)/(\d+)",  # In context like "Duh 3/4"
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
            if "|" in time_reference:
                bar, beat = time_reference.split("|")
                # Convert to 0-based beat position (bar-1)*4 + (beat-1)
                return (int(bar) - 1) * 4 + (int(beat) - 1)
            else:
                return float(time_reference)
        except (ValueError, IndexError):
            return 0.0

    def _clean_marker_name(self, name: str) -> str:
        """Clean up marker names"""
        # Remove quotes and extra whitespace
        name = name.strip("\"'").strip()

        # Skip empty names or pure numbers
        if not name or name.replace(".", "").replace("-", "").isdigit():
            return ""

        return name