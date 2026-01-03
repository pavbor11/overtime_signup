let selectedWeekStart = null;
let selectedDay = null;
let activeShift = null;
let rowSelectedForDelete = null;

// --- Format daty ---
function formatDateDMY(dateStr) {
    const dt = new Date(dateStr);
    return `${String(dt.getDate()).padStart(2,'0')}-${String(dt.getMonth()+1).padStart(2,'0')}-${dt.getFullYear()}`;
}

// --- Numer tygodnia ---
function getWeekNumber(d) {
    const dt = new Date(d);
    const firstJan = new Date(dt.getFullYear(),0,1);
    const days = Math.floor((dt - firstJan) / (24*60*60*1000));
    return Math.ceil((days + firstJan.getDay()+1)/7);
}

function showLoginMessage(text) {
  const el = document.getElementById('loginFeedback');
  if (!el) return;
  el.textContent = text;
  el.style.display = 'block';
}

function clearLoginMessage() {
  const el = document.getElementById('loginFeedback');
  if (!el) return;
  el.textContent = '';
  el.style.display = 'none';
}

// --- Ładowanie tygodni ---
function loadWeeks() {
    fetch('/api/weeks')
        .then(r=>r.json())
        .then(weeks=>{
            const list = document.getElementById('weeksList');
            list.innerHTML='';
            weeks.forEach(w=>{
                const el = document.createElement('button');
                el.className='list-group-item list-group-item-action';
                el.innerText='Week '+getWeekNumber(w.start);
                el.dataset.start=w.start;
                el.addEventListener('click',()=>selectWeek(w.start,el));
                if(selectedWeekStart===w.start) el.classList.add('selected-week');
                list.appendChild(el);
            });
        });
}

// --- Wybór tygodnia ---
function selectWeek(start,el){
    selectedWeekStart=start;
    selectedDay=null;
    document.getElementById('loginContainer').style.display='none';
    highlightSelectedWeek(el);
    loadWeekData();
}

function highlightSelectedWeek(el){
    document.querySelectorAll('#weeksList .list-group-item').forEach(b=>b.classList.remove('selected-week'));
    if(el) el.classList.add('selected-week');
}

// --- Tabela tygodnia ---
function loadWeekData(){
    if(!selectedWeekStart) return;
    fetch('/api/entries?week_start='+selectedWeekStart)
        .then(r=>r.json())
        .then(data=>{
            const container=document.getElementById('weekTableContainer');
            const per_day=data.per_day;
            let html=`<table class="table table-bordered">
                <thead><tr><th>Dzień</th><th>Data</th><th>Zapisane Osoby</th><th>Day Shift</th><th>Night Shift</th></tr></thead><tbody>`;

            const days=Object.keys(per_day).sort((a,b)=>new Date(a).getDay()-new Date(b).getDay());
            for(const d of days){
                const dayname=new Date(d).toLocaleDateString(undefined,{weekday:'long'});
                const pd=per_day[d];
                html+=`<tr class="clickable-day" data-day="${d}">
                    <td>${dayname}</td>
                    <td>${formatDateDMY(d)}</td>
                    <td></td>
                    <td>${pd.day_shift.length}</td>
                    <td>${pd.night_shift.length}</td>
                </tr>`;
            }

            html+='</tbody></table>';
            container.innerHTML=html;

            document.querySelectorAll('.clickable-day').forEach(row=>row.addEventListener('click',()=>selectDay(row.dataset.day,row)));
        });
}

// --- Wybór dnia ---
function selectDay(day,rowElement){
    selectedDay=day;
    document.getElementById('loginContainer').style.display='block';
    highlightSelectedDay(rowElement);

    fetch(`/api/entries?week_start=${selectedWeekStart}&day=${selectedDay}`)
        .then(r=>r.json())
        .then(data=>{
            renderShiftTables(data);
        });
}

function highlightSelectedDay(rowElement){
    document.querySelectorAll('.clickable-day').forEach(r=>r.classList.remove('table-success'));
    if(rowElement) rowElement.classList.add('table-success');
}

// --- Highlight aktywnego shiftu ---
function highlightActiveShift(){
    const dayHeader=document.getElementById('dayShiftHeader');
    const nightHeader=document.getElementById('nightShiftHeader');
    if(activeShift==='day'){dayHeader.classList.add('table-success'); nightHeader.classList.remove('table-success');}
    else if(activeShift==='night'){nightHeader.classList.add('table-success'); dayHeader.classList.remove('table-success');}
    else{dayHeader.classList.remove('table-success'); nightHeader.classList.remove('table-success');}
}

// --- Dodawanie wpisu ---
function addEntry(){
    const loginInput=document.getElementById('loginInput');
    const login=loginInput.value.trim();
    if(!login||!selectedDay){alert('Wybierz dzień'); return;}
    if(!activeShift){alert('Wybierz shift'); return;}

    fetch('/api/entries',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({login,work_date:selectedDay,shift:activeShift})
    }).then(r=>{
        if(r.ok){
            loginInput.value='';
            const rowEl=document.querySelector(`.clickable-day[data-day="${selectedDay}"]`);
            selectDay(selectedDay,rowEl);
        } else {r.json().then(j=>alert(j.error||'Błąd'));}
    });
}

