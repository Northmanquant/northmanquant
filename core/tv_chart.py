# -*- coding: utf-8 -*-
"""core/tv_chart.py — چارت موتور TradingView برای داشبورد (lightweight-charts v4.2)
=====================================================================================
نسخه‌ی ۳ — پکیج کامل ابزار و اندیکاتور:

  ▸ تایم‌فریم‌سوئیچر داخل چارت — ۱۳ تایم‌فریم (1m تا 1M) با داده‌ی همگام از پایتون
  ▸ انواع چارت: کندل · توخالی · میله · خط · خط+نشانگر · پله‌ای · ناحیه · بیس‌لاین · هایکن‌آشی
  ▸ اندیکاتورهای روکش: EMA 9/20/21/50/200 · SMA 20/50/100/200 · بولینگر(20,2) · VWAP روزانه
    · Parabolic SAR · SuperTrend(10,3) · ایچیموکو(9,26,52) · پیوت‌پوینت روزانه · میانگین حجم
  ▸ پنل‌های جداگانه: RSI(14) · MACD(12,26,9) · استوکاستیک(14,3,3) · استوک RSI(14,14,3,3)
    · CCI(20) · ویلیامز %R(14) · ADX/DMI(14) · ATR(14) · OBV · MFI(14)
  ▸ ابزارهای رسم یک‌بارمصرف — پس از هر رسم خودکار به نشانگر برمی‌گردند (فیبوناچی پشت‌سرهم نمی‌ماند)
  ▸ انتخاب و جابه‌جایی رسم‌ها با نشانگر، سبک تریدینگ‌ویو — کلیک روی رسم: انتخاب با دستگیره‌ها ·
    کشیدن بدنه: جابه‌جایی کل · کشیدن دستگیره‌ها: تغییر شکل (با واگرد) — کلیک روی فضای خالی: پن عادی چارت
  ▸ ابزارهای رسم: خط روند · خط افقی · پرتو افقی · خط عمودی · مستطیل · فیبوناچی (۷ سطح)
    · خط‌کش (٪/قیمت/کندل/مدت) · پوزیشن خرید/فروش (ورود/ضرر/هدف + RR) · فلش صعودی/نزولی
    · متن · قلم آزاد + پاک‌کن تک‌رسم (کلیک روی هر رسم = حذف) + واگرد/ازنوی کامل (حتی پاک‌کردن همه)
    + ذخیره‌ی خودکار localStorage (نماد+تایم‌فریم)
  ▸ روکش‌های خودکار قابل خاموش‌شدن از منوی اندیکاتورها: نواحی FVG/BVG · خطوط سیگنال (ورود/ضرر/هدف)
  ▸ لجند OHLCV + مقادیر زنده‌ی همه‌ی اندیکاتورها · مقیاس لگاریتمی · نواحی FVG/BVG
  ▸ چیپ قیمت لحظه‌ای + شمارش معکوس بسته‌شدن کندل (سبک تریدینگ‌ویو) · دکمه‌های بازه‌ی سریع
  ▸ رابط جمع‌وجور: تولبار باریک، محور زمان کم‌ارتفاع، پنل‌های فشرده — فضای بیشتری برای کندل‌ها
  ▸ بازنشانی نما · پرش به «الان» · تمام‌صفحه · اسکرین‌شات PNG (با رسم‌ها)

کتابخانه از assets/ خوانده و inline می‌شود — بدون وابستگی به CDN.
همه‌چیز stateless است؛ داده از پایتون به‌صورت JSON تزریق می‌شود.
"""
from __future__ import annotations

import json
import os
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
  if(S.tf!==DATA.base_tf || !ZONES.length || S.ind.zones===false) return;
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
const TF_ORDER = ['1s','5s','10s','15s','30s','45s','1min','2min','3min','5min','10min','15min','30min','45min','1hour','2hour','3hour','4hour','6hour','8hour','12hour','1day','2day','3day','1week','1month'];
const TF_LBL = {'1s':'1s','5s':'5s','10s':'10s','15s':'15s','30s':'30s','45s':'45s',
                '1min':'1m','2min':'2m','3min':'3m','5min':'5m','10min':'10m','15min':'15m','30min':'30m','45min':'45m',
                '1hour':'1H','2hour':'2H','3hour':'3h','4hour':'4H','6hour':'6H','8hour':'8H','12hour':'12H',
                '1day':'1D','2day':'2D','3day':'3D','1week':'1W','1month':'1M'};
const TF_QUICK = ['1min','5min','15min','1hour','4hour','1day','1week'];

/* ---- منوی بازه‌ی زمانی به سبک تریدینگ‌ویو (گروه‌ها: ثانیه/دقیقه/ساعت/روز/هفته/ماه) ---- */
const TF_GROUPS_SRC = [
  ['ثانیه‌ها · منبع Binance', ['1s','5s','10s','15s','30s','45s']],
  ['دقیقه‌ها', ['1min','2min','3min','5min','10min','15min','30min','45min']],
  ['ساعت‌ها', ['1hour','2hour','3hour','4hour','6hour','8hour','12hour']],
  ['روزها', ['1day','2day','3day']],
  ['هفته‌ها', ['1week']],
  ['ماه‌ها', ['1month']],
];
/* فارکس: کندل ثانیه‌ای از Binance بی‌معناست — گروه ثانیه‌ها از منو حذف می‌شود */
const TF_GROUPS = DATA.fx ? TF_GROUPS_SRC.filter(g => g[0].indexOf('Binance') < 0) : TF_GROUPS_SRC;
const SECS = {'1s':1,'5s':5,'10s':10,'15s':15,'30s':30,'45s':45};
const SECS_CACHE = {};
let SECS_BUSY = false;
/* کندل ثانیه‌ای از REST هیچ صرافی‌ای نمی‌آید؛ از کندل 1s بایننس (میرور عمومی بدون محدودیت جغرافیایی)
   سمت مرورگر می‌گیریم و به بازه‌ی خواسته‌شده تجمیع می‌کنیم — مثل «Add custom interval» تریدینگ‌ویو. */
async function loadSeconds(tf){
  if(TFS[tf]) return true;
  if(SECS_CACHE[tf]){ TFS[tf] = SECS_CACHE[tf]; return true; }
  if(SECS_BUSY){ toast('دریافت قبلی هنوز در جریان است…'); return false; }
  SECS_BUSY = true;
  const sym = (DATA.symbol||'').split('/')[0].split('-').join('').toUpperCase();
  const sec = SECS[tf];
  const pages = Math.min(6, Math.max(1, Math.ceil(240*sec/1000)));
  try{
    toast('⏳ دریافت کندل‌های ثانیه‌ای از Binance…');
    let rows = [], end = null, got = false;
    const hosts = ['https://data-api.binance.vision','https://api.binance.com'];
    for(let p=0; p<pages; p++){
      let part = null;
      for(const h of hosts){
        try{
          const u = h+'/api/v3/klines?symbol='+sym+'&interval=1s&limit=1000'+(end?('&endTime='+end):'');
          const r = await fetch(u);
          if(!r.ok) continue;
          const j = await r.json();
          if(!Array.isArray(j) || !j.length) continue;
          part = j.map(k=>[Math.floor(k[0]/1000), parseFloat(k[1]), parseFloat(k[2]), parseFloat(k[3]), parseFloat(k[4]), parseFloat(k[5])]);
          break;
        }catch(err){}
      }
      if(!part || !part.length) break;
      got = true;
      end = part[0][0]*1000 - 1;
      rows = part.concat(rows);
      if(part.length < 1000) break;
    }
    if(!got) throw new Error('nodata');
    const m = new Map();
    for(const r of rows){
      const t = Math.floor(r[0]/sec)*sec;
      const b = m.get(t);
      if(!b) m.set(t, [t, r[1], r[2], r[3], r[4], r[5]]);
      else { if(r[2]>b[2]) b[2]=r[2]; if(r[3]<b[3]) b[3]=r[3]; b[4]=r[4]; b[5]+=(r[5]||0); }
    }
    const agg = Array.from(m.values()).sort((a,b)=>a[0]-b[0]);
    SECS_CACHE[tf] = agg; TFS[tf] = agg;
    return true;
  }catch(err){
    toast('بازه‌ی ثانیه‌ای برای این نماد از Binance در دسترس نیست');
    return false;
  }finally{ SECS_BUSY = false; }
}
function buildTfMenu(){
  const m = document.getElementById('menuTf'); let h='';
  for(const g of TF_GROUPS){
    h += '<div class="mgroup">'+g[0]+'</div>';
    for(const tf of g[1]){
      const lazy = (SECS[tf] && !TFS[tf])? '<span class="lzi">⇣</span>' : '';
      h += '<div class="mi tfmi'+(tf===S.tf?' sel':'')+'" data-tf="'+tf+'">'
         + '<span class="chk'+(tf===S.tf?' on':'')+'"></span>'
         + '<span class="tfl">'+(TF_LBL[tf]||tf)+'</span>'+lazy+'</div>';
    }
  }
  m.innerHTML = h;
  for(const el of m.querySelectorAll('.tfmi')) el.onclick = ()=>pickTf(el);
}
async function pickTf(el){
  const tf = el.dataset.tf;
  if(TFS[tf]){ closeMenus(); if(tf!==S.tf) setTF(tf); return; }
  if(SECS[tf]){
    const lz = el.querySelector('.lzi'); if(lz) lz.textContent = '⏳';
    const ok = await loadSeconds(tf);
    if(ok && TFS[tf]){ closeMenus(); setTF(tf); }
    return;
  }
  toast('داده‌ی این تایم‌فریم در دسترس نیست');
}
function updTfBtn(){
  const b = document.getElementById('btnTfAll');
  if(b) b.innerHTML = (TF_LBL[S.tf]||S.tf) + ' ▾';
}
const ZCOL = { bull:'38,166,154', bear:'239,83,80', bvg:'168,85,247' };
const DEC = DATA.dec;
function SK(k){ return 'nqtv:' + DATA.title + ':' + k; }
function safeParse(s){ try{ return JSON.parse(s); }catch(e){ return null; } }

const IND_DEF = {
  vol:true, ema9:false, ema20:true, ema21:false, ema50:true, ema200:false,
  sma20:false, sma50:false, sma100:false, sma200:false,
  bb:true, vwap:false, volma:false, psar:false, st:false, ichi:false, piv:false,
  rsi:false, macd:false, stoch:false, srsi:false, cci:false, wr:false,
  adx:false, atr:false, obv:false, mfi:false, log:false, leg:true,
  zones:true, plines:true };
/* فارکس: ولوم یاهو همیشه صفر/تهی است — هیستوگرام حجم پیش‌فرض خاموش (کاربر می‌تواند روشن کند) */
if (DATA.fx) IND_DEF.vol = false;

let S = {
  tf:   localStorage.getItem(SK('tf'))  || DATA.base_tf,
  type: localStorage.getItem(SK('type'))|| 'candles',
  ind:  Object.assign({}, IND_DEF, safeParse(localStorage.getItem(SK('ind'))) || {}),
  tool: 'cursor',
};
if(!TFS[S.tf]) S.tf = DATA.base_tf;
/* اگر کاربر قبلاً بازه‌ی ثانیه‌ای انتخاب کرده بود، بعد از رندر اولیه همان را دوباره می‌گیریم */
const WANT_SECS = (S.tf !== (localStorage.getItem(SK('tf'))||'') && SECS[localStorage.getItem(SK('tf'))||''] && !TFS[localStorage.getItem(SK('tf'))||''])
  ? localStorage.getItem(SK('tf')) : null;
let DRAWINGS = [];
let UNDOS = [], REDOS = [];

/* ---------- ریاضیات اندیکاتورها (سمت مرورگر) ------------------------- */
function emaArr(v, n){ const o=new Array(v.length).fill(null); if(v.length<n) return o;
  let s=0; for(let i=0;i<n;i++) s+=v[i]; let e=s/n; o[n-1]=e; const k=2/(n+1);
  for(let i=n;i<v.length;i++){ e=v[i]*k+e*(1-k); o[i]=e; } return o; }
function smaArr(v, n){ const o=new Array(v.length).fill(null); let s=0;
  for(let i=0;i<v.length;i++){ s+=v[i]; if(i>=n) s-=v[i-n]; if(i>=n-1) o[i]=s/n; } return o; }
function smaN(a, n){ const o=new Array(a.length).fill(null);
  for(let i=n-1;i<a.length;i++){ let s=0, ok=true;
    for(let j=i-n+1;j<=i;j++){ if(a[j]==null){ ok=false; break; } s+=a[j]; }
    if(ok) o[i]=s/n; } return o; }
function rmaN(a, n){ const o=new Array(a.length).fill(null);
  let st=-1; for(let i=0;i<a.length;i++){ if(a[i]!=null){ st=i; break; } }
  if(st<0 || st+n>a.length) return o;
  let s=0; for(let i=st;i<st+n;i++) s+=a[i]; let v=s/n; o[st+n-1]=v;
  for(let i=st+n;i<a.length;i++){ v=(v*(n-1)+a[i])/n; o[i]=v; } return o; }
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
function trArr(cd){ const o=new Array(cd.length).fill(null);
  if(cd.length<1) return o;
  o[0]=cd[0][2]-cd[0][3];
  for(let i=1;i<cd.length;i++){ const h=cd[i][2], l=cd[i][3], pc=cd[i-1][4];
    o[i]=Math.max(h-l, Math.abs(h-pc), Math.abs(l-pc)); } return o; }
function hh(cd,i,n,f){ let m=-Infinity;
  for(let j=Math.max(0,i-n+1);j<=i;j++) m=Math.max(m,cd[j][f]); return m; }
function ll(cd,i,n,f){ let m=Infinity;
  for(let j=Math.max(0,i-n+1);j<=i;j++) m=Math.min(m,cd[j][f]); return m; }
function psarCalc(cd, step, max){
  const n=cd.length; const out=new Array(n).fill(null); const side=new Array(n).fill(0);
  if(n<3) return {v:out, s:side};
  let up=cd[1][4]>=cd[0][4];
  let ep= up? cd[0][2]:cd[0][3];
  let sar= up? cd[0][3]:cd[0][2];
  let af=step;
  for(let i=1;i<n;i++){
    sar = sar + af*(ep-sar);
    const l1=cd[i-1][3], h1=cd[i-1][2];
    const l2= i>=2? cd[i-2][3]:l1, h2= i>=2? cd[i-2][2]:h1;
    if(up) sar=Math.min(sar,l1,l2); else sar=Math.max(sar,h1,h2);
    const hit = up? cd[i][3]<sar : cd[i][2]>sar;
    if(hit){ up=!up; sar=ep; ep= up? cd[i][2]:cd[i][3]; af=step; }
    else { if(up && cd[i][2]>ep){ ep=cd[i][2]; af=Math.min(max,af+step); }
           else if(!up && cd[i][3]<ep){ ep=cd[i][3]; af=Math.min(max,af+step); } }
    out[i]=sar; side[i]= up?1:-1;
  }
  return {v:out, s:side}; }
function stCalc(cd, n, mult){
  const len=cd.length; const u=new Array(len).fill(null), d=new Array(len).fill(null);
  const tr=trArr(cd); const atr=rmaN(tr,n);
  let trend=1, fub=null, fbl=null;
  for(let i=n-1;i<len;i++){ if(atr[i]==null) continue;
    const mid=(cd[i][2]+cd[i][3])/2;
    const bu=mid+mult*atr[i], bl=mid-mult*atr[i];
    if(fub==null){ fub=bu; fbl=bl; }
    else{ fub = (bu<fub || cd[i-1][4]>fub)? bu : fub;
          fbl = (bl>fbl || cd[i-1][4]<fbl)? bl : fbl; }
    if(trend===1 && cd[i][4]<fbl) trend=-1;
    else if(trend===-1 && cd[i][4]>fub) trend=1;
    if(trend===1) u[i]=fbl; else d[i]=fub; }
  return {u:u, d:d}; }
function stochCalc(cd, n, k, d){
  const raw=new Array(cd.length).fill(null);
  for(let i=n-1;i<cd.length;i++){ const hv=hh(cd,i,n,2), lv=ll(cd,i,n,3);
    raw[i]= hv===lv? 50 : (cd[i][4]-lv)/(hv-lv)*100; }
  const K=smaN(raw,k), D=smaN(K,d);
  return {k:K, d:D}; }
