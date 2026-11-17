"""Stage 8: build the static feature browser, browser/index.html, from saved results only.

Sources: results/stage5/features.json, results/stage5_random/features.json, results/stage5_blind_per_feature.csv,
results/stage6/steering*.json, results/stage7/{analysis,selective,top_feature_examples}.json,
results/headline_numbers.json. One self-contained HTML file: no network, no libraries.
Run scripts/stage8_numbers.py first.
"""
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import ROOT

R = ROOT / "results"
J = lambda p: json.loads((R / p).read_text())
N = J("headline_numbers.json")
rows = list(csv.DictReader(open(R / "stage5_blind_per_feature.csv")))
snip = lambda lst: [{"a": round(e["act"], 2), "t": e["text"]} for e in lst]


def entry(sae, f, r):
    return {"id": f"{sae}-{f['feature']}", "sae": sae, "idx": f["index_in_list"], "feature": f["feature"], "label": r["label"],
            "verdict": r["verdict_suggested"], "random_agree": r["random_agree"], "clear": r["final_clear"] == "True",
            "blind": int(r["correct_of_5"]), "freq": f["firing_frequency"], "max": round(f["max_act"], 2), "median": round(f["median_act"], 2),
            "promoted": f["promoted_tokens"], "suppressed": f["suppressed_tokens"], "top": snip(f["top"]), "random": snip(f["random"])}


entries = []
for sae, fp in (("real", "stage5/features.json"), ("control", "stage5_random/features.json")):
    byidx = {f["index_in_list"]: f for f in J(fp)["features"]}
    for r in rows:
        if r["set"] == sae:
            entries.append(entry(sae, byidx[int(r["index_in_list"])], r))
real = {e["feature"]: e for e in entries if e["sae"] == "real"}
# blind strict-clear verdicts from the review rerun replace my non-blind verdicts (kept as old_clear, marked withdrawn)
bv = {(r["set"], int(r["feature"])): r for r in csv.DictReader(open(R / "stage5b_per_feature.csv"))}
for e in entries:
    r = bv[(e["sae"], e["feature"])]
    e["old_clear"] = e["clear"]
    e["clear"] = r["blind_strict_clear"] == "True"
    e["bv"] = {"j1t": int(r["j1_top_fit"]), "j1r": int(r["j1_random_fit"]), "j2t": int(r["j2_top_fit"]), "j2r": int(r["j2_random_fit"])}
# steering designs 2 and 3
for tag, fn in (("steer2", "stage6b_summary.json"), ("steer3", "stage6c_summary.json")):
    Sx = J(fn)
    for f in Sx["features"]:
        real[f["feature"]][tag] = {"steers": f["steers"], "threshold": round(Sx["fluent_threshold_ppl"], 2), "label_words": f["label_words"],
                                   "unsteered_hits": round(f["unsteered_hits_mean"], 1),
                                   "rows": [{"k": k, "fh": round(c["feature_hits_mean"], 1), "rh": round(c["random_hits_mean"], 1), "w": c["prompts_feature_beats_random_mean"],
                                             "ppl": round(c["feature_ppl_median"], 1), "len": round(c["vector_norm_model_units"] / N["setup"]["mean_activation_norm_model_units"], 2),
                                             "fluent": c["fluent"], "on": c["on_label"], "ok": c["success"]} for k, c in f["by_k"].items()]}

# ---- steering (stage 6 main + extension) ----
for fname, kind in (("stage6/steering.json", "main"), ("stage6/steering_extension.json", "extension")):
    d = J(fname)
    for f in d["features"]:
        real[f["feature"]]["steer"] = {
            "kind": kind, "group": f["group"], "prompts": d["prompts"], "multipliers": d["multipliers"],
            "strength_sae_units": round(f["typical_strength_sae_units"], 2),
            "runs": [{"p": r["prompt_index"], "k": r["kind"], "m": r["multiplier"], "t": r["text"], "ppl": round(r["ppl_clean"], 1),
                      "h": r["promoted_hits"]} for r in f["runs"]]}

# ---- stage 7 ----
an, sel, ex = J("stage7/analysis.json"), J("stage7/selective.json"), J("stage7/top_feature_examples.json")
trace = {}
for j, d in an["features"].items():
    trace[int(j)] = {"in_top10": "overall" in d["in_top"], "top_of": d["in_top"], "girl": round(d["heldout_effect"]["girl"], 2),
                     "boy": round(d["heldout_effect"]["boy"], 2), "peak_girl": round(d["mean_peak_act_girl_prompts"], 1),
                     "peak_boy": round(d["mean_peak_act_boy_prompts"], 1), "peak_tokens": d["peak_token_counts"], "label7": d["stage5_label_AI_written"]}
