document.addEventListener("DOMContentLoaded", () => {
  // --- CONFIGURATION ---
  const CURRENT_ADDR = window.location.origin;
  const API_PORT = "3001";
  const BASE_ADDR =
    CURRENT_ADDR.lastIndexOf(":") !== -1
      ? CURRENT_ADDR.slice(0, CURRENT_ADDR.lastIndexOf(":"))
      : CURRENT_ADDR;
  const API_BASE_URL = BASE_ADDR + ":" + API_PORT;
  console.log(`Current URL: ${CURRENT_ADDR} | API URL (derived): ${API_BASE_URL}`);

  // DOM Elements
  const serverIpElement = document.getElementById("server-ip");
  const midiInputSelect = document.getElementById("midi-input");
  const midiOutputSelect = document.getElementById("midi-output");
  const saveAndRestartBtn = document.getElementById("save-and-restart-btn");
  const restartOverlay = document.getElementById("restart-overlay");
  const mappingsTable = document.getElementById("mappings-table");
  const showAddMappingFormBtn = document.getElementById("show-add-mapping-form-btn");
  const addMappingDialog = document.getElementById("add-mapping-dialog");
  const addMappingForm = document.getElementById("add-mapping-form");
  const cancelAddMappingBtn = document.getElementById("cancel-add-mapping-btn");
  const deleteSelectedBtn = document.getElementById("delete-selected-btn");
  const selectAllCheckbox = document.getElementById("select-all-checkbox");
  const mappingSearchInput = document.getElementById("mapping-search-input");

  // OSC Relay Elements
  const oscRelayMode = document.getElementById('osc-relay-mode');
  const broadcastSettings = document.getElementById('broadcast-settings');

  // Mapping Type Elements
  const mappingType = document.getElementById('mapping-type');
  const midiMappingSection = document.getElementById('midi-mapping-section');
  const oscMappingSection = document.getElementById('osc-mapping-section');

  // OSC Command Elements
  const oscCommandsContainer = document.getElementById('osc-commands-container');
  const addOscCommandBtn = document.getElementById('add-osc-command-btn');

  let allMappings = [];
  let isEditMode = false;
  let editingMappingId = null;

  // Initialize page with proper error handling and debugging
  console.log('Starting client initialization...');
  
  // Load configuration first, then UI elements
  Promise.all([
    loadServerIP(),
    loadMIDIPorts(),
    loadConfig(),
    loadOscRelaySettings()
  ]).then(() => {
    console.log('All initial data loaded, loading mappings...');
    loadMappings();
  }).catch(error => {
    console.error('Error during initialization:', error);
    // Still try to load mappings even if other things fail
    loadMappings();
  });
  
  setupEventListeners();

  function loadServerIP() {
    console.log('Loading server IP...');
    return fetch(`${API_BASE_URL}/api/system/ip`)
      .then(response => response.json())
      .then(data => {
        console.log('Server IP response:', data);
        if (data.ip_address) {
          serverIpElement.textContent = data.ip_address;
          console.log('Set server IP to:', data.ip_address);
        }
      })
      .catch(error => {
        console.error("Error loading server IP:", error);
        throw error;
      });
  }

  function loadMIDIPorts() {
    fetch(`${API_BASE_URL}/api/midi-ports?_=${Date.now()}`)
      .then(response => response.json())
      .then(data => {
        populateSelect(midiInputSelect, data.inputs);
        populateSelect(midiOutputSelect, data.outputs);
      })
      .catch(error => console.error("Error loading MIDI ports:", error));
  }

  function populateSelect(selectElement, options) {
    selectElement.innerHTML = '<option value="">-- None --</option>';
    options.forEach(option => {
      const optionElement = document.createElement("option");
      optionElement.value = option;
      optionElement.textContent = option;
      selectElement.appendChild(optionElement);
    });
  }

  function loadConfig() {
    console.log('Loading MIDI config...');
    return fetch(`${API_BASE_URL}/api/config?_=${Date.now()}`)
      .then(response => response.json())
      .then(config => {
        console.log('MIDI config response:', config);
        midiInputSelect.value = config.midi_input_name || "";
        midiOutputSelect.value = config.midi_output_name || "";
        console.log('Set MIDI values:', config.midi_input_name, config.midi_output_name);
      })
      .catch(error => {
        console.error("Error loading config:", error);
        throw error;
      });
  }

  function loadOscRelaySettings() {
    console.log('Loading OSC relay settings...');
    return fetch(`${API_BASE_URL}/api/config?_=${Date.now()}`)
      .then(response => response.json())
      .then(config => {
        console.log('Loaded OSC relay config:', config);
        const relayMode = config.osc_relay_mode || 'zeroconf';
        const broadcastIp = config.osc_broadcast_ip || '0.0.0.0';
        const broadcastPort = config.osc_broadcast_port || 9000;

        console.log(`Setting OSC relay values: mode=${relayMode}, ip=${broadcastIp}, port=${broadcastPort}`);
        
        const relayModeElement = document.getElementById('osc-relay-mode');
        const broadcastIpElement = document.getElementById('broadcast-ip');
        const broadcastPortElement = document.getElementById('broadcast-port');
        
        if (relayModeElement) {
          relayModeElement.value = relayMode;
          console.log('Set relay mode element value to:', relayModeElement.value);
        } else {
          console.error('Could not find osc-relay-mode element');
        }
        
        if (broadcastIpElement) {
          broadcastIpElement.value = broadcastIp;
          console.log('Set broadcast IP element value to:', broadcastIpElement.value);
        } else {
          console.error('Could not find broadcast-ip element');
        }
        
        if (broadcastPortElement) {
          broadcastPortElement.value = broadcastPort;
          console.log('Set broadcast port element value to:', broadcastPortElement.value);
        } else {
          console.error('Could not find broadcast-port element');
        }

        // Show/hide broadcast settings
        if (relayMode === 'broadcast') {
          broadcastSettings.classList.remove('hidden');
          console.log('Showing broadcast settings');
        } else {
          broadcastSettings.classList.add('hidden');
          console.log('Hiding broadcast settings');
        }
      })
      .catch(error => {
        console.error('Error loading OSC relay settings:', error);
        throw error;
      });
  }

  function loadMappings() {
    fetch(`${API_BASE_URL}/api/config`)
      .then(response => response.json())
      .then(config => {
        allMappings = config.osc_mappings || [];
        renderMappingsTable(allMappings);
      })
      .catch(error => console.error("Error loading mappings:", error));
  }

  function renderMappingsTable(mappings) {
    const tbody = mappingsTable.querySelector("tbody");
    tbody.innerHTML = "";

    mappings.forEach(mapping => {
      const row = document.createElement("tr");
      const mappingTypeValue = mapping.mapping_type || 'midi';
      const typeDisplay = mappingTypeValue === 'osc' ? 'OSC→OSC' : 'OSC→MIDI';

      row.innerHTML = `
                <td class="checkbox-cell">
                    <input type="checkbox" class="mapping-checkbox" data-id="${mapping.id}" />
                </td>
                <td>${mapping.osc_address}</td>
                <td>${mapping.description || "No description"}</td>
                <td><span class="mapping-type-badge ${mappingTypeValue}">${typeDisplay}</span></td>
                <td>
                    <button class="edit-mapping-btn" data-id="${mapping.id}">Edit</button>
                    <button class="delete-mapping-btn danger" data-id="${mapping.id}">Delete</button>
                </td>
            `;
      tbody.appendChild(row);
    });

    updateDeleteButtonVisibility();
  }

  function setupEventListeners() {
    // OSC Relay Mode Toggle
    oscRelayMode.addEventListener('change', function () {
      if (this.value === 'broadcast') {
        broadcastSettings.classList.remove('hidden');
      } else {
        broadcastSettings.classList.add('hidden');
      }
    });

    // Mapping Type Toggle
    mappingType.addEventListener('change', function () {
      if (this.value === 'osc') {
        midiMappingSection.classList.add('hidden');
        oscMappingSection.classList.remove('hidden');
      } else {
        midiMappingSection.classList.remove('hidden');
        oscMappingSection.classList.add('hidden');
      }
    });

    // Save and Restart
    saveAndRestartBtn.addEventListener("click", saveConfigAndRestart);

    // Mapping Management
    showAddMappingFormBtn.addEventListener("click", () => {
      resetMappingForm();
      addMappingDialog.showModal();
    });

    cancelAddMappingBtn.addEventListener("click", () => {
      addMappingDialog.close();
    });

    addMappingForm.addEventListener("submit", handleMappingFormSubmit);

    // Search functionality
    mappingSearchInput.addEventListener("input", handleMappingSearch);

    // Select all checkbox
    selectAllCheckbox.addEventListener("change", handleSelectAll);

    // Delete selected
    deleteSelectedBtn.addEventListener("click", handleDeleteSelected);

    // Dynamic category selection
    document.getElementById("mapping-category").addEventListener("change", handleCategoryChange);

    // Table event delegation
    mappingsTable.addEventListener("click", handleTableClick);
    mappingsTable.addEventListener("change", handleTableChange);

    // OSC Command Management
    addOscCommandBtn.addEventListener('click', function () {
      const newRow = createOscCommandRow();
      oscCommandsContainer.appendChild(newRow);
      updateRemoveButtons();
    });

    // Initialize remove button visibility
    updateRemoveButtons();

    // File upload handlers
    setupFileUploadHandlers();

    // Song importer
    setupSongImporter();
  }

  function updateRemoveButtons() {
    const rows = oscCommandsContainer.querySelectorAll('.osc-command-row');
    rows.forEach((row, index) => {
      const removeBtn = row.querySelector('.remove-osc-command');
      if (rows.length > 1) {
        removeBtn.classList.remove('hidden');
      } else {
        removeBtn.classList.add('hidden');
      }
    });
  }

  function createOscCommandRow() {
    const row = document.createElement('div');
    row.className = 'osc-command-row';
    row.innerHTML = `
            <input type="text" class="osc-command-address" placeholder="/cue/1/start" />
            <input type="text" class="osc-command-args" placeholder="1.0 (optional args)" />
            <button type="button" class="remove-osc-command">Remove</button>
        `;

    row.querySelector('.remove-osc-command').addEventListener('click', function () {
      row.remove();
      updateRemoveButtons();
    });

    return row;
  }

  function saveConfigAndRestart() {
    const config = {
      midi_input_name: midiInputSelect.value || null,
      midi_output_name: midiOutputSelect.value || null,
      osc_relay_mode: document.getElementById('osc-relay-mode').value,
      osc_broadcast_ip: document.getElementById('broadcast-ip').value,
      osc_broadcast_port: parseInt(document.getElementById('broadcast-port').value)
    };

    fetch(`${API_BASE_URL}/api/config`)
      .then(response => response.json())
      .then(currentConfig => {
        const updatedConfig = { ...currentConfig, ...config };
        return fetch(`${API_BASE_URL}/api/config`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(updatedConfig)
        });
      })
      .then(() => {
        showRestartOverlay();
        return fetch(`${API_BASE_URL}/api/system/restart`, { method: "POST" });
      })
      .catch(error => {
        console.error("Error saving config:", error);
        alert("Error saving configuration. Please try again.");
      });
  }

  function showRestartOverlay() {
    restartOverlay.classList.remove("hidden");
    setTimeout(() => {
      window.location.reload();
    }, 5000);
  }

  function resetMappingForm() {
    isEditMode = false;
    editingMappingId = null;
    addMappingForm.reset();
    document.getElementById("dialog-title").textContent = "New OSC Mapping";
    document.getElementById("dialog-submit-btn").textContent = "Create Mapping";

    // Reset form state
    mappingType.value = 'midi';
    midiMappingSection.classList.remove('hidden');
    oscMappingSection.classList.add('hidden');

    // Reset OSC commands to single row
    oscCommandsContainer.innerHTML = `
            <div class="osc-command-row">
                <input type="text" class="osc-command-address" placeholder="/cue/1/start" />
                <input type="text" class="osc-command-args" placeholder="1.0 (optional args)" />
                <button type="button" class="remove-osc-command hidden">Remove</button>
            </div>
        `;

    // Re-attach event listeners to the new row
    const removeBtn = oscCommandsContainer.querySelector('.remove-osc-command');
    removeBtn.addEventListener('click', function () {
      removeBtn.closest('.osc-command-row').remove();
      updateRemoveButtons();
    });

    hideAllCategoryFields();
  }

  function handleMappingFormSubmit(e) {
    e.preventDefault();

    const oscAddress = document.getElementById('osc-address').value;
    const mappingTypeValue = document.getElementById('mapping-type').value;

    let mappingData = {
      osc_address: oscAddress,
      mapping_type: mappingTypeValue
    };

    if (mappingTypeValue === 'osc') {
      // Handle OSC-to-OSC mapping
      const description = document.getElementById('osc-description').value || 'OSC Relay';
      const oscCommands = [];

      const commandRows = oscCommandsContainer.querySelectorAll('.osc-command-row');
      commandRows.forEach(row => {
        const address = row.querySelector('.osc-command-address').value.trim();
        const argsStr = row.querySelector('.osc-command-args').value.trim();

        if (address) {
          const command = { address: address };

          // Parse arguments if provided
          if (argsStr) {
            try {
              // Simple parsing - split by spaces and try to convert numbers
              const args = argsStr.split(/\s+/).map(arg => {
                // Try to parse as number, otherwise keep as string
                const num = parseFloat(arg);
                return isNaN(num) ? arg : num;
              });
              command.args = args;
            } catch (e) {
              command.args = [argsStr]; // Fallback to single string
            }
          }

          oscCommands.push(command);
        }
      });

      if (oscCommands.length === 0) {
        alert('Please add at least one OSC command.');
        return;
      }

      mappingData.description = description;
      mappingData.osc_sequence = oscCommands;

    } else {
      // Handle OSC-to-MIDI mapping
      const category = document.getElementById('mapping-category').value;
      if (!category) {
        alert('Please select an action category.');
        return;
      }

      const midiData = generateMidiSequence(category);
      if (!midiData) {
        alert('Error generating MIDI sequence. Please check your inputs.');
        return;
      }

      mappingData.description = midiData.description;
      mappingData.midi_sequence = midiData.midi_sequence;
    }

    // Submit the mapping
    const url = isEditMode ? `${API_BASE_URL}/api/mappings/${editingMappingId}` : `${API_BASE_URL}/api/mappings`;
    const method = isEditMode ? 'PUT' : 'POST';

    console.log(`Submitting mapping: ${method} ${url}`, mappingData);

    fetch(url, {
      method: method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(mappingData)
    })
      .then(response => {
        console.log('Response status:', response.status);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
      })
      .then(data => {
        console.log('Mapping saved:', data);
        loadMappings(); // Refresh the table
        addMappingDialog.close();
      })
      .catch(error => {
        console.error('Error saving mapping:', error);
        alert(`Error saving mapping: ${error.message}. Please try again.`);
      });
  }

  function generateMidiSequence(category) {
    const channel = 1; // Default channel

    switch (category) {
      case "patch":
        const setlist = parseInt(document.getElementById("patch-setlist").value) - 1;
        const patchNumber = parseInt(document.getElementById("patch-number").value);
        const patchLetter = parseInt(document.getElementById("patch-letter").value);
        const presetIndex = (patchNumber - 1) * 8 + patchLetter;
        const bank = presetIndex > 127 ? 1 : 0;
        const program = presetIndex % 128;

        return {
          description: `QC: Setlist ${setlist + 1}, Patch ${patchNumber}${String.fromCharCode(65 + patchLetter)}`,
          midi_sequence: [
            { type: "control_change", channel: channel, control: 0, value: bank },
            { type: "control_change", channel: channel, control: 32, value: setlist },
            { type: "program_change", channel: channel, program: program }
          ]
        };

      case "scene":
        const sceneValue = parseInt(document.getElementById("scene-select").value);
        return {
          description: `QC: Select Scene ${String.fromCharCode(65 + sceneValue)}`,
          midi_sequence: [
            { type: "control_change", channel: channel, control: 43, value: sceneValue }
          ]
        };

      case "footswitch":
        const fsControl = parseInt(document.getElementById("footswitch-select").value);
        const fsLetter = String.fromCharCode(65 + (fsControl - 35));
        return {
          description: `QC: Toggle Footswitch ${fsLetter}`,
          midi_sequence: [
            { type: "control_change", channel: channel, control: fsControl, value: 127 }
          ]
        };

      case "mode_view":
        return generateModeViewSequence(document.getElementById("mode-view-select").value, channel);

      case "looper":
        return generateLooperSequence(document.getElementById("looper-select").value, channel);

      default:
        return null;
    }
  }

  function generateModeViewSequence(action, channel) {
    const sequences = {
      mode_preset: { description: "QC: Switch to Preset Mode", midi_sequence: [{ type: "control_change", channel, control: 71, value: 0 }] },
      mode_scene: { description: "QC: Switch to Scene Mode", midi_sequence: [{ type: "control_change", channel, control: 71, value: 1 }] },
      mode_stomp: { description: "QC: Switch to Stomp Mode", midi_sequence: [{ type: "control_change", channel, control: 71, value: 2 }] },
      tuner_on: { description: "QC: Turn Tuner On", midi_sequence: [{ type: "control_change", channel, control: 68, value: 127 }] },
      tuner_off: { description: "QC: Turn Tuner Off", midi_sequence: [{ type: "control_change", channel, control: 68, value: 0 }] },
      gig_view_on: { description: "QC: Turn Gig View On", midi_sequence: [{ type: "control_change", channel, control: 72, value: 127 }] },
      gig_view_off: { description: "QC: Turn Gig View Off", midi_sequence: [{ type: "control_change", channel, control: 72, value: 0 }] }
    };
    return sequences[action] || null;
  }

  function generateLooperSequence(action, channel) {
    const sequences = {
      rec_stop: { description: "QC: Looper Record/Overdub/Stop", midi_sequence: [{ type: "control_change", channel, control: 61, value: 127 }] },
      play_stop: { description: "QC: Looper Play/Stop", midi_sequence: [{ type: "control_change", channel, control: 62, value: 127 }] },
      undo_redo: { description: "QC: Looper Undo/Redo", midi_sequence: [{ type: "control_change", channel, control: 63, value: 127 }] },
      half_speed: { description: "QC: Looper Toggle Half Speed", midi_sequence: [{ type: "control_change", channel, control: 64, value: 127 }] },
      reverse: { description: "QC: Looper Toggle Reverse", midi_sequence: [{ type: "control_change", channel, control: 65, value: 127 }] },
      one_shot: { description: "QC: Looper Toggle One Shot", midi_sequence: [{ type: "control_change", channel, control: 66, value: 127 }] },
      looper_menu_open: { description: "QC: Open Looper Menu", midi_sequence: [{ type: "control_change", channel, control: 67, value: 127 }] },
      looper_menu_close: { description: "QC: Close Looper Menu", midi_sequence: [{ type: "control_change", channel, control: 67, value: 0 }] }
    };
    return sequences[action] || null;
  }

  function handleCategoryChange() {
    const category = document.getElementById("mapping-category").value;
    hideAllCategoryFields();
    if (category) {
      const categoryDiv = document.getElementById(`category-${category}`);
      if (categoryDiv) {
        categoryDiv.classList.remove("hidden");
      }
    }
  }

  function hideAllCategoryFields() {
    const categoryDivs = document.querySelectorAll("#dynamic-fields-container > div");
    categoryDivs.forEach(div => div.classList.add("hidden"));
  }

  function handleMappingSearch() {
    const searchTerm = mappingSearchInput.value.toLowerCase();
    const filteredMappings = allMappings.filter(mapping =>
      mapping.osc_address.toLowerCase().includes(searchTerm) ||
      (mapping.description && mapping.description.toLowerCase().includes(searchTerm))
    );
    renderMappingsTable(filteredMappings);
  }

  function handleSelectAll() {
    const checkboxes = document.querySelectorAll(".mapping-checkbox");
    checkboxes.forEach(checkbox => {
      checkbox.checked = selectAllCheckbox.checked;
    });
    updateDeleteButtonVisibility();
  }

  function handleTableClick(e) {
    if (e.target.classList.contains("edit-mapping-btn")) {
      const mappingId = e.target.dataset.id;
      editMapping(mappingId);
    } else if (e.target.classList.contains("delete-mapping-btn")) {
      const mappingId = e.target.dataset.id;
      deleteMapping(mappingId);
    }
  }

  function handleTableChange(e) {
    if (e.target.classList.contains("mapping-checkbox")) {
      updateDeleteButtonVisibility();
    }
  }

  function updateDeleteButtonVisibility() {
    const checkedBoxes = document.querySelectorAll(".mapping-checkbox:checked");
    if (checkedBoxes.length > 0) {
      deleteSelectedBtn.classList.remove("hidden");
    } else {
      deleteSelectedBtn.classList.add("hidden");
    }
  }

  function editMapping(mappingId) {
    const mapping = allMappings.find(m => m.id === mappingId);
    if (!mapping) return;

    isEditMode = true;
    editingMappingId = mappingId;

    document.getElementById("dialog-title").textContent = "Edit OSC Mapping";
    document.getElementById("dialog-submit-btn").textContent = "Update Mapping";
    document.getElementById("osc-address").value = mapping.osc_address;

    const mappingTypeValue = mapping.mapping_type || 'midi';
    document.getElementById('mapping-type').value = mappingTypeValue;

    if (mappingTypeValue === 'osc') {
      midiMappingSection.classList.add('hidden');
      oscMappingSection.classList.remove('hidden');

      document.getElementById('osc-description').value = mapping.description || '';

      // Populate OSC commands
      oscCommandsContainer.innerHTML = '';
      const oscSequence = mapping.osc_sequence || [];

      if (oscSequence.length === 0) {
        // Add empty row if no commands
        const row = createOscCommandRow();
        oscCommandsContainer.appendChild(row);
      } else {
        oscSequence.forEach(command => {
          const row = createOscCommandRow();
          row.querySelector('.osc-command-address').value = command.address || '';
          row.querySelector('.osc-command-args').value = command.args ? command.args.join(' ') : '';
          oscCommandsContainer.appendChild(row);
        });
      }
      updateRemoveButtons();
    } else {
      midiMappingSection.classList.remove('hidden');
      oscMappingSection.classList.add('hidden');
      // Handle MIDI mapping editing (existing logic)
    }

    addMappingDialog.showModal();
  }

  function deleteMapping(mappingId) {
    if (!confirm("Are you sure you want to delete this mapping?")) return;

    fetch(`${API_BASE_URL}/api/mappings/${mappingId}`, { method: "DELETE" })
      .then(() => loadMappings())
      .catch(error => {
        console.error("Error deleting mapping:", error);
        alert("Error deleting mapping. Please try again.");
      });
  }

  function handleDeleteSelected() {
    const checkedBoxes = document.querySelectorAll(".mapping-checkbox:checked");
    const idsToDelete = Array.from(checkedBoxes).map(cb => cb.dataset.id);

    if (idsToDelete.length === 0) return;

    if (!confirm(`Are you sure you want to delete ${idsToDelete.length} mapping(s)?`)) return;

    fetch(`${API_BASE_URL}/api/mappings`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: idsToDelete })
    })
      .then(() => {
        loadMappings();
        selectAllCheckbox.checked = false;
      })
      .catch(error => {
        console.error("Error deleting mappings:", error);
        alert("Error deleting mappings. Please try again.");
      });
  }

  function setupFileUploadHandlers() {
    // Config upload
    const uploadConfigInput = document.getElementById("upload-config-input");
    const uploadFilename = document.getElementById("upload-filename");

    uploadConfigInput.addEventListener("change", function () {
      uploadFilename.textContent = this.files[0] ? this.files[0].name : "No file selected.";
      if (this.files[0]) {
        uploadConfig(this.files[0]);
      }
    });

    // Mappings upload
    const uploadMappingsInput = document.getElementById("upload-mappings-input");
    const uploadMappingsFilename = document.getElementById("upload-mappings-filename");

    uploadMappingsInput.addEventListener("change", function () {
      uploadMappingsFilename.textContent = this.files[0] ? this.files[0].name : "No file selected.";
      if (this.files[0]) {
        uploadMappings(this.files[0]);
      }
    });

    // Config download
    document.getElementById("download-config-btn").addEventListener("click", () => {
      window.open(`${API_BASE_URL}/api/config/download`, "_blank");
    });
  }

  function uploadConfig(file) {
    const formData = new FormData();
    formData.append("file", file);

    fetch(`${API_BASE_URL}/api/config/upload`, {
      method: "POST",
      body: formData
    })
      .then(response => response.json())
      .then(data => {
        alert(data.message || "Configuration uploaded successfully.");
        loadConfig();
        loadMappings();
      })
      .catch(error => {
        console.error("Error uploading config:", error);
        alert("Error uploading configuration. Please try again.");
      });
  }

  function uploadMappings(file) {
    const reader = new FileReader();
    reader.onload = function (e) {
      try {
        const mappings = JSON.parse(e.target.result);
        fetch(`${API_BASE_URL}/api/mappings/upload-json`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(mappings)
        })
          .then(response => response.json())
          .then(data => {
            alert(data.message || "Mappings uploaded successfully.");
            loadMappings();
          })
          .catch(error => {
            console.error("Error uploading mappings:", error);
            alert("Error uploading mappings. Please try again.");
          });
      } catch (error) {
        alert("Invalid JSON file. Please check the file format.");
      }
    };
    reader.readAsText(file);
  }

  function setupSongImporter() {
    const processSongBtn = document.getElementById("process-song-btn");

    processSongBtn.addEventListener("click", function () {
      const songTitle = document.getElementById("song-title").value;
      const setlistNumber = document.getElementById("song-setlist").value;
      const csvFile = document.getElementById("song-csv-input").files[0];

      if (!songTitle || !setlistNumber || !csvFile) {
        alert("Please fill in all fields and select a CSV file.");
        return;
      }

      const formData = new FormData();
      formData.append("file", csvFile);
      formData.append("song_title", songTitle);
      formData.append("setlist_number", setlistNumber);

      fetch(`${API_BASE_URL}/api/songs/upload`, {
        method: "POST",
        body: formData
      })
        .then(response => response.json())
        .then(data => {
          alert(data.message || "Song processed successfully.");
          loadMappings();
          // Reset form
          document.getElementById("song-title").value = "";
          document.getElementById("song-setlist").value = "1";
          document.getElementById("song-csv-input").value = "";
        })
        .catch(error => {
          console.error("Error processing song:", error);
          alert("Error processing song. Please try again.");
        });
    });
  }
});