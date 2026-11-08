# -*- coding: utf-8 -*-
"""تست هشدار قیمتی روی چارت + حذف سریع رسم‌ها (کلیک/دابل‌کلیک/Delete/✕).
=======================================================================
بخش‌ها:
  ۱) ساختار: sql/price_alerts_setup.sql ، ورک‌فلو، چکر سروری، مارکرهای tv_chart
  ۲) سینتکس: node --check روی JS کامل (اپ + سینک رسم + هشدار)
  ۳) شبیه‌سازی معنایی node: افزودن/تکرار/جهت/تریگر/حذف/سینک کلود/هیت‌تست
اجرای صفر-شبکه: هیچ درخواست واقعی — fetch و localStorage ساختگی‌اند.
"""
from __future__ import annotations

import json as _json
import os
import subprocess as _sp
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_PASS = 0
_FAIL = 0


def ok(cond, msg: str) -> bool:
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  ✓ {msg}")
        return True
    _FAIL += 1
    print(f"  ✗ {msg}")
    return False


def section(t: str) -> None:
    print(f"\n— {t}")


# ---------------------------------------------------------------- بدنه‌های JS
from core.tv_chart import _MAIN_JS, _SYNC_JS, _ALERT_JS  # noqa: E402

CFG = {"url": "https://fake.supabase.co", "key": "fake-anon-key"}

MAIN_FULL = _MAIN_JS.replace("__DATA__", _json.dumps({
    "candles": [[1000, 1, 1, 1, 1, 0]], "tfs": {"1hour": [[1000, 1, 1, 1, 1, 0]]},
    "base_tf": "1hour", "symbol": "BTC/USDT", "levels": [], "dec": 2,
    "title": "T", "initial_bars": 50, "fx": False}, ensure_ascii=False))
SYNC_FULL = _SYNC_JS.replace("__SYNC_CFG__", _json.dumps(CFG))
ALERT_FULL = _ALERT_JS.replace("__ALERT_SYNC_CFG__", _json.dumps(CFG))

# ---------------------------------------------------------------- ۱) ساختار
section("ساختار پروژه")
ok(os.path.exists(ROOT / "sql" / "price_alerts_setup.sql"), "sql/price_alerts_setup.sql موجود است")
ok(os.path.exists(ROOT / ".github" / "workflows" / "price-alerts.yml"), "ورک‌فلو price-alerts.yml موجود است")
ok(os.path.exists(ROOT / "scripts" / "check_price_alerts.py"), "چکر سروری scripts/check_price_alerts.py موجود است")
_chk = _sp.run([sys.executable, "-m", "py_compile", str(ROOT / "scripts" / "check_price_alerts.py")],
               capture_output=True, text=True, timeout=60)
ok(_chk.returncode == 0, f"چکر سروری کامپایل می‌شود {_chk.stderr.strip()[:120]}")

_sql = (ROOT / "sql" / "price_alerts_setup.sql").read_text(encoding="utf-8")
for frag in ("create table if not exists price_alerts", "enable row level security",
             "policy \"alerts read\"", "price_alerts_touch", "updated_at"):
    ok(frag in _sql, f"SQL دارای «{frag}»")

_src = (ROOT / "core" / "tv_chart.py").read_text(encoding="utf-8")
for frag in ("id=\"btnAlert\"", "id=\"selX\"", "function addAlert", "function removeAlert",
             "function alertHit", "__nqDrawAlerts", "__nqPlaceSelX", "__nqAlertApi",
             "setInterval(checkAlerts, 20000)", "price_alerts", "'nqtv:al:'"):
    ok(frag in _ALERT_JS or frag in _MAIN_JS or frag in _src, f"مارکر چارت «{frag}»")

# اتصال رویدادهای حذف سریع در _MAIN_JS
for frag in ("e.target.closest('#selX')", "e.key==='Delete' || e.key==='Backspace'",
             "addEventListener('dblclick'", "typeof alertHit==='function'",
             "S.tool==='alert'", "eraseAt(selIdx)"):
    ok(frag in _MAIN_JS, f"اتصال حذف سریع «{frag}»")

# ضد «گیر کردن» قیمت زنده: مهلت هر منبع + منابع جایگزین + خط امانی چک + چیپ زنده
for frag in ("fetchTOms", "ctl.abort()", "cryptocompare", "coingecko",
             "Promise.race([livePrice()", "9000", "__nqLivePx"):
    ok(frag in _src, f"ضدگیرِ قیمت زنده «{frag}»")