for g in ("girl", "boy"):
    for j, d in sel["sets"][g]["per_feature"].items():
        t = trace.setdefault(int(j), {})
        t["selective_for"] = g
        t["sel_rank_effect"] = round(d["rank_effect_own"], 2)
        t["sel_heldout_effect_own"] = round(d["heldout_effect_own"], 2)
        t["sel_heldout_effect_other"] = round(d["heldout_effect_other"], 2)
        t["sel_peak"] = {k: round(v, 1) for k, v in d["heldout_names_peak_act"].items()}
extra = []
for j, t in sorted(trace.items()):
    if j in real:
        real[j]["trace"] = t
    else:  # traced feature that was not among the 200 labelled ones
        e = ex.get(str(j), {"top": [], "firing_frequency": None})
        toks = Counter(m.group(1).strip() for x in e["top"] for m in [re.search(r"\[\[(.*?)\]\]", x["text"])] if m)
        hint = ", ".join(json.dumps(t, ensure_ascii=False) for t, _ in toks.most_common(3)) or None
        extra.append({"id": f"real-{j}", "sae": "real", "idx": None, "feature": j, "label": None, "verdict": None, "random_agree": None,
                      "clear": False, "blind": None, "freq": e["firing_frequency"], "max": None, "median": None, "promoted": [], "suppressed": [],
                      "top": snip(e["top"]), "random": [], "trace": t, "unlabelled": True, "hint": hint})
entries += extra
# tracing rerun (held-out names x held-out frames, activation-matched control)
t2 = J("stage7b/analysis.json")
for setname, s_ in (("top 10", t2["top10"]), ("girl-selective", t2["selective"]["girl"]), ("boy-selective", t2["selective"]["boy"])):
    for j, a, b in zip(s_["features"], s_["rank_effect_each"], s_["heldout_effect_each"]):
        e = next(x for x in entries if x["sae"] == "real" and x["feature"] == j)
        e.setdefault("trace", {}).setdefault("rerun", []).append({"set": setname, "rank": round(a, 2), "heldout": round(b, 2)})
for e in extra:
    e["old_clear"], e["bv"] = False, None
V5 = N["stage5_v2"]
summary = {"clear": V5["verdicts"]["real"]["strict_clear"], "old_clear": N["interpretation"]["clear_real"], "n": N["interpretation"]["n_features_labelled"],
           "clear_ctrl_blind": V5["verdicts"]["control"]["strict_clear"],
           "fresh_real": V5["blind_test_fresh_text"]["real_50"]["mean_accuracy"], "fresh_control": V5["blind_test_fresh_text"]["control_50"]["mean_accuracy"],
           "d2": N["steering_designs"]["design2"]["n_steer_total"], "d3": N["steering_designs"]["design3"]["n_steer_total"], "dn": N["steering_designs"]["design2"]["n_features"],
           "minw": N["steering_designs"]["rule_min_wins"], "rule": V5["rule"],
           "blind_real": N["interpretation"]["blind"]["real_all_200"]["mean_accuracy"],
           "blind_control": N["interpretation"]["blind"]["control_50"]["mean_accuracy"],
           "clear_control": N["interpretation"]["clear_control"], "n_control": N["interpretation"]["n_control_labelled"],
           "lam": N["setup"]["chosen_lambda"], "m": N["setup"]["dictionary_size"], "model": N["setup"]["model"], "layer": N["setup"]["layer"],
           "break_ppl": N["steering"]["break_threshold_ppl"]}

HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Feature Browser</title>
<style>
:root{--bg:#fbfaf7;--panel:#fff;--ink:#1d1d1b;--mute:#6b6a64;--line:#e4e1d8;--accent:#2f5d8a;--mark:#ffe08a;--ok:#2f7d4f;--bad:#a8402f;--warn:#9a6a00;--chip:#f0eee7}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#161615;--panel:#1f1f1d;--ink:#ecebe6;--mute:#9c9a92;--line:#33322e;--accent:#7fb0e0;--mark:#6b5410;--ok:#6fcf97;--bad:#f08a78;--warn:#e0b44a;--chip:#2a2926}}
:root[data-theme="dark"]{--bg:#161615;--panel:#1f1f1d;--ink:#ecebe6;--mute:#9c9a92;--line:#33322e;--accent:#7fb0e0;--mark:#6b5410;--ok:#6fcf97;--bad:#f08a78;--warn:#e0b44a;--chip:#2a2926}
*{box-sizing:border-box}html,body{max-width:100%;overflow-x:hidden}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
header{padding:12px 16px;border-bottom:1px solid var(--line);background:var(--panel)}
h1{font-size:18px;margin:0 0 4px}.sub{color:var(--mute);font-size:13px}
.banner{margin-top:8px;padding:8px 12px;border-left:4px solid var(--warn);background:var(--chip);font-size:13px}
.layout{display:grid;grid-template-columns:minmax(0,340px) minmax(0,1fr);height:calc(100vh - var(--hh,150px))}
nav{min-width:0;border-right:1px solid var(--line);overflow-y:auto;overflow-x:hidden;background:var(--panel)}
.tools{position:sticky;top:0;background:var(--panel);padding:10px;border-bottom:1px solid var(--line);display:grid;gap:6px;z-index:2}
input,select,button{width:100%;max-width:100%;font:inherit;color:inherit;background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:5px 8px}
.row{padding:8px 12px;border-bottom:1px solid var(--line);cursor:pointer}.row:hover{background:var(--chip)}.row.sel{background:var(--chip);border-left:3px solid var(--accent);padding-left:9px}
.row .t{font-size:13px;word-break:break-word}.row .m{font-size:12px;color:var(--mute)}
main{min-width:0;overflow:auto;padding:16px 20px}
.chip{display:inline-block;padding:1px 8px;margin:0 4px 4px 0;border-radius:10px;background:var(--chip);font-size:12px;border:1px solid var(--line)}
.ok{color:var(--ok)}.bad{color:var(--bad)}.warn{color:var(--warn)}
h2{font-size:16px;margin:22px 0 6px;padding-top:8px;border-top:1px solid var(--line)}h3{font-size:14px;margin:14px 0 4px}
.snip{font:13px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace;padding:3px 0;border-bottom:1px dotted var(--line);white-space:pre-wrap;word-break:break-word}
.snip b{font-weight:600;color:var(--mute);margin-right:6px}mark{background:var(--mark);color:inherit;padding:0 2px;border-radius:3px}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid var(--line);padding:5px 7px;vertical-align:top;text-align:left}th{background:var(--chip)}
td.txt{font-family:ui-monospace,Menlo,monospace;font-size:12px;white-space:pre-wrap;word-break:break-word;max-width:420px}
.broken{background:rgba(168,64,47,.12)}.note{color:var(--mute);font-size:13px}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.legend{font-size:12px;color:var(--mute)}
@media (max-width:820px){.layout{display:block;height:auto}nav{max-height:42vh;border-right:0;border-bottom:1px solid var(--line)}.cols{grid-template-columns:1fr}main{padding:12px 16px}}
</style></head><body>
<header><h1>Feature browser: sparse autoencoder on TinyStories-8M</h1>
<div class="sub" id="sub"></div>
<div class="banner"><b>All feature labels are AI-written (by Claude) and have not been verified by a human.</b> The blind tests and blind verdicts shown here were also done by Claude sub-agents, so nothing has had a human check. “Blind strict-clear” means two fresh judges, not told which autoencoder a feature came from, both found that the label fits most of its strongest examples <i>and</i> most of 10 randomly chosen firings. My own earlier non-blind verdicts are shown only as withdrawn. This page was updated after a review; see REPORT.md, “Review and corrections”.</div></header>
<div class="layout"><nav><div class="tools">
<input id="q" placeholder="Search labels, tokens, feature number…" autocomplete="off">
<select id="sae"><option value="real">Real autoencoder (200 random features + traced ones)</option><option value="control">Shuffled-weights control (50 features)</option></select>
<select id="flt"><option value="all">All</option><option value="clear">Blind strict-clear</option><option value="unclear">Not blind strict-clear</option><option value="oldclear">My non-blind “clear” (withdrawn)</option><option value="b5">Blind test 5/5</option><option value="b3">Blind test 3/5 or lower</option><option value="steer">Steered in Stage 6</option><option value="steerok">Passed a fixed steering rule (design 2 or 3)</option><option value="trace">Used in Stage 7</option></select>
<div class="legend" id="count"></div></div><div id="list"></div></nav>
<main id="main"></main></div>
<script id="data" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent),E=D.entries,S=D.summary;
const $=(s)=>document.querySelector(s);
function el(tag,cls,txt){const e=document.createElement(tag);if(cls)e.className=cls;if(txt!==undefined)e.textContent=txt;return e}
function snip(a,t){const d=el('div','snip');if(a!==undefined&&a!==null){d.appendChild(el('b',null,a.toFixed(2)))}
  const m=t.match(/^([\s\S]*?)\[\[([\s\S]*?)\]\]([\s\S]*)$/);
  if(!m){d.appendChild(document.createTextNode(t));return d}
  d.appendChild(document.createTextNode(m[1]));d.appendChild(el('mark',null,m[2]));d.appendChild(document.createTextNode(m[3]));return d}
