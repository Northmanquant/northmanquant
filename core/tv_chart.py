# -*- coding: utf-8 -*-
"""core/tv_chart.py — چارت موتور TradingView برای داشبورد (lightweight-charts v4.2)
=====================================================================================
نسخه‌ی ۲: علاوه بر موتور پن/زوم/کراس‌هیر، ابزارها و اندیکاتورهای تریدینگ‌ویو:

  ▸ تایم‌فریم‌سوئیچر داخل چارت (15m/1H/4H/1D/1W) — داده‌ی همه‌ی TFها از پایتون
  ▸ انواع چارت: کندل · میله · خط · ناحیه · هایکن‌آشی
  ▸ اندیکاتورها (منوی ƒ): EMA20/50/200 · بولینگر(20,2) · VWAP · میانگین حجم · RSI(14) · MACD(12,26,9)
  ▸ پنل‌های جداگانه‌ی RSI و MACD با کراس‌هیر و محور زمان همگام
  ▸ ابزارهای رسم: خط روند · خط افقی · مستطیل · فیبوناچی · خط‌کش (اندازه‌گیری)
     + واگرد/پاک‌کردن + ذخیره‌ی خودکار در localStorage (مقاوم به رفرش)
  ▸ لجند OHLCV + مقادیر زنده‌ی اندیکاتورها (مثل TV)
  ▸ نواحی FVG/BVG و خطوط ورود/حد ضرر/اهداف (تایم‌فریم پایه)
  ▸ بازنشانی نما · پرش به «الان» · تمام‌صفحه · اسکرین‌شات PNG (با رسم‌ها)

کتابخانه از assets/ خوانده و inline می‌شود — بدون وابستگی به CDN.
همه‌چیز stateless است؛ داده از پایتون به‌صورت JSON تزریق می‌شود.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_LIB_PATH = Path(__file__).resolve().parent.parent / "assets" / "lightweight-charts.standalone.production.js"
_LIB_CACHE: Optional[str] = None


def _lib() -> str:
    global _LIB_CACHE
    if _LIB_CACHE is None:
        _LIB_CACHE = _LIB_PATH.read_text(encoding="utf-8")
    return _LIB_CACHE


_ZONES_JS = """
function drawZones(){
  if(S.tf!==DATA.base_tf || !ZONES.length) return;
  const TIMES = CAND().map(a => a[0]);      // ثانیه — برای مکان‌یابی منطقی نواحی
  function logicalForTime(sec){
    let lo=0, hi=TIMES.length-1, best=null;
    while(lo<=hi){ const mid=(lo+hi)>>1;
      if(TIMES[mid]<=sec){ best=mid; lo=mid+1; } else hi=mid-1; }
    return best;
  }
  const ts = chartMain.timeScale();
  const w = ts.width();
  const range = ts.getVisibleLogicalRange();
  for(const z of ZONES){
    const yTop = mainSeries.priceToCoordinate(z.top);
    const yBot = mainSeries.priceToCoordinate(z.bottom);
    if(yTop==null || yBot==null) continue;
    let x0 = 0;
    if(range){
      const li = logicalForTime(z.t0);
      if(li!=null && li>range.from){
        const c0 = xOfLogical(Math.min(li, range.to));
        if(c0!=null) x0 = Math.max(0, Math.min(c0, w));
      }
    }
    const col = ZCOL[z.kind] || '148,163,184';
    const y0 = Math.min(yTop,yBot), h0 = Math.abs(yBot-yTop);
    octx.fillStyle = 'rgba('+col+',0.12)';
    octx.fillRect(x0, y0, w-x0, h0);
    octx.strokeStyle = 'rgba('+col+',0.55)';
    octx.lineWidth = 1;
    octx.strokeRect(x0+0.5, y0+0.5, w-x0-1, h0-1);
    octx.fillStyle = 'rgba('+col+',0.95)';
    octx.font = '600 10px ui-monospace, monospace';
    octx.fillText(z.tag, x0+5, y0+12);
  }
}
"""

_MAIN_JS = """
const DATA = __DATA__;
const ZONES = __ZONES__;
const TFS = DATA.tfs;                       // {tf: [[t,o,h,l,c,v],...]}
const TF_ORDER = ['15min','1hour','4hour','1day','1week'];
const TF_LBL = {'15min':'15m','1hour':'1H','4hour':'4H','1day':'1D','1week':'1W'};
const ZCOL = { bull:'38,166,154', bear:'239,83,80', bvg:'168,85,247' };
const DEC = DATA.dec;
function SK(k){ return 'nqtv:' + DATA.title + ':' + k; }
function safeParse(s){ try{ return JSON.parse(s); }catch(e){ return null; } }

let S = {
  tf:   localStorage.getItem(SK('tf'))  || DATA.base_tf,
  type: localStorage.getItem(SK('type'))|| 'candles',
  ind:  safeParse(localStorage.getItem(SK('ind'))) ||
        {ema20:true, ema50:true, ema200:false, bb:true, vwap:false, volma:false, rsi:false, macd:false},
  tool: 'cursor',
};
if(!TFS[S.tf]) S.tf = DATA.base_tf;
let DRAWINGS = [];

/* ---------- ریاضیات اندیکاتورها (سمت مرورگر) ------------------------- */
function emaArr(v, n){ const o=new Array(v.length).fill(null); if(v.length<n) return o;
  let s=0; for(let i=0;i<n;i++) s+=v[i]; let e=s/n; o[n-1]=e; const k=2/(n+1);
  for(let i=n;i<v.length;i++){ e=v[i]*k+e*(1-k); o[i]=e; } return o; }
function smaArr(v, n){ const o=new Array(v.length).fill(null); let s=0;
  for(let i=0;i<v.length;i++){ s+=v[i]; if(i>=n) s-=v[i-n]; if(i>=n-1) o[i]=s/n; } return o; }
function stdArr(v, n, mid){ const o=new Array(v.length).fill(null);
  for(let i=n-1;i<v.length;i++){ let s=0;
    for(let j=i-n+1;j<=i;j++){ const d=v[j]-mid[i]; s+=d*d; } o[i]=Math.sqrt(s/n); } return o; }
function rsiArr(c, n){ const o=new Array(c.length).fill(null); if(c.length<=n) return o;
  let g=0,l=0; for(let i=1;i<=n;i++){ const ch=c[i]-c[i-1]; if(ch>=0) g+=ch; else l-=ch; }
  let ag=g/n, al=l/n; o[n]= al===0?100:100-100/(1+ag/al);
  for(let i=n+1;i<c.length;i++){ const ch=c[i]-c[i-1];
    ag=(ag*(n-1)+Math.max(ch,0))/n; al=(al*(n-1)+Math.max(-ch,0))/n;
    o[i]= al===0?100:100-100/(1+ag/al); } return o; }
