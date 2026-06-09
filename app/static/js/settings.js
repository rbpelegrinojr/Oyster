/* settings.js – LAN scanner combo-box population */

(function () {
  const scanBtn = document.getElementById('scan-btn');
  const scanStatus = document.getElementById('scan-status');
  const hostSelect = document.getElementById('host-select');
  const ipInput = document.getElementById('ip_address');
  const subnetInput = document.getElementById('subnet-input');

  let pollTimer = null;

  function pollResult() {
    fetch('/settings/scan/result')
      .then(r => r.json())
      .then(data => {
        if (data.status === 'running') {
          scanStatus.textContent = 'Scanning…';
        } else if (data.status === 'done') {
          clearInterval(pollTimer);
          scanStatus.textContent = data.hosts.length + ' host(s) found.';
          scanBtn.disabled = false;

          hostSelect.innerHTML = '<option value="">— select a host —</option>';
          data.hosts.forEach(h => {
            const opt = document.createElement('option');
            opt.value = h.ip;
            opt.textContent = h.ip + (h.hostname ? ' (' + h.hostname + ')' : '');
            hostSelect.appendChild(opt);
          });
          hostSelect.style.display = 'block';
        }
      })
      .catch(() => {});
  }

  if (scanBtn) {
    scanBtn.addEventListener('click', () => {
      scanBtn.disabled = true;
      scanStatus.textContent = 'Starting scan…';
      hostSelect.style.display = 'none';

      const subnet = subnetInput ? subnetInput.value.trim() : null;
      fetch('/settings/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subnet: subnet || null }),
      })
        .then(() => {
          pollTimer = setInterval(pollResult, 2000);
        })
        .catch(() => { scanBtn.disabled = false; });
    });
  }

  if (hostSelect && ipInput) {
    hostSelect.addEventListener('change', () => {
      if (hostSelect.value) {
        ipInput.value = hostSelect.value;
        // Auto-build RTSP URL if fields are present
        const userInput = document.getElementById('username');
        const passInput = document.getElementById('cam-password');
        const rtspInput = document.getElementById('rtsp_url');
        if (rtspInput && userInput && passInput) {
          const u = userInput.value || 'admin';
          const p = passInput.value || '';
          rtspInput.value = `rtsp://${u}:${p}@${hostSelect.value}:554/stream1`;
        }
      }
    });
  }
})();