function srsiCalc(cd, nS, nSt, k, d){
  const r=rsiArr(cd.map(a=>a[4]), nS);
  const raw=new Array(cd.length).fill(null);
  for(let i=0;i<cd.length;i++){ if(r[i]==null) continue;
    let mn=Infinity, mx=-Infinity, ok=true;
    for(let j=i-nSt+1;j<=i;j++){ if(j<0||r[j]==null){ ok=false; break; }
      mn=Math.min(mn,r[j]); mx=Math.max(mx,r[j]); }
    if(ok) raw[i]= mx===mn? 50 : (r[i]-mn)/(mx-mn)*100; }
  const K=smaN(raw,k), D=smaN(K,d);
  return {k:K, d:D}; }
function cciCalc(cd, n){
  const tp=cd.map(a=>(a[1]+a[2]+a[3]+a[4])/4);
  const m=smaArr(tp,n); const o=new Array(cd.length).fill(null);
  for(let i=n-1;i<cd.length;i++){ if(m[i]==null) continue;
    let md=0; for(let j=i-n+1;j<=i;j++) md+=Math.abs(tp[j]-m[i]);
    md/=n; o[i]= md===0? 0 : (tp[i]-m[i])/(0.015*md); }
  return o; }
function wrCalc(cd, n){ const o=new Array(cd.length).fill(null);
  for(let i=n-1;i<cd.length;i++){ const hv=hh(cd,i,n,2), lv=ll(cd,i,n,3);
    o[i]= hv===lv? -50 : -100*(hv-cd[i][4])/(hv-lv); } return o; }
function atrCalc(cd, n){ return rmaN(trArr(cd), n); }
function adxCalc(cd, n){
  const len=cd.length;
  const pdm=new Array(len).fill(0), mdm=new Array(len).fill(0);
  for(let i=1;i<len;i++){ const up=cd[i][2]-cd[i-1][2], dn=cd[i-1][3]-cd[i][3];
    pdm[i]= (up>dn && up>0)? up:0; mdm[i]= (dn>up && dn>0)? dn:0; }
  const tr=rmaN(trArr(cd),n);
  const p=rmaN(pdm,n), m=rmaN(mdm,n);
  const pdi=new Array(len).fill(null), mdi=new Array(len).fill(null), dx=new Array(len).fill(null);
  for(let i=n;i<len;i++){ if(tr[i]==null||p[i]==null||m[i]==null) continue;
    if(tr[i]===0) continue;
    pdi[i]=100*p[i]/tr[i]; mdi[i]=100*m[i]/tr[i];
    const s=pdi[i]+mdi[i]; dx[i]= s===0? 0 : 100*Math.abs(pdi[i]-mdi[i])/s; }
  return {adx:rmaN(dx,n), pdi:pdi, mdi:mdi}; }
function obvCalc(cd){ const o=new Array(cd.length).fill(0);
  for(let i=1;i<cd.length;i++){ const v=cd[i][5]||0;
    const dvi= cd[i][4]>cd[i-1][4]? v : (cd[i][4]<cd[i-1][4]? -v : 0);
    o[i]=o[i-1]+dvi; } return o; }
function mfiCalc(cd, n){
  const o=new Array(cd.length).fill(null); const qp=[], qn=[];
  for(let i=1;i<cd.length;i++){
    const tp=(cd[i][1]+cd[i][2]+cd[i][3]+cd[i][4])/4;
    const pp=(cd[i-1][1]+cd[i-1][2]+cd[i-1][3]+cd[i-1][4])/4;
    const v=cd[i][5]||0;
    const fl= tp>pp? v*tp : (tp<pp? -v*tp : 0);
    qp.push(fl>0?fl:0); qn.push(fl<0?-fl:0);
    if(qp.length>n){ qp.shift(); qn.shift(); }
    if(qp.length===n){ let s=0,t=0; for(const x of qp) s+=x; for(const x of qn) t+=x;
      o[i]= t===0? 100 : 100-100/(1+s/t); } }
  return o; }
function pivCalc(cd){
  const days={};
  for(const a of cd){ const d=new Date(a[0]*1000);
    const k=d.getUTCFullYear()+'-'+d.getUTCMonth()+'-'+d.getUTCDate();
    if(!days[k]) days[k]={h:-Infinity, l:Infinity, c:a[4]};
    days[k].h=Math.max(days[k].h,a[2]); days[k].l=Math.min(days[k].l,a[3]); days[k].c=a[4]; }
  const keys=Object.keys(days); if(keys.length<2) return null;
  const p=days[keys[keys.length-2]];
  const P=(p.h+p.l+p.c)/3;
  return { P:P, R1:2*P-p.l, S1:2*P-p.h, R2:P+(p.h-p.l), S2:P-(p.h-p.l),
           R3:p.h+2*(P-p.l), S3:p.l-2*(p.h-P) }; }
function ichiCalc(cd, sec){
  const n=cd.length; const closes=cd.map(a=>a[4]);
  const tenkan=new Array(n).fill(null), kijun=new Array(n).fill(null), spanB=new Array(n).fill(null);
  for(let i=8;i<n;i++) tenkan[i]=(hh(cd,i,9,2)+ll(cd,i,9,3))/2;
  for(let i=25;i<n;i++) kijun[i]=(hh(cd,i,26,2)+ll(cd,i,26,3))/2;
  for(let i=51;i<n;i++) spanB[i]=(hh(cd,i,52,2)+ll(cd,i,52,3))/2;
  const spanA=new Array(n).fill(null);
  for(let i=0;i<n;i++) if(tenkan[i]!=null && kijun[i]!=null) spanA[i]=(tenkan[i]+kijun[i])/2;
  const chik=new Array(n).fill(null);
  for(let i=26;i<n;i++) chik[i-26]=closes[i];
  const lastT=cd[n-1][0];
  function futT(idx){ return idx<n? cd[idx][0] : lastT+(idx-(n-1))*sec; }
  const A=[], B=[];
  for(let i=0;i<n;i++){
    if(spanA[i]!=null) A.push({time:futT(i+26), value:spanA[i]});
    if(spanB[i]!=null) B.push({time:futT(i+26), value:spanB[i]}); }
  const C=[]; for(let i=0;i<n;i++) if(chik[i]!=null) C.push({time:cd[i][0], value:chik[i]});
  return {tenkan:tenkan, kijun:kijun, A:A, B:B, C:C}; }

const CALC = {};
function calcFor(tf){
  if(CALC[tf]) return CALC[tf];
  const c = TFS[tf]; const t = c.map(a=>a[0]);
  const closes = c.map(a=>a[4]); const vols = c.map(a=>a[5]||0);
  const mid = smaArr(closes,20), sd = stdArr(closes,20,mid);
  const M = macdCalc(closes);
  const sec = c.length>1? (c[1][0]-c[0][0]) : 900;
  const ps = psarCalc(c, 0.02, 0.2);
  const stx = stCalc(c, 10, 3);
  const ad = adxCalc(c, 14);
  const sc = stochCalc(c, 14, 3, 3);
  const sr = srsiCalc(c, 14, 14, 3, 3);
  CALC[tf] = { t:t, sec:sec,
    e9:emaArr(closes,9), e20:emaArr(closes,20), e21:emaArr(closes,21),
    e50:emaArr(closes,50), e200:emaArr(closes,200),
    s20:mid, s50:smaArr(closes,50), s100:smaArr(closes,100), s200:smaArr(closes,200),
    bbU:mid.map((v,i)=> v==null||sd[i]==null? null : v+2*sd[i]),
    bbM:mid, bbL:mid.map((v,i)=> v==null||sd[i]==null? null : v-2*sd[i]),
    vw:vwapCalc(c), volma:smaArr(vols,20),
    psar:ps.v, psarS:ps.s, stU:stx.u, stD:stx.d,
    rsi:rsiArr(closes,14), m:M.m, sig:M.sig, h:M.h,
    stoK:sc.k, stoD:sc.d, srK:sr.k, srD:sr.d,
    cci:cciCalc(c,20), wr:wrCalc(c,14),
    adx:ad.adx, pdi:ad.pdi, mdi:ad.mdi,
    atr:atrCalc(c,14), obv:obvCalc(c), mfi:mfiCalc(c,14),
    piv:pivCalc(c), ichi:ichiCalc(c, sec) };
  return CALC[tf];
}
function zip(t, arr){ const o=[]; for(let i=0;i<t.length;i++) if(arr[i]!=null) o.push({time:t[i], value:arr[i]}); return o; }
function CAND(){ return TFS[S.tf] || []; }
function SEC(){ const c=CAND(); return c.length>1? (c[1][0]-c[0][0]) : 900; }
let IDX = new Map();
function buildIdx(){ IDX = new Map(CAND().map((a,i)=>[a[0], i])); }

