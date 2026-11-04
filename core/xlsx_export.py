# -*- coding: utf-8 -*-
"""core/xlsx_export.py — خروجی اکسل بدون وابستگی (پورت از TITAN)
================================================================
پورت‌شده از excel_export.py پروژه‌ی TITAN با همان اصول:
  · OOXML دست‌ساز فقط با کتابخانه‌ی استاندارد (zipfile + رشته‌های XML)
  · همه‌ی متن‌ها «inline string» می‌شوند — هیچ فرمول قابل اجرا در فایل نیست
  · هیچ کد تولیدشده‌ی مدل برای ساخت workbook اجرا نمی‌شود
  · RTL از توی خود فایل (rightToLeft + readingOrder) — مناسب فارسی

برای پروژه اضافه شد:
  · df_sheet — تبدیل DataFrame به برگه
  · arena_workbook / tse_paper_workbook / trade_log_workbook — سازنده‌های
    دامنه‌دار برای معاملات میدان ایجنت‌ها، ماکت بورس و دفتر سفارش‌های واقعی
"""
from __future__ import annotations

import io
import json
import math
import re
import zipfile
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from xml.sax.saxutils import escape

MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def clean(value: Any) -> str:
    """هر نویسه‌ی کنترلی/غیرمجاز XML دور ریخته می‌شود — متن امن."""
    text = str(value if value is not None else "")
    return "".join(c for c in text if c in "\t\n\r" or 0x20 <= ord(c) <= 0xD7FF
                   or 0xE000 <= ord(c) <= 0xFFFD or 0x10000 <= ord(c) <= 0x10FFFF)


def column(index: int) -> str:
    """شماره‌ی ستون ۱مبنا → حرف اکسل (1=A، 26=Z، 27=AA)."""
    result = ""
    while index:
        index, digit = divmod(index - 1, 26)
        result = chr(65 + digit) + result
    return result