function name(e){return e.label===null?'Feature '+e.feature+(e.hint?': top examples fire on '+e.hint:' (no examples saved)')+' (no AI label; not among the 200 labelled)':e.label}
const f2=x=>Number(x).toFixed(2);
$('#sub').textContent=S.model+', residual stream after block '+S.layer+'; sparse autoencoder with '+S.m+' features, λ='+S.lam+'. '
 +'Blind strict-clear: '+S.clear+'/'+S.n+' real, '+S.clear_ctrl_blind+'/'+S.n_control+' control (my withdrawn non-blind count was '+S.old_clear+'). Blind label test on fresh text: '+f2(S.fresh_real)+' (real) vs '+f2(S.fresh_control)+' (control); chance 0.50. Steering under fixed rules: '+S.d2+'/'+S.dn+' (design 2), '+S.d3+'/'+S.dn+' (design 3).';
let sel=null;
function matches(e){
  if(e.sae!==$('#sae').value)return false;const f=$('#flt').value;
  if(f==='clear'&&!e.clear)return false;if(f==='unclear'&&(e.clear||e.unlabelled))return false;
  if(f==='b5'&&e.blind!==5)return false;if(f==='b3'&&!(e.blind!==null&&e.blind<=3))return false;
  if(f==='steer'&&!e.steer)return false;if(f==='oldclear'&&!e.old_clear)return false;
  if(f==='steerok'&&!((e.steer2&&e.steer2.steers)||(e.steer3&&e.steer3.steers)))return false;if(f==='trace'&&!e.trace)return false;
  const q=$('#q').value.trim().toLowerCase();if(!q)return true;
  return (String(e.feature)===q)||name(e).toLowerCase().includes(q)||e.promoted.join(' ').toLowerCase().includes(q)
    ||e.top.some(s=>s.t.toLowerCase().includes(q));}
function renderList(){const L=$('#list');L.textContent='';let n=0;
  E.filter(matches).forEach(e=>{n++;const r=el('div','row'+(sel===e.id?' sel':''));r.dataset.id=e.id;
    r.appendChild(el('div','t',name(e)));
    const m=el('div','m','feature '+e.feature+(e.blind!==null?' · blind '+e.blind+'/5':'')+(e.clear?' · blind-clear':'')+(e.steer?' · steered':'')+(e.trace?' · traced':''));r.appendChild(m);
    r.onclick=()=>{location.hash=e.id};L.appendChild(r)});
  $('#count').textContent=n+' features shown'}