// --- Liczenie wpisów ---
function updateShiftCount(){
    const row=document.querySelector(`.clickable-day[data-day="${selectedDay}"]`);
    if(!row) return;

    const dayTable=document.getElementById('dayShiftTable');
    const nightTable=document.getElementById('nightShiftTable');

    row.cells[3].textContent = dayTable ? dayTable.querySelectorAll('tbody tr').length : 0;
    row.cells[4].textContent = nightTable ? nightTable.querySelectorAll('tbody tr').length : 0;
}

// --- Podwójny klik tylko w kolumnie Login ---
function attachRowDeleteHandler() {
    ['dayShiftTable','nightShiftTable'].forEach(tableId=>{
        const table = document.getElementById(tableId);
        if(!table) return;
        table.querySelectorAll('tbody tr').forEach(row=>{
            const loginCell = row.cells[0];
            loginCell.ondblclick = () => {
                if(rowSelectedForDelete) rowSelectedForDelete.classList.remove('selected-for-delete');
                row.classList.add('selected-for-delete');
                rowSelectedForDelete = row;
            };
        });
    });
}

// --- Delete ---
window.addEventListener('keydown', (e)=>{
    if(e.key==='Delete' && rowSelectedForDelete){
        const tr = rowSelectedForDelete;
        const login = tr.cells[0].innerText;
        const shift = tr.parentElement.parentElement.id.includes('day') ? 'day' : 'night';
        fetch('/api/entries/delete', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify({login, work_date:selectedDay, shift})
        }).then(r=>{
            if(r.ok){
                tr.remove();
                rowSelectedForDelete = null;
                updateShiftCount();
            } else {
                r.json().then(j=>alert(j.error || 'Błąd przy usuwaniu'));
            }
        });
    }
});

// --- Render tabel Day/Night + attach delete ---
function renderShiftTables(data){
    const dayShift = data.day_shift || [];
    const nightShift = data.night_shift || [];

    const dayBody = document.querySelector('#dayShiftTable tbody');
    const nightBody = document.querySelector('#nightShiftTable tbody');

    dayBody.innerHTML = '';
    nightBody.innerHTML = '';

    dayShift.forEach(item=>{
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${item.login}</td><td>${item.name || ''}</td><td>${item.shift_pattern || ''}</td>`;
        dayBody.appendChild(tr);
    });

    nightShift.forEach(item=>{
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${item.login}</td><td>${item.name || ''}</td><td>${item.shift_pattern || ''}</td>`;
        nightBody.appendChild(tr);
    });

    document.getElementById('dayShiftContainer').style.display='flex';
    document.getElementById('nightShiftContainer').style.display='flex';

    highlightActiveShift();
    updateShiftCount();

    attachRowDeleteHandler();
}

// --- Inicjalizacja ---
window.addEventListener('load', () => {
    // istniejące inicjalizacje
    loadWeeks();
    document.getElementById('addBtn').addEventListener('click', addEntry);
    document.getElementById('loginInput').addEventListener('keypress', e => { if(e.key==='Enter') addEntry(); });
    document.getElementById('dayShiftHeader').addEventListener('click', () => { activeShift='day'; highlightActiveShift(); });
    document.getElementById('nightShiftHeader').addEventListener('click', () => { activeShift='night'; highlightActiveShift(); });

    // --- kliknięcie gdziekolwiek odznacza wiersz do usunięcia ---
    document.addEventListener('click', (e) => {
        if (rowSelectedForDelete && !rowSelectedForDelete.contains(e.target)) {
            rowSelectedForDelete.classList.remove('selected-for-delete');
            rowSelectedForDelete = null;
        }
    });
});

// --- Miesiące ---
const months = [
  'Styczeń','Luty','Marzec','Kwiecień','Maj','Czerwiec',
  'Lipiec','Sierpień','Wrzesień','Październik','Listopad','Grudzień'
];

function loadSummaryMonths() {
  const container = document.getElementById('summaryMonthList');
  container.innerHTML = '';
  months.forEach((m,i)=>{
    const btn = document.createElement('button');
    btn.className = 'btn btn-outline-primary btn-sm m-1 month-btn';
    btn.innerText = m;
    btn.dataset.month = i+1;
    btn.addEventListener('click', ()=>selectMonth(i+1, btn));
    container.appendChild(btn);
  });
}

let selectedMonth = null;
function selectMonth(month, btn) {
  selectedMonth = month;
  document.querySelectorAll('.month-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');

  fetch(`/api/entries?month=${month}`)
    .then(r=>r.json())
    .then(data=>{
      renderMonthEntries(data.entries);
    });
}

function renderMonthEntries(entries) {
  const container = document.getElementById('summaryTableContainer');
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
      <td>${e.name}</td>
      <td>${e.work_date}</td>
      <td>${e.shift}</td>
    </tr>`;
  });

  html += '</tbody></table>';
  container.innerHTML = html;
}

// --- Inicjalizacja dla podsumowania ---
window.addEventListener('load',()=>{
  loadSummaryMonths();
});

