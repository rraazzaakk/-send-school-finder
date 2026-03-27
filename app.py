"""SEND School Finder – Flask Backend v2 (real DfE 2024/25 data)"""
import json, os
from flask import Flask, request, jsonify, render_template_string
from data_loader import get_schools, get_data_source, ingest_csv_bytes
from matching import search_schools, serialise_result, get_stats
from schools_data import SEN_LABELS, FACILITY_LABELS

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024

# ─── HTML ──────────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>SEND School Finder – England 2024/25</title>
<style>
:root{--primary:#1e40af;--pl:#3b82f6;--accent:#7c3aed;--success:#059669;--warning:#d97706;--danger:#dc2626;--bg:#f8fafc;--card:#fff;--border:#e2e8f0;--text:#1e293b;--muted:#64748b;}
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);}
.hdr{background:linear-gradient(135deg,var(--primary),var(--accent));color:#fff;padding:20px 32px;display:flex;align-items:center;gap:16px;box-shadow:0 4px 20px rgba(0,0,0,.15);}
.hdr h1{font-size:1.5rem;font-weight:700;}.hdr p{font-size:.85rem;opacity:.85;margin-top:2px;}
.badge{background:rgba(255,255,255,.2);border-radius:20px;padding:3px 10px;font-size:.75rem;margin-left:8px;}
.ds-bar{background:#eff6ff;border-bottom:1px solid #bfdbfe;padding:8px 32px;font-size:.78rem;color:var(--primary);display:flex;align-items:center;gap:8px;flex-wrap:wrap;}
.ds-dot{width:8px;height:8px;border-radius:50%;background:var(--success);flex-shrink:0;}
.ds-dot.warn{background:var(--warning);}
.wrap{max-width:1400px;margin:0 auto;padding:24px;display:grid;grid-template-columns:380px 1fr;gap:24px;}
@media(max-width:900px){.wrap{grid-template-columns:1fr;}}
.panel{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:24px;margin-bottom:0;}
.ptitle{font-size:1rem;font-weight:700;color:var(--primary);margin-bottom:16px;}
.field{margin-bottom:16px;}
.field label{display:block;font-size:.8rem;font-weight:600;color:var(--muted);margin-bottom:6px;text-transform:uppercase;letter-spacing:.04em;}
.field input,.field select{width:100%;border:1.5px solid var(--border);border-radius:8px;padding:10px 12px;font-size:.9rem;}
.field input:focus,.field select:focus{outline:none;border-color:var(--pl);}
.sgrid{display:grid;grid-template-columns:1fr 1fr;gap:6px;}
.schip{display:flex;align-items:center;gap:6px;cursor:pointer;font-size:.8rem;}
.schip input{width:16px;height:16px;accent-color:var(--primary);}
.schip .code{font-weight:700;color:var(--primary);min-width:36px;}
.slrow{display:flex;align-items:center;gap:10px;margin-bottom:10px;}
.slrow label{font-size:.8rem;width:80px;}
.slrow input[type=range]{flex:1;accent-color:var(--accent);}
.slrow .v{font-size:.8rem;font-weight:700;width:32px;text-align:right;color:var(--accent);}
.btn{width:100%;padding:12px;background:linear-gradient(135deg,var(--primary),var(--accent));color:#fff;border:none;border-radius:10px;font-size:1rem;font-weight:700;cursor:pointer;transition:opacity .2s;}
.btn:hover{opacity:.92;}.btn:disabled{opacity:.5;cursor:not-allowed;}
.btn-sm{width:auto;padding:7px 14px;font-size:.82rem;border-radius:8px;display:inline-block;text-decoration:none;color:#fff;}
.btn-grey{background:linear-gradient(135deg,#64748b,#475569);}
.sbar{display:grid;grid-template-columns:repeat(auto-fit,minmax(100px,1fr));gap:12px;margin-bottom:20px;}
.sc{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:12px 16px;text-align:center;}
.sc .n{font-size:1.6rem;font-weight:800;color:var(--primary);}
.sc .l{font-size:.72rem;color:var(--muted);margin-top:2px;text-transform:uppercase;}
.rc{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:20px;margin-bottom:16px;transition:box-shadow .2s,transform .2s;}
.rc:hover{box-shadow:0 8px 30px rgba(0,0,0,.1);transform:translateY(-2px);}
.rc.full{border-left:4px solid var(--success);}.rc.part{border-left:4px solid var(--warning);}
.ctop{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;}
.crk{font-size:1.4rem;font-weight:900;color:var(--border);min-width:32px;}
.crk.top{color:var(--accent);}
.cname{font-size:1.05rem;font-weight:700;}
.cadr{font-size:.82rem;color:var(--muted);margin-top:3px;}
.ctype{font-size:.75rem;color:var(--primary);margin-top:3px;}
.sbig{font-size:1.8rem;font-weight:900;color:var(--accent);line-height:1;}
.slbl{font-size:.65rem;color:var(--muted);text-transform:uppercase;}
.meta{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 8px;}
.pill{padding:3px 10px;border-radius:20px;font-size:.72rem;font-weight:600;}
.pd{background:#eff6ff;color:var(--primary);}
.po{background:#d1fae5;color:#065f46;}.pog{background:#e0f2fe;color:#075985;}
.por{background:#fef9c3;color:#854d0e;}.poi{background:#fee2e2;color:#991b1b;}
.pv{background:#f0fdf4;color:var(--success);}.pf{background:#fff7ed;color:var(--warning);}
.ss{display:flex;gap:12px;flex-wrap:wrap;margin-top:10px;border-top:1px solid var(--border);padding-top:10px;}
.ss-i{text-align:center;}
.ss-i .bar{height:4px;border-radius:2px;background:var(--border);margin-top:3px;width:60px;}
.ss-i .fill{height:100%;border-radius:2px;background:var(--accent);}
.ss-i .sl{font-size:.65rem;color:var(--muted);}
.ss-i .sv{font-size:.8rem;font-weight:700;}
.stags{display:flex;flex-wrap:wrap;gap:4px;margin-top:8px;}
.stag{padding:2px 8px;border-radius:12px;font-size:.7rem;font-weight:700;}
.stag-ok{background:#dcfce7;color:#166534;}
.stag-no{background:#fee2e2;color:#991b1b;}
.loading{display:none;text-align:center;padding:40px;}
.spin{width:40px;height:40px;border:4px solid var(--border);border-top-color:var(--primary);border-radius:50%;animation:spin .8s linear infinite;margin:0 auto 16px;}
@keyframes spin{to{transform:rotate(360deg);}}
.empty{text-align:center;padding:60px 20px;color:var(--muted);}
.empty .ico{font-size:3rem;margin-bottom:12px;}
.err{background:#fef2f2;border:1px solid #fca5a5;border-radius:10px;padding:12px 16px;color:#dc2626;margin-bottom:16px;font-size:.85rem;}
.ok{background:#f0fdf4;border:1px solid #86efac;border-radius:10px;padding:12px 16px;color:#166534;margin-bottom:16px;font-size:.85rem;}
.tog{cursor:pointer;user-select:none;display:flex;justify-content:space-between;align-items:center;}
.tog:hover{color:var(--primary);}
.arr{transition:transform .2s;}.arr.open{transform:rotate(180deg);}
.upz{border:2px dashed var(--border);border-radius:10px;padding:16px;text-align:center;cursor:pointer;transition:border-color .2s;margin-top:8px;}
.upz:hover{border-color:var(--pl);}
.upz p{font-size:.8rem;color:var(--muted);}
.urn{font-size:.65rem;color:var(--muted);background:#f8fafc;padding:1px 6px;border-radius:8px;border:1px solid var(--border);}
.rh{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;}
.rt{font-size:1.1rem;font-weight:700;}
</style></head>
<body>
<div class="hdr">
  <span style="font-size:2rem">🏫</span>
  <div>
    <h1>SEND School Finder <span class="badge">England</span></h1>
    <p>Smart SEN matching · Multi-criteria ranking · Official DfE 2024/25 data · Cloud-ready</p>
  </div>
</div>
<div class="ds-bar">
  <span class="ds-dot" id="ds-dot"></span>
  <span id="ds-txt">Loading…</span>
  <a href="https://explore-education-statistics.service.gov.uk/find-statistics/special-educational-needs-in-england/2024-25"
     target="_blank" style="color:var(--primary);font-size:.75rem;">📥 DfE 2024/25 official dataset</a>
</div>

<div class="wrap">
  <!-- LEFT PANEL -->
  <div style="display:flex;flex-direction:column;gap:16px;">
    <div class="panel">
      <div class="ptitle">🔍 Search</div>
      <div class="field">
        <label>Postcode</label>
        <input type="text" id="pc" placeholder="e.g. M14 4PQ, LS6 3BN…" value="M14 4PQ"/>
      </div>
      <div class="field">
        <label>Child's SEN Needs</label>
        <div class="sgrid" id="sen-boxes"></div>
      </div>
      <div class="field">
        <label>Max Distance</label>
        <select id="dist">
          <option value="">No limit</option>
          <option value="20">Within 20 miles</option>
          <option value="50" selected>Within 50 miles</option>
          <option value="100">Within 100 miles</option>
          <option value="200">Within 200 miles</option>
        </select>
      </div>
      <div class="field">
        <label>Match Mode</label>
        <select id="mode">
          <option value="full">Full match only</option>
          <option value="partial">Include partial matches</option>
        </select>
      </div>
      <div class="field">
        <div class="tog" onclick="togW()">
          <label style="cursor:pointer">⚖️ Scoring Weights</label>
          <span class="arr" id="warr">▼</span>
        </div>
        <div id="wbody" style="display:none;margin-top:12px;">
          <div class="slrow"><label>Need Match</label><input type="range" id="wn" min="0" max="100" value="40" oninput="sv('n')"/><span class="v" id="vn">40%</span></div>
          <div class="slrow"><label>Proximity</label><input type="range" id="wp" min="0" max="100" value="30" oninput="sv('p')"/><span class="v" id="vp">30%</span></div>
          <div class="slrow"><label>Capacity</label><input type="range" id="wc" min="0" max="100" value="15" oninput="sv('c')"/><span class="v" id="vc">15%</span></div>
          <div class="slrow"><label>Ofsted</label><input type="range" id="wo" min="0" max="100" value="15" oninput="sv('o')"/><span class="v" id="vo">15%</span></div>
          <small style="color:var(--muted);font-size:.72rem">Auto-normalised to 100%</small>
        </div>
      </div>
      <button class="btn" id="sbtn" onclick="doSearch()">🔎 Find Schools</button>
    </div>

    <div class="panel">
      <div class="ptitle">📥 Load Real DfE Data</div>
      <p style="font-size:.82rem;color:var(--muted);margin-bottom:10px;">
        Download the <strong>School Level Underlying Data 2024/25</strong> CSV from DfE (10 MB), then upload it here to replace the demo data with all ~1,100 real special schools.
      </p>
      <a href="https://explore-education-statistics.service.gov.uk/find-statistics/special-educational-needs-in-england/2024-25" target="_blank">
        <button class="btn btn-sm btn-grey" style="margin-bottom:10px;padding:8px 14px;border:none;cursor:pointer;font-weight:700;font-size:.82rem;border-radius:8px;">📥 Download from DfE gov.uk →</button>
      </a>
      <div class="upz" onclick="document.getElementById('csvf').click()">
        <input type="file" id="csvf" accept=".csv" style="display:none" onchange="uploadIt(this)"/>
        <div style="font-size:1.5rem">📂</div>
        <p><strong>Click to upload DfE CSV</strong><br/>school_level_underlying_data_2025.csv (~10 MB)</p>
      </div>
      <div id="upstat"></div>
    </div>
  </div>

  <!-- RIGHT PANEL -->
  <div>
    <div id="sbar"></div>
    <div class="loading" id="ld"><div class="spin"></div><p>Ranking schools…</p></div>
    <div id="errd"></div>
    <div id="resd">
      <div class="empty">
        <div class="ico">🏫</div>
        <p>Select SEN needs and enter a postcode to find matching schools</p>
        <p style="margin-top:12px;font-size:.8rem;color:var(--muted)">Using <span id="cnt">–</span> schools · DfE 2024/25 data</p>
      </div>
    </div>
  </div>
</div>

<script>
const SCODES={ASD:"Autism Spectrum Disorder",SEMH:"Social, Emotional & Mental Health",SLCN:"Speech, Language & Communication",MLD:"Moderate Learning Difficulty",SLD:"Severe Learning Difficulty",PMLD:"Profound & Multiple Learning Difficulty",SpLD:"Specific Learning Difficulty",HI:"Hearing Impairment",VI:"Visual Impairment",MSI:"Multi-Sensory Impairment",PD:"Physical Disability",OTH:"Other"};
// Live postcode geocoding via postcodes.io — supports ANY valid UK postcode
async function gc(postcode){
  const clean = postcode.trim().toUpperCase();
  try {
    const resp = await fetch('https://api.postcodes.io/postcodes/' + encodeURIComponent(clean));
    const data = await resp.json();
    if(data.status === 200 && data.result){
      return [data.result.latitude, data.result.longitude];
    }
    return null;
  } catch(e){
    return null;
  }
}

// Build SEN checkboxes
(function(){
  const g=document.getElementById('sen-boxes');
  Object.entries(SCODES).forEach(([code,label])=>{
    const el=document.createElement('label');el.className='schip';
    el.innerHTML=`<input type="checkbox" value="${code}"/><span><span class="code">${code}</span>${label.split(' ')[0]}</span>`;
    g.appendChild(el);
  });
})();

fetch('/api/info').then(r=>r.json()).then(d=>{
  const real=d.data_source&&d.data_source.includes('DfE School Level 2024');
  document.getElementById('ds-dot').className='ds-dot'+(real?'':' warn');
  document.getElementById('ds-txt').textContent=d.data_source||'Unknown';
  document.getElementById('cnt').textContent=d.total_schools+' schools';
});

function togW(){
  const b=document.getElementById('wbody'),a=document.getElementById('warr');
  const op=b.style.display!=='none';b.style.display=op?'none':'block';
  a.classList.toggle('open',!op);
}
function sv(k){const m={n:'n',p:'p',c:'c',o:'o'};document.getElementById('v'+k).textContent=document.getElementById('w'+k).value+'%';}
function gw(){const n=+document.getElementById('wn').value,p=+document.getElementById('wp').value,c=+document.getElementById('wc').value,o=+document.getElementById('wo').value,t=n+p+c+o||1;return{need_match:n/t,proximity:p/t,capacity:c/t,ofsted:o/t};}
function gn(){return[...document.querySelectorAll('#sen-boxes input:checked')].map(i=>i.value);}
function oc(o){return'p'+({'Outstanding':'o','Good':'og','Requires Improvement':'or','Inadequate':'oi'}[o]||'og');}

function rStats(s){
  if(!s){document.getElementById('sbar').innerHTML='';return;}
  document.getElementById('sbar').innerHTML=`<div class="sbar">
    <div class="sc"><div class="n">${s.total}</div><div class="l">Schools</div></div>
    <div class="sc"><div class="n">${s.full_matches}</div><div class="l">Full Match</div></div>
    <div class="sc"><div class="n">${s.outstanding_count}</div><div class="l">Outstanding</div></div>
    <div class="sc"><div class="n">${s.with_vacancies}</div><div class="l">Have Places</div></div>
    <div class="sc"><div class="n">${s.avg_distance_miles}</div><div class="l">Avg Miles</div></div>
    <div class="sc"><div class="n">${s.best_score}%</div><div class="l">Top Score</div></div>
  </div>`;
}

function rResults(rs){
  const a=document.getElementById('resd');
  if(!rs.length){a.innerHTML='<div class="empty"><div class="ico">🔍</div><p>No schools found.<br>Try wider distance or partial matches.</p></div>';return;}
  const sl={need_match:'Need Match',proximity:'Proximity',capacity:'Capacity',ofsted:'Ofsted'};
  a.innerHTML=`<div class="rh"><div class="rt">📋 ${rs.length} schools ranked</div></div>`
  +rs.map(r=>`
  <div class="rc ${r.full_match?'full':'part'}">
    <div class="ctop">
      <div style="display:flex;gap:12px;flex:1">
        <div class="crk ${r.rank<=3?'top':''}">#${r.rank}</div>
        <div>
          <div class="cname">${r.name}${r.urn?` <span class="urn">URN ${r.urn}</span>`:''}</div>
          <div class="cadr">📍 ${r.address}${r.la_name?' · '+r.la_name:''}</div>
          <div class="ctype">${r.school_type||''}${r.region?' · '+r.region:''}</div>
        </div>
      </div>
      <div style="text-align:center"><div class="sbig">${r.composite_score}%</div><div class="slbl">Suitability</div></div>
    </div>
    <div class="meta">
      <span class="pill pd">📏 ${r.distance_miles} mi</span>
      <span class="pill ${oc(r.ofsted)}">⭐ ${r.ofsted}</span>
      <span class="pill ${r.vacancies>0?'pv':'pf'}">${r.vacancies>0?'✅ '+r.vacancies+' places':'⚠️ No vacancies'}</span>
      ${r.has_sen_unit?'<span class="pill" style="background:#f5f3ff;color:#6d28d9">SEN Unit</span>':''}
      ${r.has_rp_unit?'<span class="pill" style="background:#fdf4ff;color:#86198f">Resource Prov.</span>':''}
      <span class="pill" style="background:#f1f5f9;color:#475569">Cap: ${r.capacity}</span>
    </div>
    <div class="stags">
      ${r.covered_needs.map(n=>`<span class="stag stag-ok">✓ ${n}</span>`).join('')}
      ${r.missing_needs.map(n=>`<span class="stag stag-no">✗ ${n}</span>`).join('')}
    </div>
    <div class="ss">
      ${Object.entries(r.sub_scores).map(([k,v])=>`<div class="ss-i"><div class="sv">${v}%</div><div class="sl">${sl[k]||k}</div><div class="bar"><div class="fill" style="width:${v}%"></div></div></div>`).join('')}
    </div>
  </div>`).join('');
}

async function doSearch(){
  const needs=gn();
  if(!needs.length){alert('Select at least one SEN need.');return;}
  const pc=document.getElementById('pc').value.trim();
  if(!pc){alert('Enter a postcode.');return;}
  document.getElementById('sbtn').disabled=true;
  document.getElementById('ld').style.display='block';
  document.getElementById('ld').querySelector('p').textContent='Looking up postcode…';
  document.getElementById('resd').innerHTML='';
  document.getElementById('sbar').innerHTML='';
  document.getElementById('errd').innerHTML='';
  const coords=await gc(pc);
  if(!coords){
    document.getElementById('ld').style.display='none';
    document.getElementById('sbtn').disabled=false;
    document.getElementById('errd').innerHTML='<div class="err">⚠️ Postcode not found. Please enter a valid UK postcode (e.g. M14 4PQ, N1 1AA, SW1A 1AA).</div>';
    return;
  }
  document.getElementById('ld').querySelector('p').textContent='Ranking schools…';
  try{
    const r=await fetch('/api/search',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({lat:coords[0],lng:coords[1],needs,weights:gw(),
        max_distance:document.getElementById('dist').value||null,
        require_full_match:document.getElementById('mode').value==='full'})});
    const d=await r.json();
    if(!r.ok)throw new Error(d.error||'Search failed');
    rStats(d.stats);rResults(d.results);
  }catch(e){document.getElementById('errd').innerHTML=`<div class="err">⚠️ ${e.message}</div>`;}
  finally{document.getElementById('ld').style.display='none';document.getElementById('sbtn').disabled=false;}
}

async function uploadIt(inp){
  const file=inp.files[0];if(!file)return;
  const st=document.getElementById('upstat');
  st.innerHTML='<div class="ok">⏳ Processing CSV — this can take 30–90 seconds…</div>';
  const fd=new FormData();fd.append('file',file);
  try{
    const r=await fetch('/api/upload-csv',{method:'POST',body:fd});
    const d=await r.json();
    if(!r.ok)throw new Error(d.error||'Upload failed');
    st.innerHTML=`<div class="ok">✅ Loaded <strong>${d.schools_saved}</strong> real special schools!<br>Geocoded: ${d.geocoded} · No coords: ${d.no_coords} · No SEN: ${d.no_sen}</div>`;
    fetch('/api/info').then(r=>r.json()).then(d=>{
      document.getElementById('ds-txt').textContent=d.data_source;
      document.getElementById('ds-dot').className='ds-dot';
      document.getElementById('cnt').textContent=d.total_schools+' schools';
    });
  }catch(e){st.innerHTML=`<div class="err">❌ ${e.message}</div>`;}
  inp.value='';
}

document.getElementById('pc').addEventListener('keydown',e=>{if(e.key==='Enter')doSearch();});
</script>
</body></html>"""

# ─── Routes ────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/health")
def health():
    return jsonify({"status":"ok","schools":len(get_schools()),"source":get_data_source()})

@app.route("/api/info")
def info():
    return jsonify({"total_schools":len(get_schools()),"data_source":get_data_source()})

@app.route("/api/search", methods=["POST"])
def search():
    try:
        d = request.get_json(force=True)
        raw = search_schools(
            user_lat=float(d.get("lat",51.5)),
            user_lng=float(d.get("lng",-0.13)),
            requested_needs=d.get("needs",[]),
            weights=d.get("weights") or {"need_match":.4,"proximity":.3,"capacity":.15,"ofsted":.15},
            max_distance=float(d["max_distance"]) if d.get("max_distance") else None,
            require_full_match=bool(d.get("require_full_match",True)),
            schools_override=get_schools(),
        )
        return jsonify({"results":[serialise_result(r,i+1) for i,r in enumerate(raw)],"stats":get_stats(raw,d.get("needs",[]))})
    except Exception as e:
        return jsonify({"error":str(e)}), 400

@app.route("/api/upload-csv", methods=["POST"])
def upload_csv():
    try:
        if "file" not in request.files:
            return jsonify({"error":"No file"}), 400
        f = request.files["file"]
        csv_bytes = f.read()

        import csv as csvlib, io as io_mod, urllib.request as urlreq, json as jl
        text = csv_bytes.decode("utf-8-sig")
        reader = csvlib.DictReader(io_mod.StringIO(text))
        postcodes, special = set(), 0
        for row in reader:
            ph=row.get("phase_type_grouping",""); et=row.get("type_of_establishment","")
            if "special" in ph.lower() or "special" in et.lower():
                special += 1
                pc=row.get("school_postcode","").strip().upper()
                if pc: postcodes.add(pc)

        if special == 0:
            return jsonify({"error":"No special school rows found. Check this is the DfE school-level CSV."}), 400

        # Batch geocode
        coords_map = {}
        pl = list(postcodes)
        for i in range(0, len(pl), 100):
            batch = pl[i:i+100]
            try:
                req = urlreq.Request("https://api.postcodes.io/postcodes",
                    data=jl.dumps({"postcodes":batch}).encode(),
                    headers={"Content-Type":"application/json"}, method="POST")
                with urlreq.urlopen(req, timeout=30) as resp:
                    res = jl.loads(resp.read())
                for item in res.get("result",[]):
                    if item and item.get("result"):
                        r = item["result"]
                        coords_map[item["query"].upper()] = (r["latitude"], r["longitude"])
            except Exception:
                pass

        stats = ingest_csv_bytes(csv_bytes, coords_map)
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error":str(e)}), 500

@app.route("/api/schools")
def all_schools():
    s = get_schools()
    return jsonify({"count":len(s),"data_source":get_data_source(),"schools":s})

@app.route("/api/school/<sid>")
def school_detail(sid):
    s = next((x for x in get_schools() if x["id"]==sid or x.get("urn")==sid), None)
    if not s: return jsonify({"error":"Not found"}), 404
    return jsonify(s)

@app.route("/api/stats")
def aggregate_stats():
    from collections import Counter
    schools = get_schools()
    sf = Counter(c for s in schools for c in s["sen_provision"])
    rg = Counter(s.get("region","?") for s in schools)
    tc = sum(s.get("capacity",0) for s in schools)
    tv = sum(s.get("vacancies",0) for s in schools)
    return jsonify({"total_schools":len(schools),"data_source":get_data_source(),
        "total_capacity":tc,"total_vacancies":tv,
        "occupancy_pct":round((tc-tv)/max(tc,1)*100,1),
        "by_region":dict(rg.most_common()),"by_sen_type":dict(sf.most_common())})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🏫 SEND School Finder v2 | {get_data_source()}")
    app.run(host="0.0.0.0", port=port, debug=False)