function chips(parent,items){items.forEach(([t,c])=>parent.appendChild(el('span','chip '+(c||''),t)))}
function renderMain(){const M=$('#main');M.textContent='';const e=E.find(x=>x.id===sel);
  if(!e){M.appendChild(el('p','note','Pick a feature on the left. Each page shows the AI-written label, the blind-test result, the strongest and random firings, and any steering or tracing results.'));return}
  M.appendChild(el('h2',null,name(e))).style.borderTop='0';
  if(e.sae==='control')M.appendChild(el('p','warn','This feature belongs to the shuffled-weights control autoencoder (trained on a model with scrambled weights). It is here for comparison.'));
  const c=el('div');chips(c,[['feature '+e.feature],['λ='+S.lam+(e.sae==='control'?' control':'')]]);
  if(e.verdict!==null){const b=e.bv;chips(c,[[e.clear?'blind strict-clear':'not blind strict-clear',e.clear?'ok':'bad'],
    ['judges: label fits '+b.j1t+' and '+b.j2t+' of '+S.rule.top_n+' top examples, '+b.j1r+' and '+b.j2r+' of '+S.rule.random_n+' random firings (clear needs '+S.rule.top_min+' and '+S.rule.random_min+')'],
    ['my non-blind verdict (withdrawn): '+(e.old_clear?'clear':'not clear'),'warn'],
    ['blind test: '+e.blind+'/5 (chance 2.5)',e.blind>=4?'ok':(e.blind<=3?'bad':'')]]);
    chips(c,[['fires on '+(e.freq*100).toFixed(2)+'% of tokens'],['max '+e.max+', median '+e.median]])}
  else chips(c,[['not one of the 200 randomly chosen labelled features','warn']]);
  M.appendChild(c);
  if(e.promoted.length){M.appendChild(el('h3',null,'Output tokens its direction promotes (approximate: four blocks still follow layer 3)'));
    M.appendChild(el('div',null,e.promoted.map(t=>JSON.stringify(t)).join('  ')));
    M.appendChild(el('div','note','suppresses: '+e.suppressed.map(t=>JSON.stringify(t)).join('  ')))}
  M.appendChild(el('h2',null,'Top examples (strongest firings; firing token highlighted, activation first)'));e.top.forEach(s=>M.appendChild(snip(s.a,s.t)));
  if(e.random.length){M.appendChild(el('h2',null,'Random firings (typical, often weaker)'));
    M.appendChild(el('p','note','A label that fits only the top examples but not these is the common failure.'));e.random.forEach(s=>M.appendChild(snip(s.a,s.t)))}
  if(e.steer)renderSteer(M,e);if(e.trace)renderTrace(M,e)}
function renderSteer(M,e){const s=e.steer;
  M.appendChild(el('h2',null,'Steering design 1 (exploratory: 2 prompts, judged by reading)'));
  M.appendChild(el('p','note','Chosen as: '+(s.kind==='main'?(s.group==='clear_5of5'?'strict-clear and 5/5 blind':'NOT clear (shown to see steering with a weak label)'):(s.group==='clear'?'topic label, clear':'topic label, not clear'))+
   '. Added strength × '+s.strength_sae_units+' (its typical strong firing, SAE units) × its decoder direction at layer '+S.layer+'. Random control: random direction of the same length. Text is 50 sampled tokens; “ppl” is its perplexity under the unsteered model (above '+S.break_ppl+' = shaded; an arbitrary cut-off, replaced in designs 2 and 3).'));
  const sel2=el('select');s.prompts.forEach((p,i)=>{const o=el('option',null,'Prompt: '+p);o.value=i;sel2.appendChild(o)});M.appendChild(sel2);
  const holder=el('div');M.appendChild(holder);
  const draw=()=>{holder.textContent='';const p=+sel2.value;const tb=el('table');const h=el('tr');['strength','feature steering','random direction (same length)'].forEach(x=>h.appendChild(el('th',null,x)));tb.appendChild(h);
    const base=s.runs.find(r=>r.p===p&&r.k==='none');
    const add=(lab,a,b)=>{const tr=el('tr');tr.appendChild(el('td',null,lab));[a,b].forEach(r=>{const td=el('td','txt');if(r){td.textContent='['+r.ppl+'] '+r.t.replace(/\n/g,' ⏎ ');if(r.ppl>S.break_ppl)td.className+=' broken'}else td.textContent='';tr.appendChild(td)});tb.appendChild(tr)};
    add('none',base,null);
    s.multipliers.forEach(m=>add(m+'×',s.runs.find(r=>r.p===p&&r.k==='feature'&&r.m===m),s.runs.find(r=>r.p===p&&r.k==='random'&&r.m===m)));
    holder.appendChild(tb)};
  sel2.onchange=draw;draw();
  [['steer2','Steering design 2: strength in multiples of the median firing'],['steer3','Steering design 3 (last): strength as a fraction of the mean activation length']].forEach(([k,title])=>{const d=e[k];if(!d)return;
    M.appendChild(el('h2',null,title+(d.steers?' — passes the fixed rule':' — does not pass')));
    M.appendChild(el('p','note','10 prompts, 3 random directions of the same length. Label words (from the label only): '+d.label_words.join(', ')+'. Unsteered: '+d.unsteered_hits+' label words per text. Fluent = median perplexity ≤ '+d.threshold+'; on-label = more label words than random on at least '+S.minw+' of 10 prompts. Length = fraction of the mean activation length.'));
    const tb=el('table');const h=el('tr');['strength','length','label words: feature / random','prompts won','perplexity','fluent','on-label','passes'].forEach(x=>h.appendChild(el('th',null,x)));tb.appendChild(h);
    d.rows.forEach(r=>{const tr=el('tr');[r.k,r.len,r.fh+' / '+r.rh,r.w,r.ppl,r.fluent?'yes':'no',r.on?'yes':'no',r.ok?'YES':'no'].forEach((v,i)=>{const td=el('td',null,String(v));if(i===4&&!r.fluent)td.className='broken';tr.appendChild(td)});tb.appendChild(tr)});
    M.appendChild(tb)})}
