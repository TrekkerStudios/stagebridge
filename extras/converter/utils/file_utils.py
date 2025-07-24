from pathlib import Path
from typing import List
import traceback

from parsers import ProToolsSessionParser
from audio import AudioFileMapper
from ableton import AbletonProjectEditor


def find_session_folders(root_folder: Path) -> List[Path]:
    """Find all session folders by searching one level deep from the root directory."""
    session_folders = []
    print(f"Searching for session folders in subdirectories of {root_folder}...")

    # Iterate through the top-level genre folders (e.g., "NN 4 - DANCE + POP SD")
    for genre_folder in root_folder.iterdir():
        if not genre_folder.is_dir():
            continue

        # Now iterate through the actual session folders inside the genre folder
        for session_folder in genre_folder.iterdir():
            if session_folder.is_dir():
                # Look for .txt files to confirm it's a session folder
                txt_files = list(session_folder.glob("*.txt"))
                if txt_files:
                    session_folders.append(session_folder)
                    print(f"Found session folder: {session_folder.name}")

    return session_folders


def process_session_folder(
    session_folder: Path, skeleton_file: Path, output_dir: Path
):
    """Process a single session folder"""
    try:
        print(f"\n{'='*60}")
        print(f"Processing session: {session_folder.name}")
        print(f"{'='*60}")

        # Find the .txt file in the session folder
        txt_files = list(session_folder.glob("*.txt"))
        if not txt_files:
            print(f"No .txt files found in {session_folder}")
            return False

        # Use the first .txt file found
        session_file = txt_files[0]
        print(f"Using session file: {session_file.name}")

        # Parse Pro Tools session
        session_parser = ProToolsSessionParser(session_file)
        (
            markers,
            tempo_changes,
            time_signature_changes,
            session_end_beat,
        ) = session_parser.parse()

        # Create audio file mapper and get song duration
        audio_mapper = AudioFileMapper(session_folder)
        max_duration_sec = audio_mapper.get_max_duration()
        # Format duration into mm:ss
        minutes, seconds = divmod(max_duration_sec, 60)
        duration_str = f"{int(minutes):02d}.{int(seconds):02d}"

        # Determine project names (cased for files, normalized for OSC)
        if session_parser.original_song_name:
            project_name_cased = session_parser.original_song_name
            project_name_normalized = session_parser.song_name
        else:
            # Fallback to using the session folder name
            project_name_cased = session_folder.stem
            project_name_normalized = ProToolsSessionParser.normalize_name(
                session_folder.stem
            )

        # Construct the final project name with duration
        final_project_name = f"{project_name_cased} [{duration_str}]"

        print(f"Found {len(markers)} valid markers")
        print(f"Found {len(tempo_changes)} tempo changes")
        print(f"Found {len(time_signature_changes)} time signature changes")
        if session_end_beat:
            print(f"Session ends at beat {session_end_beat}")
        print(f"Project Name: '{final_project_name}'")

        # Load and modify Ableton project
        print(f"Loading skeleton project: {skeleton_file}")
        editor = AbletonProjectEditor(skeleton_file)
        editor.load()

        # Create project folder structure with the new name
        project_folder = output_dir / f"{final_project_name} Project"
        project_folder.mkdir(exist_ok=True)

        # Create samples directory
        samples_dir = project_folder / "Samples" / "Imported"
        samples_dir.mkdir(parents=True, exist_ok=True)

        print(f"Created project folder: {project_folder}")

        # Create MIDI clips from markers
        print("Creating MIDI clips from markers...")
        editor.create_midi_clips_from_markers(markers, session_end_beat)

        # Create OSC clips from markers (using normalized name)
        print("Creating OSC clips from markers...")
        editor.create_osc_clips_from_markers(
            markers, project_name_normalized, session_end_beat
        )

        # Add audio files
        print("Adding audio files...")
        editor.add_audio_files(audio_mapper, samples_dir)

        # Apply tempo changes
        print("Applying tempo changes...")
        editor.apply_tempo_changes(tempo_changes)

        # Apply time signature changes
        print("Applying time signature changes...")
        editor.apply_time_signature_changes(time_signature_changes)

        # Save modified project (using the new name with duration)
        output_file = project_folder / f"{final_project_name}.als"
        editor.save(output_file)

        print(f"Success! Created complete project in {project_folder}")
        print(f"- {len(markers)} MIDI clips")
        print(f"- {len(markers)} OSC clips")
        print(f"- {len(audio_mapper.get_all_audio_files())} audio files")
        print(f"- {len(tempo_changes)} tempo changes")
        print(
            f"- {len(time_signature_changes)} time signature changes"
        )

        return True

    except Exception as e:
        print(f"Error processing {session_folder.name}: {e}")
        traceback.print_exc()
        return False