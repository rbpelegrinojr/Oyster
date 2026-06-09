/* dashboard.js – poll for recent intruder events and show banner */

(function () {
  const banner = document.getElementById('intruder-banner');
  const bannerText = document.getElementById('intruder-banner-text');

  function fetchRecent() {
    fetch('/intruder/api/recent')
      .then(r => r.json())
      .then(logs => {
        if (logs.length > 0) {
          const latest = logs[0];
          const cam = latest.camera_name || 'Camera ' + latest.camera_id;
          const ts = new Date(latest.timestamp).toLocaleString();
          bannerText.textContent =
            '⚠ INTRUDER DETECTED — ' + cam + '  |  ' + ts +
            '  (' + latest.event_type + ')';
          banner.style.display = 'flex';
        }
      })
      .catch(() => {});
  }

  if (banner) {
    fetchRecent();
    setInterval(fetchRecent, 5000);
  }
})();
