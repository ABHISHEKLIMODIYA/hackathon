/* static/js/script.js
   Works with the provided app.py:
   - Auth: /api/register, /api/login, /api/forgot-password
   - Images: /api/images  (display thumbnails)
   - Fetch+Detect: /api/fetch/manual, /api/detect
   - Reports: /api/reports, /api/reports/generate, /api/reports/download?id=...
   - Map: /api/detections.geojson  (and optional /api/detections)
   - Admin: /api/users (GET/POST/PUT/DELETE)
*/

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

async function jfetch(url, opts = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(opts.headers||{}) },
    ...opts,
  });
  if (!res.ok) {
    let t = "";
    try { t = await res.text(); } catch {}
    throw new Error(`${res.status} ${res.statusText} ${t}`);
  }
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res.text();
}

/* ---------------- Language toggle (navbar) ---------------- */
(function setupLanguageToggle(){
  const sel = $('#language-toggle');
  if (!sel) return;
  sel.addEventListener('change', async function () {
    try {
      await jfetch('/set_language', { method: 'POST', body: JSON.stringify({ language: this.value }) });
      location.reload();
    } catch (e) { console.error(e); }
  });
})();

/* ---------------- Auth pages ---------------- */
(function setupRegister(){
  const form = $('#register-form');
  if (!form) return;
  const err = $('#error-message');
  const ok = $('#success-message');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = $('#name').value.trim();
    const email = $('#email').value.trim();
    const password = $('#password').value;
    const confirm = $('#confirm-password').value;
    const role = $('#role').value;
    if (password !== confirm) {
      err.textContent = 'Passwords do not match.';
      err.style.display = 'block'; ok.style.display = 'none';
      return;
    }
    try {
      const data = await jfetch('/api/register', { method: 'POST', body: JSON.stringify({ name, email, password, role }) });
      if (data.success) {
        ok.style.display = 'block'; err.style.display = 'none';
        form.reset();
        setTimeout(() => location.href = '/login.html', 800);
      } else throw new Error(data.message || 'Registration failed');
    } catch (e2) {
      err.textContent = e2.message; err.style.display = 'block'; ok.style.display = 'none';
    }
  });

  // password eye toggles (if present)
  const togglePassword = $('#toggle-password');
  const toggleConfirm = $('#toggle-confirm-password');
  const pwd = $('#password');
  const cpwd = $('#confirm-password');
  function toggleEye(icon, input){
    icon.addEventListener('click', () => {
      input.type = input.type === 'password' ? 'text' : 'password';
      icon.classList.toggle('fa-eye-slash');
    });
  }
  if (togglePassword && pwd) toggleEye(togglePassword, pwd);
  if (toggleConfirm && cpwd) toggleEye(toggleConfirm, cpwd);
})();

(function setupLogin(){
  const form = $('#login-form');
  if (!form) return;
  const err = $('#error-message');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = $('#email').value.trim();
    const password = $('#password').value;
    const role = $('#role').value;
    try {
      const data = await jfetch('/api/login', { method: 'POST', body: JSON.stringify({ email, password, role }) });
      if (!data.success) throw new Error(data.message || 'Login failed');
      // Save token in memory/session for future use if needed
      sessionStorage.setItem('auth_token', data.token);
      sessionStorage.setItem('role', data.role);
      // Redirect based on role
      const dest = data.role === 'admin' ? '/admin_dashboard.html' : '/index.html';
      location.href = dest;
    } catch (e2) {
      err.textContent = e2.message;
      err.style.display = 'block';
    }
  });
})();

(function setupForgot(){
  const form = $('#forgot-form');
  if (!form) return;
  const msg = $('#message');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = $('#email').value.trim();
    try {
      const data = await jfetch('/api/forgot-password', { method: 'POST', body: JSON.stringify({ email }) });
      msg.textContent = data.message || 'Check your email.';
    } catch (e2) {
      msg.textContent = e2.message;
    }
  });
})();

