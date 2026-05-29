import sqlite3
import os
from flask import Flask, request, jsonify, render_template_string
from datetime import datetime

app = Flask(__name__)
DB_FILE = 'data.db'

# Vercel-safe SQLite path + auto init
if os.environ.get("VERCEL"):
    DB_FILE = "/tmp/data.db"

# ==========================================
# 0. CONFIGURATION
# ==========================================
# Change this to your preferred secure password
ADMIN_PASSWORD = "admin123" 

# ==========================================
# 1. DATABASE INITIALIZATION
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    name TEXT PRIMARY KEY,
                    is_active INTEGER DEFAULT 0,
                    total_units REAL DEFAULT 0.0
                 )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS global_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    last_reading REAL DEFAULT 0.0,
                    last_exited_user TEXT DEFAULT 'None'
                 )''')
                 
    c.execute('''CREATE TABLE IF NOT EXISTS missed_consumption (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT (datetime('now','localtime')),
                    missed_units REAL,
                    last_user_to_exit TEXT,
                    attempting_user TEXT
                 )''')
                 
    c.execute('''CREATE TABLE IF NOT EXISTS event_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT (datetime('now','localtime')),
                    user_name TEXT,
                    action TEXT,
                    reading REAL,
                    units_consumed REAL
                 )''')
    
    users = ['Mallinath', 'Partha', 'Mahadev', 'Joy', 'Suman', 'Soumyadeep', 'Anik']
    for u in users:
        c.execute('INSERT OR IGNORE INTO users (name) VALUES (?)', (u,))
        
    c.execute('INSERT OR IGNORE INTO global_state (id, last_reading, last_exited_user) VALUES (1, 0.0, "None")')
    
    conn.commit()
    conn.close()

# Initialize DB on import so Vercel can use it
if not os.path.exists(DB_FILE):
    init_db()

# ==========================================
# 2. MAIN APP HTML/CSS/JS (Tracker UI)
# ==========================================
MAIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart AC Unit Tracker</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <style>
        body { background-color: #f4f7f6; }
        .user-card { transition: transform 0.2s, box-shadow 0.2s; }
        .user-card:hover { transform: translateY(-3px); box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); }
    </style>
</head>
<body class="font-sans antialiased text-gray-800 pb-12">
    
    <div class="max-w-6xl mx-auto pt-10 px-6">
        <!-- Header Section -->
        <div class="flex flex-col md:flex-row justify-between items-center mb-10 gap-4">
            <div class="text-center md:text-left">
                <h1 class="text-4xl font-extrabold text-indigo-700 tracking-tight">Smart AC Tracker</h1>
                <p class="text-gray-500 mt-1 text-lg">Automated billing for room members.</p>
            </div>
            <div class="flex items-center gap-3">
                <button onclick="adminReset()" class="bg-gray-200 text-gray-600 p-3 rounded-xl hover:bg-gray-300 hover:text-gray-800 transition shadow-sm" title="Admin Reset">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path></svg>
                </button>
                <a href="/dashboard" class="bg-indigo-600 text-white px-6 py-3 rounded-xl font-bold hover:bg-indigo-700 shadow-lg transition flex items-center gap-2">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>
                    View Analytics
                </a>
            </div>
        </div>

        <!-- Dashboard Widgets -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
            <div class="bg-white rounded-2xl shadow-sm p-6 border-l-8 border-indigo-500 flex flex-col justify-center">
                <p class="text-xs text-gray-400 uppercase tracking-widest font-bold">Last Recorded Unit</p>
                <p class="text-4xl font-black text-gray-800 mt-1" id="last-reading-display">--</p>
            </div>
            
            <div class="bg-white rounded-2xl shadow-sm p-6 border-l-8 border-green-500 flex flex-col justify-center">
                <p class="text-xs text-gray-400 uppercase tracking-widest font-bold">People In Room</p>
                <p class="text-4xl font-black text-green-600 mt-1" id="active-count-display">0</p>
            </div>
            
            <div class="bg-white rounded-2xl shadow-sm p-6 border-l-8 border-amber-500 flex flex-col justify-center">
                <p class="text-xs text-gray-400 uppercase tracking-widest font-bold">Total Missed Units</p>
                <p class="text-4xl font-black text-amber-500 mt-1" id="missed-units-display">0.0</p>
                <p class="text-xs text-gray-400 mt-1 font-semibold">Unaccounted consumption</p>
            </div>
        </div>

        <div id="users-grid" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            <!-- Cards injected via JavaScript -->
        </div>
    </div>

    <script>
        let globalLastReading = 0;

        async function loadData() {
            const res = await fetch('/api/status');
            const data = await res.json();
            
            globalLastReading = data.last_reading;
            document.getElementById('last-reading-display').innerText = data.last_reading.toFixed(2);
            document.getElementById('missed-units-display').innerText = data.total_missed.toFixed(2);
            
            const activeCount = data.users.filter(u => u.is_active === 1).length;
            document.getElementById('active-count-display').innerText = activeCount;

            const grid = document.getElementById('users-grid');
            grid.innerHTML = '';

            data.users.forEach(user => {
                const isActive = user.is_active === 1;
                const statusColor = isActive ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500';
                const statusDot = isActive ? 'bg-green-500' : 'bg-gray-300';
                const statusText = isActive ? 'Inside Room' : 'Outside';
                const btnClass = isActive 
                    ? 'bg-red-50 text-red-600 hover:bg-red-100 border border-red-200' 
                    : 'bg-indigo-600 text-white hover:bg-indigo-700 shadow-md';
                const btnText = isActive ? 'Log Exit' : 'Log Entry';

                const cardHtml = `
                    <div class="user-card bg-white rounded-2xl p-5 border border-gray-100 flex flex-col justify-between h-full">
                        <div>
                            <div class="flex justify-between items-start mb-4">
                                <h3 class="text-xl font-bold text-gray-800">${user.name}</h3>
                                <span class="text-xs font-semibold px-2.5 py-1 rounded-full flex items-center gap-1.5 ${statusColor}">
                                    <span class="w-2 h-2 rounded-full ${statusDot}"></span>
                                    ${statusText}
                                </span>
                            </div>
                            <div class="mb-6">
                                <p class="text-sm text-gray-500 mb-1">Total Consumption</p>
                                <p class="text-3xl font-black text-gray-900">${user.total_units.toFixed(2)} <span class="text-base font-medium text-gray-400">units</span></p>
                            </div>
                        </div>
                        <button onclick="handleAction('${user.name}', ${isActive})" class="w-full py-3 rounded-xl font-bold transition-colors ${btnClass}">
                            ${btnText}
                        </button>
                    </div>
                `;
                grid.innerHTML += cardHtml;
            });
        }

        async function handleAction(name, currentlyActive) {
            const actionText = currentlyActive ? 'Exiting' : 'Entering';
            
            const { value: reading } = await Swal.fire({
                title: `${name} is ${actionText}`,
                text: `Current meter reading must be at least ${globalLastReading.toFixed(2)}`,
                input: 'number',
                inputPlaceholder: 'e.g. 110',
                inputAttributes: { min: globalLastReading, step: 'any' },
                showCancelButton: true,
                confirmButtonText: 'Submit Reading',
                confirmButtonColor: '#4f46e5',
                inputValidator: (value) => {
                    if (!value) return 'You need to enter a reading!';
                    if (parseFloat(value) < globalLastReading) return 'Reading cannot go backwards!';
                }
            });

            if (reading) {
                const response = await fetch('/api/action', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: name, reading: parseFloat(reading) })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    if (result.warning) {
                        Swal.fire({ icon: 'warning', title: 'Unaccounted Consumption!', text: result.warning, confirmButtonColor: '#f59e0b' });
                    } else {
                        Swal.fire({ icon: 'success', title: 'Logged Successfully', toast: true, position: 'top-end', showConfirmButton: false, timer: 2000 });
                    }
                    loadData();
                } else {
                    Swal.fire('Error', result.error, 'error');
                }
            }
        }

        async function adminReset() {
            const { value: formValues } = await Swal.fire({
                title: 'Admin Master Reset',
                html:
                    '<p class="text-sm text-gray-500 mb-4">This will wipe all consumption data, kick everyone out of the room, and clear the analytics history.</p>' +
                    '<input id="admin-pass" class="swal2-input" type="password" placeholder="Admin Password">' +
                    '<input id="admin-reading" class="swal2-input" type="number" step="any" placeholder="New Starting Meter Unit">',
                focusConfirm: false,
                showCancelButton: true,
                confirmButtonText: 'RESET EVERYTHING',
                confirmButtonColor: '#ef4444',
                preConfirm: () => {
                    const pass = document.getElementById('admin-pass').value;
                    const reading = document.getElementById('admin-reading').value;
                    if (!pass || !reading) {
                        Swal.showValidationMessage('Both fields are required');
                    }
                    return { pass: pass, reading: reading }
                }
            });

            if (formValues) {
                const response = await fetch('/api/admin/reset', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ password: formValues.pass, new_reading: parseFloat(formValues.reading) })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    Swal.fire('Reset Complete', 'All data has been wiped and the baseline is reset.', 'success');
                    loadData();
                } else {
                    Swal.fire('Access Denied', result.error, 'error');
                }
            }
        }

        loadData();
    </script>
</body>
</html>
'''

