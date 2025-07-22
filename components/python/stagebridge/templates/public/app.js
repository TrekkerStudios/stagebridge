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

  // --- DOM ELEMENTS ---
  const midiInputSelect = document.getElementById("midi-input");
  const midiOutputSelect = document.getElementById("midi-output");
  const saveAndRestartBtn = document.getElementById("save-and-restart-btn");
  const mappingsTableBody = document.querySelector("#mappings-table tbody");
  const selectAllCheckbox = document.getElementById("select-all-checkbox");
  const deleteSelectedBtn = document.getElementById("delete-selected-btn");
  const showFormBtn = document.getElementById("show-add-mapping-form-btn");
  const addMappingDialog = document.getElementById("add-mapping-dialog");
  const addMappingForm = document.getElementById("add-mapping-form");
  const cancelFormBtn = document.getElementById("cancel-add-mapping-btn");
  const mappingCategorySelect = document.getElementById("mapping-category");
  const dialogTitle = document.getElementById("dialog-title");
  const dialogSubmitBtn = document.getElementById("dialog-submit-btn");
  const mappingSearchInput = document.getElementById("mapping-search-input");
  const dynamicFieldsContainer = document.getElementById(
    "dynamic-fields-container",
  );
  const downloadConfigBtn = document.getElementById("download-config-btn");
  const uploadConfigInput = document.getElementById("upload-config-input");
  const uploadFilenameSpan = document.getElementById("upload-filename");
  const restartOverlay = document.getElementById("restart-overlay");

  const songTitleInput = document.getElementById("song-title");
  const songSetlistInput = document.getElementById("song-setlist");
  const songCsvInput = document.getElementById("song-csv-input");
  const processSongBtn = document.getElementById("process-song-btn");
  const adminRedirect = document.getElementById("admin-redirect");

  // New elements for uploading mappings only
  const uploadMappingsInput = document.getElementById("upload-mappings-input");
  const uploadMappingsFilenameSpan = document.getElementById("upload-mappings-filename");

  let currentConfig = {};
  let editingMappingId = null;
  const selectedMappingIds = new Set();

  // --- API FUNCTIONS ---
  const fetchAPI = async (endpoint, options = {}) => {
    let url = `${API_BASE_URL}${endpoint}`;
    if (!options.method || options.method.toUpperCase() === "GET") {
      url += `?_=${Date.now()}`;
    }
    try {
      const response = await fetch(url, options);
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(
          errorData.error || `HTTP error! status: ${response.status}`,
        );
      }
      const contentType = response.headers.get("content-type");
      if (contentType && contentType.indexOf("application/json") !== -1) {
        return response.json();
      }
      return { success: true };
    } catch (error) {
      console.error(`Failed to fetch ${endpoint}:`, error);
      alert(`Error communicating with the StageBridge API: ${error.message}`);
      return null;
    }
  };

  const fetchServerIP = async () => {
    const ipElement = document.getElementById('server-ip');

    try {
      const response = await fetch(`${API_BASE_URL}/api/system/ip`);
      const data = await response.json();

      if (response.ok && data.ip_address) {
        ipElement.textContent = data.ip_address;
        ipElement.classList.remove('error');
      } else {
        throw new Error(data.error || 'Unknown error');
      }
    } catch (error) {
      console.error('Failed to fetch server IP:', error);
      ipElement.textContent = 'Unable to determine IP';
      ipElement.classList.add('error');
    }
  };

  // --- INITIALIZATION & UI RENDERING ---
  const loadInitialData = async () => {
    await fetchServerIP();

    const ports = await fetchAPI("/api/midi-ports");
    if (ports) {
      populateSelect(midiInputSelect, ports.inputs);
      populateSelect(midiOutputSelect, ports.outputs);
    }
    const config = await fetchAPI("/api/config");
    if (config) {
      currentConfig = config;
      midiInputSelect.value = currentConfig.midi_input_name || "";
      midiOutputSelect.value = currentConfig.midi_output_name || "";
      renderMappingsTable();
    }
    if (adminRedirect) {
      // Ensure adminRedirect exists before trying to set href
      adminRedirect.href = API_BASE_URL + "/admin" || "/";
    }
  };

  const populateSelect = (select, items) => {
    select.innerHTML = '<option value="">-- Not Selected --</option>';
    if (items) {
      items.forEach((item) => {
        const option = document.createElement("option");
        option.value = item;
        option.textContent = item;
        select.appendChild(option);
      });
    }
  };

  const renderMappingsTable = () => {
    mappingsTableBody.innerHTML = "";
    if (!currentConfig.osc_mappings || !currentConfig.osc_mappings.length) {
      mappingsTableBody.innerHTML =
        '<tr><td colspan="4">No mappings configured.</td></tr>';
      filterMappings();
      return;
    }
    currentConfig.osc_mappings.forEach((m) => {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td class="checkbox-cell">
            <input type="checkbox" class="row-checkbox" data-id="${m.id}" />
        </td>
        <td>${m.osc_address}</td>
        <td>${m.description || "N/A"}</td>
        <td class="actions-cell">
            <button class="edit-btn" data-id="${m.id}">Edit</button>
            <button class="delete-btn" data-id="${m.id}">Delete</button>
        </td>`;
      mappingsTableBody.appendChild(row);

      // Re-check checkboxes for currently selected IDs
      const checkbox = row.querySelector(".row-checkbox");
      if (checkbox && selectedMappingIds.has(m.id)) {
        checkbox.checked = true;
      }
    });
    filterMappings(); // Apply filter after rendering
    updateBulkDeleteButtonState(); // Update button state
    updateSelectAllCheckboxState(); // Update select all checkbox state
  };

  const filterMappings = () => {
    const searchTerm = mappingSearchInput.value.toLowerCase();
    const rows = mappingsTableBody.querySelectorAll("tr");

    rows.forEach((row) => {
      const noMappingsCell = row.querySelector("td[colspan='4']");
      if (noMappingsCell) {
        row.style.display = searchTerm === "" ? "" : "none";
        return;
      }

      const oscAddressCell = row.children[1];
      const descriptionCell = row.children[2];

      const oscAddressText = oscAddressCell
        ? oscAddressCell.textContent.toLowerCase()
        : "";
      const descriptionText = descriptionCell
        ? descriptionCell.textContent.toLowerCase()
        : "";

      if (
        oscAddressText.includes(searchTerm) ||
        descriptionText.includes(searchTerm)
      ) {
        row.style.display = "";
      } else {
        row.style.display = "none";
      }
    });
    updateSelectAllCheckboxState();
  };

  const updateBulkDeleteButtonState = () => {
    if (selectedMappingIds.size > 0) {
      deleteSelectedBtn.classList.remove("hidden");
      deleteSelectedBtn.textContent = `Delete Selected (${selectedMappingIds.size})`;
    } else {
      deleteSelectedBtn.classList.add("hidden");
    }
  };

  const updateSelectAllCheckboxState = () => {
    const visibleCheckboxes = Array.from(
      mappingsTableBody.querySelectorAll(".row-checkbox"),
    ).filter((cb) => cb.closest("tr").style.display !== "none");

    if (visibleCheckboxes.length === 0) {
      selectAllCheckbox.checked = false;
      selectAllCheckbox.indeterminate = false;
      return;
    }

    const allVisibleChecked = visibleCheckboxes.every((cb) => cb.checked);

    if (allVisibleChecked) {
      selectAllCheckbox.checked = true;
      selectAllCheckbox.indeterminate = false;
    } else {
      selectAllCheckbox.checked = false;
      const someVisibleChecked = visibleCheckboxes.some((cb) => cb.checked);
      selectAllCheckbox.indeterminate = someVisibleChecked;
    }
  };

  // --- EVENT HANDLERS ---
  mappingSearchInput.addEventListener("input", filterMappings);

  processSongBtn.addEventListener("click", async () => {
    const songTitle = songTitleInput.value;
    const setlistNumber = songSetlistInput.value;
    const file = songCsvInput.files[0];

    if (!songTitle || !setlistNumber || !file) {
      alert("Please fill out all fields: Song Title, Setlist, and CSV file.");
      return;
    }

    if (
      !confirm(
        `This will add new mappings for the song "${songTitle}". Are you sure?`,
      )
    ) {
      return;
    }

    const formData = new FormData();
    formData.append("song_title", songTitle);
    formData.append("setlist_number", setlistNumber);
    formData.append("file", file);

    try {
      const response = await fetch(`${API_BASE_URL}/api/songs/upload`, {
        method: "POST",
        body: formData,
      });

      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.error || "Failed to process song.");
      }

      alert(result.message);
      songTitleInput.value = "";
      songCsvInput.value = "";
      loadInitialData();
    } catch (error) {
      alert(`Error: ${error.message}`);
    }
  });

  saveAndRestartBtn.addEventListener("click", async () => {
    if (
      !confirm(
        "This will save the current MIDI port selection and restart the service. Are you sure?",
      )
    ) {
      return;
    }
    const newConfig = { ...currentConfig };
    newConfig.midi_input_name = midiInputSelect.value;
    newConfig.midi_output_name = midiOutputSelect.value;
    const saveResult = await fetchAPI("/api/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(newConfig),
    });
    if (!saveResult) {
      alert("Failed to save settings. Restart aborted.");
      return;
    }
    restartOverlay.classList.remove("hidden");
    try {
      await fetchAPI("/api/system/restart", { method: "POST" });
    } catch (error) {
      console.log("Restart command sent. The server is going down.");
    }
    setTimeout(() => {
      location.reload();
    }, 5000);
  });

  mappingsTableBody.addEventListener("click", async (e) => {
    const target = e.target;

    if (target.classList.contains("row-checkbox")) {
      const mappingId = target.dataset.id;
      if (target.checked) {
        selectedMappingIds.add(mappingId);
      } else {
        selectedMappingIds.delete(mappingId);
      }
      updateBulkDeleteButtonState();
      updateSelectAllCheckboxState(); // Update master checkbox state after individual click
    }

    // Handle Delete
    if (target.classList.contains("delete-btn")) {
      const mappingId = target.dataset.id;
      if (confirm("Are you sure you want to delete this mapping?")) {
        // Corrected API call for single delete
        await fetchAPI(`/api/mappings/${mappingId}`, { method: "DELETE" });
        selectedMappingIds.delete(mappingId); // Ensure it's removed from selected
        updateBulkDeleteButtonState();
        loadInitialData();
      }
    }

    // Handle Edit
    if (target.classList.contains("edit-btn")) {
      const mappingId = target.dataset.id;
      const mappingToEdit = currentConfig.osc_mappings.find(
        (m) => m.id === mappingId,
      );
      if (mappingToEdit) {
        editingMappingId = mappingId;
        dialogTitle.textContent = "Edit OSC Mapping";
        dialogSubmitBtn.textContent = "Update Mapping";
        populateFormForEdit(mappingToEdit);
        addMappingDialog.showModal();
      }
    }
  });

  selectAllCheckbox.addEventListener("change", (e) => {
    const isChecked = e.target.checked;
    const allRows = mappingsTableBody.querySelectorAll("tr");

    allRows.forEach((row) => {
      const noMappingsCell = row.querySelector("td[colspan='4']");
      if (noMappingsCell) {
        return; // Skip "No mappings" row
      }

      // Only operate on rows that are not hidden by the filter
      if (row.style.display !== "none") {
        const checkbox = row.querySelector(".row-checkbox");
        if (checkbox) {
          checkbox.checked = isChecked;
          const mappingId = checkbox.dataset.id;
          if (isChecked) {
            selectedMappingIds.add(mappingId);
          } else {
            selectedMappingIds.delete(mappingId);
          }
        }
      }
    });
    updateBulkDeleteButtonState();
    // No need to call updateSelectAllCheckboxState here, as its state is already set by the event.
  });

  deleteSelectedBtn.addEventListener("click", async () => {
    if (selectedMappingIds.size === 0) return;

    if (
      !confirm(
        `Are you sure you want to delete ${selectedMappingIds.size} selected mappings?`,
      )
    ) {
      return;
    }

    // The backend API handles multiple deletes for '/api/mappings', assuming it expects a list of IDs.
    // If not, a loop and individual delete calls would be needed.
    const idsToDelete = Array.from(selectedMappingIds);
    await fetchAPI("/api/mappings", {
      method: "DELETE", // Assuming the backend supports DELETE with a body for multiple IDs
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: idsToDelete }),
    });

    selectedMappingIds.clear();
    updateBulkDeleteButtonState();
    loadInitialData();
  });

  showFormBtn.addEventListener("click", () => {
    editingMappingId = null;
    addMappingForm.reset();
    updateDynamicFields();
    document.getElementById("osc-address").value = ""; // Clear OSC address field
    dialogTitle.textContent = "New OSC Mapping";
    dialogSubmitBtn.textContent = "Create Mapping";
    addMappingDialog.showModal();
  });

  cancelFormBtn.addEventListener("click", () => {
    addMappingDialog.close();
    editingMappingId = null;
  });

  mappingCategorySelect.addEventListener("change", updateDynamicFields);

  function updateDynamicFields() {
    const selectedCategory = mappingCategorySelect.value;
    dynamicFieldsContainer
      .querySelectorAll(":scope > div")
      .forEach((div) => div.classList.add("hidden"));
    if (selectedCategory) {
      const sectionToShow = document.getElementById(
        `category-${selectedCategory}`,
      );
      if (sectionToShow) sectionToShow.classList.remove("hidden");
    }
  }

  addMappingForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const mappingData = generateMappingFromForm();
    if (!mappingData) {
      alert("Please select a category and fill out the required fields.");
      return;
    }

    if (editingMappingId) {
      // Add ID to mappingData for PUT request
      mappingData.id = editingMappingId;
      await fetchAPI(`/api/mappings/${editingMappingId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(mappingData),
      });
    } else {
      await fetchAPI("/api/mappings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(mappingData),
      });
    }

    addMappingDialog.close();
    editingMappingId = null;
    loadInitialData();
  });

  downloadConfigBtn.addEventListener("click", () => {
    const link = document.createElement("a");
    link.href = `${API_BASE_URL}/api/config/download`;
    link.setAttribute("download", "config.json");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  });

  uploadConfigInput.addEventListener("change", async () => {
    const file = uploadConfigInput.files[0];
    if (!file) {
      uploadFilenameSpan.textContent = "No file selected.";
      return;
    }
    uploadFilenameSpan.textContent = `Selected: ${file.name}`;
    if (
      !confirm(
        `Are you sure you want to upload ${file.name}? This will overwrite the current configuration.`,
      )
    ) {
      uploadConfigInput.value = "";
      uploadFilenameSpan.textContent = "No file selected.";
      return;
    }
    const formData = new FormData();
    formData.append("file", file);
    try {
      const response = await fetch(`${API_BASE_URL}/api/config/upload`, {
        method: "POST",
        body: formData,
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Upload failed");
      alert(result.message);
      loadInitialData();
    } catch (error) {
      alert(`Error: ${error.message}`);
    } finally {
      uploadConfigInput.value = "";
      uploadFilenameSpan.textContent = "No file selected.";
    }
  });

  // --- NEW: Upload Mappings Only Event Handler ---
  uploadMappingsInput.addEventListener("change", async () => {
    const file = uploadMappingsInput.files[0];
    if (!file) {
      uploadMappingsFilenameSpan.textContent = "No file selected.";
      return;
    }

    uploadMappingsFilenameSpan.textContent = `Selected: ${file.name}`;

    if (!confirm(`Are you sure you want to upload mappings from ${file.name}? Existing mappings with matching OSC addresses will be overwritten.`)) {
      uploadMappingsInput.value = ""; // Reset the input
      uploadMappingsFilenameSpan.textContent = "No file selected.";
      return;
    }

    try {
      const fileContent = await file.text();
      const mappingsData = JSON.parse(fileContent);

      const response = await fetch(`${API_BASE_URL}/api/mappings/upload-json`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(mappingsData), // Send the parsed JSON directly
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.error || "Upload failed");
      }

      alert(result.message);
      loadInitialData(); // Reload the entire UI with the new mappings
    } catch (error) {
      alert(`Error: ${error.message}`);
    } finally {
      uploadMappingsInput.value = ""; // Reset the input
      uploadMappingsFilenameSpan.textContent = "No file selected.";
    }
  });


  function populateFormForEdit(mapping) {
    addMappingForm.reset();
    document.getElementById("osc-address").value = mapping.osc_address;

    // Use a copy to avoid modifying the original config.
    const midi_sequence_copy = [...mapping.midi_sequence];

    // Determine category from MIDI message (prioritize explicit checks)
    let category = "";
    if (midi_sequence_copy.some(m => m.control === 0 && m.type === 'control_change') &&
      midi_sequence_copy.some(m => m.control === 32 && m.type === 'control_change') &&
      midi_sequence_copy.some(m => m.type === 'program_change')) {
      category = "patch";
    } else if (midi_sequence_copy.some(m => m.control === 43 && m.type === 'control_change')) {
      category = "scene";
    } else if (midi_sequence_copy.some(m => m.control >= 35 && m.control <= 42 && m.type === 'control_change')) {
      category = "footswitch";
    } else if (midi_sequence_copy.some(m => [45, 46, 47].includes(m.control) && m.type === 'control_change')) {
      category = "mode_view";
    } else if (midi_sequence_copy.some(m => [48, 50, 51, 53, 54, 55, 56].includes(m.control) && m.type === 'control_change')) {
      category = "looper";
    }

    mappingCategorySelect.value = category;
    updateDynamicFields();

    // Populate the specific fields for the category
    switch (category) {
      case "patch": {
        const setlistMsg = midi_sequence_copy.find((m) => m.control === 32);
        const bankMsg = midi_sequence_copy.find((m) => m.control === 0);
        const pcMsg = midi_sequence_copy.find(
          (m) => m.type === "program_change",
        );
        const setlist = setlistMsg ? setlistMsg.value : 0;
        const bank = bankMsg ? bankMsg.value : 0;
        const program = pcMsg ? pcMsg.program : 0;

        const presetIndex = bank * 128 + program;
        const patchNum = Math.floor(presetIndex / 8) + 1;
        const patchLetterVal = presetIndex % 8;

        document.getElementById("patch-setlist").value = setlist + 1;
        document.getElementById("patch-number").value = patchNum;
        document.getElementById("patch-letter").value = patchLetterVal;
        break;
      }
      case "scene":
        // Assuming single message for scene, otherwise find the relevant one
        document.getElementById("scene-select").value = midi_sequence_copy.find(m => m.control === 43)?.value || 0;
        break;
      case "footswitch":
        // Assuming single message for footswitch, otherwise find the relevant one
        document.getElementById("footswitch-select").value = midi_sequence_copy.find(m => m.control >= 35 && m.control <= 42)?.control || 35;
        break;
      case "mode_view": {
        const msg = midi_sequence_copy[0]; // Assuming one message for simplicity
        let action = "";
        if (msg.control === 47) {
          if (msg.value === 0) action = "mode_preset";
          else if (msg.value === 1) action = "mode_scene";
          else if (msg.value === 2) action = "mode_stomp";
        } else if (msg.control === 45) {
          action = msg.value === 0 ? "tuner_off" : "tuner_on";
        } else if (msg.control === 46) {
          action = msg.value === 0 ? "gig_view_off" : "gig_view_on";
        }
        document.getElementById("mode-view-select").value = action;
        break;
      }
      case "looper": {
        const msg = midi_sequence_copy[0]; // Assuming one message for simplicity
        let action = "";
        if (msg.control === 53) action = "rec_stop";
        else if (msg.control === 54) action = "play_stop";
        else if (msg.control === 56) action = "undo_redo";
        else if (msg.control === 51) action = "half_speed";
        else if (msg.control === 55) action = "reverse";
        else if (msg.control === 50) action = "one_shot";
        else if (msg.control === 48) {
          action = msg.value === 0 ? "looper_menu_open" : "looper_menu_close";
        }
        document.getElementById("looper-select").value = action;
        break;
      }
    }
  }

  function generateMappingFromForm() {
    const osc_address = document.getElementById("osc-address").value;
    const category = mappingCategorySelect.value;
    if (!osc_address || !category) return null;
    let midi_sequence = [];
    let description = "";
    const channel = 1;
    switch (category) {
      case "patch": {
        const setlist =
          parseInt(document.getElementById("patch-setlist").value) - 1;
        const patchNum = parseInt(document.getElementById("patch-number").value);
        const patchLetterVal = parseInt(
          document.getElementById("patch-letter").value,
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
        const sceneVal = parseInt(document.getElementById("scene-select").value);
        const sceneChar = String.fromCharCode(65 + sceneVal);
        description = `QC: Select Scene ${sceneChar}`;
        midi_sequence = [
          { type: "control_change", channel, control: 43, value: sceneVal },
        ];
        break;
      }
      case "footswitch": {
        const fsSelect = document.getElementById("footswitch-select");
        const control = parseInt(fsSelect.value);
        const fsChar = fsSelect.options[fsSelect.selectedIndex].text;
        description = `QC: Toggle Footswitch ${fsChar}`;
        midi_sequence = [
          { type: "control_change", channel, control, value: 127 },
        ];
        break;
      }
      case "mode_view": {
        const select = document.getElementById("mode-view-select");
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
        const select = document.getElementById("looper-select");
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
    return { osc_address, description, midi_sequence };
  }

  // --- START ---
  loadInitialData();
});