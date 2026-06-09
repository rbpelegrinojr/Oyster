/* line_setup.js – interactive line drawing on camera frame */

(function () {
  const canvas = document.getElementById('line-canvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  const img = document.getElementById('camera-preview');
  const saveBtn = document.getElementById('save-line-btn');
  const cameraSelect = document.getElementById('camera-select');
  const enabledChk = document.getElementById('line-enabled');
  const msgEl = document.getElementById('line-message');

  function showMsg(text, ok) {
    if (!msgEl) return;
    msgEl.textContent = text;
    msgEl.style.color = ok ? 'var(--color-success)' : 'var(--color-danger)';
  }

  let drawing = false;
  let startX = 0, startY = 0, endX = 0, endY = 0;
  let hasLine = false;

  function resizeCanvas() {
    canvas.width = img.offsetWidth;
    canvas.height = img.offsetHeight;
    if (hasLine) drawLine();
  }

  function getPos(e) {
    const rect = canvas.getBoundingClientRect();
    const touch = e.touches ? e.touches[0] : e;
    return {
      x: touch.clientX - rect.left,
      y: touch.clientY - rect.top,
    };
  }

  function drawLine() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!hasLine) return;
    ctx.beginPath();
    ctx.moveTo(startX, startY);
    ctx.lineTo(endX, endY);
    ctx.strokeStyle = '#EA580C';
    ctx.lineWidth = 3;
    ctx.setLineDash([8, 4]);
    ctx.stroke();
    // Endpoints
    [{ x: startX, y: startY }, { x: endX, y: endY }].forEach(p => {
      ctx.beginPath();
      ctx.arc(p.x, p.y, 6, 0, Math.PI * 2);
      ctx.fillStyle = '#EA580C';
      ctx.fill();
    });
  }

  canvas.addEventListener('mousedown', e => {
    const p = getPos(e);
    startX = p.x; startY = p.y;
    drawing = true;
  });

  canvas.addEventListener('mousemove', e => {
    if (!drawing) return;
    const p = getPos(e);
    endX = p.x; endY = p.y;
    hasLine = true;
    drawLine();
  });

  canvas.addEventListener('mouseup', () => {
    drawing = false;
    hasLine = true;
  });

  // Load existing config for selected camera
  function loadConfig() {
    const cameraId = encodeURIComponent(
      cameraSelect ? cameraSelect.value : canvas.dataset.cameraId
    );
    if (!cameraId) return;
    img.src = '/line/snapshot/' + cameraId + '?t=' + Date.now();
    img.onload = resizeCanvas;
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
    saveBtn.addEventListener('click', () => {
      if (!hasLine) {
        showMsg('Draw a line on the preview first.', false);
        return;
      }
      const cameraId = cameraSelect ? cameraSelect.value : canvas.dataset.cameraId;
      const w = canvas.width;
      const h = canvas.height;
      const payload = {
        camera_id: parseInt(cameraId, 10),
        x1: startX / w,
        y1: startY / h,
        x2: endX / w,
        y2: endY / h,
        enabled: enabledChk ? enabledChk.checked : true,
      };
      fetch('/line/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
        .then(r => r.json())
        .then(d => {
          if (d.success) {
            showMsg('Line saved successfully.', true);
          } else {
            showMsg('Error saving line.', false);
          }
        })
        .catch(() => showMsg('Request failed.', false));
    });
  }
})();
