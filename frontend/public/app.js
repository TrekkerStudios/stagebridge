document.addEventListener("DOMContentLoaded", () => {
  // --- CONFIGURATION ---
  const CURRENT_ADDR = window.location.origin
  const API_PORT = "3001"; // IMPORTANT: Set your Pi's IP
  const BASE_ADDR = CURRENT_ADDR.lastIndexOf(':') !== -1 ?
    CURRENT_ADDR.slice(0, CURRENT_ADDR.lastIndexOf(':')) :
    CURRENT_ADDR;
  const API_BASE_URL = BASE_ADDR + ":" + API_PORT;
  console.log(`Current URL: ${CURRENT_ADDR} | API URL (derived): ${API_BASE_URL}`);

  // --- DOM ELEMENTS ---
  const midiInputSelect = document.getElementById("midi-input");
  const midiOutputSelect = document.getElementById("midi-output");
  const saveAndRestartBtn = document.getElementById("save-and-restart-btn");
  const mappingsTableBody = document.querySelector("#mappings-table tbody");
  const showFormBtn = document.getElementById("show-add-mapping-form-btn");
  const addMappingDialog = document.getElementById("add-mapping-dialog");
  const addMappingForm = document.getElementById("add-mapping-form");
  const cancelFormBtn = document.getElementById("cancel-add-mapping-btn");
  const mappingCategorySelect = document.getElementById("mapping-category");
  const dynamicFieldsContainer = document.getElementById(
    "dynamic-fields-container"
  );
  const downloadConfigBtn = document.getElementById("download-config-btn");
  const uploadConfigInput = document.getElementById("upload-config-input");
  const uploadFilenameSpan = document.getElementById("upload-filename");
  const restartOverlay = document.getElementById("restart-overlay");
  // New Song Importer Elements
  const songTitleInput = document.getElementById("song-title");
  const songSetlistInput = document.getElementById("song-setlist");
  const songCsvInput = document.getElementById("song-csv-input");
  const processSongBtn = document.getElementById("process-song-btn");
  const adminRedirect = document.getElementById("admin-redirect")

  let currentConfig = {};

  // --- API FUNCTIONS (Unchanged) ---
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
          errorData.error || `HTTP error! status: ${response.status}`
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

  // --- INITIALIZATION & UI RENDERING (Unchanged) ---
  const loadInitialData = async () => {
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
        '<tr><td colspan="3">No mappings configured.</td></tr>';
      return;
    }
    currentConfig.osc_mappings.forEach((m) => {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${m.osc_address}</td>
        <td>${m.description || "N/A"}</td>
        <td><button class="delete-btn" data-id="${m.id}">Delete</button></td>`;
      mappingsTableBody.appendChild(row);
    });
  };

  // --- EVENT HANDLERS ---
  // All previous event handlers (saveAndRestartBtn, mappingsTableBody, etc.) remain the same...

  // --- NEW: Song Importer Event Handler ---
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
        `This will add new mappings for the song "${songTitle}". Are you sure?`
      )
    ) {
      return;
    }

    const formData = new FormData();
    formData.append("song_title", songTitle);
    formData.append("setlist_number", setlistNumber);
    formData.append("file", file);

    try {
      // Note: When using FormData, the browser sets the Content-Type header automatically.
      const response = await fetch(`${API_BASE_URL}/api/songs/upload`, {
        method: "POST",
        body: formData,
      });

      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.error || "Failed to process song.");
      }

      alert(result.message);
      // Clear the form and reload the data
      songTitleInput.value = "";
      songCsvInput.value = "";
      loadInitialData();
    } catch (error) {
      alert(`Error: ${error.message}`);
    }
  });

  // ... other event handlers ...
  saveAndRestartBtn.addEventListener("click", async () => {
    if (
      !confirm(
        "This will save the current MIDI port selection and restart the service. Are you sure?"
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
    if (e.target.classList.contains("delete-btn")) {
      const mappingId = e.target.dataset.id;
      if (confirm("Are you sure you want to delete this mapping?")) {
        await fetchAPI(`/api/mappings/${mappingId}`, { method: "DELETE" });
        loadInitialData();
      }
    }
  });

  showFormBtn.addEventListener("click", () => {
    addMappingForm.reset();
    updateDynamicFields();
    addMappingDialog.showModal();
  });

  cancelFormBtn.addEventListener("click", () => addMappingDialog.close());

  mappingCategorySelect.addEventListener("change", updateDynamicFields);

  function updateDynamicFields() {
    const selectedCategory = mappingCategorySelect.value;
    dynamicFieldsContainer
      .querySelectorAll(":scope > div")
      .forEach((div) => div.classList.add("hidden"));
    if (selectedCategory) {
      const sectionToShow = document.getElementById(
        `category-${selectedCategory}`
      );
      if (sectionToShow) sectionToShow.classList.remove("hidden");
    }
  }

  addMappingForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const newMapping = generateMappingFromForm();
    if (!newMapping) {
      alert("Please select a category and fill out the required fields.");
      return;
    }
    await fetchAPI("/api/mappings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(newMapping),
    });
    addMappingDialog.close();
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
        `Are you sure you want to upload ${file.name}? This will overwrite the current configuration.`
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
        const patchNum = parseInt(
          document.getElementById("patch-number").value
        );
        const patchLetterVal = parseInt(
          document.getElementById("patch-letter").value
        );
        const patchLetterChar = String.fromCharCode(65 + patchLetterVal);
        const presetIndex = (patchNum - 1) * 8 + patchLetterVal;
        const bank = presetIndex > 127 ? 1 : 0;
        const program = presetIndex % 128;
        description = `QC: Setlist ${setlist + 1
          }, Patch ${patchNum}${patchLetterChar}`;
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
          case "mode_preset": (control = 47), (value = 0); break;
          case "mode_scene": (control = 47), (value = 1); break;
          case "mode_stomp": (control = 47), (value = 2); break;
          case "tuner_on": (control = 45), (value = 127); break;
          case "tuner_off": (control = 45), (value = 0); break;
          case "gig_view_on": (control = 46), (value = 127); break;
          case "gig_view_off": (control = 46), (value = 0); break;
        }
        midi_sequence = [{ type: "control_change", channel, control, value }];
        break;
      }
      case "looper": {
        const select = document.getElementById("looper-select");
        const action = select.value;
        const text = select.options[select.selectedIndex].text;
        description = `QC Looper: ${text}`;
        let control, value = 127;
        switch (action) {
          case "rec_stop": control = 53; break;
          case "play_stop": control = 54; break;
          case "undo_redo": control = 56; break;
          case "half_speed": control = 51; break;
          case "reverse": control = 55; break;
          case "one_shot": control = 50; break;
          case "looper_menu_open": (control = 48), (value = 0); break;
          case "looper_menu_close": (control = 48), (value = 127); break;
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