# پل اسکوپ: _MAIN_JS همین نام‌ها را سراسری صدا می‌زند — بدون export مرورگر کرش می‌کند
# (باگ واقعی: ReferenceError: addAlert is not defined — فقط در مرورگر، نه در سیم node)
for fn in ("addAlert", "removeAlert", "alertHit"):
    ok(("window." + fn + "=") in _ALERT_JS, f"پل اسکوپ window.{fn} در _ALERT_JS")

_yml = (ROOT / ".github" / "workflows" / "price-alerts.yml").read_text(encoding="utf-8")
ok("check_price_alerts.py" in _yml and "cron:" in _yml, "ورک‌فلو چکر را اجرا می‌کند (کرون)")
_cksrc = (ROOT / "scripts" / "check_price_alerts.py").read_text(encoding="utf-8")
for frag in ("price_for", "_is_crypto_symbol", "_is_fx_symbol", "active", "updated_by.*checker" if False else "_save_row", "_telegram"):
    ok(frag in _cksrc, f"چکر سروری دارای «{frag}»")

# ---------------------------------------------------------------- ۲) سینتکس
section("سینتکس JS (node --check)")
try:
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(MAIN_FULL + "\n" + SYNC_FULL + "\n" + ALERT_FULL)
        _f1 = f.name
    _c = _sp.run(["node", "--check", _f1], capture_output=True, text=True, timeout=60)
    ok(_c.returncode == 0, f"اپ + سینک رسم + هشدار — سینتکس سالم {_c.stderr.strip()[:120]}")
    os.unlink(_f1)
except FileNotFoundError:
    print("  ⚠ node در دسترس نیست — بخش JS رد شد")

