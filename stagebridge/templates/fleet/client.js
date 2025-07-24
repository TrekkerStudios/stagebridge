document.addEventListener("DOMContentLoaded", () => {
  // --- CONFIGURATION ---
  const CURRENT_ADDR = window.location.origin;
  const API_PORT = "3000";
  const BASE_ADDR =
    CURRENT_ADDR.lastIndexOf(":") !== -1
      ? CURRENT_ADDR.slice(0, CURRENT_ADDR.lastIndexOf(":"))
      : CURRENT_ADDR;
  const API_BASE_URL = BASE_ADDR + ":" + API_PORT;
  console.log(`Current URL: ${CURRENT_ADDR} | API URL (derived): ${API_BASE_URL}`);


  const deviceList = document.getElementById("device-list");
  const refreshBtn = document.getElementById("refresh-devices-btn");
  const syncBtn = document.getElementById("sync-settings-btn");

  const fetchDevices = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/fleet/devices`);
      if (!response.ok) throw new Error("Proxy not responding");
      const discoveredDevices = await response.json();
      renderDevices(discoveredDevices);
    } catch (error) {
      deviceList.innerHTML = `<p class="status-offline">Could not connect to discovery server.</p>`;
    }
  };

  const renderDevices = (devices) => {
    deviceList.innerHTML = "";
    if (devices.length === 0) {
      deviceList.innerHTML = `<p>No StageBridge devices found on the network.</p>`;
      return;
    }
    devices.forEach((device) => {
      const deviceCard = document.createElement("div");
      deviceCard.className = "card";
      deviceCard.innerHTML = `
        <h3>${device.name}</h3>
        <p><strong>IP:</strong> ${device.ip}:${device.port}</p>
        <p><strong>Status:</strong> <span class="status-online">Online</span></p>
      `;
      deviceList.appendChild(deviceCard);
    });
  };

  const syncSettings = async () => {
    const rtp_ip = document.getElementById("global-rtp-ip").value;
    const rtp_port = parseInt(document.getElementById("global-rtp-port").value);

    if (!rtp_ip || !rtp_port) {
      alert("Please fill in both RTP IP and Port fields.");
      return;
    }
    if (
      !confirm(
        "This will update the network settings and restart ALL online devices. Are you sure?"
      )
    ) {
      return;
    }

    syncBtn.textContent = "Syncing...";
    syncBtn.disabled = true;

    try {
      const response = await fetch(`${API_BASE_URL}/api/sync`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rtp_ip, rtp_port }),
      });
      const results = await response.json();
      console.log("Sync results:", results);
      alert(
        "Sync command sent to all devices. They will now restart. Refreshing list in 5 seconds..."
      );
    } catch (error) {
      alert("An error occurred during sync.");
    } finally {
      syncBtn.textContent = "Sync Settings to All Devices";
      syncBtn.disabled = false;
      setTimeout(fetchDevices, 5000);
    }
  };

  refreshBtn.addEventListener("click", fetchDevices);
  syncBtn.addEventListener("click", syncSettings);

  // Initial load and periodic refresh
  fetchDevices();
  setInterval(fetchDevices, 10000); // Refresh every 10 seconds
});