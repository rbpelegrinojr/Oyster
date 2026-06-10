/* zone_setup.js – interactive polygon zone drawing on camera frame */

(function () {
  const canvas = document.getElementById('zone-canvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  const img = document.getElementById('camera-preview');
  const saveBtn = document.getElementById('save-zone-btn');
  const clearBtn = document.getElementById('clear-btn');
  const undoBtn = document.getElementById('undo-btn');
  const cameraSelect = document.getElementById('camera-select');
  const enabledChk = document.getElementById('zone-enabled');
  const msgEl = document.getElementById('zone-message');

  // Polygon points in canvas pixel coordinates
  let points = [];
  let isClosed = false;
  const CLOSE_RADIUS = 12; // pixels – click within this radius of first point to close

  function showMsg(text, ok) {
    if (!msgEl) return;
    msgEl.textContent = text;
    msgEl.style.color = ok ? 'var(--color-success)' : 'var(--color-danger)';
  }

  function resizeCanvas() {
    canvas.width = img.offsetWidth;
    canvas.height = img.offsetHeight;
    drawPolygon();
  }

  function getPos(e) {
    const rect = canvas.getBoundingClientRect();
    const touch = e.touches ? e.touches[0] : e;
    return {
      x: touch.clientX - rect.left,
      y: touch.clientY - rect.top,
    };
  }

  function drawPolygon() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (points.length === 0) return;

    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i++) {
      ctx.lineTo(points[i].x, points[i].y);
    }

    if (isClosed) {
      ctx.closePath();
      ctx.fillStyle = 'rgba(234, 88, 12, 0.15)';
      ctx.fill();
    }

    ctx.strokeStyle = '#EA580C';
    ctx.lineWidth = 2;
    ctx.setLineDash(isClosed ? [] : [6, 4]);
    ctx.stroke();

    // Draw vertices
    points.forEach(function (p, idx) {
      ctx.beginPath();
      ctx.arc(p.x, p.y, idx === 0 ? 7 : 5, 0, Math.PI * 2);
      ctx.fillStyle = idx === 0 ? '#EA580C' : '#FF8C00';
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    });
  }

  function distanceTo(a, b) {
    return Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2);
  }

  canvas.addEventListener('click', function (e) {
    if (isClosed) return; // Already closed; user must clear to redraw

    const p = getPos(e);

    // If clicking near the first point and we have >=3 points, close the polygon
    if (points.length >= 3 && distanceTo(p, points[0]) < CLOSE_RADIUS) {
      isClosed = true;
      drawPolygon();
      showMsg('Zone closed. Click "Save Zone" to persist.', true);
      return;
    }

    points.push(p);
    drawPolygon();
  });

  canvas.addEventListener('dblclick', function (e) {
    e.preventDefault();
    if (points.length >= 3 && !isClosed) {
      isClosed = true;
      drawPolygon();
      showMsg('Zone closed. Click "Save Zone" to persist.', true);
    }
  });

  // Clear
  clearBtn.addEventListener('click', function () {
    points = [];
    isClosed = false;
    drawPolygon();
    showMsg('', true);
  });

  // Undo last point
  undoBtn.addEventListener('click', function () {
    if (isClosed) {
      isClosed = false;
    } else {
      points.pop();
    }
    drawPolygon();
  });

  // Load existing zone config for selected camera
  function loadConfig() {
    const cameraId = cameraSelect ? cameraSelect.value : '';
    if (!cameraId) return;

    img.src = '/zone/snapshot/' + encodeURIComponent(cameraId) + '?t=' + Date.now();
    img.onload = function () {
      resizeCanvas();
      // Fetch existing zone config
      fetch('/zone/get/' + encodeURIComponent(cameraId))
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.polygon && data.polygon.length >= 3) {
            // Convert fractional coordinates to canvas pixels
            points = data.polygon.map(function (pt) {
              return { x: pt[0] * canvas.width, y: pt[1] * canvas.height };
            });
            isClosed = true;
            if (enabledChk) enabledChk.checked = data.enabled !== false;
            drawPolygon();
          } else {
            points = [];
            isClosed = false;
            drawPolygon();
          }
        })
        .catch(function () {
          points = [];
          isClosed = false;
          drawPolygon();
        });
    };
  }

  if (cameraSelect) {
    cameraSelect.addEventListener('change', loadConfig);
    loadConfig();
  } else {
    img.onload = resizeCanvas;
    resizeCanvas();
  }

  window.addEventListener('resize', resizeCanvas);

  // Save
  if (saveBtn) {
    saveBtn.addEventListener('click', function () {
      if (!isClosed || points.length < 3) {
        showMsg('Draw and close a polygon zone first (at least 3 points).', false);
        return;
      }
      var cameraId = cameraSelect ? cameraSelect.value : '';
      var w = canvas.width;
      var h = canvas.height;
      // Convert pixel coords to fractional (0-1) for resolution independence
      var polygon = points.map(function (p) {
        return [p.x / w, p.y / h];
      });
      var payload = {
        camera_id: parseInt(cameraId, 10),
        polygon: polygon,
        enabled: enabledChk ? enabledChk.checked : true,
      };
      fetch('/zone/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (d.success) {
            showMsg('Zone saved successfully.', true);
          } else {
            showMsg(d.message || 'Error saving zone.', false);
          }
        })
        .catch(function () { showMsg('Request failed.', false); });
    });
  }
})();