# ==========================================
# 3. DASHBOARD HTML/CSS/JS (Analytics UI)
# ==========================================
DASHBOARD_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AC Analytics Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style> body { background-color: #f8fafc; } </style>
</head>
<body class="font-sans antialiased text-gray-800 pb-12">
    
    <div class="max-w-7xl mx-auto pt-8 px-6">
        <div class="flex justify-between items-center mb-8 border-b pb-4">
            <div>
                <h1 class="text-3xl font-extrabold text-gray-900 tracking-tight">Analytics Dashboard</h1>
                <p class="text-gray-500 mt-1">Comprehensive view of AC consumption and anomalies.</p>
            </div>
            <a href="/" class="text-indigo-600 font-bold hover:text-indigo-800 flex items-center gap-1 bg-indigo-50 px-4 py-2 rounded-lg">
                &larr; Back to Tracker
            </a>
        </div>

        <!-- Top Overview Cards -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div class="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
                <p class="text-sm text-gray-500 font-semibold mb-1">Total Accounted Units</p>
                <p class="text-3xl font-black text-indigo-600" id="stat-accounted">0</p>
            </div>
            <div class="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
                <p class="text-sm text-gray-500 font-semibold mb-1">Total Missed Units</p>
                <p class="text-3xl font-black text-amber-500" id="stat-missed">0</p>
            </div>
            <div class="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
                <p class="text-sm text-gray-500 font-semibold mb-1">Efficiency Ratio (Accounted %)</p>
                <p class="text-3xl font-black text-green-500" id="stat-ratio">0%</p>
            </div>
        </div>

        <!-- Charts Grid -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
            <div class="lg:col-span-2 bg-white p-6 rounded-xl shadow-sm border border-gray-100">
                <h3 class="text-lg font-bold text-gray-800 mb-4">Consumption History (Interval Usage over Time)</h3>
                <canvas id="timelineChart" height="100"></canvas>
            </div>
            <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex flex-col justify-center">
                <h3 class="text-lg font-bold text-gray-800 mb-4 text-center">Accounted vs. Missed</h3>
                <canvas id="donutChart"></canvas>
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
            <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
                <h3 class="text-lg font-bold text-gray-800 mb-4">Total Consumption by User</h3>
                <canvas id="barChart"></canvas>
            </div>

            <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-100 overflow-hidden flex flex-col">
                <h3 class="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
                    <span class="w-3 h-3 rounded-full bg-amber-500 inline-block"></span> 
                    Anomaly Logs (Missed Consumption)
                </h3>
                <div class="overflow-y-auto flex-grow" style="max-height: 300px;">
                    <table class="w-full text-left border-collapse">
                        <thead>
                            <tr class="bg-gray-50 text-gray-500 text-sm border-b">
                                <th class="p-3 font-semibold rounded-tl-lg">Date</th>
                                <th class="p-3 font-semibold">Units Lost</th>
                                <th class="p-3 font-semibold">Last Exited</th>
                                <th class="p-3 font-semibold rounded-tr-lg">Found By</th>
                            </tr>
                        </thead>
                        <tbody id="anomaly-table-body" class="text-sm">
                            <!-- Injected via JS -->
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- NEW: User History Table -->
        <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-100 mb-8">
            <div class="flex flex-col sm:flex-row justify-between items-center mb-6 gap-4">
                <h3 class="text-lg font-bold text-gray-800">Detailed Activity & Event Log</h3>
                <select id="user-filter" class="border-gray-300 bg-gray-50 rounded-lg shadow-sm px-4 py-2 text-sm focus:ring-indigo-500 focus:border-indigo-500 font-semibold" onchange="filterUserHistory()">
                    <option value="ALL">Show All Users</option>
                    <!-- Options injected via JS -->
                </select>
            </div>
            <div class="overflow-y-auto" style="max-height: 400px;">
                <table class="w-full text-left border-collapse">
                    <thead>
                        <tr class="bg-gray-50 text-gray-500 text-sm border-b">
                            <th class="p-3 font-semibold rounded-tl-lg">Date & Time</th>
                            <th class="p-3 font-semibold">User Name</th>
                            <th class="p-3 font-semibold">Action</th>
                            <th class="p-3 font-semibold">Meter Reading</th>
                        </tr>
                    </thead>
                    <tbody id="user-history-body" class="text-sm">
                        <!-- Injected via JS -->
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        let allEventsData = [];

        async function loadDashboard() {
            const res = await fetch('/api/analytics_data');
            const data = await res.json();
            
            // Stats
            const totalAccounted = data.users.reduce((acc, user) => acc + user.total_units, 0);
            const totalMissed = data.missed_total;
            const grandTotal = totalAccounted + totalMissed;
            const ratio = grandTotal > 0 ? ((totalAccounted / grandTotal) * 100).toFixed(1) : 100;
            
            document.getElementById('stat-accounted').innerText = totalAccounted.toFixed(2);
            document.getElementById('stat-missed').innerText = totalMissed.toFixed(2);
            document.getElementById('stat-ratio').innerText = ratio + '%';

            // Charts Setup
            const colors = ['#4f46e5', '#ec4899', '#8b5cf6', '#14b8a6', '#f97316', '#3b82f6', '#ef4444'];

            new Chart(document.getElementById('barChart'), {
                type: 'bar',
                data: {
                    labels: data.users.map(u => u.name),
                    datasets: [{ label: 'Units Consumed', data: data.users.map(u => u.total_units), backgroundColor: colors, borderRadius: 6 }]
                },
                options: { plugins: { legend: { display: false } } }
            });

            new Chart(document.getElementById('donutChart'), {
                type: 'doughnut',
                data: {
                    labels: ['Properly Tracked', 'Missed / Wasted'],
                    datasets: [{ data: [totalAccounted, totalMissed], backgroundColor: ['#10b981', '#f59e0b'], borderWidth: 0 }]
                },
                options: { cutout: '70%', plugins: { legend: { position: 'bottom' } } }
            });

            const labels = data.events_for_chart.map(e => e.timestamp.split(' ')[1]); 
            const units = data.events_for_chart.map(e => e.units_consumed);
            
            new Chart(document.getElementById('timelineChart'), {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Units Consumed Since Last Action',
                        data: units,
                        borderColor: '#4f46e5',
                        backgroundColor: 'rgba(79, 70, 229, 0.1)',
                        fill: true, tension: 0.3, pointBackgroundColor: '#4f46e5'
                    }]
                },
                options: { scales: { y: { beginAtZero: true } } }
            });

            // Anomaly Table
            const tbody = document.getElementById('anomaly-table-body');
            if(data.missed_logs.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" class="p-4 text-center text-gray-400">No anomalies detected!</td></tr>';
            } else {
                data.missed_logs.forEach(log => {
                    tbody.innerHTML += `
                        <tr class="border-b border-gray-50 hover:bg-amber-50">
                            <td class="p-3 text-xs text-gray-500">${log.timestamp}</td>
                            <td class="p-3 font-bold text-amber-600">${log.missed_units.toFixed(2)}</td>
                            <td class="p-3">${log.last_user_to_exit}</td>
                            <td class="p-3">${log.attempting_user}</td>
                        </tr>
                    `;
                });
            }

            // User History Feature Setup
            allEventsData = data.all_events;
            const userFilter = document.getElementById('user-filter');
            data.users.forEach(u => {
                userFilter.innerHTML += `<option value="${u.name}">${u.name}</option>`;
            });
            filterUserHistory();
        }

        // Logic for User Activity Filtering
        function filterUserHistory() {
            const selectedUser = document.getElementById('user-filter').value;
            const tbody = document.getElementById('user-history-body');
            tbody.innerHTML = '';

            const filteredEvents = selectedUser === 'ALL' 
                ? allEventsData 
                : allEventsData.filter(e => e.user_name === selectedUser);

            if(filteredEvents.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" class="p-4 text-center text-gray-400">No activity found.</td></tr>';
                return;
            }

            filteredEvents.forEach(e => {
                const isEnter = e.action === 'ENTER';
                const actionColor = isEnter ? 'text-green-600 bg-green-50 border-green-200' : 'text-red-600 bg-red-50 border-red-200';
                
                tbody.innerHTML += `
                    <tr class="border-b border-gray-50 hover:bg-gray-50 transition">
                        <td class="p-3 text-xs text-gray-500 whitespace-nowrap">${e.timestamp}</td>
                        <td class="p-3 font-bold text-gray-700">${e.user_name}</td>
                        <td class="p-3">
                            <span class="px-2 py-1 text-[10px] uppercase font-black tracking-wider rounded border ${actionColor}">
                                ${e.action}
                            </span>
                        </td>
                        <td class="p-3 font-medium text-gray-900">${e.reading.toFixed(2)}</td>
                    </tr>
                `;
            });
        }
        
        loadDashboard();
    </script>