# ---------------------------------------------------------------- ۳) شبیه‌سازی
section("شبیه‌سازی معنایی هشدارها (node)")
_sim = r'''
const assert = (c, m) => { if(!c){ console.error('SIM FAIL: '+m); process.exit(1); } };
const sleep = ms => new Promise(r => setTimeout(r, ms));

const store = {};
globalThis.localStorage = {
  getItem: k => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: k => { delete store[k]; },
};
const btnAlert = { textContent:'', title:'', onclick:null };
globalThis.document = { getElementById: id => (id==='btnAlert' ? btnAlert : null) };
globalThis.window = globalThis;
globalThis.DATA = { symbol:'BTC/USDT', fx:false };
globalThis.safeParse = s => { try{ return JSON.parse(s); }catch(e){ return null; } };
const toasts = [];
globalThis.toast = m => { toasts.push(String(m)); };
globalThis.fmtP = v => (v==null? '—' : Number(v).toLocaleString('en-US'));
globalThis.CAND = () => [[0,1,1,1,100,0], [60,1,1,1,100,0]];   // آخرین بسته‌شدن = ۱۰۰
globalThis.yOf = p => 200 - Number(p);                          // قیمت→پیکسل
globalThis.mainSeries = { stub:true };
globalThis.mainPane = { getBoundingClientRect: () => ({width:800, height:400}) };
const octxCalls = { fillText: 0, moveTo: 0 };
globalThis.octx = new Proxy({}, { get: (t, k) => {
  if(k==='measureText') return () => ({width: 40});
  if(k==='fillText') return () => { octxCalls.fillText++; };
  if(k==='moveTo') return () => { octxCalls.moveTo++; };
  return () => {};
}, set: () => true });
globalThis.S = { tool:'cursor' };
const toolCalls = [];
globalThis.setTool = t => { toolCalls.push(t); };

// تایمرها: interval هرگز خودکار اجرا نمی‌شود؛ timeout فشرده به ۱ms
const _st = setTimeout;
globalThis.setTimeout = (f, ms) => _st(f, Math.min(ms||0, 1));
globalThis.setInterval = () => 0;
globalThis.clearInterval = () => {};
globalThis.clearTimeout = () => {};

// جدول کلود ساختگی برای price_alerts
const clock = { now: '2026-01-01T10:00:00+00:00' };
const table = {};
let tickerPrice = null;         // اگر ست باشد، fetch به جای جدول پاسخ قیمت می‌دهد (بایننس)
let ccPrice = null;             // قیمت ساختگی منبع جایگزین (کریپتوکمپیر/کوین‌گکو)
let failGet = false;
const log = { get: [], put: [] };
globalThis.fetch = async (url, opt) => {
  opt = opt || {};
  if(String(url).includes('ticker/price')){
    if(tickerPrice == null) return { ok:false, status:500, json: async()=>({}) };
    return { ok:true, status:200, json: async()=>({price: String(tickerPrice)}) };
  }
  if(String(url).includes('data/price')){
    if(ccPrice == null) return { ok:false, status:500, json: async()=>({}) };
    return { ok:true, status:200, json: async()=>({USDT: String(ccPrice)}) };
  }
  if(String(url).includes('simple/price')){
    if(ccPrice == null) return { ok:false, status:500, json: async()=>({}) };
    return { ok:true, status:200, json: async()=>({bitcoin:{usd: ccPrice}}) };
  }
  if(!opt.method){
    log.get.push(url);
    if(failGet) return { ok:false, status:500, json: async()=>[] };
    const m = /scope=eq.([^&]+)/.exec(url);
    const sc = decodeURIComponent(m[1]);
    return { ok:true, status:200, json: async()=> (table[sc] ? [table[sc]] : []) };
  }
  log.put.push({ url, body: JSON.parse(opt.body) });
  const row = JSON.parse(opt.body)[0];
  table[row.scope] = Object.assign({}, row, { updated_at: clock.now });
  return { ok:true, status:200, json: async()=>[table[row.scope]] };
};

const ALERTJS_SRC = ''' + _json.dumps(ALERT_FULL) + ''';
const vm = require('vm');
vm.runInThisContext(ALERTJS_SRC, {filename:'alert.js'});

(async () => {
  const api = globalThis.__nqAlertApi;
  assert(api && typeof api.addAlert==='function', 'api هشدار در دسترس است');
  // پل اسکوپ — بدون این، هندلر کلیک _MAIN_JS در مرورگر ReferenceError می‌دهد
  assert(typeof globalThis.addAlert==='function', 'window.addAlert صادر شد');
  assert(typeof globalThis.removeAlert==='function', 'window.removeAlert صادر شد');
  assert(typeof globalThis.alertHit==='function', 'window.alertHit صادر شد');
  await sleep(80);   // reconcile اول (کلود خالی) تمام شود

  // ۱) کلود خالی + محلی خالی → فقط مُهر، بدون push
  assert(log.put.length===0, 'boot بی‌هشدار → بدون push');
  assert(store['nqtv:alsync:BTC/USDT'], 'مُهر همگام اولیه ثبت شد');

  // ۲) افزودن بالای قیمت → dir=above
  api.addAlert(110);
  let L = api.list();
  assert(L.length===1 && L[0].dir==='above' && L[0].active===true, 'هشدار ۱۱۰ = above فعال');
  assert(JSON.parse(store['nqtv:al:BTC/USDT']).length===1, 'ذخیره محلی انجام شد');

  // ۳) هشدار مشابه رد می‌شود
  api.addAlert(110.05);
  assert(api.list().length===1, 'هشدار مشابه (۰.۱٪) رد شد');

  // ۴) افزودن زیر قیمت → dir=below
  api.addAlert(90);
  assert(api.list().length===2 && api.list()[1].dir==='below', 'هشدار ۹۰ = below');

  // ۵) دبانس push → یک put با scope و ۲ هشدار
  await sleep(80);
  assert(log.put.length>=1, 'push کلود انجام شد');
  const put0 = log.put[0].body[0];
  assert(put0.scope==='BTC/USDT' && put0.alerts.length===2, 'scope و تعداد هشدارها درست');
  assert(table['BTC/USDT'] && table['BTC/USDT'].updated_at===clock.now, 'ردیف کلود ساخته شد');

  // ۶) تریگر زنده: قیمت ۱۱۱ → هشدار بالای ۱۱۰ می‌ترگد، زیر ۹۰ نه
  tickerPrice = 111;
  await api.checkAlerts();
  L = api.list();
  assert(L[0].active===false && L[0].trigger_price===111, 'هشدار above تریگر شد');
  assert(L[1].active===true, 'هشدار below دست‌نخورده');
  assert(toasts.some(t=>t.indexOf('🔔')>=0 && t.indexOf('۱۱۰')>=0 || t.indexOf('110')>=0), 'توست تریگر آمد');
  assert(JSON.parse(store['nqtv:al:BTC/USDT'])[0].active===false, 'وضعیت تریگر ذخیره شد');

  // ۷) حذف با ایندکس (مسیر کلیک/دابل‌کلیک/✕ همین تابع است)
  tickerPrice = null;
  api.removeAlert(0);
  assert(api.list().length===1 && api.list()[0].price===90, 'حذف هشدار انجام شد');

  // ۸) هیت‌تست خط هشدار (y=200-price) — ۱۲۰ آخرین هشدار است → ایندکس ۱
  api.addAlert(120);
  assert(api.list().length===2, 'هشدار ۱۲۰ اضافه شد');
  assert(api.alertHit(400, 200-120)===1, 'alertHit روی خط → ۱');
  assert(api.alertHit(400, 200-135)===-1, 'alertHit دور از خط → -۱');

  // ۹) منبع جایگزین: بایننس از دسترس خارج (tickerPrice=null) → کریپتوکمپیر قیمت
  //    می‌دهد و هشدار زیر ۹۰ می‌ترگد — دقیقا سناریوی شبکه‌ای که بایننس را فیلتر می‌کند
  ccPrice = 89;
  await api.checkAlerts();
  L = api.list();
  const belowAl = L.find(a=>Number(a.price)===90);
  assert(belowAl && belowAl.active===false && belowAl.trigger_price===89,
         'تریگر با منبع جایگزین (کریپتوکمپیر) — ضدگیر');
  ccPrice = null;

  // ۱۰) رسم هشدار روی بوم استاب نمی‌شکند و خط/برچسب می‌کشد
  globalThis.__nqDrawAlerts();
  assert(octxCalls.moveTo>=1 && octxCalls.fillText>=1, 'خط و برچسب هشدار کشیده شد');

  // ۱۱) دکمه 🔔 ابزار هشدار را مسلح می‌کند
  btnAlert.onclick();
  assert(toolCalls.indexOf('alert')>=0, 'دکمه 🔔 → setTool(alert)');

  // تخلیه‌ی push معلق قبل از سناریوی pull — مثل دنیای واقعی که کاربر بین تغییر و رفرش مکث می‌کند
  await sleep(80);

  // ۱۲) pull: کلود جدیدتر با هشدار تازه → جایگزین محلی
  clock.now = '2026-01-01T11:00:00+00:00';
  table['BTC/USDT'] = { scope:'BTC/USDT', alerts:[{id:'x', price:130, dir:'above', active:true}],
                        updated_at: clock.now, updated_by:'dev-other' };
  store['nqtv:alsync:BTC/USDT'] = '2026-01-01T09:00:00+00:00';   // مُهر قدیمی
  await globalThis.__alSyncReconcile();
  assert(api.list().length===1 && api.list()[0].price===130, 'pull کلود جایگزین محلی شد');
  assert(JSON.parse(store['nqtv:al:BTC/USDT'])[0].price===130, 'pull در localStorage هم ذخیره شد');

  // ۱۳) مُهر برابر → reconcile کاری نمی‌کند
  const before = api.list().length;
  clock.now = '2026-01-01T12:00:00+00:00';
  table['BTC/USDT'].updated_at = clock.now;
  table['BTC/USDT'].alerts = [{id:'y', price:140, dir:'above', active:true}];
  // مُهر قدیمی‌تر از کلود → باید pull کند؛ این‌بار مُهر را برابر می‌کنیم
  store['nqtv:alsync:BTC/USDT'] = '2026-01-01T12:00:00+00:00';
  await globalThis.__alSyncReconcile();
  assert(api.list().length===1 && api.list()[0].price===130, 'مُهر برابر → بدون تغییر');

  // ۱۴) خطای کلود → اپ نمی‌شکند
  failGet = true;
  await globalThis.__alSyncReconcile();
  assert(true, 'خطای کلود مدیریت شد (بدون crash)');
  failGet = false;

  console.log('ALERT_SIM_OK');
})().catch(e => { console.error('SIM ERR:', e); process.exit(1); });
'''
try:
    _run = _sp.run(["node", "-e", _sim], capture_output=True, text=True, timeout=120)
    ok("ALERT_SIM_OK" in _run.stdout,
       "۱۴ سناریوی هشدار (افزودن/تکرار/جهت/تریگر/منبع‌جایگزین/حذف/هیت‌تست/رسم/دکمه/pull/مُهر/خطا) "
       + (_run.stderr.strip()[:300] if "ALERT_SIM_OK" not in _run.stdout else ""))
except FileNotFoundError:
    print("  ⚠ node در دسترس نیست — شبیه‌سازی رد شد")

print(f"\n===== نتیجه: {_PASS} سبز / {_FAIL} قرمز =====")
sys.exit(1 if _FAIL else 0)
