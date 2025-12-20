// --- Dane miesięcy ---
const months = [
  {num:1, name:'Styczeń'},
  {num:2, name:'Luty'},
  {num:3, name:'Marzec'},
  {num:4, name:'Kwiecień'},
  {num:5, name:'Maj'},
  {num:6, name:'Czerwiec'},
  {num:7, name:'Lipiec'},
  {num:8, name:'Sierpień'},
  {num:9, name:'Wrzesień'},
  {num:10, name:'Październik'},
  {num:11, name:'Listopad'},
  {num:12, name:'Grudzień'}
];

let selectedMonth = null;

// --- Render listy miesięcy ---
function renderMonths() {
    const container = document.getElementById('monthsContainer');
    container.innerHTML = '';
    months.forEach(m=>{
        const btn = document.createElement('button');
        btn.className = 'btn btn-outline-primary';
        btn.innerText = m.name;
        btn.dataset.month = m.num;
        btn.addEventListener('click',()=>selectMonth(m.num, btn));
        container.appendChild(btn);
    });
}

// --- Wybór miesiąca ---
function selectMonth(monthNum, btnElement) {
    selectedMonth = monthNum;

    // Odznacz poprzednio zaznaczone
    document.querySelectorAll('#monthsContainer button').forEach(b=>b.classList.remove('active'));
    btnElement.classList.add('active');

    loadMonthEntries(monthNum);
}

// --- Pobranie wpisów dla miesiąca ---
function loadMonthEntries(monthNum) {
    fetch(`/api/entries?month=${monthNum}`)
        .then(r=>r.json())
        .then(data=>{
            renderMonthEntriesTable(data.entries);
        });
}

// --- Render tabeli ---
function renderMonthEntriesTable(entries) {
    const tbody = document.querySelector('#monthEntriesTable tbody');
    tbody.innerHTML = '';
    entries.forEach(e=>{
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${formatDateDMY(e.work_date)}</td><td>${e.login}</td><td>${e.name || ''}</td><td>${e.shift}</td>`;
        tbody.appendChild(tr);
    });
}

// --- Format daty (używamy z main.js) ---
function formatDateDMY(dateStr) {
  const dt = new Date(dateStr);
  return `${String(dt.getDate()).padStart(2,'0')}-${String(dt.getMonth()+1).padStart(2,'0')}-${dt.getFullYear()}`;
}

// --- Inicjalizacja ---
window.addEventListener('load',()=>{
    renderMonths();
});
