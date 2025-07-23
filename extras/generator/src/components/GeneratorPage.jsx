/** @jsx jsx */
/** @jsxFrag Fragment */
/** @jsxImportSource hono/jsx */
import { jsx, Fragment } from "hono/jsx";

export const GeneratorPage = () => (
    <div class="container">
        <h1>StageBridge Mapping Generator</h1>
        <p>Generate OSC-to-MIDI mappings for your StageBridge configuration. This tool runs entirely in your browser.</p>

        <section class="card">
            <h2>Manual Mapping Creator</h2>
            <form id="manual-mapping-form">
                <h3>New OSC Mapping</h3>
                <div class="form-section">
                    <label for="manual-osc-address">OSC Address:</label>
                    <input type="text" id="manual-osc-address" placeholder="/song/my_song/intro" required />
                </div>
                <div class="form-section">
                    <label for="manual-mapping-category">Action Category:</label>
                    <select id="manual-mapping-category">
                        <option value="">-- Select a Category --</option>
                        <option value="patch">Preset/Patch Change</option>
                        <option value="scene">Scene Select</option>
                        <option value="footswitch">Footswitch Toggle</option>
                        <option value="mode_view">Mode & View Control</option>
                        <option value="looper">Looper Control</option>
                    </select>
                </div>
                {/* Dynamic Fields Container */}
                <div id="manual-dynamic-fields-container">
                    <div id="manual-category-patch" class="hidden">
                        <label for="manual-patch-setlist">Setlist (1-13):</label>
                        <input type="number" id="manual-patch-setlist" value="1" min="1" max="13" />
                        <label for="manual-patch-number">Patch Number (1-32):</label>
                        <input type="number" id="manual-patch-number" value="1" min="1" max="32" />
                        <label for="manual-patch-letter">Patch Letter (A-H):</label>
                        <select id="manual-patch-letter">
                            <option value="0">A</option><option value="1">B</option><option value="2">C</option><option value="3">D</option>
                            <option value="4">E</option><option value="5">F</option><option value="6">G</option><option value="7">H</option>
                        </select>
                    </div>
                    <div id="manual-category-scene" class="hidden">
                        <label for="manual-scene-select">Select Scene (A-H):</label>
                        <select id="manual-scene-select">
                            <option value="0">A</option><option value="1">B</option><option value="2">C</option><option value="3">D</option>
                            <option value="4">E</option><option value="5">F</option><option value="6">G</option><option value="7">H</option>
                        </select>
                    </div>
                    <div id="manual-category-footswitch" class="hidden">
                        <label for="manual-footswitch-select">Select Footswitch (A-H):</label>
                        <select id="manual-footswitch-select">
                            <option value="35">A</option><option value="36">B</option><option value="37">C</option><option value="38">D</option>
                            <option value="39">E</option><option value="40">F</option><option value="41">G</option><option value="42">H</option>
                        </select>
                    </div>
                    <div id="manual-category-mode_view" class="hidden">
                        <label for="manual-mode-view-select">Select Action:</label>
                        <select id="manual-mode-view-select">
                            <option value="mode_preset">Switch to Preset Mode</option><option value="mode_scene">Switch to Scene Mode</option>
                            <option value="mode_stomp">Switch to Stomp Mode</option><option value="tuner_on">Turn Tuner On</option>
                            <option value="tuner_off">Turn Tuner Off</option><option value="gig_view_on">Turn Gig View On</option>
                            <option value="gig_view_off">Turn Gig View Off</option>
                        </select>
                    </div>
                    <div id="manual-category-looper" class="hidden">
                        <label for="manual-looper-select">Select Looper Action:</label>
                        <select id="manual-looper-select">
                            <option value="rec_stop">Record / Overdub / Stop</option><option value="play_stop">Play / Stop</option>
                            <option value="undo_redo">Undo / Redo</option><option value="half_speed">Toggle Half Speed</option>
                            <option value="reverse">Toggle Reverse</option><option value="one_shot">Toggle One Shot</option>
                            <option value="looper_menu_open">Open Looper Menu</option><option value="looper_menu_close">Close Looper Menu</option>
                        </select>
                    </div>
                </div>
                <button type="submit" id="add-manual-mapping-btn">Add Manual Mapping</button>
            </form>
        </section>

        <section class="card">
            <h2>Bulk CSV Importer</h2>
            <p>Upload one or more CSV files to generate mappings for multiple songs.</p>
            <div class="form-grid single-col">
                <div>
                    <label for="csv-files-input">CSV Files:</label>
                    <input type="file" id="csv-files-input" accept=".csv" multiple required />
                    <div id="selected-files-display" class="file-list">No files selected.</div>
                </div>
            </div>
            <h3>Parser Settings</h3>
            <p class="small-text">These settings control how the CSV files are parsed.</p>
            <div class="form-grid">
                <div>
                    <label for="parser-column-name">Column Name for Values:</label>
                    <input type="text" id="parser-column-name" value="Song Part" />
                </div>
                <div>
                    <label for="parser-footswitch-prefix">Footswitch Prefix:</label>
                    <input type="text" id="parser-footswitch-prefix" value="FS" />
                </div>
                <div>
                    <label for="parser-scene-prefix">Scene Prefix:</label>
                    <input type="text" id="parser-scene-prefix" value="SC" />
                </div>
                <div>
                    <label for="parser-osc-prefix">OSC Base Prefix:</label>
                    <input type="text" id="parser-osc-prefix" value="/song" />
                </div>
                <div>
                    <label for="start-setlist-number">Starting Setlist Number (1-13):</label>
                    <input type="number" id="start-setlist-number" value="1" min="1" max="13" />
                </div>
            </div>
            <button id="process-csv-btn">Process CSVs & Add Mappings</button>
            <p id="csv-error-message" class="error-message hidden"></p>
        </section>

        <section class="card">
            <h2>Generated Mappings</h2>
            <div class="table-actions">
                <button id="download-all-btn" disabled>Download Config JSON</button>
                <button id="clear-all-btn" class="danger" disabled>Clear All Mappings</button>
            </div>
            <p id="total-mappings-count">Total Mappings: 0</p>
            <pre id="generated-mappings-output"></pre>
        </section>
    </div>
);