# -*- coding: utf-8 -*-
"""core/tv_chart.py — چارت موتور TradingView برای داشبورد (lightweight-charts v4)
==================================================================================
چرا این؟ چارت قبلی Plotly بود و زوم/درگ/کراس‌هیرش برای کار سخت بود. این ماژول
همان موتور متن‌باز خودِ TradingView (lightweight-charts) را به‌صورت self-contained
داخل iframe رندر می‌کند:

  • پن/زوم روان با درگ و اسکرول‌ویل (حس واقعی تریدینگ‌ویو)
  • کراس‌هیر + لجند OHLCV زنده (بالا-چپ، مثل TV)
  • محور قیمت راست، محور زمان پایین، ساعت محلی مرورگر
  • کندل + حجم (هیستوگرام هم‌پوشان پایین چارت مثل TV)
  • EMA20/EMA50 + بولینگر (خطوط ظریف)
  • خطوط ورود/حد ضرر/اهداف — پین‌شده به محور راست (createPriceLine)
  • نواحی FVG/BVG — مستطیل نیمه‌شفاف روی canvas هم‌پوشان (هر فریم بازترسیم)
  • دکمه‌ها: بازنشانی نما · پرش به «الان» · دانلود اسکرین‌شات PNG

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
const ZONES = __ZONES__;
const TIMES = CAND.map(a => a[0]);          // ثانیه — برای مکان‌یابی منطقی نواحی
function logicalForTime(sec){
  let lo=0, hi=TIMES.length-1, best=null;
  while(lo<=hi){ const mid=(lo+hi)>>1;
    if(TIMES[mid]<=sec){ best=mid; lo=mid+1; } else hi=mid-1; }
  return best;
}
const zc = document.getElementById('zones');
const zctx = zc.getContext('2d');
function sizeZoneCanvas(){
  const r = wrap.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  zc.width = Math.round(r.width*dpr); zc.height = Math.round(r.height*dpr);
  zc.style.width = r.width+'px'; zc.style.height = r.height+'px';
  zctx.setTransform(dpr,0,0,dpr,0,0);
}
const ZCOL = { bull:'38,166,154', bear:'239,83,80', bvg:'168,85,247' };
function drawZones(){
  const r = wrap.getBoundingClientRect();
  zctx.clearRect(0,0,r.width,r.height);
  if(!ZONES.length) return;
  const ts = chart.timeScale();
  const w = ts.width();
  const range = ts.getVisibleLogicalRange();
  for(const z of ZONES){
    const yTop = candleSeries.priceToCoordinate(z.top);
    const yBot = candleSeries.priceToCoordinate(z.bottom);
    if(yTop==null || yBot==null) continue;
    let x0 = 0;
    if(range){
      const li = logicalForTime(z.t0);
      if(li!=null && li>range.from){
        const c0 = ts.logicalToCoordinate(Math.min(li, range.to));
        if(c0!=null) x0 = Math.max(0, Math.min(c0, w));
      }
    }
    const col = ZCOL[z.kind] || '148,163,184';
    const y0 = Math.min(yTop,yBot), h0 = Math.abs(yBot-yTop);
    zctx.fillStyle = 'rgba('+col+',0.12)';
    zctx.fillRect(x0, y0, w-x0, h0);
    zctx.strokeStyle = 'rgba('+col+',0.55)';
    zctx.lineWidth = 1;
    zctx.strokeRect(x0+0.5, y0+0.5, w-x0-1, h0-1);
    zctx.fillStyle = 'rgba('+col+',0.95)';
    zctx.font = '600 10px ui-monospace, monospace';
    zctx.fillText(z.tag, x0+5, y0+12);
  }
}
"""