/* ---------- ساخت چارت‌ها ---------------------------------------------- */
const MONO = 'ui-monospace, SFMono-Regular, Menlo, monospace';
function mkChart(el, opts){
  return LightweightCharts.createChart(el, Object.assign({
    autoSize: true,
    layout: { background:{type:'solid', color:'#0e1117'}, textColor:'#b2b5be', fontFamily:MONO, fontSize:10 },
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
  rightPriceScale: { borderColor:'rgba(148,163,184,0.18)', entireTextOnly:true, scaleMargins:{top:0.05,bottom:0.20} },
  watermark: { visible:true, text:DATA.symbol, fontSize:40, color:'rgba(148,163,184,0.05)',
               fontFamily:MONO, fontStyle:'' },
});
chartMain._el = document.getElementById('chart');

const fmtP = v => v==null ? '—' : Number(v).toLocaleString('en-US',{minimumFractionDigits:DEC, maximumFractionDigits:DEC});
function fmtV(v){ if(v==null) return '—';
  if(v>=1e9) return (v/1e9).toFixed(2)+'B'; if(v>=1e6) return (v/1e6).toFixed(2)+'M';
  if(v>=1e3) return (v/1e3).toFixed(2)+'K'; return v.toFixed(2); }
function F1(v){ return v==null? '—' : v.toFixed(1); }
function F4(v){ if(v==null) return '—'; const a=Math.abs(v);
  return a<0.01? v.toFixed(6) : a<1000? v.toFixed(4) : v.toFixed(1); }
function fmtDur(sec){ sec=Math.round(Math.abs(sec));
  const d=Math.floor(sec/86400), h=Math.floor(sec%86400/3600), m=Math.floor(sec%3600/60);
  if(d) return d+'d '+h+'h'; if(h) return h+'h '+m+'m'; return m+'m'; }

/* ---------- پنل‌های اندیکاتور (ساخت پویا) ------------------------------ */
const PANE_DEFS = [
  {k:'rsi',  h:82, t:'RSI 14'},
  {k:'macd', h:98, t:'MACD 12·26·9'},
  {k:'stoch',h:82, t:'استوکاستیک 14·3·3'},
  {k:'srsi', h:82, t:'استوک RSI 14·14·3·3'},
  {k:'cci',  h:82, t:'CCI 20'},
  {k:'wr',   h:82, t:'Williams %R 14'},
  {k:'adx',  h:98, t:'ADX / DMI 14'},
  {k:'atr',  h:72, t:'ATR 14'},
  {k:'obv',  h:82, t:'OBV'},
  {k:'mfi',  h:82, t:'MFI 14'},
];
const PANE = {};
(function buildPanes(){
  const host = document.getElementById('panes');
  for(const d of PANE_DEFS){
    const el = document.createElement('div');
    el.className='subpane'; el.id='pane-'+d.k; el.style.height=d.h+'px';
    el.innerHTML = '<div class="pch" id="pch-'+d.k+'"></div>'
                 + '<div class="sublegend" id="leg-'+d.k+'">'+d.t+' · <b>—</b></div>';
    host.appendChild(el);
    const ch = mkChart(document.getElementById('pch-'+d.k),
      { timeScale:{visible:false}, rightPriceScale:{scaleMargins:{top:0.13,bottom:0.13}} });
    ch._el = document.getElementById('pch-'+d.k);
    PANE[d.k] = { el:el, chart:ch, def:d, s:{} };
  }
})();
function pline(ch, opts){ return ch.addLineSeries(Object.assign(
  { lineWidth:1.4, priceLineVisible:false, lastValueVisible:false, crosshairMarkerVisible:false }, opts)); }
function guide(series, price, col){ series.createPriceLine({ price:price, color:col, lineWidth:1,
  lineStyle:LightweightCharts.LineStyle.Dashed, axisLabelVisible:true, title:'' }); }
function fixScale(lo, hi){ return { autoscaleInfoProvider: () => ({ priceRange:{ minValue:lo, maxValue:hi } }) }; }

(function buildPaneSeries(){
  const P = PANE;
  P.rsi.s.main = pline(P.rsi.chart,  Object.assign({color:'#7e57c2', lineWidth:1.5}, fixScale(0,100)));
  guide(P.rsi.s.main, 70, 'rgba(148,163,184,0.35)'); guide(P.rsi.s.main, 30, 'rgba(148,163,184,0.35)');

  P.macd.s.m    = pline(P.macd.chart, {color:'#2962ff', lineWidth:1.5});
  P.macd.s.sig  = pline(P.macd.chart, {color:'#ff9800', lineWidth:1.5});
  P.macd.s.hist = P.macd.chart.addHistogramSeries({ priceLineVisible:false, lastValueVisible:false });
  guide(P.macd.s.m, 0, 'rgba(148,163,184,0.3)');

  P.stoch.s.k = pline(P.stoch.chart, Object.assign({color:'#2962ff', lineWidth:1.6}, fixScale(0,100)));
  P.stoch.s.d = pline(P.stoch.chart, {color:'#ff9800', lineWidth:1.3});
  guide(P.stoch.s.k, 80, 'rgba(148,163,184,0.35)'); guide(P.stoch.s.k, 20, 'rgba(148,163,184,0.35)');

  P.srsi.s.k = pline(P.srsi.chart, Object.assign({color:'#a855f7', lineWidth:1.6}, fixScale(0,100)));
  P.srsi.s.d = pline(P.srsi.chart, {color:'#26a69a', lineWidth:1.3});
  guide(P.srsi.s.k, 80, 'rgba(148,163,184,0.35)'); guide(P.srsi.s.k, 20, 'rgba(148,163,184,0.35)');

  P.cci.s.main = pline(P.cci.chart, {color:'#ff9800', lineWidth:1.4});
  guide(P.cci.s.main, 100, 'rgba(148,163,184,0.35)'); guide(P.cci.s.main, -100, 'rgba(148,163,184,0.35)');

  P.wr.s.main = pline(P.wr.chart, Object.assign({color:'#ef5350', lineWidth:1.4}, fixScale(-100,0)));
  guide(P.wr.s.main, -20, 'rgba(148,163,184,0.35)'); guide(P.wr.s.main, -80, 'rgba(148,163,184,0.35)');

  P.adx.s.a   = pline(P.adx.chart, {color:'#b2b5be', lineWidth:1.8});
  P.adx.s.p   = pline(P.adx.chart, {color:'#26a69a', lineWidth:1.2});
  P.adx.s.m   = pline(P.adx.chart, {color:'#ef5350', lineWidth:1.2});
  guide(P.adx.s.a, 20, 'rgba(148,163,184,0.35)');

  P.atr.s.main = pline(P.atr.chart, {color:'#f59e0b', lineWidth:1.4});
  P.obv.s.main = pline(P.obv.chart, {color:'#2962ff', lineWidth:1.4});
  P.mfi.s.main = pline(P.mfi.chart, Object.assign({color:'#a855f7', lineWidth:1.4}, fixScale(0,100)));
  guide(P.mfi.s.main, 80, 'rgba(148,163,184,0.35)'); guide(P.mfi.s.main, 20, 'rgba(148,163,184,0.35)');
})();

/* ---------- داده‌ی پنل‌ها ---------------------------------------------- */
const FILL = {
  rsi(){ const K=calcFor(S.tf); PANE.rsi.s.main.setData(zip(K.t, K.rsi)); },
  macd(){ const K=calcFor(S.tf);
    PANE.macd.s.m.setData(zip(K.t, K.m)); PANE.macd.s.sig.setData(zip(K.t, K.sig));
    PANE.macd.s.hist.setData(K.t.map((t,i)=>{
      const v=K.h[i]; if(v==null) return null;
      const pv=K.h[i-1];
      const col = v>=0 ? (pv!=null && v>=pv ? 'rgba(38,166,154,0.65)' : 'rgba(38,166,154,0.28)')
                       : (pv!=null && v<=pv ? 'rgba(239,83,80,0.65)'  : 'rgba(239,83,80,0.28)');
      return {time:t, value:v, color:col};
    }).filter(Boolean)); },
  stoch(){ const K=calcFor(S.tf);
    PANE.stoch.s.k.setData(zip(K.t, K.stoK)); PANE.stoch.s.d.setData(zip(K.t, K.stoD)); },
  srsi(){ const K=calcFor(S.tf);
    PANE.srsi.s.k.setData(zip(K.t, K.srK)); PANE.srsi.s.d.setData(zip(K.t, K.srD)); },
  cci(){ const K=calcFor(S.tf); PANE.cci.s.main.setData(zip(K.t, K.cci)); },
  wr(){ const K=calcFor(S.tf); PANE.wr.s.main.setData(zip(K.t, K.wr)); },
  adx(){ const K=calcFor(S.tf);
    PANE.adx.s.a.setData(zip(K.t, K.adx)); PANE.adx.s.p.setData(zip(K.t, K.pdi));
    PANE.adx.s.m.setData(zip(K.t, K.mdi)); },
  atr(){ const K=calcFor(S.tf); PANE.atr.s.main.setData(zip(K.t, K.atr)); },
  obv(){ const K=calcFor(S.tf); PANE.obv.s.main.setData(zip(K.t, K.obv)); },
  mfi(){ const K=calcFor(S.tf); PANE.mfi.s.main.setData(zip(K.t, K.mfi)); },
};
function rebuildAllPanes(){ for(const k in FILL) FILL[k](); }
/* ---------- سری اصلی + اندیکاتورهای روکش ------------------------------- */
let mainSeries=null, volSeries=null; const IND={}; let priceLines=[]; let sigLines=[];
function rm(s){ if(s){ try{ chartMain.removeSeries(s); }catch(e){} } }

const IND_MENU = [
  ['_g','میانگین‌های متحرک'],
  ['ema9','EMA 9','#00bcd4'], ['ema20','EMA 20','#2962ff'], ['ema21','EMA 21','#8d6e63'],
  ['ema50','EMA 50','#ff9800'], ['ema200','EMA 200','#e91e63'],
  ['sma20','SMA 20','#f23645'], ['sma50','SMA 50','#089981'],
  ['sma100','SMA 100','#7e57c2'], ['sma200','SMA 200','#fbc02d'],
  ['_g','روند'],
  ['psar','Parabolic SAR','#26a69a'], ['st','SuperTrend (10,3)','#00e676'],
  ['ichi','ایچیموکو (9,26,52)','#5b8def'],
  ['_g','باندها و سطوح'],
  ['bb','باندهای بولینگر (20,2)','#94a3b8'], ['vwap','VWAP (روزانه)','#f59e0b'],
  ['piv','پیوت‌پوینت روزانه','#8ea1c0'],
  ['_g','روکش‌های خودکار — قابل خاموش‌کردن'],
  ['zones','نواحی FVG/BVG','#a855f7'], ['plines','خطوط سیگنال (ورود/ضرر/هدف)','#f59e0b'],
  ['_g','نوسان‌گرها — پنل جداگانه'],
  ['rsi','RSI (14)','#7e57c2'], ['macd','MACD (12,26,9)','#26a69a'],
  ['stoch','استوکاستیک (14,3,3)','#2962ff'], ['srsi','استوک RSI (14,14,3,3)','#a855f7'],
  ['cci','CCI (20)','#ff9800'], ['wr','ویلیامز %R (14)','#ef5350'],
  ['adx','ADX / DMI (14)','#b2b5be'], ['atr','ATR (14)','#f59e0b'],
  ['_g','حجم'],
  ['vol','هیستوگرام حجم','#26a69a'], ['volma','میانگین حجم ۲۰','#8ea1c0'],
  ['obv','OBV — پنل جداگانه','#2962ff'], ['mfi','MFI (14) — پنل جداگانه','#a855f7'],
];
const VIS = { e9:'ema9', e20:'ema20', e21:'ema21', e50:'ema50', e200:'ema200',
  s20:'sma20', s50:'sma50', s100:'sma100', s200:'sma200',
  bbU:'bb', bbM:'bb', bbL:'bb', vwap:'vwap', volma:'volma',
  stU:'st', stD:'st', ichiT:'ichi', ichiK:'ichi', ichiA:'ichi', ichiB:'ichi', ichiC:'ichi' };

function applyMarkers(){
  if(!mainSeries) return;
  if(!S.ind.psar){ mainSeries.setMarkers([]); return; }
  const K = calcFor(S.tf); const c = CAND();
  const mks = [];
  for(let i=0;i<c.length;i++){ const v=K.psar[i]; if(v==null) continue;
    mks.push({ time:c[i][0], position: K.psarS[i]===1? 'belowBar':'aboveBar',
               color: K.psarS[i]===1? '#26a69a':'#ef5350', shape:'circle' }); }
  mainSeries.setMarkers(mks);
}

function rebuildMain(keepRange){
  const prev = keepRange ? chartMain.timeScale().getVisibleLogicalRange() : null;
  rm(mainSeries); rm(volSeries);
  for(const k in IND) rm(IND[k]);
  for(const k in IND) IND[k]=null;
  const c = CAND(); if(c.length<2) return;
  const up='#26a69a', dn='#ef5350';
  const pf = { type:'price', precision:DEC, minMove:Math.pow(10,-DEC) };
  volSeries = chartMain.addHistogramSeries({ priceScaleId:'vol', priceFormat:{type:'volume'},
    priceLineVisible:false, lastValueVisible:false });
  chartMain.priceScale('vol').applyOptions({ scaleMargins:{top:0.8, bottom:0} });
  volSeries.setData(c.filter(a=>a[5]!=null).map(a=>({time:a[0], value:a[5],
    color: a[4]>=a[1] ? 'rgba(38,166,154,0.5)' : 'rgba(239,83,80,0.5)'})));
  volSeries.applyOptions({ visible: !!S.ind.vol });

  const isHA = S.type==='heikin';
  const src = isHA ? haCalc(c) : c;
  if(S.type==='candles' || isHA){
    mainSeries = chartMain.addCandlestickSeries({ upColor:up, downColor:dn,
      borderUpColor:up, borderDownColor:dn, wickUpColor:up, wickDownColor:dn,
      priceFormat:pf, priceLineColor:'rgba(148,163,184,0.6)', priceLineStyle:0 });
    mainSeries.setData(src.map(a=>({time:a[0], open:a[1], high:a[2], low:a[3], close:a[4]})));
  } else if(S.type==='hollow'){
    mainSeries = chartMain.addCandlestickSeries({ priceFormat:pf,
      priceLineColor:'rgba(148,163,184,0.6)', priceLineStyle:0 });
    mainSeries.setData(src.map(a=>{ const isUp=a[4]>=a[1];
      return { time:a[0], open:a[1], high:a[2], low:a[3], close:a[4],
        color: isUp? 'rgba(0,0,0,0)' : dn,
        borderColor: isUp? up : dn,
        wickColor: isUp? up : dn }; }));
  } else if(S.type==='bars'){
    mainSeries = chartMain.addBarSeries({ upColor:up, downColor:dn, priceFormat:pf,
      priceLineColor:'rgba(148,163,184,0.6)' });
    mainSeries.setData(src.map(a=>({time:a[0], open:a[1], high:a[2], low:a[3], close:a[4]})));
  } else if(S.type==='line' || S.type==='linemk' || S.type==='step'){
    const lopts = { color:'#2962ff', lineWidth:2, priceFormat:pf };
    if(S.type==='step') lopts.lineType = LightweightCharts.LineType.WithSteps;
    if(S.type==='linemk') lopts.pointMarkersVisible = true;
    mainSeries = chartMain.addLineSeries(lopts);
    mainSeries.setData(src.map(a=>({time:a[0], value:a[4]})));
  } else if(S.type==='baseline'){
    mainSeries = chartMain.addBaselineSeries({ baseValue:{type:'price', price:src[0][4]},
      topLineColor:'rgba(38,166,154,0.9)', topFillColor1:'rgba(38,166,154,0.28)', topFillColor2:'rgba(38,166,154,0.03)',
      bottomLineColor:'rgba(239,83,80,0.9)', bottomFillColor1:'rgba(239,83,80,0.03)', bottomFillColor2:'rgba(239,83,80,0.28)',
      lineWidth:2, priceFormat:pf });
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
  mk('e9',  {color:'#00bcd4', lineWidth:1.4}).setData(zip(K.t, K.e9));
  mk('e20', {color:'#2962ff', lineWidth:1.6}).setData(zip(K.t, K.e20));
  mk('e21', {color:'#8d6e63', lineWidth:1.4}).setData(zip(K.t, K.e21));
  mk('e50', {color:'#ff9800', lineWidth:1.6}).setData(zip(K.t, K.e50));
  mk('e200',{color:'#e91e63', lineWidth:1.6}).setData(zip(K.t, K.e200));
  mk('s20', {color:'#f23645', lineWidth:1.4}).setData(zip(K.t, K.s20));
  mk('s50', {color:'#089981', lineWidth:1.4}).setData(zip(K.t, K.s50));
  mk('s100',{color:'#7e57c2', lineWidth:1.4}).setData(zip(K.t, K.s100));
  mk('s200',{color:'#fbc02d', lineWidth:1.4}).setData(zip(K.t, K.s200));
  mk('bbU',{color:'rgba(148,163,184,0.45)', lineWidth:1}).setData(zip(K.t, K.bbU));
  mk('bbM',{color:'rgba(148,163,184,0.28)', lineWidth:1, lineStyle:2}).setData(zip(K.t, K.bbM));
  mk('bbL',{color:'rgba(148,163,184,0.45)', lineWidth:1}).setData(zip(K.t, K.bbL));
  mk('vwap',{color:'#f59e0b', lineWidth:1.6}).setData(zip(K.t, K.vw));
  mk('volma',{color:'#8ea1c0', lineWidth:1, priceScaleId:'vol'}).setData(zip(K.t, K.volma));
  chartMain.priceScale('vol').applyOptions({ scaleMargins:{top:0.8, bottom:0} });
  mk('stU',{color:'#00e676', lineWidth:1.8}).setData(zip(K.t, K.stU));
  mk('stD',{color:'#ff5252', lineWidth:1.8}).setData(zip(K.t, K.stD));
  mk('ichiT',{color:'#2962ff', lineWidth:1.1}).setData(zip(K.t, K.ichi.tenkan));
  mk('ichiK',{color:'#f23645', lineWidth:1.1}).setData(zip(K.t, K.ichi.kijun));
  mk('ichiA',{color:'rgba(38,166,154,0.55)', lineWidth:1}).setData(K.ichi.A);
  mk('ichiB',{color:'rgba(239,83,80,0.55)',  lineWidth:1}).setData(K.ichi.B);
  mk('ichiC',{color:'rgba(168,85,247,0.5)',  lineWidth:1}).setData(K.ichi.C);
  for(const k of Object.keys(VIS))
    if(IND[k]) IND[k].applyOptions({ visible: !!S.ind[VIS[k]] });

  applyMarkers();

  priceLines = [];
  sigLines = [];
  if(S.ind.plines!==false && S.tf===DATA.base_tf){
    for(const lv of DATA.levels){
      sigLines.push(mainSeries.createPriceLine({ price:lv.price, color:lv.color, lineWidth:1,
        lineStyle: lv.dash ? LightweightCharts.LineStyle.Dashed : LightweightCharts.LineStyle.Solid,
        axisLabelVisible:true, title:lv.name }));
    }
  }
  if(S.ind.piv && SEC() < 86400 && K.piv){
    const pv = K.piv;
    const defs = [['P',pv.P,'#f59e0b'], ['R1',pv.R1,'#ef5350'], ['R2',pv.R2,'#ef5350'],
                  ['R3',pv.R3,'#ef5350'], ['S1',pv.S1,'#26a69a'], ['S2',pv.S2,'#26a69a'],
                  ['S3',pv.S3,'#26a69a']];
    for(const d of defs)
      priceLines.push(mainSeries.createPriceLine({ price:d[1], color:d[2], lineWidth:1,
        lineStyle:LightweightCharts.LineStyle.Dotted, axisLabelVisible:true, title:d[0] }));
  }
  if(prev) chartMain.timeScale().setVisibleLogicalRange(prev);
}

/* ---------- خطوط سیگنال: خاموش/روشن بدون بازسازی چارت ------------------ */
function applySigLines(){
  if(!mainSeries) return;
  for(const pl of sigLines){ try{ mainSeries.removePriceLine(pl); }catch(e){} }
  sigLines = [];
  if(S.ind.plines!==false && S.tf===DATA.base_tf){
    for(const lv of DATA.levels){
      sigLines.push(mainSeries.createPriceLine({ price:lv.price, color:lv.color, lineWidth:1,
        lineStyle: lv.dash ? LightweightCharts.LineStyle.Dashed : LightweightCharts.LineStyle.Solid,
        axisLabelVisible:true, title:lv.name }));
    }
  }
}

/* ---------- لجند ------------------------------------------------------ */
const legend = document.getElementById('legend');
const lind = document.getElementById('lind');
const ltitle = document.getElementById('ltitle');
function setLegend(bar){
  const d = new Date(bar.t*1000);
  const ts = d.toLocaleString('en-GB',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
  const Ci = CAND(); const bi = IDX.get(bar.t);
  const pc = (bi!=null && bi>0 && Ci[bi-1]) ? Ci[bi-1][4] : bar.o;   // تغییر مثل TV: نسبت به کلوز کندل قبل
  const up = bar.c>=pc, cls = up?'up':'dn';
  const chg = pc? ((bar.c-pc)/pc*100) : 0;
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
  if(S.ind.ema9)  add('#00bcd4','EMA9',K.e9[i]);
  if(S.ind.ema20) add('#2962ff','EMA20',K.e20[i]);
  if(S.ind.ema21) add('#8d6e63','EMA21',K.e21[i]);
  if(S.ind.ema50) add('#ff9800','EMA50',K.e50[i]);
  if(S.ind.ema200) add('#e91e63','EMA200',K.e200[i]);
  if(S.ind.sma20) add('#f23645','SMA20',K.s20[i]);
  if(S.ind.sma50) add('#089981','SMA50',K.s50[i]);
  if(S.ind.sma100) add('#7e57c2','SMA100',K.s100[i]);
  if(S.ind.sma200) add('#fbc02d','SMA200',K.s200[i]);
  if(S.ind.bb && K.bbU[i]!=null) rows.push('<span class="ik" style="color:#94a3b8">BB '+fmtP(K.bbU[i])+' / '+fmtP(K.bbL[i])+'</span>');
  if(S.ind.vwap) add('#f59e0b','VWAP',K.vw[i]);
  if(S.ind.st) rows.push('<span class="ik" style="color:'+(K.stU[i]!=null?'#00e676':'#ff5252')+'">ST '+fmtP(K.stU[i]!=null?K.stU[i]:K.stD[i])+'</span>');
  if(S.ind.psar && K.psar[i]!=null) add(K.psarS[i]===1?'#26a69a':'#ef5350','PSAR',K.psar[i]);
  if(S.ind.ichi && K.ichi.tenkan[i]!=null) rows.push('<span class="ik" style="color:#5b8def">ICH '+fmtP(K.ichi.tenkan[i])+' / '+fmtP(K.ichi.kijun[i])+'</span>');
  lind.innerHTML = rows.join('');
}
function paneLegendHTML(k, K, i){
  const sp=(col,txt)=> '<span style="color:'+col+'">'+txt+'</span>';
  if(k==='rsi')  return sp('#7e57c2', F1(K.rsi[i]));
  if(k==='macd') return sp('#2962ff',F4(K.m[i]))+' '+sp('#ff9800',F4(K.sig[i]))+' '
                      + sp(K.h[i]==null||K.h[i]>=0?'#26a69a':'#ef5350', F4(K.h[i]));
  if(k==='stoch') return sp('#2962ff','K '+F1(K.stoK[i]))+' '+sp('#ff9800','D '+F1(K.stoD[i]));
  if(k==='srsi') return sp('#a855f7','K '+F1(K.srK[i]))+' '+sp('#26a69a','D '+F1(K.srD[i]));
  if(k==='cci')  return sp('#ff9800', F1(K.cci[i]));
  if(k==='wr')   return sp('#ef5350', F1(K.wr[i]));
  if(k==='adx')  return sp('#b2b5be',F1(K.adx[i]))+' '+sp('#26a69a','+DI '+F1(K.pdi[i]))+' '+sp('#ef5350','−DI '+F1(K.mdi[i]));
  if(k==='atr')  return sp('#f59e0b', fmtP(K.atr[i]));
  if(k==='obv')  return sp('#2962ff', fmtV(K.obv[i]));
  if(k==='mfi')  return sp('#a855f7', F1(K.mfi[i]));
  return '';
}
function updatePaneLegends(time){
  const K = CALC[S.tf]; const i = IDX.get(time);
  for(const k in PANE){
    if(!S.ind[k]) continue;
    const el = document.getElementById('leg-'+k);
    el.innerHTML = PANE[k].def.t + ' · <b>' + ((K && i!=null)? paneLegendHTML(k,K,i) : '—') + '</b>';
  }
}
function updateTitle(){ ltitle.textContent = DATA.symbol + ' · ' + (TF_LBL[S.tf]||S.tf); }

/* ---------- همگام‌سازی کراس‌هیر و محور زمان ---------------------------- */
const ALLCH = () => [chartMain].concat(Object.keys(PANE).map(k=>PANE[k].chart));
let syncing = false;
let suppressed = false;
function syncFrom(src){
  if(syncing || suppressed) return; syncing = true;
  const r = src.timeScale().getVisibleLogicalRange();
  if(r) for(const c of ALLCH()){
    if(c!==src && c._el && c._el.clientWidth>0){ try{ c.timeScale().setVisibleLogicalRange(r); }catch(e){} }
  }
  syncing = false;
}
let lastT = {};
function setCross(ch, key, price, t, series){
  if(lastT[key]===t) return; lastT[key]=t;
  try{ ch.setCrosshairPosition(price, t, series); }catch(e){}
}
function clearCross(key, ch){
  if(lastT[key]==null) return; lastT[key]=null;
  try{ ch.clearCrosshairPosition(); }catch(e){}
}
chartMain.subscribeCrosshairMove(param => {
  if(param && param.time && param.seriesData){
    const c = param.seriesData.get(mainSeries);
    if(c){
      const isOHLC = c.high!=null;
      const cv = isOHLC ? c.close : c.value;
      const a = CAND()[IDX.get(c.time)];
      setLegend({t:c.time, o:isOHLC?c.open:cv, h:isOHLC?c.high:cv, l:isOHLC?c.low:cv, c:cv,
                 v:a?a[5]:null});
      setIndLegend(c.time); updatePaneLegends(c.time);
      const K=CALC[S.tf]; const i=IDX.get(c.time);
      if(K && i!=null){
        for(const k in PANE){
          if(!S.ind[k]) continue;
          const v = PANE_VAL[k](K, i);
          if(v!=null) setCross(PANE[k].chart, 'p:'+k, v, c.time, PANE_PRIM[k]);
          else clearCross('p:'+k, PANE[k].chart);
        }
      }
    }
  } else {
    const c=CAND(); const l=c.length-1; const a=c[l];
    if(a){ setLegend({t:a[0],o:a[1],h:a[2],l:a[3],c:a[4],v:a[5]}); setIndLegend(a[0]); updatePaneLegends(a[0]); }
    for(const k in PANE) clearCross('p:'+k, PANE[k].chart);
  }
});
for(const k in PANE){
  const p = PANE[k];
  p.chart.subscribeCrosshairMove(param => {
    if(param && param.time && param.seriesData){
      const c = CAND(); const i = IDX.get(param.time);
      if(i!=null && c[i]){ updatePaneLegends(param.time);
        setCross(chartMain, 'm', c[i][4], param.time, mainSeries); }
    } else { clearCross('m', chartMain); }
  });
}
const PANE_PRIM = {};
const PANE_VAL = {};
(function definePrim(){
  PANE_PRIM.rsi=PANE.rsi.s.main;  PANE_VAL.rsi=(K,i)=>K.rsi[i];
  PANE_PRIM.macd=PANE.macd.s.m;   PANE_VAL.macd=(K,i)=>K.m[i];
  PANE_PRIM.stoch=PANE.stoch.s.k; PANE_VAL.stoch=(K,i)=>K.stoK[i];
  PANE_PRIM.srsi=PANE.srsi.s.k;   PANE_VAL.srsi=(K,i)=>K.srK[i];
  PANE_PRIM.cci=PANE.cci.s.main;  PANE_VAL.cci=(K,i)=>K.cci[i];
  PANE_PRIM.wr=PANE.wr.s.main;    PANE_VAL.wr=(K,i)=>K.wr[i];
  PANE_PRIM.adx=PANE.adx.s.a;     PANE_VAL.adx=(K,i)=>K.adx[i];
  PANE_PRIM.atr=PANE.atr.s.main;  PANE_VAL.atr=(K,i)=>K.atr[i];
  PANE_PRIM.obv=PANE.obv.s.main;  PANE_VAL.obv=(K,i)=>K.obv[i];
  PANE_PRIM.mfi=PANE.mfi.s.main;  PANE_VAL.mfi=(K,i)=>K.mfi[i];
})();
for(const c of ALLCH()) c.timeScale().subscribeVisibleLogicalRangeChange(()=>syncFrom(c));
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
function yOf(p){ return (mainSeries && p!=null)? mainSeries.priceToCoordinate(p) : null; }
function snapTime(x){
  const ts = chartMain.timeScale(); let li = ts.coordinateToLogical(x);
  if(li==null) return null;
  li = Math.max(0, Math.min(CAND().length-1, Math.round(li)));
  return CALC[S.tf].t[li];
}
function loadDraw(){ const v = safeParse(localStorage.getItem(SK('draw:'+S.tf))); return Array.isArray(v)? v : []; }
function saveDraw(){ try{ localStorage.setItem(SK('draw:'+S.tf), JSON.stringify(DRAWINGS)); }catch(e){} if(window.__nqSyncQueue) window.__nqSyncQueue(); }
function saveInd(){ try{ localStorage.setItem(SK('ind'), JSON.stringify(S.ind)); }catch(e){} }
/* رسم‌های قدیمی (قالب تخت) → قالب جدید (تودرتو) */
function normDraw(d){
  if(d && typeof d.p1==='number'){
    return { type:d.type, txt:d.txt||null,
      p1:{ t:(d.t1!=null? d.t1:null), price:d.p1 },
      p2: (d.p2!=null)? { t:(d.t2!=null? d.t2:null), price:d.p2 } : null };
  }
  return d;
}

const FIB_LV = [[0,'#f59e0b'],[0.236,'#ef5350'],[0.382,'#f59e0b'],[0.5,'#2962ff'],[0.618,'#26a69a'],[0.786,'#a855f7'],[1,'#f59e0b']];
function drawSeg(a, b){
  const x1=a&&a.t!=null? xOfT(a.t):null, x2=b&&b.t!=null? xOfT(b.t):null;
  const y1=a&&a.price!=null? yOf(a.price):null, y2=b&&b.price!=null? yOf(b.price):null;
  if(x1==null||x2==null||y1==null||y2==null) return;
  octx.save(); octx.setLineDash([4,4]);
  octx.strokeStyle='rgba(148,163,184,0.8)'; octx.lineWidth=1.2;
  octx.beginPath(); octx.moveTo(x1,y1); octx.lineTo(x2,y2); octx.stroke();
  octx.restore();
}
function drawOne(d, dashed){
  const pt1=d.p1||null, pt2=d.p2||null, pt3=d.p3||null;
  const x1= pt1&&pt1.t!=null? xOfT(pt1.t):null;
  const x2= pt2&&pt2.t!=null? xOfT(pt2.t):null;
  const y1= pt1&&pt1.price!=null? yOf(pt1.price):null;
  const y2= pt2&&pt2.price!=null? yOf(pt2.price):null;
  const y3= pt3&&pt3.price!=null? yOf(pt3.price):null;
  octx.save();
  if(dashed) octx.setLineDash([4,4]);
  const W = chartMain.timeScale().width(), H = ovl.height/(window.devicePixelRatio||1);
  if(d.type==='hline'){
    if(y1==null){ octx.restore(); return; }
    octx.strokeStyle='#f59e0b'; octx.lineWidth=1;
    octx.beginPath(); octx.moveTo(0,y1); octx.lineTo(W,y1); octx.stroke();
    octx.setLineDash([]);
    const txt = fmtP(pt1.price);
    octx.font='600 10px '+MONO; const tw = octx.measureText(txt).width;
    octx.fillStyle='#f59e0b'; octx.fillRect(W-tw-10, y1-9, tw+8, 16);
    octx.fillStyle='#0e1117'; octx.fillText(txt, W-tw-6, y1+3);
  } else if(d.type==='hray'){
    if(y1==null){ octx.restore(); return; }
    const x0 = x1!=null? x1 : 0;
    octx.strokeStyle='#8ea1c0'; octx.lineWidth=1.2;
    octx.beginPath(); octx.moveTo(x0,y1); octx.lineTo(W,y1); octx.stroke();
    octx.setLineDash([]);
    octx.fillStyle='#8ea1c0';
    octx.beginPath(); octx.arc(x0,y1,3,0,7); octx.fill();
    const txt = fmtP(pt1.price);
    octx.font='600 10px '+MONO; const tw = octx.measureText(txt).width;
    octx.fillStyle='#8ea1c0'; octx.fillRect(Math.min(x0+6, W-tw-10), y1-9, tw+8, 16);
    octx.fillStyle='#0e1117'; octx.fillText(txt, Math.min(x0+10, W-tw-6), y1+3);
  } else if(d.type==='vline'){
    if(x1==null){ octx.restore(); return; }
    octx.strokeStyle='#8ea1c0'; octx.lineWidth=1.2;
    octx.beginPath(); octx.moveTo(x1,0); octx.lineTo(x1,H); octx.stroke();
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
      const p = pt2.price + (pt1.price-pt2.price)*lv[0];
      const y = yOf(p); if(y==null) continue;
      octx.strokeStyle=lv[1]; octx.lineWidth=1;
      octx.beginPath(); octx.moveTo(xa,y); octx.lineTo(xb,y); octx.stroke();
      octx.fillStyle=lv[1];
      octx.fillText(lv[0].toFixed(3)+' · '+fmtP(p), xb+5, y-3);
    }
  } else if(d.type==='arrowU' || d.type==='arrowD'){
    if(x1==null||y1==null){ octx.restore(); return; }
    const isU = d.type==='arrowU';
    octx.fillStyle = isU? '#26a69a' : '#ef5350';
    octx.beginPath();
    if(isU){ octx.moveTo(x1,y1-9); octx.lineTo(x1-6,y1+4); octx.lineTo(x1+6,y1+4); }
    else   { octx.moveTo(x1,y1+9); octx.lineTo(x1-6,y1-4); octx.lineTo(x1+6,y1-4); }
    octx.closePath(); octx.fill();
  } else if(d.type==='text'){
    if(x1==null||y1==null){ octx.restore(); return; }
    octx.font='600 11px Tahoma, sans-serif';
    const txt = d.txt||'';
    const tw = octx.measureText(txt).width;
    octx.fillStyle='rgba(14,17,23,0.75)';
    octx.fillRect(x1-2, y1-13, tw+6, 17);
    octx.fillStyle='#f59e0b';
    octx.fillText(txt, x1+1, y1);
  } else if(d.type==='brush'){
    if(!d.pts || d.pts.length<2){ octx.restore(); return; }
    octx.strokeStyle='rgba(41,98,255,0.85)'; octx.lineWidth=1.6;
    octx.beginPath();
    let started=false;
    for(const pt of d.pts){
      const x= pt.t!=null? xOfT(pt.t):null, y= pt.price!=null? yOf(pt.price):null;
      if(x==null||y==null){ started=false; continue; }
      if(!started){ octx.moveTo(x,y); started=true; } else octx.lineTo(x,y);
    }
    octx.stroke();
  } else if(d.type==='posL' || d.type==='posS'){
    if(y1==null||y2==null||y3==null){ octx.restore(); return; }
    const x0 = x1!=null? Math.max(0,x1) : 0;
    octx.fillStyle='rgba(38,166,154,0.13)';
    octx.fillRect(x0, Math.min(y1,y3), W-x0, Math.abs(y3-y1));
    octx.strokeStyle='rgba(38,166,154,0.6)'; octx.lineWidth=1;
    octx.strokeRect(x0+0.5, Math.min(y1,y3)+0.5, W-x0-1, Math.abs(y3-y1)-1);
    octx.fillStyle='rgba(239,83,80,0.13)';
    octx.fillRect(x0, Math.min(y1,y2), W-x0, Math.abs(y2-y1));
    octx.strokeStyle='rgba(239,83,80,0.6)';
    octx.strokeRect(x0+0.5, Math.min(y1,y2)+0.5, W-x0-1, Math.abs(y2-y1)-1);
    octx.strokeStyle='rgba(148,163,184,0.8)';
    octx.beginPath(); octx.moveTo(x0,y1); octx.lineTo(W,y1); octx.stroke();
    const risk = Math.abs(pt1.price-pt2.price), rew = Math.abs(pt3.price-pt1.price);
    const rr = risk>0? rew/risk : 0;
    const rpct = pt1.price? (rew/pt1.price*100) : 0;
    const spct = pt1.price? (risk/pt1.price*100) : 0;
    octx.font='600 10px '+MONO;
    const t1 = 'TARGET +'+rpct.toFixed(2)+'% · RR 1:'+(rr?rr.toFixed(1):'—');
    const t2 = 'RISK −'+spct.toFixed(2)+'%';
    octx.fillStyle='rgba(38,166,154,0.92)';
    octx.fillRect(x0+4, Math.min(y1,y3)+2, octx.measureText(t1).width+10, 15);
    octx.fillStyle='#04120e'; octx.fillText(t1, x0+9, Math.min(y1,y3)+13);
    octx.fillStyle='rgba(239,83,80,0.92)';
    octx.fillRect(x0+4, Math.max(y1,y2)-16, octx.measureText(t2).width+10, 15);
    octx.fillStyle='#140505'; octx.fillText(t2, x0+9, Math.max(y1,y2)-5);
  }
  octx.restore();
}
function drawPend(pd){
  const a = pd.pts[0];
  const b = pd.pts[1] || pd.p2p || a;
  drawSeg(a, b);
  if(pd.pts.length>=2 && (pd.type==='posL' || pd.type==='posS')){
    const t = a.price + (a.price - b.price)*2;
    drawSeg(b, {t:a.t, price:t});
  }
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
/* ---------- تشخیص برخورد برای پاک‌کن ----------------------------------- */
function segDist(x, y, x1, y1, x2, y2){
  if(x1==null||y1==null||x2==null||y2==null) return Infinity;
  const dx=x2-x1, dy=y2-y1, L2=dx*dx+dy*dy;
  if(!L2) return Math.hypot(x-x1, y-y1);
  let t=((x-x1)*dx+(y-y1)*dy)/L2; t=Math.max(0, Math.min(1, t));
  return Math.hypot(x-(x1+t*dx), y-(y1+t*dy));
}
function hitTest(x, y){
  const TOL = 7;
  for(let i=DRAWINGS.length-1; i>=0; i--){
    const d = DRAWINGS[i]; const pt1=d.p1, pt2=d.p2;
    const x1= pt1&&pt1.t!=null? xOfT(pt1.t):null;
    const x2= pt2&&pt2.t!=null? xOfT(pt2.t):null;
    const y1= pt1&&pt1.price!=null? yOf(pt1.price):null;
    const y2= pt2&&pt2.price!=null? yOf(pt2.price):null;
    if(d.type==='hline'){ if(y1!=null && Math.abs(y-y1)<=TOL) return i; }
    else if(d.type==='hray'){ if(y1!=null){ const x0=(x1!=null? x1:0);
      if(Math.abs(y-y1)<=TOL && x>=x0-TOL) return i; } }
    else if(d.type==='vline'){ if(x1!=null && Math.abs(x-x1)<=TOL) return i; }
    else if(d.type==='trend'){ if(segDist(x,y,x1,y1,x2,y2)<=TOL) return i; }
    else if(d.type==='rect'){ if(x1!=null&&x2!=null&&y1!=null&&y2!=null){
      const xa=Math.min(x1,x2), xb=Math.max(x1,x2), ya=Math.min(y1,y2), yb=Math.max(y1,y2);
      if(x>=xa-TOL && x<=xb+TOL && (Math.abs(y-ya)<=TOL || Math.abs(y-yb)<=TOL)) return i;
      if(y>=ya-TOL && y<=yb+TOL && (Math.abs(x-xa)<=TOL || Math.abs(x-xb)<=TOL)) return i; } }
    else if(d.type==='fib'){ if(x1!=null&&x2!=null&&y1!=null&&y2!=null){
      if(segDist(x,y,x1,y1,x2,y2)<=TOL) return i;
      const xa=Math.min(x1,x2), xb=Math.max(x1,x2);
      if(x>=xa-TOL && x<=xb+TOL){
        for(const lv of FIB_LV){ const p= pt2.price+(pt1.price-pt2.price)*lv[0];
          const yy=yOf(p); if(yy!=null && Math.abs(y-yy)<=TOL+3) return i; } } } }
    else if(d.type==='arrowU' || d.type==='arrowD'){
      if(x1!=null&&y1!=null && dist({x:x, y:y}, {x:x1, y:y1})<=11) return i; }
    else if(d.type==='text'){ if(x1!=null&&y1!=null){
      octx.font='600 11px Tahoma, sans-serif';
      const tw=octx.measureText(d.txt||'').width;
      if(x>=x1-4 && x<=x1+tw+6 && y>=y1-15 && y<=y1+4) return i; } }
    else if(d.type==='brush'){ if(d.pts){ for(const pt of d.pts){
      const px= pt.t!=null? xOfT(pt.t):null, py= pt.price!=null? yOf(pt.price):null;
      if(px!=null&&py!=null && dist({x:x, y:y}, {x:px, y:py})<=8) return i; } } }
    else if(d.type==='posL' || d.type==='posS'){
      if(y1!=null && Math.abs(y-y1)<=TOL && x>=(x1!=null? x1-TOL:0)) return i; }
  }
  return -1;
}

/* ---------- انتخاب و جابه‌جایی رسم‌ها (سبک تریدینگ‌ویو) ----------------- */
let selIdx=-1, drag=null;   // drag={mode:'move'|'p1'|'p2'|'p3', idx, orig, grab:{t,price}, cx, cy, moved}
function cpDraw(d){ return JSON.parse(JSON.stringify(d)); }
function ptSc(pt){ return { x:(pt&&pt.t!=null)? xOfT(pt.t):null, y:(pt&&pt.price!=null)? yOf(pt.price):null }; }
function handlesOf(d){
  if(d.type==='trend'||d.type==='rect'||d.type==='fib') return [['p1',d.p1],['p2',d.p2]];
  if(d.type==='posL'||d.type==='posS') return [['p1',d.p1],['p2',d.p2],['p3',d.p3]];
  return [];
}
function handleHit(x,y){
  if(selIdx<0 || !DRAWINGS[selIdx]) return null;
  for(const h of handlesOf(DRAWINGS[selIdx])){
    const s=ptSc(h[1]);
    if(s.x!=null&&s.y!=null && Math.hypot(x-s.x,y-s.y)<=10) return h[0];
  }
  return null;
}
function drawSel(d){
  octx.save();
  for(const h of handlesOf(d)){
    const s=ptSc(h[1]); if(s.x==null||s.y==null) continue;
    octx.beginPath(); octx.arc(s.x,s.y,4.5,0,Math.PI*2);
    octx.fillStyle='#2962ff'; octx.fill();
    octx.lineWidth=1.6; octx.strokeStyle='#eaeef6'; octx.stroke();
  }
  octx.restore();
}
/* جابه‌جایی همه‌ی نقاط رسم با دلتای زمان/قیمت — نقاطِ null (مثل t خط افقی) دست‌نخورده می‌مانند */
function applyDelta(d, dt, dp){
  for(const k of ['p1','p2','p3']){
    const pt=d[k];
    if(pt){ if(pt.t!=null && dt) pt.t+=dt; if(pt.price!=null && dp) pt.price+=dp; }
  }
  if(d.pts) for(const pt of d.pts){ if(pt.t!=null && dt) pt.t+=dt; if(pt.price!=null && dp) pt.price+=dp; }
}
let pend=null, measure=null, brush=null, dragMoved=false;
/* دکمه‌ی ✕ روی رسم انتخاب‌شده — کلیک = حذف همان رسم (قابل واگرد) */
const selXBtn = document.getElementById('selX');
if(selXBtn){
  selXBtn.addEventListener('pointerdown', e=>e.stopPropagation());
  selXBtn.addEventListener('click', e=>{ e.stopPropagation(); if(selIdx>=0) eraseAt(selIdx); });
}
function selXAnchor(d){
  for(const h of handlesOf(d)){ const s=ptSc(h[1]); if(s.x!=null&&s.y!=null) return s; }
  if(d.pts && d.pts.length){ const s=ptSc(d.pts[0]); if(s.x!=null&&s.y!=null) return s; }
  if(d.p1){ const s=ptSc(d.p1); if(s.x!=null&&s.y!=null) return s; }
  return null;
}
window.__nqPlaceSelX = function(){
  if(!selXBtn) return;
  const d = (selIdx>=0)? DRAWINGS[selIdx] : null;
  const a = d? selXAnchor(d) : null;
  if(!a){ selXBtn.style.display='none'; return; }
  const r = mainPane.getBoundingClientRect();
  selXBtn.style.display='block';
  selXBtn.style.left = Math.max(4, Math.min(a.x+13, r.width-26)) + 'px';
  selXBtn.style.top  = Math.max(4, Math.min(a.y-29, r.height-26)) + 'px';
};
__ZONES_JS__
function renderLoop(){
  const r = mainPane.getBoundingClientRect();
  octx.clearRect(0,0,r.width,r.height);
  drawZones();
  for(const d of DRAWINGS) drawOne(d,false);
  if(selIdx>=0 && DRAWINGS[selIdx]) drawSel(DRAWINGS[selIdx]);
  if(window.__nqDrawAlerts) window.__nqDrawAlerts();
  if(window.__nqPlaceSelX) window.__nqPlaceSelX();
  if(brush && brush.pts.length>1) drawOne({type:'brush', pts:brush.pts}, true);
  if(pend) drawPend(pend);
  if(measure) drawMeasure(measure);
  requestAnimationFrame(renderLoop);
}
if(window.ResizeObserver) new ResizeObserver(()=>sizeOvl()).observe(mainPane);

/* ---------- رویدادهای ماوس/لمس رسم ------------------------------------ */
const CLICKS = { trend:2, rect:2, fib:2, posL:3, posS:3,
                 hline:1, hray:1, vline:1, arrowU:1, arrowD:1, text:1 };
function evPos(e){
  const r = ovl.getBoundingClientRect();
  const x = e.clientX-r.left, y = e.clientY-r.top;
  return { x:x, y:y, price: mainSeries? mainSeries.coordinateToPrice(y) : null, t: snapTime(x) };
}
function dist(a,b){ return Math.sqrt(Math.pow(a.x-b.x,2)+Math.pow(a.y-b.y,2)); }
/* ابزارها یک‌بارمصرف‌اند: بعد از هر رسم، خودکار به نشانگر برمی‌گردیم (فیبوناچی پشت‌سرهم نمی‌ماند) */
function oneShotDone(){ setTool('cursor'); buildToolsMenu(); }
function commit(d){ DRAWINGS.push(d); UNDOS.push({op:'draw', d:d}); REDOS=[]; saveDraw(); selIdx=DRAWINGS.length-1; oneShotDone(); }
function eraseAt(i){ if(i<0 || i>=DRAWINGS.length) return;
  const d = DRAWINGS.splice(i,1)[0]; UNDOS.push({op:'erase', idx:i, d:d}); REDOS=[]; saveDraw();
  if(selIdx===i) selIdx=-1; else if(selIdx>i) selIdx--;
  toast('حذف شد — ↩ واگرد برای بازگردانی'); }
function doUndo(){ const op = UNDOS.pop(); if(!op) return;
  if(op.op==='draw'){ DRAWINGS.pop(); }
  else if(op.op==='erase'){ DRAWINGS.splice(Math.min(op.idx, DRAWINGS.length), 0, op.d); }
  else if(op.op==='move'){ if(op.idx>=0 && op.idx<DRAWINGS.length) DRAWINGS[op.idx]=op.before; }
  else if(op.op==='clear'){ DRAWINGS = op.items.slice(); }
  REDOS.push(op); saveDraw(); }
function doRedo(){ const op = REDOS.pop(); if(!op) return;
  if(op.op==='draw'){ DRAWINGS.push(op.d); }
  else if(op.op==='erase'){ DRAWINGS.splice(Math.min(op.idx, DRAWINGS.length), 1); }
  else if(op.op==='move'){ if(op.idx>=0 && op.idx<DRAWINGS.length) DRAWINGS[op.idx]=op.after; }
  else if(op.op==='clear'){ DRAWINGS = []; }
  UNDOS.push(op); saveDraw(); }
function clearAll(){ if(!DRAWINGS.length) return;
  UNDOS.push({op:'clear', items:DRAWINGS.slice()}); DRAWINGS=[]; REDOS=[]; selIdx=-1; saveDraw();
  toast('همه‌ی رسم‌ها پاک شد'); }
ovl.addEventListener('pointerdown', e=>{
  if(S.tool==='cursor' || !mainSeries) return;
  e.preventDefault();
  if(S.tool==='erase'){ eraseAt(hitTest(evPos(e).x, evPos(e).y)); return; }
  if(S.tool==='alert'){
    const pa = evPos(e);
    if(pa.price!=null){ addAlert(pa.price); oneShotDone(); }
    return;
  }
  if(measure){ measure=null; }
  const p = evPos(e);
  if(S.tool==='measure'){ measure={p1:p, p2:p}; return; }
  if(S.tool==='brush'){ brush={pts:[p]}; return; }
  if(CLICKS[S.tool]===1){
    if(S.tool==='hline'){ if(p.price!=null) commit({type:'hline', p1:{t:null, price:p.price}}); }
    else if(S.tool==='vline'){ if(p.t!=null) commit({type:'vline', p1:{t:p.t, price:null}}); }
    else if(S.tool==='hray'){ if(p.price!=null) commit({type:'hray', p1:{t:p.t, price:p.price}}); }
    else if(S.tool==='arrowU'){ if(p.t!=null&&p.price!=null) commit({type:'arrowU', p1:p}); }
    else if(S.tool==='arrowD'){ if(p.t!=null&&p.price!=null) commit({type:'arrowD', p1:p}); }
    else if(S.tool==='text'){ if(p.t!=null&&p.price!=null){
      const ti=document.getElementById('txtIn');
      commit({type:'text', p1:p, txt:(ti && ti.value.trim()) || 'یادداشت'}); } }
    return;
  }
  const need = CLICKS[S.tool] || 2;
  if(pend){
    if(p.t!=null && p.price!=null){
      pend.pts.push(p);
      if(pend.pts.length>=need){
        commit({type:pend.type, p1:pend.pts[0], p2:pend.pts[1], p3:pend.pts[2]||null});
        pend=null;
      }
    }
    return;
  }
  if(p.t!=null && p.price!=null){ pend={type:S.tool, pts:[p]}; dragMoved=false; }
});
ovl.addEventListener('pointermove', e=>{
  if(!mainSeries) return;
  const p = evPos(e);
  if(measure){ if(p.t!=null && p.price!=null) measure.p2=p; return; }
  if(brush){ const last=brush.pts[brush.pts.length-1];
    if(brush.pts.length<240 && dist(last,p)>3) brush.pts.push(p); return; }
  if(pend){ if(dist(pend.pts[0],p)>6) dragMoved=true; pend.p2p=p; }
});
ovl.addEventListener('pointerup', e=>{
  if(S.tool==='measure' && measure) return;
  if(brush){ if(brush.pts.length>=3) commit({type:'brush', pts:brush.pts}); brush=null; return; }
  if(pend && CLICKS[pend.type]===2 && dragMoved){
    const p = evPos(e);
    if(dist(pend.pts[0],p)>14){
      const p2 = { t:(p.t!=null? p.t : pend.pts[0].t), price:(p.price!=null? p.price : pend.pts[0].price) };
      commit({type:pend.type, p1:pend.pts[0], p2:p2});
      pend=null;
    }
  }
});
window.addEventListener('keydown', e=>{
  if(e.key==='Escape'){ pend=null; measure=null; brush=null; selIdx=-1; drag=null; setTool('cursor'); }
  /* Delete/Backspace = حذف رسم انتخاب‌شده (وقتی در حال تایپ نیستیم) */
  if((e.key==='Delete' || e.key==='Backspace') && selIdx>=0 && S.tool==='cursor' && !drag){
    const ae=document.activeElement;
    if(ae && (ae.tagName==='INPUT' || ae.tagName==='TEXTAREA')) return;
    e.preventDefault(); eraseAt(selIdx);
  }
});

/* ---------- انتخاب و جابه‌جایی با نشانگر (سبک تریدینگ‌ویو) --------------
   رهگیری در فاز capture روی mainPane: کلیک روی رسم → انتخاب/درگ (رویداد به چارت نمی‌رسد)
   کلیک روی فضای خالی → رویداد عادی به چارت می‌رسد و پن/زوم مثل قبل کار می‌کند */
mainPane.addEventListener('pointerdown', e=>{
  if(S.tool!=='cursor' || !mainSeries) return;
  if(e.button!==undefined && e.button!==0) return;
  if(e.target && e.target.closest && e.target.closest('#selX')) return;  /* کلیک روی ✕ — به خودش برسد */
  const r = ovl.getBoundingClientRect();
  const x = e.clientX-r.left, y = e.clientY-r.top;
  /* کلیک روی خط هشدار قیمتی = بستن همان هشدار (قبل از رسم‌ها) */
  if(typeof alertHit==='function'){ const ah=alertHit(x,y);
    if(ah>=0){ e.stopPropagation(); e.preventDefault(); removeAlert(ah); return; } }
  const hk = handleHit(x,y);
  if(hk){
    e.stopPropagation(); e.preventDefault();
    try{ mainPane.setPointerCapture(e.pointerId); }catch(err){}
    drag={mode:hk, idx:selIdx, orig:cpDraw(DRAWINGS[selIdx]), grab:null, cx:e.clientX, cy:e.clientY, moved:false};
    mainPane.style.cursor='grabbing';
    return;
  }
  const h = hitTest(x,y);
  if(h<0){ selIdx=-1; return; }   // خروج از انتخاب — چارت آزاد است تا پن شود
  e.stopPropagation(); e.preventDefault();
  selIdx=h;
  try{ mainPane.setPointerCapture(e.pointerId); }catch(err){}
  const p = evPos(e);
  drag={mode:'move', idx:h, orig:cpDraw(DRAWINGS[h]), grab:{t:p.t, price:p.price}, cx:e.clientX, cy:e.clientY, moved:false};
  mainPane.style.cursor='grabbing';
}, true);
window.addEventListener('pointermove', e=>{
  if(drag){
    if(Math.abs(e.clientX-drag.cx)+Math.abs(e.clientY-drag.cy)>2) drag.moved=true;
    const d = DRAWINGS[drag.idx]; if(!d){ drag=null; return; }
    const p = evPos(e);
    if(drag.mode==='move'){
      const dt=(drag.grab.t!=null && p.t!=null)? p.t-drag.grab.t : 0;
      const dp=(drag.grab.price!=null && p.price!=null)? p.price-drag.grab.price : 0;
      const cur = cpDraw(drag.orig);       // همیشه از نسخه‌ی اصلی محاسبه — بدون رانش
      applyDelta(cur, dt, dp);
      DRAWINGS[drag.idx] = cur;
    } else {
      const pt = d[drag.mode];
      if(pt){ if(pt.t!=null && p.t!=null) pt.t=p.t; if(pt.price!=null && p.price!=null) pt.price=p.price; }
    }
    return;
  }
  if(S.tool!=='cursor' || !mainSeries) return;
  const r = ovl.getBoundingClientRect();
  const x = e.clientX-r.left, y = e.clientY-r.top;
  mainPane.style.cursor = (handleHit(x,y) || hitTest(x,y)>=0) ? 'grab' : '';
}, true);
window.addEventListener('pointerup', e=>{
  if(!drag) return;
  if(drag.moved){
    UNDOS.push({op:'move', idx:drag.idx, before:drag.orig, after:cpDraw(DRAWINGS[drag.idx])});
    REDOS=[]; saveDraw();
  }
  drag=null; mainPane.style.cursor='';
}, true);
/* دابل‌کلیک روی هر چیز روی چارت = بستن/حذف فوری (هشدار یا رسم) — قابل واگرد */
mainPane.addEventListener('dblclick', e=>{
  if(S.tool!=='cursor' || !mainSeries) return;
  const r = ovl.getBoundingClientRect();
  const x = e.clientX-r.left, y = e.clientY-r.top;
  if(typeof alertHit==='function'){ const ah=alertHit(x,y);
    if(ah>=0){ e.stopPropagation(); e.preventDefault(); removeAlert(ah); return; } }
  const h = hitTest(x,y);
  if(h>=0){ e.stopPropagation(); e.preventDefault(); eraseAt(h); }
}, true);

/* ---------- تولبار: تایم‌فریم · نوع چارت · منوها ---------------------- */
function toast(msg){
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('show');
  clearTimeout(t._h); t._h = setTimeout(()=>t.classList.remove('show'), 2600);
}
const tfBtns = document.getElementById('tfBtns');
function buildTfBtns(){
  let h='';
  for(const tf of TF_QUICK){
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
  DRAWINGS = loadDraw().map(normDraw); UNDOS=[]; REDOS=[]; selIdx=-1; drag=null;
  buildIdx();
  rebuildMain(false);
  rebuildAllPanes();
  buildTfBtns();
  updTfBtn();
  updateTitle();
  const c = CAND(); const n = c.length;
  const win = Math.min(DATA.initial_bars, n);
  chartMain.timeScale().setVisibleLogicalRange({ from: Math.max(0, n-win-2), to: n+4 });
  const a = c[c.length-1];
  if(a){ setLegend({t:a[0],o:a[1],h:a[2],l:a[3],c:a[4],v:a[5]}); setIndLegend(a[0]); updatePaneLegends(a[0]); }
  closeMenus();
  if(window.__nqSyncReconcile) window.__nqSyncReconcile();   // همگام‌سازی رسم‌های تایم‌فریم جدید
}
const TYPE_LBL = {candles:'کندل', hollow:'توخالی', bars:'میله', line:'خط', linemk:'خط + نشانگر',
                  step:'پله‌ای', area:'ناحیه', baseline:'بیس‌لاین', heikin:'هایکن‌آشی'};
function setType(t){
  S.type = t; localStorage.setItem(SK('type'), t);
  document.getElementById('typeLbl').textContent = TYPE_LBL[t]||t;
  rebuildMain(true);
  closeMenus();
}
function applyPanes(){
  let last=null;
  for(const k in PANE){
    const on = !!S.ind[k];
    PANE[k].el.style.display = on? 'block':'none';
    if(on) last = PANE[k];
  }
  for(const k in PANE) PANE[k].chart.applyOptions({ timeScale:{ visible: PANE[k]===last } });
  chartMain.applyOptions({ timeScale:{ visible: !last } });
  /* چارت تازه‌نمایش‌شده هنوز عرض نگرفته؛ چند فریم رنجِ اصلی را به‌زور اعمال می‌کنیم
     تا barSpacing خراب (حداقل 0.5px) از چارت‌های مخفی نشت نکند. */
  suppressed = true;
  let n = 0;
  const tick = () => {
    n++;
    const r = chartMain.timeScale().getVisibleLogicalRange();
    if(r) for(const k in PANE){
      const c = PANE[k].chart;
      if(c._el && c._el.clientWidth>0){ try{ c.timeScale().setVisibleLogicalRange(r); }catch(e){} }
    }
    sizeOvl();
    if(n < 10) requestAnimationFrame(tick); else suppressed = false;
  };
  requestAnimationFrame(tick);
}
function toggleInd(k){
  S.ind[k] = !S.ind[k]; saveInd();
  if(k==='plines'){ applySigLines(); return; }
  if(k==='zones'){ return; }   /* renderLoop هر فریم با S.ind.zones می‌کشد — فریم بعد خودش می‌رود */
  if(PANE[k]){ FILL[k](); applyPanes(); return; }
  const grp = (keys)=>{ for(const s of keys) if(IND[s]) IND[s].applyOptions({visible:S.ind[k]}); };
  if(k==='bb'){ grp(['bbU','bbM','bbL']); return; }
  if(k==='st'){ grp(['stU','stD']); return; }
  if(k==='ichi'){ grp(['ichiT','ichiK','ichiA','ichiB','ichiC']); return; }
  if(k==='psar'){ applyMarkers(); return; }
  if(k==='piv'){ rebuildMain(true); return; }
  if(k==='vol'){ if(volSeries) volSeries.applyOptions({visible:S.ind.vol}); return; }
  if(IND[k]) IND[k].applyOptions({visible:S.ind[k]});
}
function buildIndMenu(){
  const m = document.getElementById('menuInd');
  let h='';
  for(const it of IND_MENU){
    if(it[0]==='_g'){ h += '<div class="mgroup">'+it[1]+'</div>'; continue; }
    h += '<div class="mi" data-k="'+it[0]+'">'
       + '<span class="chk'+(S.ind[it[0]]?' on':'')+'"></span>'
       + '<span class="dot" style="background:'+it[2]+'"></span><span>'+it[1]+'</span></div>';
  }
  m.innerHTML = h;
  for(const el of m.querySelectorAll('.mi'))
    el.onclick = ()=>{ toggleInd(el.dataset.k); el.querySelector('.chk').classList.toggle('on', !!S.ind[el.dataset.k]); };
}
const TOOLS = [
  ['_g','حالت و خطوط'],
  ['cursor','⌖','نشانگر — کلیک روی رسم: انتخاب و جابه‌جایی'],
  ['erase','⌫','پاک‌کن — کلیک روی هر رسم، حذف می‌شود'],
  ['trend','↗','خط روند'], ['hline','─','خط افقی'],
  ['hray','⟼','پرتو افقی'], ['vline','↕','خط عمودی'],
  ['_g','اشکال'],
  ['rect','▭','مستطیل'], ['fib','Ⓕ','فیبوناچی بازگشتی'],
  ['_g','اندازه‌گیری و پوزیشن'],
  ['measure','📏','خط‌کش (اندازه‌گیری)'],
  ['posL','🟢','پوزیشن خرید (ورود/ضرر/هدف)'], ['posS','🔴','پوزیشن فروش (ورود/ضرر/هدف)'],
  ['_g','هشدار'],
  ['alert','🔔','هشدار قیمتی — کلیک روی چارت در قیمت هدف؛ کلیک روی خط = حذف'],
  ['_g','یادداشت'],
  ['arrowU','⬆','فلش صعودی'], ['arrowD','⬇','فلش نزولی'],
  ['text','ℹ','متن'], ['brush','✎','قلم آزاد'],
];
function buildToolsMenu(){
  const m = document.getElementById('menuTools');
  let h='';
  for(const t of TOOLS){
    if(t[0]==='_g'){ h += '<div class="mgroup">'+t[1]+'</div>'; continue; }
    h += '<div class="mi'+(S.tool===t[0]?' sel':'')+'" data-t="'+t[0]+'"><span class="ti">'+t[1]+'</span><span>'+t[2]+'</span></div>';
  }
  h += '<div class="msep"></div>'
     + '<div class="mi" data-t="undo"><span class="ti">↩</span><span>واگرد آخرین</span></div>'
     + '<div class="mi" data-t="redo"><span class="ti">↪</span><span>ازنو (Redo)</span></div>'
     + '<div class="mi" data-t="clear"><span class="ti">🗑</span><span>پاک‌کردن همه</span></div>';
  m.innerHTML = h;
  for(const el of m.querySelectorAll('.mi'))
    el.onclick = ()=>{
      const t = el.dataset.t;
      if(t==='undo'){ doUndo(); }
      else if(t==='redo'){ doRedo(); }
      else if(t==='clear'){ clearAll(); }
      else { setTool(t); if(t==='erase') toast('روی رسم کلیک کن تا حذف شود — Esc برای خروج'); }
      buildToolsMenu(); closeMenus();
    };
}
function setTool(t){
  S.tool = t; pend=null; brush=null; measure=null; if(t!=='cursor') selIdx=-1;
  ovl.classList.toggle('armed', t!=='cursor');
  const btn = document.getElementById('btnTools');
  btn.classList.toggle('active', t!=='cursor');
  document.getElementById('txtIn').classList.toggle('show', t==='text');
}
function closeMenus(){
  for(const id of ['menuInd','menuTools','menuType','menuTf'])
    document.getElementById(id).classList.remove('open');
}
function openMenu(btnId, menuId, mw){
  const wrap = document.getElementById('wrap');
  const btn = document.getElementById(btnId), m = document.getElementById(menuId);
  const wr = wrap.getBoundingClientRect(), br = btn.getBoundingClientRect();
  m.style.left = Math.max(6, Math.min(br.left - wr.left, wr.width - (mw||232))) + 'px';
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
document.getElementById('btnTfAll').addEventListener('click', e=>{
  e.stopPropagation();
  const m = document.getElementById('menuTf');
  const was = m.classList.contains('open');
  closeMenus();
  if(!was){ buildTfMenu(); openMenu('btnTfAll','menuTf', 270); }
});
document.addEventListener('click', e=>{
  if(!e.target.closest('.menu') && !e.target.closest('#btnInd,#btnTools,#btnType,#btnTfAll')) closeMenus();
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
const btnLog = document.getElementById('btnLog');
function applyLog(){
  try{ chartMain.priceScale('right').applyOptions({ mode: S.ind.log?
    LightweightCharts.PriceScaleMode.Logarithmic : LightweightCharts.PriceScaleMode.Normal }); }catch(e){}
  btnLog.classList.toggle('active', !!S.ind.log);
}
btnLog.onclick = ()=>{ S.ind.log = !S.ind.log; saveInd(); applyLog(); };

/* ---------- نوار پایین به سبک تریدینگ‌ویو: رنج‌های سریع + SELL/BUY + ساعت زنده ------ */
const BRANGES = [['1D',86400],['5D',432000],['1M',2592000],['3M',7776000],['6M',15552000],['YTD','ytd'],['همه',0]];
(function buildBbar(){
  const el = document.getElementById('bbarRanges'); let h='';
  for(const r of BRANGES) h += '<button class="bb-r" data-s="'+r[1]+'">'+r[0]+'</button>';
  el.innerHTML = h;
  for(const b of el.querySelectorAll('.bb-r'))
    b.onclick = ()=> setRange(b.dataset.s==='ytd' ? 'ytd' : parseInt(b.dataset.s,10));
})();
function setRange(sec){
  const c = CAND(); const n = c.length; if(!n) return;
  let cnt;
  if(sec==='ytd'){
    const jan = Math.floor(Date.UTC(new Date().getUTCFullYear(),0,1)/1000);
    cnt = Math.min(n, Math.ceil((c[n-1][0]-jan)/SEC())+1);
  } else if(!sec){ cnt = n; }
  else cnt = Math.min(n, Math.ceil(sec/SEC()));
  chartMain.timeScale().setVisibleLogicalRange({from:Math.max(0,n-cnt-2), to:n+4});
}
document.getElementById('bbSell').onclick = ()=>{ setTool('posS'); toast('پوزیشن فروش: ۳ کلیک روی چارت — ورود، حد ضرر، هدف'); };
document.getElementById('bbBuy').onclick  = ()=>{ setTool('posL'); toast('پوزیشن خرید: ۳ کلیک روی چارت — ورود، حد ضرر، هدف'); };
function tickClock(){
  const el = document.getElementById('clock');
  if(el) el.textContent = new Date().toLocaleTimeString('en-GB',{timeZone:'Asia/Tehran',hour12:false});
}
setInterval(tickClock, 1000); tickClock();

/* ---------- لجند: روشن/خاموش ------------------------------------------ */
const btnLeg = document.getElementById('btnLeg');
function applyLeg(){
  document.getElementById('legend').style.display = (S.ind.leg===false)? 'none' : '';
  btnLeg.classList.toggle('active', S.ind.leg!==false);
}
btnLeg.onclick = ()=>{ S.ind.leg = (S.ind.leg===false)? true : false; saveInd(); applyLeg(); };

/* ---------- چیپ قیمت + شمارش معکوس کندل (سبک تریدینگ‌ویو) --------------- */
const cdown = document.getElementById('cdown');
cdown.onclick = ()=> chartMain.timeScale().scrollToRealTime();
function fmtRem(ms){ if(ms<=0) return '00:00';
  const s=Math.floor(ms/1000), d=Math.floor(s/86400), h=Math.floor(s%86400/3600),
        m=Math.floor(s%3600/60), ss=s%60;
  const p=n=>(n<10?'0':'')+n;
  if(d) return d+'d '+p(h)+':'+p(m);
  if(h) return h+':'+p(m)+':'+p(ss);
  return p(m)+':'+p(ss); }
setInterval(function(){
  const c=CAND(); if(!c.length || !mainSeries) return;
  const a=c[c.length-1];
  /* قیمت زنده‌ی موتور هشدار (اگر تیک تازه <۹۰ث) جلوی قیمت کهنه‌ی کندل دیده می‌شود */
  let px=a[4], liveNow=false;
  try{ const L=window.__nqLivePx;
    if(L && isFinite(L.v) && L.v>0 && (Date.now()-L.at)<90000){ px=L.v; liveNow=true; } }catch(e){}
  const cls = px>=a[1] ? '#26a69a' : '#ef5350';
  const pc = c.length>1? c[c.length-2][4] : a[1];
  const chg = pc? ((px-pc)/pc*100):0;
  const rem = (a[0]+SEC())*1000 - Date.now();
  cdown.innerHTML = '<span style="color:'+cls+'">'+fmtP(px)+' '+(chg>=0?'+':'')+chg.toFixed(2)+'%'
                  + '</span><span style="color:#f59e0b">⏱ '+fmtRem(rem)+(liveNow?' <span style="color:#26a69a">●</span>':'')+'</span>';
}, 500);

/* ---------- منوی نوع چارت -------------------------------------------- */
(function(){
  const m = document.getElementById('menuType');
  let h='';
  for(const k of ['candles','hollow','bars','line','linemk','step','area','baseline','heikin'])
    h += '<div class="mi'+(S.type===k?' sel':'')+'" data-y="'+k+'"><span>'+TYPE_LBL[k]+'</span></div>';
  m.innerHTML = h;
  for(const el of m.querySelectorAll('.mi')) el.onclick = ()=>setType(el.dataset.y);
})();

/* ---------- شروع ------------------------------------------------------ */
buildTfBtns();
updTfBtn();
buildIndMenu();
buildToolsMenu();
document.getElementById('typeLbl').textContent = TYPE_LBL[S.type]||S.type;
setTool('cursor');
DRAWINGS = loadDraw().map(normDraw);
buildIdx();
rebuildMain(false);
rebuildAllPanes();
updateTitle();
(function(){ const c=CAND(); const a=c[c.length-1];
  if(a){ setLegend({t:a[0],o:a[1],h:a[2],l:a[3],c:a[4],v:a[5]}); setIndLegend(a[0]); updatePaneLegends(a[0]); } })();
applyPanes();
applyLog();
applyLeg();
(function(){ const c=CAND(); const n=c.length;
  const win = Math.min(DATA.initial_bars, n);
  chartMain.timeScale().setVisibleLogicalRange({ from: Math.max(0, n-win-2), to: n+4 }); })();
sizeOvl();
if(WANT_SECS) loadSeconds(WANT_SECS).then(ok=>{ if(ok && TFS[WANT_SECS]) setTF(WANT_SECS); });
requestAnimationFrame(renderLoop);
"""

# ------------------------------------------------------------------ همگام‌سازی ابری رسم‌ها
_SYNC_JS = """
/* ---------- همگام‌سازی ابری رسم‌ها (Supabase) — آخرین نسخه برنده است ---------- */
(function(){
  const SCFG = __SYNC_CFG__;
  if(!SCFG || !SCFG.url || !SCFG.key) return;
  const chip = document.getElementById('btnSync');
  const TABLE_URL = String(SCFG.url).replace(/\\/$/,'') + '/rest/v1/chart_drawings';
  const MAX_DRAWS = 400;
  const devId = (function(){ try{ let d=localStorage.getItem('nqtv:device');
    if(!d){ d='dev-'+Math.random().toString(36).slice(2,10); localStorage.setItem('nqtv:device',d); } return d; }
    catch(e){ return 'dev-anon'; } })();
  let dirty=false, pushTimer=null, pushAgain=false, inFlight=false, syncSeq=0;
  const scopeOf  = ()=> (String(DATA.symbol||'')+':'+S.tf).toUpperCase().replace(/\\s+/g,'_');
  const stampKey = ()=> SK('dsync:'+S.tf);
  function stampGet(){ try{ return localStorage.getItem(stampKey()); }catch(e){ return null; } }
  function stampSet(v){ try{ if(v) localStorage.setItem(stampKey(), v); }catch(e){} }
  function setChip(cls, tip){ if(!chip) return; chip.className='tb-btn '+cls; if(tip) chip.title=tip; }
  function hdrs(extra){ return Object.assign({'Content-Type':'application/json',
    'apikey':SCFG.key, 'Authorization':'Bearer '+SCFG.key}, extra||{}); }
  function fetchTO(url, opt){ const ctl=new AbortController(); const t=setTimeout(()=>ctl.abort(), 6000);
    return fetch(url, Object.assign({}, opt||{}, {signal:ctl.signal})).finally(()=>clearTimeout(t)); }

  async function cloudGet(scope){
    const u = TABLE_URL + '?scope=eq.' + encodeURIComponent(scope) + '&select=scope,drawings,updated_at,updated_by';
    const r = await fetchTO(u, {headers: hdrs()});
    if(!r.ok) throw new Error('HTTP '+r.status);
    const rows = await r.json();
    return (rows && rows[0]) || null;
  }
  async function cloudPut(scope, drawings){
    const body = [{scope:scope, symbol:String(DATA.symbol||''), timeframe:S.tf,
                   drawings:drawings, updated_by:devId}];
    const r = await fetchTO(TABLE_URL, {method:'POST',
      headers:hdrs({'Prefer':'resolution=merge-duplicates,return=representation'}),
      body:JSON.stringify(body)});
    if(!r.ok) throw new Error('HTTP '+r.status);
    const rows = await r.json();
    return (rows && rows[0] && rows[0].updated_at) || null;
  }
  function pushNow(){
    if(inFlight){ pushAgain=true; return Promise.resolve(); }
    inFlight=true; const mySeq=++syncSeq;
    setChip('busy','در حال بارگذاری رسم‌ها به کلود…');
    return cloudPut(scopeOf(), DRAWINGS.slice(0,MAX_DRAWS)).then(ts=>{
      inFlight=false; if(mySeq!==syncSeq) return;
      dirty=false; stampSet(ts);
      setChip('ok','همگام ✓ — کلیک = بارگذاری اجباری رسم‌های محلی');
      if(pushAgain){ pushAgain=false; queuePush(); }
    }).catch(err=>{
      inFlight=false; if(mySeq!==syncSeq) return;
      setChip('err','خطای همگام‌سازی: '+String(err&&err.message||err)+' — کلیک = تلاش دوباره');
    });
  }
  function queuePush(){
    dirty=true; clearTimeout(pushTimer);
    pushTimer=setTimeout(()=>{ pushTimer=null; pushNow(); }, 1200);
    setChip('busy','تغییرات در انتظار همگام‌سازی…');
  }
  async function reconcile(){
    const scope=scopeOf(); const mySeq=++syncSeq;
    clearTimeout(pushTimer); pushTimer=null;
    setChip('busy','بررسی نسخه‌ی ابری…');
    let row=null;
    try{ row = await cloudGet(scope); }
    catch(err){ if(mySeq===syncSeq) setChip('err','خطای همگام‌سازی: '+String(err&&err.message||err)+' — کلیک = تلاش دوباره'); return; }
    if(mySeq!==syncSeq) return;
    const cloudTs  = row? (row.updated_at||null) : null;
    const cloudArr = (row && Array.isArray(row.drawings))? row.drawings : null;
    if(dirty){ await pushNow(); return; }                        /* ۱) اول آپلود محلی */
    if(!row || !cloudArr || cloudArr.length===0){                 /* ۲) کلود خالی */
      if(DRAWINGS.length>0){ await pushNow(); return; }           /*    محلی کار دارد → ببر بالا */
      stampSet(cloudTs || new Date().toISOString());
      setChip('ok','همگام ✓ — بدون رسم'); return;
    }
    const st = stampGet();
    if(st && cloudTs===st){ setChip('ok','همگام ✓ — کلیک = بارگذاری اجباری'); return; }  /* ۳) همان نسخه */
    if(DRAWINGS.length>0 && !st){ await pushNow(); return; }      /* ۴) دستگاه جدید + محلی کار دارد → محلی اولویت */
    DRAWINGS = cloudArr.map(normDraw).slice(0,MAX_DRAWS);          /* ۵) کلود جدیدتر → بارگذاری */
    try{ localStorage.setItem(SK('draw:'+S.tf), JSON.stringify(DRAWINGS)); }catch(e){}
    UNDOS=[]; REDOS=[]; selIdx=-1; drag=null;
    buildIdx(); sizeOvl();
    stampSet(cloudTs); dirty=false;
    setChip('ok','همگام ✓ — از کلود بارگذاری شد');
    toast('☁ رسم‌ها از کلود بارگذاری شد ('+DRAWINGS.length+' رسم)');
  }
  if(chip){
    chip.className='tb-btn';
    chip.onclick = ()=>{ dirty=true; clearTimeout(pushTimer); pushNow(); };
  }
  window.__nqSyncQueue = queuePush;
  window.__nqSyncReconcile = reconcile;
  reconcile();
})();
"""


# ------------------------------------------------------------------ هشدار قیمتی روی چارت
_ALERT_JS = """
/* ---------- هشدار قیمتی (🔔) — ذخیره محلی + سینک کلود + تریگر زنده ----------
   • ابزار «هشدار» یا دکمه‌ی 🔔 → کلیک روی چارت در قیمت هدف → خط نارنجی چین‌چین
   • کلیک روی خط هشدار (یا دابل‌کلیک) = حذف
   • تریگر زنده: کریپتو هر ۲۰ ثانیه قیمت زنده از ۴ منبع با مهلت (بایننس ×۲،
     کریپتوکمپیر، کوین‌گکو)؛ بقیه بازارها روی آخرین قیمت کندل + چکر سروری (Actions)
   • بدون کلید کلود هم کار می‌کند (فقط localStorage) */
(function(){
  const symKey  = ()=> (String(DATA.symbol||'')||'NQ').toUpperCase().replace(/\\s+/g,'_');
  const symDisp = ()=> String(DATA.symbol||'');
  const binSym  = ()=> symDisp().split('/')[0].split('-').join('').toUpperCase();
  const isCrypto= ()=> !DATA.fx && /^[A-Z0-9]{2,15}$/.test(binSym());
  function devId(){ try{ let d=localStorage.getItem('nqtv:device');
    if(!d){ d='dev-'+Math.random().toString(36).slice(2,10); localStorage.setItem('nqtv:device',d); } return d; }
    catch(e){ return 'dev-anon'; } }
  const AL_KEY = ()=> 'nqtv:al:'+symKey();
  function loadAl(){ const v=safeParse(localStorage.getItem(AL_KEY())); return Array.isArray(v)? v.filter(a=>a && isFinite(parseFloat(a.price))) : []; }
  function saveLocalOnly(){ try{ localStorage.setItem(AL_KEY(), JSON.stringify(ALERTS)); }catch(e){} }
  function saveAlerts(){ saveLocalOnly(); if(window.__alSyncQueue) window.__alSyncQueue(); }

  let ALERTS = loadAl().slice(0,100);

  function activeN(){ let n=0; for(const a of ALERTS) if(a.active) n++; return n; }
  function updateBadge(){ const b=document.getElementById('btnAlert'); if(!b) return;
    const n=activeN();
    b.textContent = n? ('🔔'+n) : '🔔';
    b.title = n? ('هشدارهای فعال: '+n+' — برای افزودن از منوی ابزارها') : 'هشدار قیمتی — از منوی ابزارها؛ کلیک روی خط = حذف'; }
  function beep(){ try{
    const AC = window.AudioContext || window.webkitAudioContext; if(!AC) return;
    const ac = beep._ac || (beep._ac = new AC());
    const o=ac.createOscillator(), g=ac.createGain();
    o.type='sine'; o.frequency.value=880; g.gain.value=0.07;
    o.connect(g); g.connect(ac.destination);
    o.start(); o.frequency.setValueAtTime(1320, ac.currentTime+0.12);
    o.stop(ac.currentTime+0.26);
  }catch(e){} }

  function addAlert(price){
    price = parseFloat(price); if(!isFinite(price) || price<=0) return;
    const near = ALERTS.find(a=>a.active && Math.abs(parseFloat(a.price)-price)/price < 0.001);
    if(near){ toast('هشدار مشابه در '+fmtP(near.price)+' از قبل هست'); return; }
    const px0 = lastClosePrice();
    const a = { id:'al:'+symKey()+':'+price+':'+Date.now(),
                price:price, dir:(px0!=null && price<px0)? 'below':'above',
                active:true, created_at:new Date().toISOString(), by:devId() };
    ALERTS.push(a);
    if(ALERTS.length>100) ALERTS = ALERTS.slice(-100);
    updateBadge(); saveAlerts();
    toast('🔔 هشدار ثبت شد '+(a.dir==='above'?'⬆ بالای ':'⬇ زیر ')+fmtP(price)+(isCrypto()? ' — هنگام رسیدن قیمت مطلع می‌شوی':''));
  }
  function removeAlert(i){ if(i<0 || i>=ALERTS.length) return;
    const a=ALERTS.splice(i,1)[0];
    updateBadge(); saveAlerts();
    toast('🔔 هشدار '+fmtP(a.price)+' حذف شد'); }
  function alertHit(x,y){
    for(let i=ALERTS.length-1; i>=0; i--){
      const a=ALERTS[i]; if(!a.active) continue;
      const yy=yOf(a.price); if(yy==null) continue;
      if(Math.abs(y-yy)<=10) return i;
    }
    return -1;
  }

  window.__nqDrawAlerts = function(){
    if(!ALERTS.length || !mainSeries) return;
    const w = mainPane.getBoundingClientRect().width;
    octx.save();
    for(const a of ALERTS){
      if(!a.active) continue;
      const y = yOf(a.price); if(y==null || y<-20) continue;
      octx.beginPath(); octx.setLineDash([7,5]); octx.lineWidth=1.4; octx.strokeStyle='#f59e0b';
      octx.moveTo(0,y); octx.lineTo(w,y); octx.stroke();
      octx.setLineDash([]);
      const lbl='🔔 '+fmtP(a.price);
      octx.font='700 10px ui-monospace,monospace';
      const tw=octx.measureText(lbl).width;
      const bx=w-tw-24, by=y-9;
      octx.fillStyle='rgba(245,158,11,0.95)';
      if(octx.roundRect){ octx.beginPath(); octx.roundRect(bx,by,tw+20,17,4); octx.fill(); }
      else octx.fillRect(bx,by,tw+20,17);
      octx.fillStyle='#131722'; octx.textBaseline='middle';
      octx.fillText(lbl, bx+9, by+9);
    }
    octx.restore();
  };

  /* ---------- تریگر ---------- */
  function lastClosePrice(){ try{ const c=CAND(); return (c && c.length)? c[c.length-1][4] : null; }catch(e){ return null; } }
  /* ضد «گیر کردن»: هر منبع قیمت مهلت ۵ ثانیه‌ای دارد — قبلاً fetch بی‌مهلت بود و
     از شبکه‌هایی که بایننس را فیلتر می‌کنند، اتصال معلق می‌ماند و کل چکِ هشدار
     تا ابد قفل می‌شد (checking هرگز آزاد نمی‌شد). اگر بایننس در دسترس نبود،
     جمع‌کننده‌های عمومی (کریپتوکمپیر/کوین‌گکو) که از شبکه‌های محدود هم معمولاً
     باز می‌شوند امتحان می‌شوند؛ هیچ‌کدام هم نیامد → آخرین کندل چارت. */
  function fetchTOms(url, ms){ const ctl=new AbortController();
    const t=setTimeout(()=>ctl.abort(), ms||5000);
    return fetch(url, {signal:ctl.signal}).finally(()=>clearTimeout(t)); }
  const CG_IDS = { BTC:'bitcoin', ETH:'ethereum', SOL:'solana', XRP:'ripple',
    BNB:'binancecoin', DOGE:'dogecoin', ADA:'cardano', TRX:'tron',
    TON:'the-open-network', AVAX:'avalanche-2', LINK:'chainlink',
    DOT:'polkadot', LTC:'litecoin', MATIC:'matic-network', SHIB:'shiba-inu' };
  async function livePrice(){
    if(!isCrypto()) return null;
    const sym = binSym();
    const base = symDisp().split('/')[0].split('-')[0].trim().toUpperCase();
    const hosts = [
      ['https://data-api.binance.vision/api/v3/ticker/price?symbol='+sym, j=>parseFloat(j&&j.price)],
      ['https://api.binance.com/api/v3/ticker/price?symbol='+sym,         j=>parseFloat(j&&j.price)],
      ['https://min-api.cryptocompare.com/data/price?fsym='+base+'&tsyms=USDT,USD',
        j=>{ const v = j && (j.USDT!=null? j.USDT : j.USD); return parseFloat(v); }]
    ];
    const cg = CG_IDS[base];
    if(cg) hosts.push(['https://api.coingecko.com/api/v3/simple/price?ids='+cg+'&vs_currencies=usd',
      j=> (j && j[cg])? parseFloat(j[cg].usd) : NaN]);
    for(const h of hosts){
      try{
        const r = await fetchTOms(h[0], 5000);
        if(!r.ok) continue;
        const v = h[1](await r.json());
        if(isFinite(v) && v>0){
          try{ window.__nqLivePx = {v:v, at:Date.now()}; }catch(e){}
          return v;
        }
      }catch(e){}
    }
    return null;
  }
  let checking=false;
  async function checkAlerts(){
    if(checking) return; checking=true;
    try{
      if(!ALERTS.some(a=>a.active)) return;
      /* خط امانی ۹ ثانیه‌ای: هر چه شد چک تمام می‌شود — قفل checking تا ابد نمی‌ماند */
      const live = await Promise.race([livePrice(),
        new Promise(r=>setTimeout(()=>r(null), 9000))]);
      const px = (live!=null)? live : lastClosePrice();
      if(px==null) return;
      const nowIso = new Date().toISOString();
      let hits=0;
      for(const a of ALERTS){
        if(!a.active) continue;
        const ap = parseFloat(a.price); if(!isFinite(ap)) continue;
        const hit = (a.dir==='below')? (px<=ap) : (px>=ap);
        if(hit){ a.active=false; a.triggered_at=nowIso; a.trigger_price=px; hits++;
          toast('🔔 هشدار: '+symDisp()+' '+(a.dir==='below'?'به زیر ':'به بالای ')+fmtP(ap)+' رسید — قیمت: '+fmtP(px)); }
      }
      if(hits){ beep(); updateBadge(); saveAlerts(); }
    }finally{ checking=false; }
  }
  setInterval(checkAlerts, 20000);
  setTimeout(checkAlerts, 1500);

  const btnA = document.getElementById('btnAlert');
  if(btnA) btnA.onclick = ()=>{ setTool('alert'); toast('هشدار قیمتی: روی چارت در قیمت هدف کلیک کن — Esc برای خروج'); };
  updateBadge();
  window.__nqAlertApi = { addAlert:addAlert, removeAlert:removeAlert, alertHit:alertHit,
                          checkAlerts:checkAlerts, list:()=>ALERTS };

  /* ---------- همگام‌سازی ابری هشدارها (Supabase — اختیاری) ---------- */
  (function(){
    const CFG = __ALERT_SYNC_CFG__;
    if(!CFG || !CFG.url || !CFG.key) return;
    const TURL = String(CFG.url).replace(/\\/$/,'') + '/rest/v1/price_alerts';
    const dev = devId();
    let dirty=false, t=null, again=false, busy=false, seq=0;
    const stampKey = ()=> 'nqtv:alsync:'+symKey();
    function hdrs(extra){ return Object.assign({'Content-Type':'application/json',
      'apikey':CFG.key, 'Authorization':'Bearer '+CFG.key}, extra||{}); }
    function fetchTO(url, opt){ const ctl=new AbortController(); const to=setTimeout(()=>ctl.abort(), 6000);
      return fetch(url, Object.assign({}, opt||{}, {signal:ctl.signal})).finally(()=>clearTimeout(to)); }
    async function cGet(){ const u=TURL+'?scope=eq.'+encodeURIComponent(symKey())+'&select=scope,alerts,updated_at,updated_by';
      const r=await fetchTO(u,{headers:hdrs()}); if(!r.ok) throw new Error('HTTP '+r.status);
      const rows=await r.json(); return (rows&&rows[0])||null; }
    async function cPut(list){ const body=[{scope:symKey(), alerts:list, updated_by:dev}];
      const r=await fetchTO(TURL,{method:'POST',headers:hdrs({'Prefer':'resolution=merge-duplicates,return=representation'}),
        body:JSON.stringify(body)});
      if(!r.ok) throw new Error('HTTP '+r.status);
      const rows=await r.json();
      return (rows&&rows[0]&&rows[0].updated_at)||null; }
    function pushNow(){ if(busy){ again=true; return Promise.resolve(); }
      busy=true; const my=++seq;
      return cPut(ALERTS.slice(0,100)).then(ts=>{ busy=false; if(my!==seq) return;
        dirty=false; try{ if(ts) localStorage.setItem(stampKey(), ts); }catch(e){}
        if(again){ again=false; queuePush(); } })
      .catch(()=>{ busy=false; }); }
    function queuePush(){ dirty=true; clearTimeout(t); t=setTimeout(()=>{ t=null; pushNow(); }, 1200); }
    async function reconcile(){
      const my=++seq; clearTimeout(t); t=null;
      let row=null;
      try{ row=await cGet(); }catch(e){ return; }
      if(my!==seq) return;
      const cloudTs = row? (row.updated_at||null) : null;
      const cloudArr = (row && Array.isArray(row.alerts))? row.alerts : null;
      if(dirty){ await pushNow(); return; }                          /* ۱) اول آپلود محلی */
      if(!row || !cloudArr || !cloudArr.length){                     /* ۲) کلود خالی */
        if(ALERTS.length>0){ await pushNow(); return; }
        try{ localStorage.setItem(stampKey(), cloudTs || new Date().toISOString()); }catch(e){}
        return; }
      let st=null; try{ st=localStorage.getItem(stampKey()); }catch(e){}
      if(st && cloudTs===st) return;                                 /* ۳) همان نسخه */
      if(ALERTS.length>0 && !st){ await pushNow(); return; }         /* ۴) دستگاه جدید + محلی کار دارد */
      ALERTS = cloudArr.slice(0,100);                                /* ۵) کلود جدیدتر → بارگذاری */
      saveLocalOnly(); updateBadge();
      try{ localStorage.setItem(stampKey(), cloudTs); }catch(e){}
      dirty=false;
      const n=activeN();
      if(n) toast('🔔 '+n+' هشدار فعال از کلود بارگذاری شد');
    }
    window.__alSyncQueue = queuePush;
    window.__alSyncReconcile = reconcile;
    reconcile();
  })();
})();
"""

def _sync_cfg() -> Optional[Dict[str, str]]:
    """تنظیمات اتصال Supabase برای همگام‌سازی رسم‌ها — None یعنی خاموش.

    ترتیب: متغیر محیطی (لوکال/CI) → st.secrets (کلاد). هیچ خطایی به بیرون
    نشت نمی‌کند؛ در نبود کلیدها چارت دقیقاً مثل قبل آفلاین کار می‌کند.
    """
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_KEY", "").strip()
    if not (url and key):
        try:
            import streamlit as st  # type: ignore
            url = str(st.secrets.get("SUPABASE_URL", "") or "").strip()
            key = str(st.secrets.get("SUPABASE_KEY", "") or "").strip()
        except Exception:
            pass
    return {"url": url, "key": key} if (url and key) else None

_CSS = """
html,body{margin:0;padding:0;background:#0e1117;height:100%;overflow:hidden;}
#wrap{position:relative;width:100%;height:100%;direction:ltr;background:#0e1117;display:flex;flex-direction:column;}
#toolbar{height:30px;min-height:30px;display:flex;align-items:center;gap:3px;padding:0 6px;
  background:#131722;border-bottom:1px solid rgba(148,163,184,0.14);direction:rtl;
  overflow-x:auto;overflow-y:hidden;scrollbar-width:none;}
#toolbar::-webkit-scrollbar{display:none;}
.tb-btn{all:unset;cursor:pointer;font:600 11px/1 ui-monospace,monospace;color:#b2b5be;
  background:transparent;border-radius:6px;padding:5px 7px;white-space:nowrap;user-select:none;}
.tb-btn:hover{background:rgba(148,163,184,0.12);color:#e2e8f0;}
.tb-btn.active{color:#5b8def;background:rgba(41,98,255,0.16);}
.tf{min-width:30px;text-align:center;}
.tb-sep{width:1px;height:18px;background:rgba(148,163,184,0.22);flex:none;}
.tb-spacer{flex:1;}
#txtIn{display:none;background:#0e1117;border:1px solid rgba(148,163,184,0.35);border-radius:6px;
  color:#e2e8f0;font:11.5px Tahoma,sans-serif;padding:5px 8px;width:132px;direction:rtl;flex:none;}
#txtIn.show{display:inline-block;}
#txtIn::placeholder{color:#78849e;}
#panes{flex:1;position:relative;display:flex;flex-direction:column;min-height:0;}
#mainPane{flex:1;position:relative;min-height:110px;}
#chart{position:absolute;inset:0;}
.subpane{position:relative;border-top:1px solid rgba(148,163,184,0.14);display:none;background:#0e1117;}
.subpane .pch{position:absolute;inset:0;}
.sublegend{position:absolute;top:2px;right:8px;z-index:7;pointer-events:none;direction:rtl;
  font:600 9.5px/1.5 ui-monospace,monospace;color:#8ea1c0;}
.sublegend b{color:#cfd6e4;}
#ovl{position:absolute;inset:0;z-index:5;pointer-events:none;}
#ovl.armed{pointer-events:auto;cursor:crosshair;touch-action:none;}
#legend{position:absolute;top:4px;left:6px;z-index:6;pointer-events:none;direction:ltr;
  font:10px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace;color:#b2b5be;
  background:rgba(14,17,23,0.82);padding:2px 7px;border-radius:6px;
  border:1px solid rgba(148,163,184,0.12);max-width:calc(100% - 96px);}
#ltitle{color:#e2e8f0;font-weight:700;margin-right:6px;}
#lbar .k{color:#78849e;margin:0 3px 0 8px;}
#lbar b{font-weight:600;color:#e2e8f0;}
#lbar b.up{color:#26a69a;} #lbar b.dn{color:#ef5350;}
#lbar .kt{color:#78849e;margin-left:10px;}
#lind{display:flex;gap:10px;flex-wrap:wrap;}
#lind .ik{font-weight:600;}
#cdown{position:absolute;right:0;bottom:26px;z-index:8;pointer-events:auto;cursor:pointer;
  direction:ltr;display:flex;gap:9px;align-items:center;background:rgba(31,42,61,0.95);
  border:1px solid rgba(148,163,184,0.3);border-right:none;border-radius:8px 0 0 8px;
  padding:4px 10px;font:700 11px/1.2 ui-monospace,monospace;color:#e2e8f0;}
#cdown:hover{background:rgba(41,98,255,0.35);}
.menu{position:absolute;top:34px;left:8px;z-index:40;background:#1c2333;
  border:1px solid rgba(148,163,184,0.2);border-radius:10px;padding:6px;display:none;
  min-width:220px;box-shadow:0 10px 28px rgba(0,0,0,0.5);direction:rtl;max-height:72%;overflow-y:auto;}
.menu.open{display:block;}
.mgroup{font:600 10px/1.6 Tahoma,sans-serif;color:#78849e;padding:7px 9px 2px;letter-spacing:0.3px;}
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
#bbar{height:24px;min-height:24px;display:flex;align-items:center;justify-content:space-between;gap:8px;
  background:#131722;border-top:1px solid rgba(148,163,184,0.14);padding:0 8px;direction:ltr;overflow:hidden;}
#bbarRanges{display:flex;gap:1px;overflow-x:auto;scrollbar-width:none;flex:1;min-width:0;}
#bbarRanges::-webkit-scrollbar{display:none;}
.bb-r{all:unset;cursor:pointer;font:700 10px/1 ui-monospace,monospace;color:#8ea1c0;
  padding:4px 7px;border-radius:5px;white-space:nowrap;}
.bb-r:hover{background:rgba(148,163,184,0.12);color:#e2e8f0;}
#bbarRight{display:flex;align-items:center;gap:7px;flex:none;}
#clock{font:700 10.5px/1 ui-monospace,monospace;color:#e2e8f0;letter-spacing:0.4px;}
#tzt{font:600 9px/1 ui-monospace,monospace;color:#78849e;}
.bb-sell,.bb-buy{all:unset;cursor:pointer;font:800 9.5px/1 ui-monospace,monospace;color:#fff;
  padding:4px 9px;border-radius:5px;letter-spacing:0.5px;}
.bb-sell{background:#ef5350;} .bb-sell:hover{background:#ff6b66;}
.bb-buy{background:#26a69a;} .bb-buy:hover{background:#31c2b4;}
#menuTf{min-width:270px;}
.tfmi .tfl{font:700 11px/1 ui-monospace,monospace;min-width:36px;color:#e2e8f0;}
.tfmi .lzi{color:#f59e0b;font-size:10px;font-weight:700;}
a[href*="tradingview.com"]{opacity:0.28; filter:grayscale(1);}
a[href*="tradingview.com"]:hover{opacity:0.7;}
#btnSync{font-size:12.5px;line-height:1;}
#btnSync.busy{color:#f59e0b;}
#btnSync.ok{color:#26a69a;}
#btnSync.err{color:#ef5350;}
#btnAlert{font-size:12.5px;line-height:1;}
#selX{position:absolute;z-index:9;display:none;width:22px;height:22px;padding:0;
  text-align:center;border-radius:50%;border:1px solid rgba(239,83,80,0.75);cursor:pointer;
  background:rgba(239,83,80,0.92);color:#fff;font:700 12px/20px Tahoma,sans-serif;
  box-shadow:0 2px 8px rgba(0,0,0,0.45);user-select:none;}
#selX:hover{background:#ff6b66;}
@media (max-width:700px){ .tb-label{display:none;} .menu{min-width:190px;} #tzt{display:none;}
  .bb-sell,.bb-buy{padding:3px 6px;} #clock{font-size:10px;} }
"""


def build_tv_chart_html(*, candles: List[List[Any]], tfs: Dict[str, List[List[Any]]],
                        base_tf: str, symbol: str, zones: List[Dict[str, Any]],
                        levels: List[Dict[str, Any]], title: str, dec: int,
                        initial_bars: int = 160, fx: bool = False,
                        sync: Any = "auto") -> str:
    """HTML خودکفای چارت TV کامل.
    candles:  [t_s, o, h, l, c, v]  (t ثانیه · NaN قبلاً None شده)
    tfs:      {tf_key: candles} — تا ۲۶ تایم‌فریم برای سوئیچر (بومی + تجمیعی سرور، ثانیه‌ای مرورگر)
    zones:    {t0,top,bottom,kind,tag} — فقط برای تایم‌فریم پایه
    levels:   {price,name,color,dash} — فقط برای تایم‌فریم پایه
    fx:       True = نماد فارکس — گروه «ثانیه‌های Binance» از منو حذف و حجم پیش‌فرض خاموش می‌شود
    """
    if base_tf not in tfs:
        tfs = {base_tf: candles}
    # --- همگام‌سازی ابری رسم‌ها: sync="auto" (پیش‌فرض: env/secrets) | dict | None=خاموش ---
    if isinstance(sync, dict) and sync.get("url") and sync.get("key"):
        scfg: Optional[Dict[str, str]] = {"url": str(sync["url"]), "key": str(sync["key"])}
    elif sync == "auto":
        scfg = _sync_cfg()
    else:
        scfg = None
    sync_js = (_SYNC_JS.replace("__SYNC_CFG__", json.dumps(scfg, ensure_ascii=False))
               if scfg else "")
    alert_cfg = scfg   # همان کلیدها برای جدول price_alerts — None یعنی هشدار فقط محلی
    alert_js = _ALERT_JS.replace("__ALERT_SYNC_CFG__",
                                 json.dumps(alert_cfg, ensure_ascii=False))
    sync_chip = ('<button class="tb-btn" id="btnSync" '
                 'title="همگام‌سازی رسم‌ها با کلود — کلیک = بارگذاری اجباری">☁</button>'
                 if scfg else '')
    data = json.dumps({"candles": candles, "tfs": tfs, "base_tf": base_tf,
                       "symbol": symbol, "levels": levels, "dec": dec,
                       "title": title, "initial_bars": int(initial_bars),
                       "fx": bool(fx)},
                      ensure_ascii=False, allow_nan=False)
    zones_js = json.dumps(zones, ensure_ascii=False, allow_nan=False)
    js = (_MAIN_JS
          .replace("__DATA__", data)
          .replace("__ZONES__", zones_js)
          .replace("__ZONES_JS__", _ZONES_JS)
          + sync_js + alert_js)
    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<style>" + _CSS + "</style></head><body>"
        '<div id="wrap">'
        '<div id="toolbar">'
        '<button class="tb-btn tf" id="btnTfAll" title="همه‌ی بازه‌ها — سبک تریدینگ‌ویو">▾</button>'
        '<span class="tb-sep"></span>'
        '<div id="tfBtns" style="display:flex;gap:2px;"></div>'
        '<button class="tb-btn" id="btnType">🕯 <span class="tb-label" id="typeLbl">کندل</span> ▾</button>'
        '<button class="tb-btn" id="btnInd">ƒ<span class="tb-label"> اندیکاتورها</span> ▾</button>'
        '<button class="tb-btn" id="btnTools">📐<span class="tb-label"> ابزارها</span> ▾</button>'
        '<button class="tb-btn" id="btnLog" title="مقیاس لگاریتمی">log</button>'
        '<input id="txtIn" placeholder="متن یادداشت…">'
        '<div class="tb-spacer"></div>'
        + '<button class="tb-btn" id="btnAlert" title="هشدار قیمتی — از منوی ابزارها؛ کلیک روی خط = حذف">🔔</button>'
        + sync_chip +
        '<button class="tb-btn" id="btnLeg" title="لجند">ℹ</button>'
        '<button class="tb-btn" id="btnFit" title="بازنشانی نما">⤢</button>'
        '<button class="tb-btn" id="btnNow" title="پرش به کندل آخر">▶▏</button>'
        '<button class="tb-btn" id="btnFull" title="تمام‌صفحه">⛶</button>'
        '<button class="tb-btn" id="btnShot" title="دانلود اسکرین‌شات PNG">📷</button>'
        '</div>'
        '<div id="panes">'
        '<div id="mainPane">'
        '<div id="chart"></div>'
        '<canvas id="ovl"></canvas>'
        '<button id="selX" title="حذف این رسم">✕</button>'
        '<div id="legend"><span id="ltitle"></span><span id="lbar"></span><div id="lind"></div></div>'
        '<div id="cdown"></div>'
        '</div>'
        '</div>'
        '<div id="bbar" dir="ltr">'
        '<div id="bbarRanges"></div>'
        '<div id="bbarRight">'
        '<button class="bb-sell" id="bbSell" title="شروع ابزار پوزیشن فروش (۳ کلیک)">SELL</button>'
        '<button class="bb-buy" id="bbBuy" title="شروع ابزار پوزیشن خرید (۳ کلیک)">BUY</button>'
        '<span id="clock">--:--:--</span><span id="tzt">UTC+3:30</span>'
        '</div>'
        '</div>'
        '<div class="menu" id="menuInd"></div>'
        '<div class="menu" id="menuTools"></div>'
        '<div class="menu" id="menuType"></div>'
        '<div class="menu" id="menuTf"></div>'
        '<div id="toast"></div>'
        '</div>'
        "<script>" + _lib() + "</script>"
        "<script>" + js + "</script></body></html>"
    )
    return html
