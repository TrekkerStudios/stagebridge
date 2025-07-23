/**
 * Parses a song CSV string and generates a list of OSC mappings.
 * @param {string} csvString - The content of the CSV file as a string.
 * @param {string} songTitle - The title of the song.
 * @param {number} setlistNumber - The 0-indexed setlist number.
 * @param {object} settings - Parser settings.
 * @param {function} [onWarning] - Optional callback for warnings.
 * @returns {Array<object>} An array of generated mapping objects.
 */
async function parseSongCsvJs(
  csvString,
  songTitle,
  setlistNumber,
  settings,
  onWarning,
) {
  const generated = [];
  const lines = csvString.trim().split("\n");
  if (lines.length === 0) return generated;

  const headers = lines[0].split(",").map((h) => h.trim());
  const columnIndex = headers.indexOf(settings.column_name);
  if (columnIndex === -1) {
    throw new Error(
      `Column '${settings.column_name}' not found in CSV for '${songTitle}'. Available columns: ${headers.join(", ")}`,
    );
  }

  let lastValue = null;
  const tempMappings = [];

  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;

    const values = line.split(",").map((v) => v.trim());
    if (values.length <= columnIndex) continue;

    const value = values[columnIndex].trim();

    if (!value || value === lastValue) continue;
    lastValue = value;

    let midi_sequence = [];
    let description = "";
    const channel = 1;

    try {
      if (value.startsWith(settings.footswitch_prefix)) {
        const fs_char = value
          .replace(settings.footswitch_prefix, "")
          .trim()
          .toUpperCase();
        if (fs_char.length === 1 && fs_char >= "A" && fs_char <= "H") {
          const control = 35 + (fs_char.charCodeAt(0) - "A".charCodeAt(0));
          description = `QC: Toggle Footswitch ${fs_char}`;
          midi_sequence = [
            { type: "control_change", channel: channel, control: control, value: 127 },
          ];
        }
      } else if (value.startsWith(settings.scene_prefix)) {
        const sc_char = value
          .replace(settings.scene_prefix, "")
          .trim()
          .toUpperCase();
        if (sc_char.length === 1 && sc_char >= "A" && sc_char <= "H") {
          const scene_val = sc_char.charCodeAt(0) - "A".charCodeAt(0);
          description = `QC: Select Scene ${sc_char}`;
          midi_sequence = [
            { type: "control_change", channel: channel, control: 43, value: scene_val },
          ];
        }
      } else {
        const patchNumMatch = value.match(/\d+/);
        const patchCharMatch = value.match(/[a-zA-Z]/);

        if (patchNumMatch && patchCharMatch) {
          const patchNum = parseInt(patchNumMatch[0]);
          const patchChar = patchCharMatch[0].toUpperCase();

          if (patchNum >= 1 && patchChar >= "A" && patchChar <= "H") {
            const patchLetterVal = patchChar.charCodeAt(0) - "A".charCodeAt(0);
            const presetIndex = (patchNum - 1) * 8 + patchLetterVal;
            const bank = presetIndex > 127 ? 1 : 0;
            const program = presetIndex % 128;
            description = `QC: Setlist ${setlistNumber + 1}, Patch ${patchNum}${patchChar}`;
            midi_sequence = [
              { type: "control_change", channel: channel, control: 0, value: bank },
              { type: "control_change", channel: channel, control: 32, value: setlistNumber },
              { type: "program_change", channel: channel, program: program },
            ];
          }
        }
      }
      if (midi_sequence.length > 0) {
        tempMappings.push({ description, midi_sequence });
      }
    } catch (e) {
      if (onWarning) {
        onWarning(
          `Warning for song '${songTitle}': Could not parse row value '${value}'. Error: ${e.message}`,
        );
      }
    }
  }

  const sanitizedTitle = songTitle.toLowerCase().replace(/[^a-z0-9_]/g, "_").replace(/_+/g, "_");
  for (let i = 0; i < tempMappings.length; i++) {
    const tempMap = tempMappings[i];
    const osc_address = `${settings.osc_prefix}/${sanitizedTitle}/${i + 1}`;
    generated.push({ id: crypto.randomUUID().replace(/-/g, ""), osc_address, ...tempMap });
  }
  return generated;
}