_MAIN_JS = """
const DATA = __DATA__;
const CAND = DATA.candles;                  // [t(s),o,h,l,c,v,e20,e50,bbu,bbl]
const LEVELS = DATA.levels;
const DEC = DATA.dec;
const wrap = document.getElementById('wrap');
const fmtP = v => v==null ? '—' : Number(v).toLocaleString('en-US',{minimumFractionDigits:DEC, maximumFractionDigits:DEC});
function fmtV(v){
  if(v==null) return '—';
  if(v>=1e9) return (v/1e9).toFixed(2)+'B';
  if(v>=1e6) return (v/1e6).toFixed(2)+'M';
  if(v>=1e3) return (v/1e3).toFixed(2)+'K';
  return v.toFixed(2);
}
const chart = LightweightCharts.createChart(document.getElementById('chart'), {
  autoSize: true,
  layout: {
    background: { type:'solid', color:'#0e1117' },
    textColor: '#b2b5be',
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
    fontSize: 11,
  },
  grid: {
    vertLines: { color:'rgba(148,163,184,0.07)' },
    horzLines: { color:'rgba(148,163,184,0.07)' },
  },
  rightPriceScale: {
    borderColor: 'rgba(148,163,184,0.18)',
    scaleMargins: { top:0.07, bottom:0.24 },
    entireTextOnly: true,
  },
  timeScale: {
    borderColor: 'rgba(148,163,184,0.18)',
    timeVisible: true, secondsVisible: false,
    rightOffset: 4,
  },
  crosshair: {
    mode: LightweightCharts.CrosshairMode.Normal,
    vertLine: { color:'rgba(148,163,184,0.45)', width:1, style:3, labelBackgroundColor:'#1f2a3d' },
    horzLine: { color:'rgba(148,163,184,0.45)', width:1, style:3, labelBackgroundColor:'#1f2a3d' },
  },
  localization: { priceFormatter: p => fmtP(p) },
});

const candleSeries = chart.addCandlestickSeries({
  upColor:'#26a69a', downColor:'#ef5350',
  borderUpColor:'#26a69a', borderDownColor:'#ef5350',
  wickUpColor:'#26a69a', wickDownColor:'#ef5350',
  priceFormat: { type:'price', precision:DEC, minMove: Math.pow(10,-DEC) },
  priceLineColor:'rgba(148,163,184,0.6)', priceLineStyle:0,
});

const volSeries = chart.addHistogramSeries({
  priceScaleId:'vol',
  priceFormat: { type:'volume' },
  priceLineVisible:false, lastValueVisible:false,
});
chart.priceScale('vol').applyOptions({ scaleMargins:{ top:0.8, bottom:0 } });

const lineOpts = (color,width) => ({ color, lineWidth:width, priceLineVisible:false, lastValueVisible:false, crosshairMarkerVisible:false });
const ema20 = chart.addLineSeries(lineOpts('#2962ff',1.6));
const ema50 = chart.addLineSeries(lineOpts('#ff9800',1.6));
const bbU   = chart.addLineSeries(lineOpts('rgba(148,163,184,0.4)',1));
const bbL   = chart.addLineSeries(lineOpts('rgba(148,163,184,0.4)',1));

const rows = CAND.map(a => ({
  time: a[0], open:a[1], high:a[2], low:a[3], close:a[4],
}));
candleSeries.setData(rows);
volSeries.setData(CAND.filter(a => a[5]!=null).map(a => ({
  time:a[0], value:a[5], color: a[4]>=a[1] ? 'rgba(38,166,154,0.5)' : 'rgba(239,83,80,0.5)',
})));
ema20.setData(CAND.filter(a => a[6]!=null).map(a => ({time:a[0], value:a[6]})));
ema50.setData(CAND.filter(a => a[7]!=null).map(a => ({time:a[0], value:a[7]})));
bbU.setData(CAND.filter(a => a[8]!=null).map(a => ({time:a[0], value:a[8]})));
bbL.setData(CAND.filter(a => a[9]!=null).map(a => ({time:a[0], value:a[9]})));

for(const lv of LEVELS){
  candleSeries.createPriceLine({
    price: lv.price, color: lv.color, lineWidth: 1,
    lineStyle: lv.dash ? LightweightCharts.LineStyle.Dashed : LightweightCharts.LineStyle.Solid,
    axisLabelVisible: true, title: lv.name,
  });
}

chart.timeScale().fitContent();

/* ---- لجند OHLCV — TV style ---------------------------------------- */
const legend = document.getElementById('legend');
const legendTitle = document.getElementById('ltitle');
legendTitle.textContent = DATA.title;
function barHtml(c){
  const up = c.c>=c.o;
  const cls = up ? 'up' : 'dn';
  return '<span class="k">O</span><b class="'+cls+'">'+fmtP(c.o)+'</b>'
       + '<span class="k">H</span><b class="'+cls+'">'+fmtP(c.h)+'</b>'
       + '<span class="k">L</span><b class="'+cls+'">'+fmtP(c.l)+'</b>'
       + '<span class="k">C</span><b class="'+cls+'">'+fmtP(c.c)+'</b>'
       + '<span class="k">V</span><b>'+fmtV(c.v)+'</b>';
}
function arrBar(a){ return {t:a[0], o:a[1], h:a[2], l:a[3], c:a[4], v:a[5]}; }
function volFor(t){ const a = CAND.find(x => x[0] === t); return a ? a[5] : null; }
function setLegend(bar){
  const d = new Date(bar.t*1000);
  const ts = d.toLocaleString('en-GB',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
  legend.querySelector('#lbar').innerHTML = barHtml(bar) + '<span class="kt">'+ts+'</span>';
}
setLegend(arrBar(CAND[CAND.length-1]));
chart.subscribeCrosshairMove(param => {
  if(param && param.time && param.seriesData){
    const c = param.seriesData.get(candleSeries);
    if(c){ setLegend({t:c.time, o:c.open, h:c.high, l:c.low, c:c.close, v:volFor(c.time)}); }
  } else {
    setLegend(arrBar(CAND[CAND.length-1]));
  }
});

/* ---- نواحی FVG/BVG — canvas هم‌پوشان -------------------------------- */
__ZONES_JS__
sizeZoneCanvas();
(function loop(){ drawZones(); requestAnimationFrame(loop); })();
if(window.ResizeObserver){ new ResizeObserver(()=>{ sizeZoneCanvas(); }).observe(wrap); }

/* ---- دکمه‌ها --------------------------------------------------------- */
document.getElementById('btnFit').onclick  = () => chart.timeScale().fitContent();
document.getElementById('btnNow').onclick  = () => chart.timeScale().scrollToRealTime();
document.getElementById('btnShot').onclick = () => {
  const c = chart.takeScreenshot();
  const a = document.createElement('a');
  a.download = DATA.title.replace(/\\s+/g,'_') + '.png';
  a.href = c.toDataURL('image/png');
  a.click();
};
"""