def workbook(sheets: Sequence[Tuple[str, Iterable[Sequence[Any]], ...]]) -> bytes:
    """sheets: [(name, rows, optional widths)]. ردیف اول = سرستون.
    خروجی: بایت‌های یک فایل .xlsx معتبر."""
    if not sheets:
        raise ValueError("Workbook needs a sheet")
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    styles = (f'<styleSheet xmlns="{ns}"><fonts count="2"><font><sz val="11"/>'
              '<name val="Tahoma"/><color rgb="FF202B3D"/></font><font><b/>'
              '<sz val="11"/><name val="Tahoma"/><color rgb="FFFFFFFF"/></font></fonts>'
              '<fills count="4"><fill><patternFill patternType="none"/></fill>'
              '<fill><patternFill patternType="gray125"/></fill><fill><patternFill '
              'patternType="solid"><fgColor rgb="FF151F2D"/><bgColor indexed="64"/></patternFill></fill>'
              '<fill><patternFill patternType="solid"><fgColor rgb="FFF7F4EC"/>'
              '<bgColor indexed="64"/></patternFill></fill></fills><borders count="1">'
              '<border><left/><right/><top/><bottom/><diagonal/></border></borders>'
              '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
              '<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" '
              'applyAlignment="1"><alignment horizontal="right" vertical="top" wrapText="1" readingOrder="2"/></xf>'
              '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyAlignment="1">'
              '<alignment horizontal="right" vertical="center" wrapText="1" readingOrder="2"/></xf>'
              '<xf numFmtId="0" fontId="0" fillId="3" borderId="0" xfId="0" applyAlignment="1">'
              '<alignment horizontal="right" vertical="top" wrapText="1" readingOrder="2"/></xf></cellXfs>'
              '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
    names = set()
    sheet_entries, relations, overrides = [], [], []
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("_rels/.rels", f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                                  f'<Relationship Id="rId1" Type="{rel}/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr("xl/styles.xml", styles)
        for sid, spec in enumerate(sheets, 1):
            name, rows = spec[0], spec[1]
            widths = spec[2] if len(spec) > 2 else []
            name = re.sub(r"[\\/*?:\[\]]", " ", clean(name)).strip().strip("'")[:31] or "Sheet"
            base, suffix = name, 1
            while name.casefold() in names:
                suffix += 1
                name = base[:26] + str(suffix)
            names.add(name.casefold())
            rows = list(rows) or [["بدون داده"]]
            if len(rows) > 1048576:
                raise ValueError("Too many Excel rows")
            count = max(len(row) for row in rows)
            if count > 16384:
                raise ValueError("Too many Excel columns")
            if not widths:
                widths = [22] * count
            cols = "".join(
                f'<col min="{i}" max="{i}" width="{min(120, max(8, w))}" customWidth="1"/>'
                for i, w in enumerate(widths, 1))
            data = []
            for rid, row in enumerate(rows, 1):
                cells = []
                style = 1 if rid == 1 else (2 if rid % 2 == 0 else 0)
                for cid, value in enumerate(row, 1):
                    ref = column(cid) + str(rid)
                    if isinstance(value, (float, int)) and not isinstance(value, bool) \
                            and math.isfinite(value):
                        cells.append(f'<c r="{ref}" s="{style}"><v>{value}</v></c>')
                    else:
                        text = clean(value)
                        if len(text) > 32767:
                            raise ValueError("Excel cell text exceeds 32767 characters")
                        cells.append(f'<c r="{ref}" s="{style}" t="inlineStr"><is>'
                                     f'<t xml:space="preserve">{escape(text)}</t></is></c>')
                height = ' ht="32" customHeight="1"' if rid == 1 else ""
                data.append(f'<row r="{rid}"{height}>' + "".join(cells) + "</row>")
            dimension = f"A1:{column(count)}{len(rows)}"
            auto = f'<autoFilter ref="{dimension}"/>' if count > 1 else ""
            xml = (f'<worksheet xmlns="{ns}"><dimension ref="{dimension}"/>'
                   '<sheetViews><sheetView workbookViewId="0" rightToLeft="1">'
                   '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
                   '</sheetView></sheetViews><sheetFormatPr defaultRowHeight="24"/>'
                   f'<cols>{cols}</cols><sheetData>' + "".join(data) + f'</sheetData>{auto}'
                   '<pageMargins left="0.3" right="0.3" top="0.5" bottom="0.5" header="0.2" footer="0.2"/>'
                   "</worksheet>")
            z.writestr(f"xl/worksheets/sheet{sid}.xml", xml)
            sheet_entries.append(f'<sheet name="{escape(name, {chr(34): "&quot;"})}" '
                                 f'sheetId="{sid}" r:id="rId{sid}"/>')
            relations.append(f'<Relationship Id="rId{sid}" Type="{rel}/worksheet" '
                             f'Target="worksheets/sheet{sid}.xml"/>')
            overrides.append(f'<Override PartName="/xl/worksheets/sheet{sid}.xml" '
                             'ContentType="application/vnd.openxmlformats-officedocument.'
                             'spreadsheetml.worksheet+xml"/>')
        relations.append(f'<Relationship Id="rId{len(sheets)+1}" Type="{rel}/styles" Target="styles.xml"/>')
        z.writestr("xl/workbook.xml", f'<workbook xmlns="{ns}" xmlns:r="{rel}"><bookViews>'
                                      f'<workbookView/></bookViews><sheets>' + "".join(sheet_entries) + "</sheets></workbook>")
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + "".join(relations) + "</Relationships>")
        z.writestr("[Content_Types].xml",
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-'
                   'officedocument.spreadsheetml.sheet.main+xml"/>'
                   '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-'
                   'officedocument.spreadsheetml.styles+xml"/>' + "".join(overrides) + "</Types>")
    return output.getvalue()


# ------------------------------------------------------------- سازنده‌های دامنه‌دار
def df_sheet(df, widths: Optional[List[int]] = None) -> Tuple[str, List[List[Any]], List[int]]:
    """DataFrame → برگه‌ی (نام، ردیف‌ها، پهناها). نام ستون‌ها = ردیف اول."""
    if df is None or len(df.columns) == 0:
        return "برگه", [["بدون داده"]], []
    rows: List[List[Any]] = [[str(c) for c in df.columns]]
    for _, r in df.iterrows():
        rows.append([_cell(r[c]) for c in df.columns])
    if not widths:
        widths = [22] * len(df.columns)
    return "برگه", rows, widths


def _cell(v: Any) -> Any:
    """سلول امن: عدد شناور/هسته‌ای همان عدد؛ نان/بی‌نهایت = «—»؛ بقیه = متن."""
    if isinstance(v, (float, int)) and not isinstance(v, bool):
        try:
            f = float(v)
        except (TypeError, ValueError):
            return clean(v)
        return f if math.isfinite(f) else "—"
    if v is None:
        return ""
    return clean(v)


def arena_workbook(trades: List[Dict[str, Any]]) -> bytes:
    """معاملات میدان ایجنت‌ها → اکسل دوبرگه: معاملات + خلاصه."""
    head = ["ایجنت", "نماد", "جهت", "وضعیت", "ورود", "استاپ", "TP1", "TP2", "TP3",
            "استاپ فعلی", "قیمت بسته", "R نهایی", "امتیاز", "باز شده", "بسته شده", "دلیل"]
    rows: List[List[Any]] = [head]
    for t in trades or []:
        d = int(t.get("direction") or 0)
        rows.append([
            t.get("agent") or "", t.get("symbol") or "",
            {"1": "خرید", "-1": "فروش", "0": "خنثی"}.get(str(d), str(d)),
            t.get("status") or "",
            _num(t.get("entry")), _num(t.get("stop")), _num(t.get("tp1")),
            _num(t.get("tp2")), _num(t.get("tp3")), _num(t.get("cur_stop")),
            _num(t.get("closed_price")), _num(t.get("realized_r")),
            _num(t.get("score")), t.get("opened_at") or "",
            t.get("closed_at") or "", clean(t.get("evidence") or "")[:600],
        ])
    open_n = sum(1 for t in trades or [] if t.get("status") == "open")
    closed = [t for t in trades or [] if t.get("status") == "closed"]
    wins = sum(1 for t in closed if _num(t.get("realized_r"), 0.0) > 0)
    total_r = sum(_num(t.get("realized_r"), 0.0) for t in closed)
    summary = [["شاخص", "مقدار"],
               ["تعداد کل معاملات", len(trades or [])],
               ["باز", open_n], ["بسته‌شده", len(closed)],
               ["بردها", wins], ["مجموع R بسته‌شده‌ها", round(total_r, 2)],
               ["یادداشت", "داده‌ی خام میدان ایجنت‌ها؛ R نهایی معاملات باز هنوز قطعی نیست."]]
    return workbook([("معاملات", rows, [16, 12, 8, 8, 12, 12, 12, 12, 12, 12, 12, 10, 9, 20, 20, 60]),
                     ("خلاصه", summary, [28, 44])])


def tse_paper_workbook(port: Dict[str, Any]) -> bytes:
    """ماکت بورس ایران → اکسل: مبلغ‌های باز + خلاصه + دفتر سفارش‌ها."""
    from core.tse_paper import portfolio_table, summary  # ایمپورت داخلی — بدون چرخه

    info = [["شاخص", "مقدار"],
            ["نقد (ریال)", _num(port.get("cash"))],
            ["ارزش مبلغ‌ها (ریال)", _num(summary(port).get("positions_value"))],
            ["ارزش کل (ریال)", _num(summary(port).get("equity"))],
            ["سود/زیان کل نسبت به شروع (ریال)", _num(summary(port).get("pnl"))],
            ["یادداشت", "پول واقعی نیست؛ ماکت آموزشی با کارمزد واقعی TSE."]]
    df = portfolio_table(port)
    _, rows, widths = df_sheet(df)
    if rows and len(rows[0]) >= 8:
        widths = [14, 10, 10, 18, 18, 16, 16, 12]
    orders = [["زمان", "جهت", "نماد", "تعداد", "قیمت (ریال)", "کارمزد (ریال)"]]
    for o in list((port.get("orders") or [])):
        orders.append([o.get("when") or "", "خرید" if o.get("side") == "buy" else "فروش",
                       o.get("symbol") or "", _num(o.get("qty")), _num(o.get("price")),
                       _num(o.get("fee"))])
    return workbook([("مبلغ‌های باز", rows or [["بدون داده"]], widths),
                     ("خلاصه", info, [32, 30]),
                     ("دفتر سفارش‌ها", orders, [20, 8, 12, 10, 14, 14])])


def trade_log_workbook(rows: List[Dict[str, Any]]) -> bytes:
    """دفتر سفارش‌های واقعی (trade_log سوپابیس) → اکسل."""
    head = ["زمان (UTC)", "صرافی", "نماد", "جهت", "نوع سفارش", "مقدار", "قیمت",
            "ارزش (USDT)", "شناسه سفارش", "حالت"]
    data: List[List[Any]] = [head]
    for r in rows or []:
        data.append([r.get("ts") or "", r.get("exchange") or "", r.get("symbol") or "",
                     r.get("side") or "", r.get("otype") or "", _num(r.get("amount")),
                     _num(r.get("price")), _num(r.get("notional")),
                     r.get("order_id") or "", r.get("mode") or ""])
    return workbook([("دفتر سفارش‌های واقعی", data,
                      [22, 14, 14, 8, 12, 12, 12, 14, 26, 10])])


def _num(v: Any, default: Optional[float] = None) -> Any:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default if default is not None else ""
    return f if math.isfinite(f) else (default if default is not None else "")


def json_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else json.loads(value or "[]")