document.addEventListener("DOMContentLoaded", () => {
  let generatedMappings = [];

  // --- DOM ELEMENTS ---
  const manualMappingForm = document.getElementById("manual-mapping-form");
  const manualOscAddressInput = document.getElementById("manual-osc-address");
  const manualMappingCategorySelect = document.getElementById("manual-mapping-category");
  const manualDynamicFieldsContainer = document.getElementById("manual-dynamic-fields-container");
  const addManualMappingBtn = document.getElementById("add-manual-mapping-btn");

  const csvFilesInput = document.getElementById("csv-files-input");
  const selectedFilesDisplay = document.getElementById("selected-files-display");
  const parserColumnNameInput = document.getElementById("parser-column-name");
  const parserFootswitchPrefixInput = document.getElementById("parser-footswitch-prefix");
  const parserScenePrefixInput = document.getElementById("parser-scene-prefix");
  const parserOscPrefixInput = document.getElementById("parser-osc-prefix");
  const startSetlistNumberInput = document.getElementById("start-setlist-number");
  const processCsvBtn = document.getElementById("process-csv-btn");
  const csvErrorMessage = document.getElementById("csv-error-message");

  const generatedMappingsOutput = document.getElementById("generated-mappings-output");
  const downloadAllBtn = document.getElementById("download-all-btn");
  const clearAllBtn = document.getElementById("clear-all-btn");
  const totalMappingsCount = document.getElementById("total-mappings-count");

  // --- UTILITY FUNCTIONS ---

  function generateMappingFromForm(prefix = "manual-") {
    const osc_address = document.getElementById(`${prefix}osc-address`).value;
    const category = document.getElementById(`${prefix}mapping-category`).value;

    if (!osc_address || !category) return null;

    let midi_sequence = [];
    let description = "";
    const channel = 1;

    switch (category) {
      case "patch": {
        const setlist =
          parseInt(document.getElementById(`${prefix}patch-setlist`).value) - 1;
        const patchNum = parseInt(
          document.getElementById(`${prefix}patch-number`).value,
        );
        const patchLetterVal = parseInt(
          document.getElementById(`${prefix}patch-letter`).value,
        );
        const patchLetterChar = String.fromCharCode(65 + patchLetterVal);
        const presetIndex = (patchNum - 1) * 8 + patchLetterVal;
        const bank = presetIndex > 127 ? 1 : 0;
        const program = presetIndex % 128;
        description = `QC: Setlist ${setlist + 1}, Patch ${patchNum}${patchLetterChar}`;
        midi_sequence = [
          { type: "control_change", channel, control: 0, value: bank },
          { type: "control_change", channel, control: 32, value: setlist },
          { type: "program_change", channel, program },
        ];
        break;
      }
      case "scene": {
        const sceneVal = parseInt(
          document.getElementById(`${prefix}scene-select`).value,
        );
        const sceneChar = String.fromCharCode(65 + sceneVal);
        description = `QC: Select Scene ${sceneChar}`;
        midi_sequence = [
          { type: "control_change", channel, control: 43, value: sceneVal },
        ];
        break;
      }
      case "footswitch": {
        const fsSelect = document.getElementById(`${prefix}footswitch-select`);
        const control = parseInt(fsSelect.value);
        const fsChar = fsSelect.options[fsSelect.selectedIndex].text;
        description = `QC: Toggle Footswitch ${fsChar}`;
        midi_sequence = [
          { type: "control_change", channel, control, value: 127 },
        ];
        break;
      }
      case "mode_view": {
        const select = document.getElementById(`${prefix}mode-view-select`);
        const action = select.value;
        const text = select.options[select.selectedIndex].text;
        description = `QC: ${text}`;
        let control, value;
        switch (action) {
          case "mode_preset":
            (control = 47), (value = 0);
            break;
          case "mode_scene":
            (control = 47), (value = 1);
            break;
          case "mode_stomp":
            (control = 47), (value = 2);
            break;
          case "tuner_on":
            (control = 45), (value = 127);
            break;
          case "tuner_off":
            (control = 45), (value = 0);
            break;
          case "gig_view_on":
            (control = 46), (value = 127);
            break;
          case "gig_view_off":
            (control = 46), (value = 0);
            break;
        }
        midi_sequence = [{ type: "control_change", channel, control, value }];
        break;
      }
      case "looper": {
        const select = document.getElementById(`${prefix}looper-select`);
        const action = select.value;
        const text = select.options[select.selectedIndex].text;
        description = `QC Looper: ${text}`;
        let control,
          value = 127;
        switch (action) {
          case "rec_stop":
            control = 53;
            break;
          case "play_stop":
            control = 54;
            break;
          case "undo_redo":
            control = 56;
            break;
          case "half_speed":
            control = 51;
            break;
          case "reverse":
            control = 55;
            break;
          case "one_shot":
            control = 50;
            break;
          case "looper_menu_open":
            (control = 48), (value = 0);
            break;
          case "looper_menu_close":
            (control = 48), (value = 127);
            break;
        }
        midi_sequence = [{ type: "control_change", channel, control, value }];
        break;
      }
    }
    const id = crypto.randomUUID().replace(/-/g, "");
    return { id, osc_address, description, midi_sequence };
  }

  function renderMappings() {
    generatedMappingsOutput.textContent = JSON.stringify(
      generatedMappings,
      null,
      2,
    );
    totalMappingsCount.textContent = `Total Mappings: ${generatedMappings.length}`;
    downloadAllBtn.disabled = generatedMappings.length === 0;
    clearAllBtn.disabled = generatedMappings.length === 0;
  }

  // --- EVENT HANDLERS ---

  // Manual Mapping Form
  manualMappingCategorySelect.addEventListener("change", () => {
    const selectedCategory = manualMappingCategorySelect.value;
    manualDynamicFieldsContainer
      .querySelectorAll(":scope > div")
      .forEach((div) => div.classList.add("hidden"));
    if (selectedCategory) {
      const sectionToShow = document.getElementById(
        `manual-category-${selectedCategory}`,
      );
      if (sectionToShow) sectionToShow.classList.remove("hidden");
    }
  });

  manualMappingForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const newMapping = generateMappingFromForm("manual-");
    if (newMapping) {
      generatedMappings.push(newMapping);
      renderMappings();
      manualMappingForm.reset();
      manualMappingCategorySelect.dispatchEvent(new Event("change"));
    } else {
      alert("Please fill out all required fields for the manual mapping.");
    }
  });

  // CSV Importer
  csvFilesInput.addEventListener("change", (e) => {
    selectedFilesDisplay.innerHTML = "";
    if (e.target.files.length > 0) {
      for (const file of e.target.files) {
        const p = document.createElement("p");
        p.textContent = file.name;
        selectedFilesDisplay.appendChild(p);
      }
    } else {
      selectedFilesDisplay.textContent = "No files selected.";
    }
    csvErrorMessage.classList.add("hidden");
  });

  processCsvBtn.addEventListener("click", async () => {
    const files = csvFilesInput.files;
    if (files.length === 0) {
      alert("Please select one or more CSV files.");
      return;
    }

    const parserSettings = {
      column_name: parserColumnNameInput.value.trim(),
      footswitch_prefix: parserFootswitchPrefixInput.value.trim(),
      scene_prefix: parserScenePrefixInput.value.trim(),
      osc_prefix: parserOscPrefixInput.value.trim(),
    };

    if (
      !parserSettings.column_name ||
      !parserSettings.footswitch_prefix ||
      !parserSettings.scene_prefix ||
      !parserSettings.osc_prefix
    ) {
      alert("Please fill in all parser settings.");
      return;
    }

    let currentSetlistNumber = parseInt(startSetlistNumberInput.value) - 1;

    csvErrorMessage.classList.add("hidden");
    const newMappingsFromCsv = [];

    const onParserWarning = (message) => {
      csvErrorMessage.textContent = message;
      csvErrorMessage.classList.remove("hidden");
    };

    for (const file of files) {
      const songTitle = file.name.replace(/\.csv$/i, "");
      try {
        const csvString = await file.text();
        const parsed = await parseSongCsvJs(
          csvString,
          songTitle,
          currentSetlistNumber,
          parserSettings,
          onParserWarning,
        );
        newMappingsFromCsv.push(...parsed);
        currentSetlistNumber++;
      } catch (error) {
        console.error(`Error parsing ${file.name}:`, error);
        csvErrorMessage.textContent = `Error parsing ${file.name}: ${error.message}`;
        csvErrorMessage.classList.remove("hidden");
        return;
      }
    }
    generatedMappings.push(...newMappingsFromCsv);
    renderMappings();
    alert(
      `Successfully processed ${files.length} CSVs and added ${newMappingsFromCsv.length} mappings.`,
    );
    csvFilesInput.value = "";
    selectedFilesDisplay.textContent = "No files selected.";
  });

  // Generated Mappings Actions
  downloadAllBtn.addEventListener("click", () => {
    const jsonString = JSON.stringify({ osc_mappings: generatedMappings }, null, 2);
    const blob = new Blob([jsonString], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "stagebridge_mappings.json";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  });

  clearAllBtn.addEventListener("click", () => {
    if (
      confirm("Are you sure you want to clear all generated mappings? This action cannot be undone.")
    ) {
      generatedMappings = [];
      renderMappings();
    }
  });

  // --- INITIAL RENDER ---
  renderMappings();
  manualMappingCategorySelect.dispatchEvent(new Event("change"));
});