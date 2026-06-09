/* training.js – frame capture and training progress */

(function () {
  const captureBtn = document.getElementById('capture-btn');
  const captureCount = document.getElementById('capture-count');
  const trainBtn = document.getElementById('train-btn');
  const trainStatus = document.getElementById('train-status');
  const progressBar = document.getElementById('train-progress');

  let personId = captureBtn ? captureBtn.dataset.personId : null;
  let cameraSelect = document.getElementById('capture-camera');

  if (captureBtn) {
    captureBtn.addEventListener('click', () => {
      const cameraId = cameraSelect ? cameraSelect.value : captureBtn.dataset.cameraId;
      fetch('/training/capture/' + personId + '/' + cameraId, { method: 'POST' })
        .then(r => r.json())
        .then(d => {
          if (d.success) {
            captureCount.textContent = d.count;
          } else {
            alert(d.message);
          }
        });
    });
  }

  let pollTimer = null;
  function pollTraining() {
    fetch('/training/train/status')
      .then(r => r.json())
      .then(d => {
        if (d.running) {
          trainStatus.textContent = 'Training in progress…';
          if (progressBar) progressBar.style.width = '60%';
        } else {
          clearInterval(pollTimer);
          trainStatus.textContent = d.message || '';
          if (progressBar) progressBar.style.width = d.success ? '100%' : '0%';
          trainStatus.style.color = d.success ? 'var(--color-success)' : 'var(--color-danger)';
          if (trainBtn) trainBtn.disabled = false;
        }
      });
  }

  if (trainBtn) {
    trainBtn.addEventListener('click', () => {
      trainBtn.disabled = true;
      trainStatus.textContent = 'Starting…';
      if (progressBar) progressBar.style.width = '20%';

      fetch('/training/train', { method: 'POST' })
        .then(r => r.json())
        .then(() => {
          pollTimer = setInterval(pollTraining, 2000);
        });
    });
  }
})();