</body>
</html>
'''

# ==========================================
# 4. FLASK API ROUTES
# ==========================================
@app.route('/')
def index():
    return render_template_string(MAIN_TEMPLATE)

@app.route('/dashboard')
def dashboard():
    return render_template_string(DASHBOARD_TEMPLATE)

@app.route('/api/status', methods=['GET'])
def status():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute('SELECT last_reading FROM global_state WHERE id = 1')
    last_reading = c.fetchone()['last_reading']
    
    c.execute('SELECT * FROM users')
    users = [dict(row) for row in c.fetchall()]
    
    c.execute('SELECT SUM(missed_units) as total_missed FROM missed_consumption')
    missed_row = c.fetchone()
    total_missed = missed_row['total_missed'] if missed_row['total_missed'] else 0.0
    
    conn.close()
    return jsonify({
        "last_reading": last_reading, 
        "users": users,
        "total_missed": total_missed
    })

@app.route('/api/action', methods=['POST'])
def action():
    data = request.json
    name = data.get('name')
    current_reading = float(data.get('reading'))
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('SELECT last_reading, last_exited_user FROM global_state WHERE id = 1')
    state = c.fetchone()
    last_reading = state[0]
    last_exited_user = state[1]
    
    if current_reading < last_reading:
        return jsonify({"success": False, "error": "Reading cannot be lower than the previous reading."}), 400

    c.execute('SELECT is_active FROM users WHERE name = ?', (name,))
    user_row = c.fetchone()
    if not user_row:
        return jsonify({"success": False, "error": "User not found."}), 404
    
    is_entering = (user_row[0] == 0)
    
    c.execute('SELECT name FROM users WHERE is_active = 1')
    active_users = [row[0] for row in c.fetchall()]
    active_count = len(active_users)
    
    warning_message = None
    units_consumed = current_reading - last_reading

    # EMPTY ROOM ANOMALY CHECK
    if is_entering and active_count == 0 and units_consumed > 0:
        c.execute('''INSERT INTO missed_consumption (missed_units, last_user_to_exit, attempting_user) 
                     VALUES (?, ?, ?)''', (units_consumed, last_exited_user, name))
        warning_message = f"{units_consumed:.2f} units were consumed while empty! Last exit was by {last_exited_user}."
    
    # STANDARD CONSUMPTION SPLIT
    elif active_count > 0 and units_consumed > 0:
        split_amount = units_consumed / active_count
        for au in active_users:
            c.execute('UPDATE users SET total_units = total_units + ? WHERE name = ?', (split_amount, au))
            
    # LOG EVENT FOR HISTORY
    if units_consumed >= 0:
        action_type = "ENTER" if is_entering else "EXIT"
        c.execute('''INSERT INTO event_logs (user_name, action, reading, units_consumed) 
                     VALUES (?, ?, ?, ?)''', (name, action_type, current_reading, units_consumed))

    # TOGGLE USER PRESENCE
    new_status = 1 if is_entering else 0
    c.execute('UPDATE users SET is_active = ? WHERE name = ?', (new_status, name))
    
    # UPDATE GLOBAL STATE
    if not is_entering and active_count == 1:
        c.execute('UPDATE global_state SET last_exited_user = ? WHERE id = 1', (name,))
        
    c.execute('UPDATE global_state SET last_reading = ? WHERE id = 1', (current_reading,))
    
    conn.commit()
    conn.close()
    
    response_payload = {"success": True}
    if warning_message: response_payload["warning"] = warning_message
    return jsonify(response_payload)

@app.route('/api/admin/reset', methods=['POST'])
def admin_reset():
    data = request.json
    password = data.get('password')
    new_reading = float(data.get('new_reading', 0.0))
    
    if password != ADMIN_PASSWORD:
        return jsonify({"success": False, "error": "Invalid admin password."}), 403
        
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('UPDATE users SET total_units = 0.0, is_active = 0')
    c.execute('DELETE FROM missed_consumption')
    c.execute('DELETE FROM event_logs')
    c.execute('UPDATE global_state SET last_reading = ?, last_exited_user = "None" WHERE id = 1', (new_reading,))
    
    conn.commit()
    conn.close()
    
    return jsonify({"success": True})

@app.route('/api/analytics_data', methods=['GET'])
def analytics_data():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute('SELECT * FROM users')
    users = [dict(row) for row in c.fetchall()]
    
    c.execute('SELECT SUM(missed_units) as total FROM missed_consumption')
    missed_total_row = c.fetchone()
    missed_total = missed_total_row['total'] if missed_total_row['total'] else 0.0
    
    c.execute('SELECT timestamp, missed_units, last_user_to_exit, attempting_user FROM missed_consumption ORDER BY id DESC')
    missed_logs = [dict(row) for row in c.fetchall()]
    
    # Filtered for line chart (only when units were consumed)
    c.execute('SELECT timestamp, user_name, action, reading, units_consumed FROM event_logs WHERE units_consumed > 0 ORDER BY id ASC')
    events_for_chart = [dict(row) for row in c.fetchall()]

    # Complete history for table list (most recent first)
    c.execute('SELECT timestamp, user_name, action, reading, units_consumed FROM event_logs ORDER BY id DESC')
    all_events = [dict(row) for row in c.fetchall()]
    
    conn.close()
    return jsonify({
        "users": users,
        "missed_total": missed_total,
        "missed_logs": missed_logs,
        "events_for_chart": events_for_chart,
        "all_events": all_events
    })

# ==========================================
# 5. RUN SCRIPT
# ==========================================
if __name__ == '__main__':
    app.run()