/* ---------------- Index page: thumbnails + fetch/detect ---------------- */
(function setupIndex(){
  const oldImg = $('#old-image');
  const newImg = $('#new-image');
  const fetchForm = $('#fetch-form'); // fields: #start_date, #end_date
  const detectBtn = $('#run-detect');

  async function loadThumbs() {
    if (!oldImg || !newImg) return;
    try {
      const items = await jfetch('/api/images');
      const oldDoc = items.find(x => x.tag === 'manual_old');
      const newDoc = items.find(x => x.tag === 'manual_new');
      if (oldDoc?.display_image) oldImg.src = `data:image/png;base64,${oldDoc.display_image}`;
      if (newDoc?.display_image) newImg.src = `data:image/png;base64,${newDoc.display_image}`;
    } catch (e) { console.warn(e); }
  }

  if (fetchForm) {
    fetchForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const start_date = $('#start_date').value;
      const end_date = $('#end_date').value;
      try {
        await jfetch('/api/fetch/manual', { method: 'POST', body: JSON.stringify({ start_date, end_date }) });
        await loadThumbs();
        alert('Images fetched successfully.');
      } catch (e2) { alert(e2.message); }
    });
  }

  if (detectBtn) {
    detectBtn.addEventListener('click', async () => {
      try {
        const res = await jfetch('/api/detect');
        if (res.detected) {
          alert(`Detection found.\nOwner: ${res.owner?.owner_name || 'Unknown'}\nMask: ${res.mask_path || 'N/A'}`);
        } else {
          alert('No illegal construction detected.');
        }
      } catch (e2) { alert(e2.message); }
    });
  }

  if (oldImg || newImg) loadThumbs();
})();

/* ---------------- Report viewer ---------------- */
(function setupReportViewer(){
  const table = $('#report-table');
  const applyBtn = $('#apply-filters');
  if (!table || !applyBtn) return;

  async function loadReports() {
    const type = $('#report-type-filter').value || '';
    const ward = $('#ward-filter').value || '';
    const date = $('#date-filter').value || '';
    // The backend list_reports filters on filename; we pass as query hints
    const params = new URLSearchParams();
    if (ward) params.set('ward', ward);
    if (date) params.set('start', date); // simple filtering in reports.py
    try {
      const data = await jfetch(`/api/reports?${params.toString()}`);
      const rows = (data.reports || []).map(r => `
        <tr>
          <td>${(r.type || '').toUpperCase()}</td>
          <td>${r.ward || 'All'}</td>
          <td>${r.date || '-'}</td>
          <td>${Array.isArray(r.details) ? r.details.join(' / ') : (r.details || '')}</td>
          <td><a class="btn btn-sm btn-primary" href="/api/reports/download?id=${r.id}">
              <i class="fas fa-download"></i> Download</a></td>
        </tr>
      `).join('');
      table.innerHTML = rows || '<tr><td colspan="5">No reports found.</td></tr>';
    } catch (e) {
      table.innerHTML = `<tr><td colspan="5">Error: ${e.message}</td></tr>`;
    }
  }

  applyBtn.addEventListener('click', loadReports);
  loadReports();

  // Optional: “Generate” buttons if you have them:
  $$('[data-generate-report]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const rtype = btn.getAttribute('data-type') || 'pdf';
      try {
        const res = await jfetch('/api/reports/generate', { method: 'POST', body: JSON.stringify({ type: rtype }) });
        if (res.success) {
          alert(`Report generated: ${res.filename}`);
          loadReports();
        } else {
          alert(res.message || 'Failed to generate report');
        }
      } catch (e) { alert(e.message); }
    });
  });
})();

/* ---------------- Map page ---------------- */
(function setupMapPage(){
  const mapRoot = $('#map'); // you likely have Leaflet map with #map
  if (!mapRoot) return;

  async function loadGeojson() {
    try {
      const gj = await jfetch('/api/detections.geojson');
      // Example Leaflet integration (requires leaflet loaded on page)
      // eslint-disable-next-line no-undef
      if (window.L && window.myMap) {
        // eslint-disable-next-line no-undef
        L.geoJSON(gj, {
          onEachFeature: (feat, layer) => {
            const p = feat.properties || {};
            layer.bindPopup(`<b>Owner:</b> ${p.owner || 'Unknown'}<br><b>Khasra:</b> ${p.khasra || '-'}<br><b>Time:</b> ${p.timestamp || '-'}`);
          }
        }).addTo(window.myMap);
      } else {
        console.log('GeoJSON loaded', gj);
      }
    } catch (e) { console.error(e); }
  }

  loadGeojson();
})();