function macdCalc(c){ const e12=emaArr(c,12), e26=emaArr(c,26);
  const m=c.map((_,i)=> (e12[i]!=null&&e26[i]!=null)? e12[i]-e26[i] : null);
  const first=m.findIndex(v=>v!=null); const sig=new Array(c.length).fill(null);
  if(first>=0){ const seq=m.slice(first).map(v=>v==null?0:v); const e9=emaArr(seq,9);
    for(let i=0;i<e9.length;i++) if(e9[i]!=null) sig[first+i]=e9[i]; }
  const h=m.map((v,i)=> (v!=null&&sig[i]!=null)? v-sig[i] : null);
  return {m:m, sig:sig, h:h}; }
function vwapCalc(cd){ const o=new Array(cd.length).fill(null);
  let day=null, cpv=0, cv=0;
  for(let i=0;i<cd.length;i++){ const d=new Date(cd[i][0]*1000);
    const k=d.getUTCFullYear()+'-'+d.getUTCMonth()+'-'+d.getUTCDate();
    if(k!==day){ day=k; cpv=0; cv=0; }
    const tp=(cd[i][1]+cd[i][2]+cd[i][3]+cd[i][4])/4; const v=cd[i][5]||0;
    if(v>0){ cpv+=tp*v; cv+=v; o[i]=cpv/cv; } } return o; }
function haCalc(cd){ const o=[]; let po=null, pc=null;
  for(const a of cd){ const c=(a[1]+a[2]+a[3]+a[4])/4;
    const op= po==null? (a[1]+a[4])/2 : (po+pc)/2;
    o.push([a[0], op, Math.max(a[2],op,c), Math.min(a[3],op,c), c, a[5]]); po=op; pc=c; }
  return o; }

const CALC = {};
function calcFor(tf){
  if(CALC[tf]) return CALC[tf];
  const c = TFS[tf]; const t = c.map(a=>a[0]);
  const closes = c.map(a=>a[4]); const vols = c.map(a=>a[5]);
  const mid = smaArr(closes,20), sd = stdArr(closes,20,mid);
  const M = macdCalc(closes);
  CALC[tf] = { t:t,
    e20:emaArr(closes,20), e50:emaArr(closes,50), e200:emaArr(closes,200),
    bbU:mid.map((v,i)=> v==null||sd[i]==null? null : v+2*sd[i]),
    bbM:mid, bbL:mid.map((v,i)=> v==null||sd[i]==null? null : v-2*sd[i]),
    vw:vwapCalc(c), volma:smaArr(vols,20),
    rsi:rsiArr(closes,14), m:M.m, sig:M.sig, h:M.h };
  return CALC[tf];
}
function zip(t, arr){ const o=[]; for(let i=0;i<t.length;i++) if(arr[i]!=null) o.push({time:t[i], value:arr[i]}); return o; }
function CAND(){ return TFS[S.tf] || []; }
let IDX = new Map();
function buildIdx(){ IDX = new Map(CAND().map((a,i)=>[a[0], i])); }

/* ---------- ساخت چارت‌ها ---------------------------------------------- */
const MONO = 'ui-monospace, SFMono-Regular, Menlo, monospace';
function mkChart(el, opts){
  return LightweightCharts.createChart(el, Object.assign({
    autoSize: true,
    layout: { background:{type:'solid', color:'#0e1117'}, textColor:'#b2b5be', fontFamily:MONO, fontSize:11 },
    grid: { vertLines:{color:'rgba(148,163,184,0.07)'}, horzLines:{color:'rgba(148,163,184,0.07)'} },
    rightPriceScale: { borderColor:'rgba(148,163,184,0.18)', entireTextOnly:true },
    timeScale: { borderColor:'rgba(148,163,184,0.18)', timeVisible:true, secondsVisible:false, rightOffset:4 },
    crosshair: {
      mode: LightweightCharts.CrosshairMode.Normal,
      vertLine: { color:'rgba(148,163,184,0.45)', width:1, style:3, labelBackgroundColor:'#1f2a3d' },
      horzLine: { color:'rgba(148,163,184,0.45)', width:1, style:3, labelBackgroundColor:'#1f2a3d' },
    },
    localization: { priceFormatter: p => fmtP(p) },
  }, opts||{}));
}
const chartMain = mkChart(document.getElementById('chart'), {
  rightPriceScale: { borderColor:'rgba(148,163,184,0.18)', entireTextOnly:true, scaleMargins:{top:0.07,bottom:0.24} },
  watermark: { visible:true, text:DATA.symbol, fontSize:46, color:'rgba(148,163,184,0.05)',
               fontFamily:MONO, fontStyle:'' },
});
const chartRsi  = mkChart(document.getElementById('rsiChart'),  { timeScale:{visible:false}, rightPriceScale:{scaleMargins:{top:0.12,bottom:0.12}} });
const chartMacd = mkChart(document.getElementById('macdChart'), { timeScale:{visible:false}, rightPriceScale:{scaleMargins:{top:0.12,bottom:0.12}} });
chartMain._el = document.getElementById('chart');
chartRsi._el  = document.getElementById('rsiChart');
chartMacd._el = document.getElementById('macdChart');

const fmtP = v => v==null ? '—' : Number(v).toLocaleString('en-US',{minimumFractionDigits:DEC, maximumFractionDigits:DEC});
function fmtV(v){ if(v==null) return '—';
  if(v>=1e9) return (v/1e9).toFixed(2)+'B'; if(v>=1e6) return (v/1e6).toFixed(2)+'M';
  if(v>=1e3) return (v/1e3).toFixed(2)+'K'; return v.toFixed(2); }
function fmtDur(sec){ sec=Math.round(Math.abs(sec));
  const d=Math.floor(sec/86400), h=Math.floor(sec%86400/3600), m=Math.floor(sec%3600/60);
  if(d) return d+'d '+h+'h'; if(h) return h+'h '+m+'m'; return m+'m'; }

let mainSeries=null, volSeries=null; const IND={}; let priceLines=[];
function rm(s){ if(s){ try{ chartMain.removeSeries(s); }catch(e){} } }

const IND_META = [
  ['ema20','EMA 20','#2962ff'], ['ema50','EMA 50','#ff9800'], ['ema200','EMA 200','#e91e63'],
  ['bb','باندهای بولینگر (20,2)','#94a3b8'], ['vwap','VWAP (روزانه)','#f59e0b'],
  ['volma','میانگین حجم ۲۰','#8ea1c0'], ['rsi','RSI (14) — پنل جداگانه','#7e57c2'],
  ['macd','MACD (12,26,9) — پنل جداگانه','#26a69a'],
];

