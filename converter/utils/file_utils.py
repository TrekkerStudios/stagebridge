from pathlib import Path
from typing import List
import traceback

from parsers import ProToolsSessionParser
from audio import AudioFileMapper
from ableton import AbletonProjectEditor


def find_session_folders(root_folder: Path) -> List[Path]:
    """Find all session folders in the root directory"""
    session_folders = []

    for item in root_folder.iterdir():
        if item.is_dir():
            # Look for .txt files in this directory
            txt_files = list(item.glob("*.txt"))
            if txt_files:
                session_folders.append(item)
                print(f"Found session folder: {item.name}")

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

        print(f"Found {len(markers)} valid markers")
        print(f"Found {len(tempo_changes)} tempo changes")
        print(f"Found {len(time_signature_changes)} time signature changes")
        if session_end_beat:
            print(f"Session ends at beat {session_end_beat}")
        print(f"Project Name: '{project_name_cased}'")

        # Create audio file mapper
        audio_mapper = AudioFileMapper(session_folder)

        # Load and modify Ableton project
        print(f"Loading skeleton project: {skeleton_file}")
        editor = AbletonProjectEditor(skeleton_file)
        editor.load()

        # Create project folder structure
        project_folder = output_dir / f"{project_name_cased} Project"
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

        # Save modified project (using cased name)
        output_file = project_folder / f"{project_name_cased}.als"
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