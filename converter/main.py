#!/usr/bin/env python3
"""
Pro Tools to Ableton Live Marker Converter

Extracts markers from Pro Tools session text files and converts them to 
MIDI clips in Ableton Live .als project files. Also handles tempo and time signature changes.
Now also creates OSC clips for external control and automatically adds audio files.
"""

import argparse
from pathlib import Path

from utils import find_session_folders, process_session_folder


def main():
    parser = argparse.ArgumentParser(
        description="Convert Pro Tools sessions to complete Ableton Live projects with audio files"
    )
    parser.add_argument('input_folder', type=Path, 
                       help='Root folder containing session folders (e.g., "NN 4 - DANCE + POP SD")')
    
    args = parser.parse_args()
    
    # Hardcoded paths
    skeleton_file = Path("./utils/skeleton Project/skeleton.als")
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
    
    # Find all session folders
    session_folders = find_session_folders(args.input_folder)
    
    if not session_folders:
        print(f"No session folders found in {args.input_folder}")
        return 1
    
    print(f"Found {len(session_folders)} session folders to process")
    
    # Process each session folder
    successful = 0
    failed = 0
    
    for session_folder in session_folders:
        if process_session_folder(session_folder, skeleton_file, output_dir):
            successful += 1
        else:
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"PROCESSING COMPLETE")
    print(f"{'='*60}")
    print(f"Successfully processed: {successful} sessions")
    print(f"Failed to process: {failed} sessions")
    print(f"Output projects saved to: {output_dir.absolute()}")
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    exit(main())