function rebuildMain(keepRange){
  const prev = keepRange ? chartMain.timeScale().getVisibleLogicalRange() : null;
  rm(mainSeries); rm(volSeries);
  for(const k in IND) rm(IND[k]);
  IND.e20=IND.e50=IND.e200=IND.bbU=IND.bbM=IND.bbL=IND.vwap=IND.volma=null;
  const c = CAND(); if(c.length<2) return;
  const up='#26a69a', dn='#ef5350';
  const pf = { type:'price', precision:DEC, minMove:Math.pow(10,-DEC) };
  volSeries = chartMain.addHistogramSeries({ priceScaleId:'vol', priceFormat:{type:'volume'},
    priceLineVisible:false, lastValueVisible:false });
  chartMain.priceScale('vol').applyOptions({ scaleMargins:{top:0.8, bottom:0} });
  volSeries.setData(c.filter(a=>a[5]!=null).map(a=>({time:a[0], value:a[5],
    color: a[4]>=a[1] ? 'rgba(38,166,154,0.5)' : 'rgba(239,83,80,0.5)'})));

  const isHA = S.type==='heikin';
  const src = isHA ? haCalc(c) : c;
  if(S.type==='candles' || isHA){
    mainSeries = chartMain.addCandlestickSeries({ upColor:up, downColor:dn,
      borderUpColor:up, borderDownColor:dn, wickUpColor:up, wickDownColor:dn,
      priceFormat:pf, priceLineColor:'rgba(148,163,184,0.6)', priceLineStyle:0 });
    mainSeries.setData(src.map(a=>({time:a[0], open:a[1], high:a[2], low:a[3], close:a[4]})));
  } else if(S.type==='bars'){
    mainSeries = chartMain.addBarSeries({ upColor:up, downColor:dn, priceFormat:pf,
      priceLineColor:'rgba(148,163,184,0.6)' });
    mainSeries.setData(src.map(a=>({time:a[0], open:a[1], high:a[2], low:a[3], close:a[4]})));
  } else if(S.type==='line'){
    mainSeries = chartMain.addLineSeries({ color:'#2962ff', lineWidth:2, priceFormat:pf });
    mainSeries.setData(src.map(a=>({time:a[0], value:a[4]})));
  } else {
    mainSeries = chartMain.addAreaSeries({ lineColor:'#2962ff', topColor:'rgba(41,98,255,0.25)',
      bottomColor:'rgba(41,98,255,0.02)', lineWidth:2, priceFormat:pf });
    mainSeries.setData(src.map(a=>({time:a[0], value:a[4]})));
  }

  const K = calcFor(S.tf);
  const mk=(key,opts)=>{ IND[key]=chartMain.addLineSeries(Object.assign(
    { priceLineVisible:false, lastValueVisible:false, crosshairMarkerVisible:false, visible:false }, opts));
    return IND[key]; };
  mk('ema20',{color:'#2962ff', lineWidth:1.6}).setData(zip(K.t, K.e20));
  mk('ema50',{color:'#ff9800', lineWidth:1.6}).setData(zip(K.t, K.e50));
  mk('ema200',{color:'#e91e63', lineWidth:1.6}).setData(zip(K.t, K.e200));
  mk('bbU',{color:'rgba(148,163,184,0.45)', lineWidth:1}).setData(zip(K.t, K.bbU));
  mk('bbM',{color:'rgba(148,163,184,0.28)', lineWidth:1, lineStyle:2}).setData(zip(K.t, K.bbM));
  mk('bbL',{color:'rgba(148,163,184,0.45)', lineWidth:1}).setData(zip(K.t, K.bbL));
  mk('vwap',{color:'#f59e0b', lineWidth:1.6}).setData(zip(K.t, K.vw));
  mk('volma',{color:'#8ea1c0', lineWidth:1, priceScaleId:'vol', priceLineVisible:false,
    lastValueVisible:false, crosshairMarkerVisible:false}).setData(zip(K.t, K.volma));
  chartMain.priceScale('vol').applyOptions({ scaleMargins:{top:0.8, bottom:0} });
  const visMap = { ema20:'ema20', ema50:'ema50', ema200:'ema200', vwap:'vwap', volma:'volma',
                   bbU:'bb', bbL:'bb', bbM:'bb' };
  for(const k of ['ema20','ema50','ema200','bbU','bbM','bbL','vwap','volma'])
    IND[k].applyOptions({ visible: !!S.ind[visMap[k]] });

  priceLines = [];
  if(S.tf===DATA.base_tf){
    for(const lv of DATA.levels){
      priceLines.push(mainSeries.createPriceLine({ price:lv.price, color:lv.color, lineWidth:1,
        lineStyle: lv.dash ? LightweightCharts.LineStyle.Dashed : LightweightCharts.LineStyle.Solid,
        axisLabelVisible:true, title:lv.name }));
    }
  }
  if(prev) chartMain.timeScale().setVisibleLogicalRange(prev);
}

const rsiSeries = chartRsi.addLineSeries({ color:'#7e57c2', lineWidth:1.5, priceLineVisible:false,
  autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }) });
rsiSeries.createPriceLine({ price:70, color:'rgba(148,163,184,0.35)', lineWidth:1,
  lineStyle:LightweightCharts.LineStyle.Dashed, axisLabelVisible:true, title:'' });
rsiSeries.createPriceLine({ price:30, color:'rgba(148,163,184,0.35)', lineWidth:1,
  lineStyle:LightweightCharts.LineStyle.Dashed, axisLabelVisible:true, title:'' });
const macdLine = chartMacd.addLineSeries({ color:'#2962ff', lineWidth:1.5, priceLineVisible:false, lastValueVisible:false, crosshairMarkerVisible:false });
const sigLine  = chartMacd.addLineSeries({ color:'#ff9800', lineWidth:1.5, priceLineVisible:false, lastValueVisible:false, crosshairMarkerVisible:false });
const macdHist = chartMacd.addHistogramSeries({ priceLineVisible:false, lastValueVisible:false });
macdLine.createPriceLine({ price:0, color:'rgba(148,163,184,0.3)', lineWidth:1,
  lineStyle:LightweightCharts.LineStyle.Dashed, axisLabelVisible:false, title:'' });

function rebuildSubs(){
  const K = calcFor(S.tf);
  rsiSeries.setData(zip(K.t, K.rsi));
  macdLine.setData(zip(K.t, K.m));
  sigLine.setData(zip(K.t, K.sig));
  macdHist.setData(K.t.map((t,i)=>{
    const v=K.h[i]; if(v==null) return null;
    const pv=K.h[i-1];
    const col = v>=0 ? (pv!=null && v>=pv ? 'rgba(38,166,154,0.65)' : 'rgba(38,166,154,0.28)')
                     : (pv!=null && v<=pv ? 'rgba(239,83,80,0.65)'  : 'rgba(239,83,80,0.28)');
    return {time:t, value:v, color:col};
  }).filter(Boolean));
}