/* ---------------- Admin dashboard ---------------- */
(function setupAdminDashboard(){
  const statsBox = $('#stats-box');      // optional container
  const alertsTable = $('#alerts-table'); // tbody
  const usersTable = $('#users-table');   // tbody
  const addUserForm = $('#add-user-form');

  async function loadStats() {
    if (!statsBox) return;
    try {
      const s = await jfetch('/api/dashboard_stats');
      statsBox.innerHTML = `
        <div>Total Detections: <b>${s.total_detections}</b></div>
        <div>Pending Alerts: <b>${s.pending_alerts}</b></div>
        <div>Resolved Cases: <b>${s.resolved_cases}</b></div>
      `;
    } catch (e) { console.warn(e); }
  }

  async function loadAlerts() {
    if (!alertsTable) return;
    try {
      const data = await jfetch('/api/alerts');
      const rows = (data.alerts || []).map(a => `
        <tr>
          <td>${a.ward}</td>
          <td>${a.location}</td>
          <td>${a.coordinates}</td>
          <td>${a.date}</td>
          <td>${a.severity}</td>
          <td>${a.status}</td>
        </tr>
      `).join('');
      alertsTable.innerHTML = rows || '<tr><td colspan="6">No alerts.</td></tr>';
    } catch (e) {
      alertsTable.innerHTML = `<tr><td colspan="6">Error: ${e.message}</td></tr>`;
    }
  }

  async function loadUsers() {
    if (!usersTable) return;
    try {
      const data = await jfetch('/api/users');
      const rows = (data.users || []).map(u => `
        <tr>
          <td>${u.name || '-'}</td>
          <td>${u.email || '-'}</td>
          <td>${u.role || '-'}</td>
          <td>
            <button class="btn btn-sm btn-outline-primary" data-edit="${u.email}">Edit</button>
            <button class="btn btn-sm btn-outline-danger" data-del="${u.email}">Delete</button>
          </td>
        </tr>
      `).join('');
      usersTable.innerHTML = rows || '<tr><td colspan="4">No users.</td></tr>';

      // Wire row buttons
      $$('button[data-del]').forEach(btn => {
        btn.addEventListener('click', async () => {
          const email = btn.getAttribute('data-del');
          if (!confirm(`Delete ${email}?`)) return;
          try {
            await jfetch('/api/users', { method: 'DELETE', body: JSON.stringify({ email }) });
            loadUsers();
          } catch (e) { alert(e.message); }
        });
      });

      $$('button[data-edit]').forEach(btn => {
        btn.addEventListener('click', async () => {
          const email = btn.getAttribute('data-edit');
          const name = prompt('New name (leave blank to keep same):', '');
          const role = prompt('New role (admin/officer/public or blank):', '');
          const password = prompt('New password (blank to keep same):', '');
          const body = { email };
          if (name) body.name = name;
          if (role) body.role = role;
          if (password) body.password = password;
          try {
            await jfetch('/api/users', { method: 'PUT', body: JSON.stringify(body) });
            loadUsers();
          } catch (e) { alert(e.message); }
        });
      });

    } catch (e) {
      usersTable.innerHTML = `<tr><td colspan="4">Error: ${e.message}</td></tr>`;
    }
  }

  if (addUserForm) {
    addUserForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = $('#u_name').value.trim();
      const email = $('#u_email').value.trim();
      const role = $('#u_role').value.trim();
      const password = $('#u_password').value;
      try {
        await jfetch('/api/users', { method: 'POST', body: JSON.stringify({ name, email, role, password }) });
        addUserForm.reset();
        loadUsers();
      } catch (e2) {
        alert(e2.message);
      }
    });
  }

  // Initial loads (if present)
  if (statsBox) loadStats();
  if (alertsTable) loadAlerts();
  if (usersTable) loadUsers();

  // Real-time updates (Socket.IO) — optional if you include socket.io client on page
  if (window.io) {
    const socket = io(); // assumes <script src="/socket.io/socket.io.js"></script>
    socket.on('connect', () => console.log('Socket connected'));
    socket.on('new_detection', (payload) => {
      console.log('Realtime detection:', payload);
      loadAlerts();
      // optionally refresh map or show toast here
    });
  }
})();
