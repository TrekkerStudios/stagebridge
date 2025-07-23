# song_parser.py
import csv
import io
import uuid

def parse_song_csv(file_stream, song_title, setlist_number, settings):
    """Parses a song CSV and generates a list of OSC mappings."""
    generated_mappings = []
    last_value = None
    try:
        csv_file = io.TextIOWrapper(file_stream, encoding='utf-8')
        reader = csv.DictReader(csv_file)
        if settings['column_name'] not in reader.fieldnames:
            raise ValueError(f"Column '{settings['column_name']}' not found in CSV.")
        
        temp_mappings = []
        for row in reader:
            value = row.get(settings['column_name'], "").strip()
            if not value or value == last_value: continue
            last_value = value
            
            midi_sequence, description, channel = [], "", 1
            try:
                if value.startswith(settings['footswitch_prefix']):
                    fs_char = value.replace(settings['footswitch_prefix'], '').strip().upper()
                    if 'A' <= fs_char <= 'H':
                        control = 35 + (ord(fs_char) - ord('A'))
                        description = f"QC: Toggle Footswitch {fs_char}"
                        midi_sequence = [{"type": "control_change", "channel": channel, "control": control, "value": 127}]
                elif value.startswith(settings['scene_prefix']):
                    sc_char = value.replace(settings['scene_prefix'], '').strip().upper()
                    if 'A' <= sc_char <= 'H':
                        scene_val = ord(sc_char) - ord('A')
                        description = f"QC: Select Scene {sc_char}"
                        midi_sequence = [{"type": "control_change", "channel": channel, "control": 43, "value": scene_val}]
                else:
                    patch_num_str = ''.join(filter(str.isdigit, value))
                    patch_char = ''.join(filter(str.isalpha, value)).upper()
                    if patch_num_str and 'A' <= patch_char <= 'H':
                        patch_num, patch_letter_val = int(patch_num_str), ord(patch_char) - ord('A')
                        preset_index = (patch_num - 1) * 8 + patch_letter_val
                        bank, program = (1 if preset_index > 127 else 0), preset_index % 128
                        description = f"QC: Setlist {setlist_number + 1}, Patch {patch_num}{patch_char}"
                        midi_sequence = [
                            {"type": "control_change", "channel": channel, "control": 0, "value": bank},
                            {"type": "control_change", "channel": channel, "control": 32, "value": setlist_number},
                            {"type": "program_change", "channel": channel, "program": program}
                        ]
                if midi_sequence:
                    temp_mappings.append({"description": description, "midi_sequence": midi_sequence})
            except Exception as e:
                print(f"Warning: Could not parse row value '{value}'. Error: {e}")
        
        sanitized_title = song_title.lower().replace(' ', '_').replace('/', '_')
        for i, temp_map in enumerate(temp_mappings):
            # osc_address = f"{settings['osc_prefix']}/{sanitized_title}/{i+1}_of_{len(temp_mappings)}"
            osc_address = f"{settings['osc_prefix']}/{sanitized_title}/{i+1}"
            generated_mappings.append({"id": uuid.uuid4().hex, "osc_address": osc_address, **temp_map})
    except Exception as e:
        raise e
    return generated_mappings