_CSS = """
html,body{margin:0;padding:0;background:#0e1117;height:100%;overflow:hidden;}
#wrap{position:relative;width:100%;height:100%;direction:ltr;}
#chart{position:absolute;inset:0;}
#zones{position:absolute;inset:0;pointer-events:none;z-index:5;}
#legend{position:absolute;top:6px;left:8px;z-index:6;pointer-events:none;
  font:11px/1.6 ui-monospace,SFMono-Regular,Menlo,monospace;color:#b2b5be;
  background:rgba(14,17,23,0.82);padding:3px 8px;border-radius:6px;
  border:1px solid rgba(148,163,184,0.12);max-width:calc(100% - 120px);}
#ltitle{color:#e2e8f0;font-weight:700;margin-right:6px;}
#lbar .k{color:#78849e;margin:0 3px 0 8px;}
#lbar b{font-weight:600;color:#e2e8f0;}
#lbar b.up{color:#26a69a;} #lbar b.dn{color:#ef5350;}
#lbar .kt{color:#78849e;margin-left:10px;}
#tools{position:absolute;top:6px;right:8px;z-index:6;display:flex;gap:4px;}
#tools button{all:unset;cursor:pointer;font:12px/1 ui-monospace,monospace;color:#b2b5be;
  background:rgba(31,42,61,0.9);border:1px solid rgba(148,163,184,0.18);
  border-radius:6px;padding:5px 8px;}
#tools button:hover{color:#e2e8f0;background:rgba(51,65,85,0.95);}
"""


def build_tv_chart_html(*, candles: List[List[Any]], zones: List[Dict[str, Any]],
                        levels: List[Dict[str, Any]], title: str, dec: int) -> str:
    """HTML خودکفای چارت. candles: [t_s, o, h, l, c, v, e20, e50, bbu, bbl]
    (t ثانیه‌ی UTC · مقادیر NaN قبلاً None شده‌اند) · zones: {t0,top,bottom,kind,tag}
    · levels: {price,name,color,dash}"""
    data = json.dumps({"candles": candles, "zones": [], "levels": levels,
                       "dec": dec, "title": title}, ensure_ascii=False, allow_nan=False)
    zones_js = json.dumps(zones, ensure_ascii=False, allow_nan=False)
    js = (_MAIN_JS
          .replace("__ZONES_JS__", _ZONES_JS)
          .replace("__DATA__", data)
          .replace("__ZONES__", zones_js))
    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<style>" + _CSS + "</style></head><body>"
        '<div id="wrap">'
        '<div id="chart"></div>'
        '<canvas id="zones"></canvas>'
        '<div id="legend"><span id="ltitle"></span><span id="lbar"></span></div>'
        '<div id="tools">'
        '<button id="btnFit" title="بازنشانی نما">⤢</button>'
        '<button id="btnNow" title="پرش به کندل آخر">▶▏</button>'
        '<button id="btnShot" title="دانلود اسکرین‌شات PNG">📷</button>'
        '</div></div>'
        "<script>" + _lib() + "</script>"
        "<script>" + js + "</script></body></html>"
    )
    return html
