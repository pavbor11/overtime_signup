// ===============================
// PODSUMOWANIE: miesiące + kwartały
// ===============================

// --- Miesiące (bez zmian w logice) ---
const SummaryMonths = [
  'Styczeń','Luty','Marzec','Kwiecień','Maj','Czerwiec',
  'Lipiec','Sierpień','Wrzesień','Październik','Listopad','Grudzień'
];

let summarySelectedMonth = null;

// --- Kwartały ---
const SummaryQuarters = [
  {q: 1, name: 'Kwartał 1'},
  {q: 2, name: 'Kwartał 2'},
  {q: 3, name: 'Kwartał 3'},
  {q: 4, name: 'Kwartał 4'}
];

let summarySelectedQuarter = null;

// 6 tabel dokładnie jak chcesz:
const SummaryManagerOrder = ["Paweł","Michał","Mariia","Aleksy","Piotr","Daria"];

// ============ helpers ============
function summaryFormatDateDMY(dateStr) {
  const dt = new Date(dateStr);
  return `${String(dt.getDate()).padStart(2,'0')}-${String(dt.getMonth()+1).padStart(2,'0')}-${dt.getFullYear()}`;
}

function showMonthView() {
  summarySelectedQuarter = null;

  // odznacz kwartaly
  document.querySelectorAll('.quarter-btn').forEach(b=>b.classList.remove('active'));

  // pokaż duża tabela, schowaj kwartalne
  const big = document.getElementById('summaryTableContainer');
  const qbox = document.getElementById('quarterTablesContainer');
  if (big) big.style.display = 'block';
  if (qbox) qbox.style.display = 'none';
}

function showQuarterView() {
  const big = document.getElementById('summaryTableContainer');
  const qbox = document.getElementById('quarterTablesContainer');
  if (big) big.style.display = 'none';
  if (qbox) qbox.style.display = 'grid';
}

// ============ miesiące ============
function loadSummaryMonths() {
  const container = document.getElementById('summaryMonthList');
  if (!container) return;

  container.innerHTML = '';

  SummaryMonths.forEach((m,i)=>{
    const btn = document.createElement('button');
    btn.className = 'btn btn-outline-primary btn-sm month-btn';
    btn.innerText = m;
    btn.dataset.month = i+1;
    btn.addEventListener('click', ()=>selectSummaryMonth(i+1, btn));
    container.appendChild(btn);
  });
}

function selectSummaryMonth(month, btn) {
  showMonthView();

  summarySelectedMonth = month;
  document.querySelectorAll('.month-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');

  fetch(`/api/entries?month=${month}`)
    .then(r=>r.json())
    .then(data=>{
      renderMonthEntries(data.entries || []);
    });
}

function renderMonthEntries(entries) {
  const container = document.getElementById('summaryTableContainer');
  if (!container) return;

  if(entries.length === 0){
    container.innerHTML = '<p>Brak wpisów w tym miesiącu.</p>';
    return;
  }

  let html = `<table class="table table-bordered table-striped">
      <thead><tr>
        <th>Login</th>
        <th>Name</th>
        <th>Work Date</th>
        <th>Shift</th>
      </tr></thead><tbody>`;

  entries.forEach(e=>{
    html += `<tr>
      <td>${e.login}</td>
      <td>${e.name || ''}</td>
      <td>${summaryFormatDateDMY(e.work_date)}</td>
      <td>${e.shift}</td>
    </tr>`;
  });

  html += '</tbody></table>';
  container.innerHTML = html;
}

// ============ kwartały ============
function loadSummaryQuarters() {
  const container = document.getElementById('summaryQuarterList');
  if (!container) return;

  container.innerHTML = '';

  SummaryQuarters.forEach(item => {
    const btn = document.createElement('button');
    btn.className = 'btn btn-outline-primary btn-sm quarter-btn';
    btn.innerText = item.name;
    btn.dataset.q = item.q;
    btn.addEventListener('click', ()=>selectSummaryQuarter(item.q, btn));
    container.appendChild(btn);
  });
}

function selectSummaryQuarter(q, btn) {
  summarySelectedQuarter = q;

  // odznacz miesiące (bo jesteśmy w kwartale)
  document.querySelectorAll('.month-btn').forEach(b=>b.classList.remove('active'));

  document.querySelectorAll('.quarter-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');

  showQuarterView();

  const year = new Date().getFullYear();
  fetch(`/api/summary/quarter?q=${q}&year=${year}`)
    .then(r=>r.json())
    .then(data=>{
      renderQuarterTables(data.per_manager || {});
    });
}

function renderQuarterTables(perManager) {
  const container = document.getElementById('quarterTablesContainer');
  if (!container) return;

  container.innerHTML = '';

  SummaryManagerOrder.forEach(mgr => {
    const rows = perManager[mgr] || [];

    const card = document.createElement('div');
    card.className = 'quarter-table-card';

    let html = `
      <div class="quarter-table-header">${mgr}</div>
      <table class="table quarter-mini-table">
        <thead>
          <tr>
            <th>Login</th>
            <th>Ilość</th>
          </tr>
        </thead>
        <tbody>
    `;

    // ZAWSZE 5 wierszy
    for (let i = 0; i < 5; i++) {
      const r = rows[i];

      if (r) {
        html += `<tr>
          <td>${r.login}</td>
          <td style="text-align:center;">${r.count}</td>
        </tr>`;
      } else {
        html += `<tr>
          <td style="opacity:0.6; font-style:italic;">–</td>
          <td style="text-align:center; opacity:0.6;">–</td>
        </tr>`;
      }
    }

    html += `</tbody></table>`;
    card.innerHTML = html;
    container.appendChild(card);
  });
}

// --- init ---
window.addEventListener('load', () => {
  loadSummaryMonths();
  loadSummaryQuarters();
  showMonthView(); // domyślnie miesiące
});