/* ---------- لجند ------------------------------------------------------ */
const legend = document.getElementById('legend');
const lind = document.getElementById('lind');
const ltitle = document.getElementById('ltitle');
function setLegend(bar){
  const d = new Date(bar.t*1000);
  const ts = d.toLocaleString('en-GB',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
  const up = bar.c>=bar.o, cls = up?'up':'dn';
  const chg = bar.o? ((bar.c-bar.o)/bar.o*100) : 0;
  legend.querySelector('#lbar').innerHTML =
    '<span class="k">O</span><b class="'+cls+'">'+fmtP(bar.o)+'</b>'
    + '<span class="k">H</span><b class="'+cls+'">'+fmtP(bar.h)+'</b>'
    + '<span class="k">L</span><b class="'+cls+'">'+fmtP(bar.l)+'</b>'
    + '<span class="k">C</span><b class="'+cls+'">'+fmtP(bar.c)+'</b>'
    + '<b class="'+cls+'"> '+(chg>=0?'+':'')+chg.toFixed(2)+'%</b>'
    + '<span class="k">V</span><b>'+fmtV(bar.v)+'</b>'
    + '<span class="kt">'+ts+'</span>';
}
function setIndLegend(time){
  const K = CALC[S.tf]; const i = IDX.get(time);
  if(!K || i==null){ lind.innerHTML=''; return; }
  const rows=[];
  const add=(col,lbl,val)=>{ if(val!=null) rows.push('<span class="ik" style="color:'+col+'">'+lbl+' '+fmtP(val)+'</span>'); };
  if(S.ind.ema20) add('#2962ff','EMA20',K.e20[i]);
  if(S.ind.ema50) add('#ff9800','EMA50',K.e50[i]);
  if(S.ind.ema200) add('#e91e63','EMA200',K.e200[i]);
  if(S.ind.bb && K.bbU[i]!=null) rows.push('<span class="ik" style="color:#94a3b8">BB '+fmtP(K.bbU[i])+' / '+fmtP(K.bbL[i])+'</span>');
  if(S.ind.vwap) add('#f59e0b','VWAP',K.vw[i]);
  lind.innerHTML = rows.join('');
}
function setSubLegends(time){
  const K = CALC[S.tf]; const i = IDX.get(time);
  document.getElementById('rsiVal').textContent = (K && i!=null && K.rsi[i]!=null)? K.rsi[i].toFixed(1) : '—';
  if(K && i!=null){
    document.getElementById('macdVal').textContent =
      (K.m[i]!=null?K.m[i].toFixed(4):'—') + ' · ' + (K.sig[i]!=null?K.sig[i].toFixed(4):'—') + ' · ' + (K.h[i]!=null?K.h[i].toFixed(4):'—');
  } else document.getElementById('macdVal').textContent = '—';
}
function updateTitle(){ ltitle.textContent = DATA.symbol + ' · ' + (TF_LBL[S.tf]||S.tf); }

chartMain.subscribeCrosshairMove(param => {
  if(param && param.time && param.seriesData){
    const c = param.seriesData.get(mainSeries);
    if(c){
      const isOHLC = c.high!=null;
      const cv = isOHLC ? c.close : c.value;
      const a = CAND()[IDX.get(c.time)];
      setLegend({t:c.time, o:isOHLC?c.open:cv, h:isOHLC?c.high:cv, l:isOHLC?c.low:cv, c:cv,
                 v:a?a[5]:null});
      setIndLegend(c.time); setSubLegends(c.time);
      const K=CALC[S.tf]; const i=IDX.get(c.time);
      if(K && i!=null){
        if(K.rsi[i]!=null) chartRsi.setCrosshairPosition(K.rsi[i], c.time, rsiSeries); else chartRsi.clearCrosshairPosition();
        if(K.m[i]!=null) chartMacd.setCrosshairPosition(K.m[i], c.time, macdLine); else chartMacd.clearCrosshairPosition();
      }
    }
  } else {
    const c=CAND(); const l=c.length-1; const a=c[l];
    if(a){ setLegend({t:a[0],o:a[1],h:a[2],l:a[3],c:a[4],v:a[5]}); setIndLegend(a[0]); setSubLegends(a[0]); }
    chartRsi.clearCrosshairPosition(); chartMacd.clearCrosshairPosition();
  }
});
chartRsi.subscribeCrosshairMove(param => {
  if(param && param.time && param.seriesData){
    const v = param.seriesData.get(rsiSeries);
    const c = CAND(); const i = IDX.get(param.time);
    if(v && i!=null && c[i]){ setSubLegends(param.time);
      chartMain.setCrosshairPosition(c[i][4], param.time, mainSeries); }
  } else { chartMain.clearCrosshairPosition(); }
});

/* ---------- همگام‌سازی محور زمان -------------------------------------- */
const ALLCH = [chartMain, chartRsi, chartMacd];
let syncing = false;
let suppressed = false;                     // هنگام نمایش/مخفی‌شدن پنل‌ها حلقه‌ی سینک خاموش می‌شود
function syncFrom(src){
  if(syncing || suppressed) return; syncing = true;
  const r = src.timeScale().getVisibleLogicalRange();
  if(r) for(const c of ALLCH){
    if(c!==src && c._el && c._el.clientWidth>0){ try{ c.timeScale().setVisibleLogicalRange(r); }catch(e){} }
  }
  syncing = false;
}
for(const c of ALLCH) c.timeScale().subscribeVisibleLogicalRangeChange(()=>syncFrom(c));

/* ---------- بوم پوشانو: نواحی + رسم‌ها + خط‌کش ------------------------ */
const mainPane = document.getElementById('mainPane');
const ovl = document.getElementById('ovl');
const octx = ovl.getContext('2d');
function sizeOvl(){
  const r = mainPane.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  ovl.width = Math.round(r.width*dpr); ovl.height = Math.round(r.height*dpr);
  ovl.style.width = r.width+'px'; ovl.style.height = r.height+'px';
  octx.setTransform(dpr,0,0,dpr,0,0);
}
function xOfLogical(li){
  const ts = chartMain.timeScale(); const n = CAND().length;
  const i0 = Math.floor(li);
  const a = ts.logicalToCoordinate(i0);
  if(a==null){
    const last = ts.logicalToCoordinate(n-1), prev = ts.logicalToCoordinate(Math.max(0,n-2));
    if(last==null||prev==null) return null;
    const sp = n>=2 ? (last-prev) : 0;
    return last + (li-(n-1))*sp;
  }
  const i1 = Math.min(i0+1, n-1);
  if(i1===i0) return a;
  const b = ts.logicalToCoordinate(i1);
  if(b==null) return a;
  return a + (b-a)*(li-i0);
}
function xOfT(t){
  const times = CALC[S.tf].t; const n = times.length;
  if(n<2) return null;
  let i=0, lo=0, hi=n-1;
  if(t<=times[0]) i=0;
  else if(t>=times[n-1]) i=n-1;
  else { while(lo<=hi){ const m=(lo+hi)>>1; if(times[m]<=t){ i=m; lo=m+1; } else hi=m-1; } }
  const t1 = times[Math.min(i+1,n-1)];
  const li = i + (t-times[i]) / ((t1-times[i])||1);
  return xOfLogical(li);
}
function yOf(p){ return mainSeries.priceToCoordinate(p); }
function snapTime(x){
  const ts = chartMain.timeScale(); let li = ts.coordinateToLogical(x);
  if(li==null) return null;
  li = Math.max(0, Math.min(CAND().length-1, Math.round(li)));
  return CALC[S.tf].t[li];
}
function loadDraw(){ const v = safeParse(localStorage.getItem(SK('draw:'+S.tf))); return Array.isArray(v)? v : []; }
function saveDraw(){ try{ localStorage.setItem(SK('draw:'+S.tf), JSON.stringify(DRAWINGS)); }catch(e){} }

const FIB_LV = [[0,'#f59e0b'],[0.236,'#ef5350'],[0.382,'#f59e0b'],[0.5,'#2962ff'],[0.618,'#26a69a'],[0.786,'#a855f7'],[1,'#f59e0b']];
function drawOne(d, dashed){
  const x1=d.t1!=null?xOfT(d.t1):null, x2=d.t2!=null?xOfT(d.t2):null;
  const y1=d.p1!=null?yOf(d.p1):null, y2=d.p2!=null?yOf(d.p2):null;
  octx.save();
  if(dashed) octx.setLineDash([4,4]);
  if(d.type==='hline'){
    if(y1==null){ octx.restore(); return; }
    const w = chartMain.timeScale().width();
    octx.strokeStyle='#f59e0b'; octx.lineWidth=1;
    octx.beginPath(); octx.moveTo(0,y1); octx.lineTo(w,y1); octx.stroke();
    octx.setLineDash([]);
    const txt = fmtP(d.p1);
    octx.font='600 10px '+MONO; const tw = octx.measureText(txt).width;
    octx.fillStyle='#f59e0b'; octx.fillRect(w-tw-10, y1-9, tw+8, 16);
    octx.fillStyle='#0e1117'; octx.fillText(txt, w-tw-6, y1+3);
  } else if(d.type==='trend'){
    if(x1==null||x2==null||y1==null||y2==null){ octx.restore(); return; }
    octx.strokeStyle='#2962ff'; octx.lineWidth=1.6;
    octx.beginPath(); octx.moveTo(x1,y1); octx.lineTo(x2,y2); octx.stroke();
    octx.setLineDash([]);
    octx.fillStyle='#2962ff';
    octx.beginPath(); octx.arc(x1,y1,3,0,7); octx.fill();
    octx.beginPath(); octx.arc(x2,y2,3,0,7); octx.fill();
  } else if(d.type==='rect'){
    if(x1==null||x2==null||y1==null||y2==null){ octx.restore(); return; }
    const x=Math.min(x1,x2), y=Math.min(y1,y2), w=Math.abs(x2-x1), h=Math.abs(y2-y1);
    octx.fillStyle='rgba(41,98,255,0.10)'; octx.fillRect(x,y,w,h);
    octx.strokeStyle='rgba(41,98,255,0.7)'; octx.lineWidth=1;
    octx.strokeRect(x+0.5,y+0.5,w-1,h-1);
  } else if(d.type==='fib'){
    if(x1==null||x2==null||y1==null||y2==null){ octx.restore(); return; }
    const xa=Math.min(x1,x2), xb=Math.max(x1,x2);
    octx.font='600 10px '+MONO;
    for(const lv of FIB_LV){
      const p = d.p2 + (d.p1-d.p2)*lv[0];
      const y = yOf(p); if(y==null) continue;
      octx.strokeStyle=lv[1]; octx.lineWidth=1;
      octx.beginPath(); octx.moveTo(xa,y); octx.lineTo(xb,y); octx.stroke();
      octx.fillStyle=lv[1];
      octx.fillText(lv[0].toFixed(3)+' · '+fmtP(p), xb+5, y-3);
    }
  }
  octx.restore();
}
function drawMeasure(m){
  const x1=xOfT(m.p1.t), x2=xOfT(m.p2.t), y1=yOf(m.p1.price), y2=yOf(m.p2.price);
  if(x1==null||x2==null||y1==null||y2==null) return;
  const up = m.p2.price>=m.p1.price;
  const col = up? '38,166,154':'239,83,80';
  octx.fillStyle='rgba('+col+',0.14)';
  octx.fillRect(Math.min(x1,x2), Math.min(y1,y2), Math.abs(x2-x1), Math.abs(y2-y1));
  octx.strokeStyle='rgba('+col+',0.8)'; octx.lineWidth=1;
  octx.strokeRect(Math.min(x1,x2)+0.5, Math.min(y1,y2)+0.5, Math.abs(x2-x1), Math.abs(y2-y1));
  const dp = m.p2.price-m.p1.price;
  const pc = m.p1.price? dp/m.p1.price*100 : 0;
  const i1=IDX.get(m.p1.t), i2=IDX.get(m.p2.t);
  const bars = (i1!=null&&i2!=null)? Math.abs(i2-i1) : '—';
  const dt = m.p2.t-m.p1.t;
  const txt = (up?'▲ +':'▼ ') + pc.toFixed(2)+'% ('+fmtP(Math.abs(dp)) + ') · ' + bars + ' bars · ' + fmtDur(dt);
  octx.font='600 11px '+MONO;
  const tw = octx.measureText(txt).width;
  let bx = Math.min(x1,x2) + Math.abs(x2-x1)/2 - tw/2 - 8;
  let by = Math.min(y1,y2) - 26;
  bx = Math.max(4, Math.min(bx, chartMain.timeScale().width()-tw-16));
  if(by<2) by = Math.min(y1,y2) + 6;
  octx.fillStyle='rgba('+col+',0.92)';
  octx.fillRect(bx, by, tw+16, 20);
  octx.fillStyle='#ffffff';
  octx.fillText(txt, bx+8, by+14);
}
let pend=null, measure=null, dragMoved=false;
__ZONES_JS__
function renderLoop(){
  const r = mainPane.getBoundingClientRect();
  octx.clearRect(0,0,r.width,r.height);
  drawZones();
  for(const d of DRAWINGS) drawOne(d,false);
  if(pend) drawOne(pend,true);
  if(measure) drawMeasure(measure);
  requestAnimationFrame(renderLoop);
}
if(window.ResizeObserver) new ResizeObserver(()=>sizeOvl()).observe(mainPane);

/* ---------- رویدادهای ماوس/لمس رسم ------------------------------------ */
function evPos(e){
  const r = ovl.getBoundingClientRect();
  const x = e.clientX-r.left, y = e.clientY-r.top;
  return { x:x, y:y, price: mainSeries.coordinateToPrice(y), t: snapTime(x) };
}
function dist(a,b){ return Math.sqrt(Math.pow(a.x-b.x,2)+Math.pow(a.y-b.y,2)); }
function commit(d){ DRAWINGS.push(d); saveDraw(); }
ovl.addEventListener('pointerdown', e=>{
  if(S.tool==='cursor') return;
  e.preventDefault();
  if(measure){ measure=null; }
  const p = evPos(e);
  if(S.tool==='hline'){ if(p.price!=null) commit({type:'hline', p1:p.price, t1:null, p2:null, t2:null}); return; }
  if(S.tool==='measure'){ measure={p1:p, p2:p}; return; }
  if(pend){
    if(p.t!=null && p.price!=null){ pend.p2={t:p.t, price:p.price}; commit({type:pend.type, p1:pend.p1.price, t1:pend.p1.t, p2:pend.p2.price, t2:pend.p2.t}); pend=null; }
    return;
  }
  if(p.t!=null && p.price!=null){ pend={type:S.tool, p1:{t:p.t, price:p.price}, p2:{t:p.t, price:p.price}}; dragMoved=false; }
});
ovl.addEventListener('pointermove', e=>{
  const p = evPos(e);
  if(measure){ if(p.t!=null && p.price!=null) measure.p2=p; return; }
  if(pend){ if(dist(pend.p1,p)>6) dragMoved=true;
    if(p.t!=null) pend.p2.t=p.t;
    if(p.price!=null) pend.p2.price=p.price; }
});
ovl.addEventListener('pointerup', e=>{
  if(S.tool==='measure' && measure) return;
  if(pend && dragMoved){
    const p = evPos(e);
    if(dist(pend.p1,p)>14){
      if(p.t!=null) pend.p2.t=p.t;
      if(p.price!=null) pend.p2.price=p.price;
      commit({type:pend.type, p1:pend.p1.price, t1:pend.p1.t, p2:pend.p2.price, t2:pend.p2.t});
      pend=null;
    }
  }
});
window.addEventListener('keydown', e=>{ if(e.key==='Escape'){ pend=null; measure=null; setTool('cursor'); } });

/* ---------- تولبار: تایم‌فریم · نوع چارت · منوها ---------------------- */
function toast(msg){
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('show');
  clearTimeout(t._h); t._h = setTimeout(()=>t.classList.remove('show'), 2600);
}
const tfBtns = document.getElementById('tfBtns');
function buildTfBtns(){
  let h='';
  for(const tf of TF_ORDER){
    if(!TFS[tf]) continue;
    h += '<button class="tb-btn tf'+(tf===S.tf?' active':'')+'" data-tf="'+tf+'">'+TF_LBL[tf]+'</button>';
  }
  tfBtns.innerHTML = h;
  for(const b of tfBtns.querySelectorAll('.tf'))
    b.onclick = ()=>{ if(b.dataset.tf!==S.tf) setTF(b.dataset.tf); };
}
function setTF(tf){
  if(!TFS[tf]){ toast('داده‌ی این تایم‌فریم در دسترس نیست'); return; }
  S.tf = tf; localStorage.setItem(SK('tf'), tf);
  DRAWINGS = loadDraw();
  buildIdx();
  rebuildMain(false);
  rebuildSubs();
  buildTfBtns();
  updateTitle();
  const c = CAND(); const n = c.length;
  const win = Math.min(DATA.initial_bars, n);
  chartMain.timeScale().setVisibleLogicalRange({ from: Math.max(0, n-win-2), to: n+4 });
  closeMenus();
}
const TYPE_LBL = {candles:'کندل', bars:'میله', line:'خط', area:'ناحیه', heikin:'هایکن‌آشی'};
function setType(t){
  S.type = t; localStorage.setItem(SK('type'), t);
  document.getElementById('typeLbl').textContent = TYPE_LBL[t]||t;
  rebuildMain(true);
  closeMenus();
}
function anySub(){ return !!(S.ind.rsi || S.ind.macd); }
function applyPanes(){
  document.getElementById('rsiPane').style.display  = S.ind.rsi ? 'block' : 'none';
  document.getElementById('macdPane').style.display = S.ind.macd ? 'block' : 'none';
  chartMain.applyOptions({ timeScale:{ visible: !anySub() } });
  /* محور زمان فقط روی پایین‌ترین پنلِ فعال */
  chartRsi.applyOptions({ timeScale:{ visible: !!(S.ind.rsi && !S.ind.macd) } });
  chartMacd.applyOptions({ timeScale:{ visible: !!S.ind.macd } });
  /* چارت تازه‌نمایش‌شده هنوز عرض نگرفته؛ چند فریم رنجِ اصلی را به‌زور اعمال می‌کنیم
     تا barSpacing خراب (حداقل 0.5px) از چارت‌های مخفی نشت نکند. */
  suppressed = true;
  let n = 0;
  const tick = () => {
    n++;
    const r = chartMain.timeScale().getVisibleLogicalRange();
    if(r) for(const c of ALLCH){
      if(c!==chartMain && c._el && c._el.clientWidth>0){ try{ c.timeScale().setVisibleLogicalRange(r); }catch(e){} }
    }
    sizeOvl();
    if(n < 10) requestAnimationFrame(tick); else suppressed = false;
  };
  requestAnimationFrame(tick);
}
function toggleInd(k){
  S.ind[k] = !S.ind[k];
  localStorage.setItem(SK('ind'), JSON.stringify(S.ind));
  if(k==='rsi' || k==='macd'){ applyPanes(); return; }
  if(k==='bb'){ if(IND.bbU) IND.bbU.applyOptions({visible:S.ind.bb});
    if(IND.bbL) IND.bbL.applyOptions({visible:S.ind.bb});
    if(IND.bbM) IND.bbM.applyOptions({visible:S.ind.bb}); return; }
  if(IND[k]) IND[k].applyOptions({visible:S.ind[k]});
}
function buildIndMenu(){
  const m = document.getElementById('menuInd');
  let h='';
  for(const it of IND_META){
    h += '<div class="mi" data-k="'+it[0]+'">'
       + '<span class="chk'+(S.ind[it[0]]?' on':'')+'"></span>'
       + '<span class="dot" style="background:'+it[2]+'"></span><span>'+it[1]+'</span></div>';
  }
  m.innerHTML = h;
  for(const el of m.querySelectorAll('.mi'))
    el.onclick = ()=>{ toggleInd(el.dataset.k); el.querySelector('.chk').classList.toggle('on', !!S.ind[el.dataset.k]); };
}
const TOOLS = [
  ['cursor','🖱','نشانگر (حالت عادی)'],
  ['trend','↗','خط روند'],
  ['hline','➖','خط افقی'],
  ['rect','▭','مستطیل'],
  ['fib','📐','فیبوناچی بازگشتی'],
  ['measure','📏','خط‌کش (اندازه‌گیری)'],
];
function buildToolsMenu(){
  const m = document.getElementById('menuTools');
  let h='';
  for(const t of TOOLS)
    h += '<div class="mi'+(S.tool===t[0]?' sel':'')+'" data-t="'+t[0]+'"><span class="ti">'+t[1]+'</span><span>'+t[2]+'</span></div>';
  h += '<div class="msep"></div>'
     + '<div class="mi" data-t="undo"><span class="ti">↩</span><span>واگرد آخرین</span></div>'
     + '<div class="mi" data-t="clear"><span class="ti">🗑</span><span>پاک‌کردن همه</span></div>';
  m.innerHTML = h;
  for(const el of m.querySelectorAll('.mi'))
    el.onclick = ()=>{
      const t = el.dataset.t;
      if(t==='undo'){ DRAWINGS.pop(); saveDraw(); }
      else if(t==='clear'){ DRAWINGS=[]; saveDraw(); toast('همه‌ی رسم‌ها پاک شد'); }
      else setTool(t);
      buildToolsMenu(); closeMenus();
    };
}
function setTool(t){
  S.tool = t; pend=null;
  ovl.classList.toggle('armed', t!=='cursor');
  const btn = document.getElementById('btnTools');
  btn.classList.toggle('active', t!=='cursor');
}
function closeMenus(){
  for(const id of ['menuInd','menuTools','menuType'])
    document.getElementById(id).classList.remove('open');
}
function openMenu(btnId, menuId){
  const wrap = document.getElementById('wrap');
  const btn = document.getElementById(btnId), m = document.getElementById(menuId);
  const wr = wrap.getBoundingClientRect(), br = btn.getBoundingClientRect();
  m.style.left = Math.max(6, Math.min(br.left - wr.left, wr.width - 232)) + 'px';
  m.classList.add('open');
}
function bindMenu(btnId, menuId){
  document.getElementById(btnId).addEventListener('click', e=>{
    e.stopPropagation();
    const m = document.getElementById(menuId);
    const was = m.classList.contains('open');
    closeMenus();
    if(!was) openMenu(btnId, menuId);
  });
}
bindMenu('btnInd','menuInd'); bindMenu('btnTools','menuTools'); bindMenu('btnType','menuType');
document.addEventListener('click', e=>{
  if(!e.target.closest('.menu') && !e.target.closest('#btnInd,#btnTools,#btnType')) closeMenus();
});

/* ---------- دکمه‌های کناری -------------------------------------------- */
document.getElementById('btnFit').onclick = ()=>{ const c=CAND(); const n=c.length;
  chartMain.timeScale().setVisibleLogicalRange({from:Math.max(0,n-DATA.initial_bars-2), to:n+4}); };
document.getElementById('btnNow').onclick = ()=> chartMain.timeScale().scrollToRealTime();
document.getElementById('btnShot').onclick = ()=>{
  const shot = chartMain.takeScreenshot();
  const off = document.createElement('canvas');
  off.width = shot.width; off.height = shot.height;
  const cx = off.getContext('2d');
  cx.drawImage(shot,0,0);
  cx.drawImage(ovl, 0,0, ovl.width, ovl.height, 0,0, off.width, off.height);
  const a = document.createElement('a');
  a.download = (DATA.symbol+'_'+(TF_LBL[S.tf]||S.tf)).replace(/\\s+/g,'_') + '.png';
  a.href = off.toDataURL('image/png');
  a.click();
};
const btnFull = document.getElementById('btnFull');
if(!document.fullscreenEnabled) btnFull.style.display='none';
btnFull.onclick = ()=>{
  if(document.fullscreenElement) document.exitFullscreen();
  else document.getElementById('wrap').requestFullscreen().catch(()=>toast('تمام‌صفحه در دسترس نیست'));
};

/* ---------- منوی نوع چارت -------------------------------------------- */
(function(){
  const m = document.getElementById('menuType');
  let h='';
  for(const k of ['candles','bars','line','area','heikin'])
    h += '<div class="mi'+(S.type===k?' sel':'')+'" data-y="'+k+'"><span>'+TYPE_LBL[k]+'</span></div>';
  m.innerHTML = h;
  for(const el of m.querySelectorAll('.mi')) el.onclick = ()=>setType(el.dataset.y);
})();

/* ---------- شروع ------------------------------------------------------ */
buildTfBtns();
buildIndMenu();
buildToolsMenu();
document.getElementById('typeLbl').textContent = TYPE_LBL[S.type]||S.type;
setTool('cursor');
DRAWINGS = loadDraw();
buildIdx();
rebuildMain(false);
rebuildSubs();
updateTitle();
(function initLegend(){ const c=CAND(); const a=c[c.length-1];
  if(a){ setLegend({t:a[0],o:a[1],h:a[2],l:a[3],c:a[4],v:a[5]}); setIndLegend(a[0]); setSubLegends(a[0]); } })();
applyPanes();
(function(){ const c=CAND(); const n=c.length;
  const win = Math.min(DATA.initial_bars, n);
  chartMain.timeScale().setVisibleLogicalRange({ from: Math.max(0, n-win-2), to: n+4 }); })();
sizeOvl();
requestAnimationFrame(renderLoop);
"""

_CSS = """
html,body{margin:0;padding:0;background:#0e1117;height:100%;overflow:hidden;}
#wrap{position:relative;width:100%;height:100%;direction:ltr;background:#0e1117;display:flex;flex-direction:column;}
#toolbar{height:38px;min-height:38px;display:flex;align-items:center;gap:5px;padding:0 8px;
  background:#131722;border-bottom:1px solid rgba(148,163,184,0.14);direction:rtl;
  overflow-x:auto;overflow-y:hidden;scrollbar-width:none;}
#toolbar::-webkit-scrollbar{display:none;}
.tb-btn{all:unset;cursor:pointer;font:600 11.5px/1 ui-monospace,monospace;color:#b2b5be;
  background:transparent;border-radius:6px;padding:6px 8px;white-space:nowrap;user-select:none;}
.tb-btn:hover{background:rgba(148,163,184,0.12);color:#e2e8f0;}
.tb-btn.active{color:#5b8def;background:rgba(41,98,255,0.16);}
.tf{min-width:30px;text-align:center;}
.tb-sep{width:1px;height:18px;background:rgba(148,163,184,0.22);flex:none;}
.tb-spacer{flex:1;}
#panes{flex:1;position:relative;display:flex;flex-direction:column;min-height:0;}
#mainPane{flex:1;position:relative;min-height:140px;}
#chart{position:absolute;inset:0;}
.subpane{position:relative;border-top:1px solid rgba(148,163,184,0.14);display:none;background:#0e1117;}
#rsiPane{height:112px;} #macdPane{height:128px;}
#rsiChart,#macdChart{position:absolute;inset:0;}
.sublegend{position:absolute;top:4px;right:10px;z-index:7;pointer-events:none;direction:rtl;
  font:600 10.5px/1.6 ui-monospace,monospace;color:#8ea1c0;}
.sublegend b{color:#cfd6e4;}
#ovl{position:absolute;inset:0;z-index:5;pointer-events:none;}
#ovl.armed{pointer-events:auto;cursor:crosshair;touch-action:none;}
#legend{position:absolute;top:6px;left:8px;z-index:6;pointer-events:none;direction:ltr;
  font:11px/1.7 ui-monospace,SFMono-Regular,Menlo,monospace;color:#b2b5be;
  background:rgba(14,17,23,0.82);padding:3px 8px;border-radius:6px;
  border:1px solid rgba(148,163,184,0.12);max-width:calc(100% - 130px);}
#ltitle{color:#e2e8f0;font-weight:700;margin-right:6px;}
#lbar .k{color:#78849e;margin:0 3px 0 8px;}
#lbar b{font-weight:600;color:#e2e8f0;}
#lbar b.up{color:#26a69a;} #lbar b.dn{color:#ef5350;}
#lbar .kt{color:#78849e;margin-left:10px;}
#lind{display:flex;gap:10px;flex-wrap:wrap;}
#lind .ik{font-weight:600;}
.menu{position:absolute;top:42px;left:8px;z-index:40;background:#1c2333;
  border:1px solid rgba(148,163,184,0.2);border-radius:10px;padding:6px;display:none;
  min-width:210px;box-shadow:0 10px 28px rgba(0,0,0,0.5);direction:rtl;max-height:70%;overflow-y:auto;}
.menu.open{display:block;}
.mi{display:flex;align-items:center;gap:8px;padding:7px 9px;border-radius:6px;cursor:pointer;
  color:#cfd6e4;font:12px/1.6 Tahoma,sans-serif;white-space:nowrap;}
.mi:hover{background:rgba(148,163,184,0.1);}
.mi.sel{color:#5b8def;background:rgba(41,98,255,0.12);}
.mi .dot{width:9px;height:9px;border-radius:2px;flex:none;}
.mi .chk{width:13px;height:13px;border:1.5px solid rgba(148,163,184,0.6);border-radius:3px;
  flex:none;position:relative;font-size:10px;line-height:12px;text-align:center;color:#5b8def;}
.mi .chk.on::after{content:'✓';}
.mi .ti{width:16px;text-align:center;flex:none;}
.msep{height:1px;background:rgba(148,163,184,0.16);margin:5px 4px;}
#toast{position:absolute;bottom:14px;left:50%;transform:translateX(-50%);z-index:60;
  background:rgba(31,42,61,0.95);color:#e2e8f0;font:12px/1.6 Tahoma,sans-serif;
  padding:8px 14px;border-radius:8px;border:1px solid rgba(148,163,184,0.25);
  opacity:0;transition:opacity .25s;pointer-events:none;}
#toast.show{opacity:1;}
a[href*="tradingview.com"]{opacity:0.28; filter:grayscale(1);}
a[href*="tradingview.com"]:hover{opacity:0.7;}
@media (max-width:700px){ .tb-label{display:none;} .menu{min-width:180px;} }
"""


def build_tv_chart_html(*, candles: List[List[Any]], tfs: Dict[str, List[List[Any]]],
                        base_tf: str, symbol: str, zones: List[Dict[str, Any]],
                        levels: List[Dict[str, Any]], title: str, dec: int,
                        initial_bars: int = 160) -> str:
    """HTML خودکفای چارت TV کامل.
    candles:  [t_s, o, h, l, c, v]  (t ثانیه · NaN قبلاً None شده)
    tfs:      {tf_key: candles} — تایم‌فریم‌های موجود برای سوئیچر
    zones:    {t0,top,bottom,kind,tag} — فقط برای تایم‌فریم پایه
    levels:   {price,name,color,dash} — فقط برای تایم‌فریم پایه
    """
    if base_tf not in tfs:
        tfs = {base_tf: candles}
    data = json.dumps({"candles": candles, "tfs": tfs, "base_tf": base_tf,
                       "symbol": symbol, "levels": levels, "dec": dec,
                       "title": title, "initial_bars": int(initial_bars)},
                      ensure_ascii=False, allow_nan=False)
    zones_js = json.dumps(zones, ensure_ascii=False, allow_nan=False)
    js = (_MAIN_JS
          .replace("__DATA__", data)
          .replace("__ZONES__", zones_js)
          .replace("__ZONES_JS__", _ZONES_JS))
    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<style>" + _CSS + "</style></head><body>"
        '<div id="wrap">'
        '<div id="toolbar">'
        '<div id="tfBtns" style="display:flex;gap:2px;"></div>'
        '<span class="tb-sep"></span>'
        '<button class="tb-btn" id="btnType">🕯 <span class="tb-label" id="typeLbl">کندل</span> ▾</button>'
        '<button class="tb-btn" id="btnInd">ƒ<span class="tb-label"> اندیکاتورها</span> ▾</button>'
        '<button class="tb-btn" id="btnTools">📐<span class="tb-label"> ابزارها</span> ▾</button>'
        '<div class="tb-spacer"></div>'
        '<button class="tb-btn" id="btnFit" title="بازنشانی نما">⤢</button>'
        '<button class="tb-btn" id="btnNow" title="پرش به کندل آخر">▶▏</button>'
        '<button class="tb-btn" id="btnFull" title="تمام‌صفحه">⛶</button>'
        '<button class="tb-btn" id="btnShot" title="دانلود اسکرین‌شات PNG">📷</button>'
        '</div>'
        '<div id="panes">'
        '<div id="mainPane">'
        '<div id="chart"></div>'
        '<canvas id="ovl"></canvas>'
        '<div id="legend"><span id="ltitle"></span><span id="lbar"></span><div id="lind"></div></div>'
        '</div>'
        '<div class="subpane" id="rsiPane">'
        '<div id="rsiChart"></div>'
        '<div class="sublegend">RSI 14 · <b id="rsiVal">—</b></div>'
        '</div>'
        '<div class="subpane" id="macdPane">'
        '<div id="macdChart"></div>'
        '<div class="sublegend">MACD 12·26·9 · <b id="macdVal">—</b></div>'
        '</div>'
        '</div>'
        '<div class="menu" id="menuInd"></div>'
        '<div class="menu" id="menuTools"></div>'
        '<div class="menu" id="menuType"></div>'
        '<div id="toast"></div>'
        '</div>'
        "<script>" + _lib() + "</script>"
        "<script>" + js + "</script></body></html>"
    )
    return html
