/* dashboard.js – poll for recent intruder events and show banner */

(function () {
  const banner = document.getElementById('intruder-banner');
  const bannerText = document.getElementById('intruder-banner-text');

  // Track the timestamp of the last dismissed intruder so we don't re-show it
  let dismissedTimestamp = null;

  function dismissBanner() {
    banner.style.display = 'none';
    // Remember the latest intruder timestamp so we don't show it again
    const currentText = bannerText.textContent;
    dismissedTimestamp = banner.dataset.latestTimestamp || null;
  }

  function fetchRecent() {
    fetch('/intruder/api/recent')
      .then(r => r.json())
      .then(logs => {
        if (logs.length > 0) {
          const latest = logs[0];
          const latestTs = latest.timestamp;

          // Only show banner if this is a NEW intruder (after the dismissed one)
          if (dismissedTimestamp && latestTs <= dismissedTimestamp) {
            return;
          }

          const cam = latest.camera_name || 'Camera ' + latest.camera_id;
          const ts = new Date(latestTs).toLocaleString();
          bannerText.textContent =
            '\u26a0 INTRUDER DETECTED \u2014 ' + cam + '  |  ' + ts +
            '  (' + latest.event_type + ')';
          banner.dataset.latestTimestamp = latestTs;
          banner.style.display = 'flex';
        }
      })
      .catch(() => {});
  }

  if (banner) {
    // Attach dismiss handler to the close button
    const closeBtn = banner.querySelector('button');
    if (closeBtn) {
      closeBtn.onclick = function () {
        dismissBanner();
      };
    }

    fetchRecent();
    setInterval(fetchRecent, 5000);
  }
})();