function renderTrace(M,e){const t=e.trace;M.appendChild(el('h2',null,'Pronoun tracing (Stage 7)'));
  M.appendChild(el('p','note','Score = logit(correct pronoun) − logit(wrong pronoun). Effect = drop in score when this one feature is switched off (SAE error added back); positive means the feature supports the correct pronoun. Held-out names, name-only prompts.'));
  const c=el('div');
  if(t.girl!==undefined)chips(c,[['first run — effect on girl-name prompts: '+t.girl],['effect on boy-name prompts: '+t.boy],['peak activation girl / boy prompts: '+t.peak_girl+' / '+t.peak_boy],
    [t.top_of.length?('in the top 10 ranking for: '+t.top_of.join(', ')):'not in a top-10 list']]);
  if(t.selective_for)chips(c,[['gender-selective feature (exploratory): '+t.selective_for,'warn'],['effect on '+t.selective_for+' prompts (held-out): '+t.sel_heldout_effect_own],['on the other gender: '+t.sel_heldout_effect_other]]);
  M.appendChild(c);
  if(t.peak_tokens&&Object.keys(t.peak_tokens).length)M.appendChild(el('div','note','where it peaks on the test prompts: '+Object.entries(t.peak_tokens).map(([k,v])=>JSON.stringify(k)+' ×'+v).join(', ')));
  if(t.sel_peak)M.appendChild(el('div','note','peak activation by held-out name: '+Object.entries(t.sel_peak).map(([k,v])=>k+' '+v).join(', ')));
  if(t.rerun){M.appendChild(el('h3',null,'Rerun (held-out names and new sentence frames, activation-matched control)'));const c2=el('div');
    chips(c2,t.rerun.map(r=>['in '+r.set+': effect on ranking prompts '+r.rank+', on held-out prompts '+r.heldout]));M.appendChild(c2)}
  M.appendChild(el('p','note','The chips above the rerun line are from the first run, whose random control was not matched and whose test shared sentence frames with the ranking. The gender-selective analysis is exploratory. Full tables: results/stage7b_report.md (rerun), results/stage7_report.md (first run).'))}
function sync(){const h=decodeURIComponent(location.hash.slice(1));const e=E.find(x=>x.id===h);
  if(e){if(e.sae!==$('#sae').value){$('#sae').value=e.sae}sel=e.id}else sel=null;renderList();renderMain();
  const r=document.querySelector('.row.sel');if(r&&r.scrollIntoView)r.scrollIntoView({block:'nearest'})}
['q','sae','flt'].forEach(i=>$('#'+i).addEventListener(i==='q'?'input':'change',renderList));
$('#sae').addEventListener('change',()=>{location.hash=''});
window.addEventListener('hashchange',sync);
function setH(){document.documentElement.style.setProperty('--hh',document.querySelector('header').offsetHeight+'px')}setH();window.addEventListener('resize',setH);
sync();
</script></body></html>"""

payload = json.dumps({"entries": entries, "summary": summary}, ensure_ascii=False).replace("</", "<\\/")
out = ROOT / "browser"
out.mkdir(exist_ok=True)
(out / "index.html").write_text(HTML.replace("__DATA__", payload))
print(f"wrote browser/index.html ({(out / 'index.html').stat().st_size / 1e6:.2f} MB): "
      f"{sum(e['sae'] == 'real' and not e.get('unlabelled') for e in entries)} real, {sum(e['sae'] == 'control' for e in entries)} control, "
      f"{len(extra)} traced-only, {sum('steer' in e for e in entries)} steered, {sum('trace' in e for e in entries)} traced")
