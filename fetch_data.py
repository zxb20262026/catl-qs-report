#!/usr/bin/env python3
"""
CATL QuantiSkills 全景分析 — 数据采集模块
基于 QuantiSkills 框架：个股尽调 + 财务健康 + 芒格5维 + 反共识 + 聪明钱 + AH溢价 + 事件风险 + 市场状态
所有数据通过新浪/腾讯/东财公开API获取，零外部依赖
"""

import urllib.request, ssl, json, re, time, statistics, os, sys
from datetime import datetime

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

H_SINA = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn/"}
H_EM = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.eastmoney.com/"}
H_TENCENT = {"User-Agent": "Mozilla/5.0", "Referer": "https://stockapp.finance.qq.com/"}

CACHE = {}
CACHE_FILE = os.path.join(os.path.dirname(__file__), "data_cache.json")

def get(url, enc="utf-8", t=15, headers=None):
    req = urllib.request.Request(url, headers=headers or H_SINA)
    return urllib.request.urlopen(req, timeout=t, context=ssl_ctx).read().decode(enc, errors="replace")

def get_json(url, t=15):
    raw = get(url, t=t, headers=H_EM)
    # Handle UTF-8 BOM
    if raw.startswith('\ufeff'):
        raw = raw[1:]
    return json.loads(raw)

def fetch_url(url, enc="utf-8"):
    try:
        return get(url, enc)
    except:
        return None

# ════════════════════════════════════════════════════
# 模块1: 核心行情 (A+H股)
# ════════════════════════════════════════════════════

def fetch_core():
    """CATL A+H 实时行情"""
    result = {"a": None, "h": None, "market": {}}
    
    # A股
    try:
        raw = get("https://hq.sinajs.cn/list=sz300750", "gbk")
        m = re.search(r'"(.+?)"', raw)
        if m:
            p = m.group(1).split(",")
            if len(p) >= 10:
                price, prev = float(p[3]), float(p[2])
                result["a"] = {
                    "name": p[0], "price": price, "prev_close": prev,
                    "open": float(p[1]), "high": float(p[4]), "low": float(p[5]),
                    "volume": int(p[8]) if p[8] else 0,
                    "amount": float(p[9]) if p[9] else 0,
                    "change": round(price - prev, 2),
                    "change_pct": round((price - prev) / prev * 100, 2) if prev else 0,
                }
    except Exception as e:
        result["a_error"] = str(e)
    
    # H股
    try:
        raw = get("https://hq.sinajs.cn/list=hk03750", "gbk")
        m = re.search(r'"(.+?)"', raw)
        if m:
            p = m.group(1).split(",")
            if len(p) >= 10:
                price_h = float(p[6])  # 港股现价在p[6]
                prev_h = float(p[5])   # 昨收在p[5]
                result["h"] = {
                    "name": p[0], "price": price_h, "prev_close": prev_h,
                    "open": float(p[2]), "high": float(p[4]), "low": float(p[5]),
                    "change": round(price_h - prev_h, 2) if price_h and prev_h else None,
                    "change_pct": round((price_h - prev_h) / prev_h * 100, 2) if prev_h and price_h else None,
                }
                # AH溢价
                if result["a"] and result["h"]:
                    a_price = result["a"]["price"]
                    h_price = result["h"]["price"]
                    # 粗略汇率 1 HKD ≈ 0.92 RMB
                    ah_premium = round((a_price / (h_price * 0.92) - 1) * 100, 1)
                    result["ah_premium"] = ah_premium
    except Exception as e:
        result["h_error"] = str(e)
    
    # 大盘指数
    for name, code in [("上证指数", "sh000001"), ("沪深300", "sh000300"), 
                        ("创业板指", "sz399006"), ("科创50", "sh000688")]:
        try:
            raw = get(f"https://hq.sinajs.cn/list={code}", "gbk")
            m = re.search(r'"(.+?)"', raw)
            if m:
                p = m.group(1).split(",")
                result["market"][name] = {
                    "price": float(p[3]), "change_pct": round(float(p[3])/float(p[2])*100-100, 2)
                }
        except:
            pass
    
    return result


# ════════════════════════════════════════════════════
# 模块2: 基本面 + 估值 (腾讯qt)
# ════════════════════════════════════════════════════

def fetch_fundamentals():
    """PE/PB/ROE/市值等基本面指标"""
    result = {}
    try:
        raw = get("https://web.ifzq.gtimg.cn/appstock/app/minute/query?_var=qt&code=sz300750", t=15, headers=H_TENCENT)
        # Parse the nested JSON structure: qt={...}
        jdata = json.loads(raw[3:])  # skip "qt="
        qt_arr = jdata.get("data", {}).get("sz300750", {}).get("qt", {}).get("sz300750", [])
        if not qt_arr:
            # Try alternative: qt field directly
            qt_arr = jdata.get("data", {}).get("sz300750", {}).get("qt", [])
        if isinstance(qt_arr, list) and len(qt_arr) > 65:
            result["pe"] = float(qt_arr[39]) if qt_arr[39] else None
            result["pb"] = float(qt_arr[46]) if qt_arr[46] else None
            result["roe"] = float(qt_arr[65]) if qt_arr[65] else None
            result["market_cap"] = float(qt_arr[45]) if qt_arr[45] else None
            result["price"] = float(qt_arr[3]) if qt_arr[3] else None
            result["turnover_rate"] = float(qt_arr[38]) if qt_arr[38] else None
            result["volume_ratio"] = float(qt_arr[51]) if qt_arr[51] else None
            result["total_shares"] = float(qt_arr[44]) if qt_arr[44] else None
            result["high_52w"] = float(qt_arr[33]) if qt_arr[33] else None
            result["low_52w"] = float(qt_arr[34]) if qt_arr[34] else None
    except Exception as e:
        pass
    return result


# ════════════════════════════════════════════════════
# 模块3: K线 + 技术分析
# ════════════════════════════════════════════════════

def fetch_kline(days=90):
    """90日K线数据"""
    try:
        raw = get(f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?_var=kline&param=sz300750,day,,,{days},qfq", 
                  t=15, headers=H_TENCENT)
        jdata = json.loads(raw[6:])  # skip "kline="
        klines = jdata.get("data", {}).get("sz300750", {}).get("qfqday", [])
        if not klines:
            klines = jdata.get("data", {}).get("sz300750", {}).get("day", [])
        result = []
        for k in klines:
            if isinstance(k, list) and len(k) >= 6:
                result.append({
                    "date": k[0],
                    "open": float(k[1]), "close": float(k[2]),
                    "high": float(k[3]), "low": float(k[4]),
                    "volume": float(k[5]) if k[5] else 0,
                })
        return result
    except:
        pass
    return []


def calc_ma(klines, window):
    """计算移动平均线"""
    if len(klines) < window:
        return []
    result = []
    for i in range(len(klines)):
        if i >= window - 1:
            avg = statistics.mean(k["close"] for k in klines[i-window+1:i+1])
            result.append({"date": klines[i]["date"], "value": round(avg, 2)})
        else:
            result.append({"date": klines[i]["date"], "value": None})
    return result


def calc_macd(klines):
    """MACD(12,26,9)"""
    if len(klines) < 35:
        return []
    closes = [k["close"] for k in klines]
    ema12 = closes[0]
    ema26 = closes[0]
    dif_list = []
    for i, c in enumerate(closes):
        ema12 = c * 2/13 + ema12 * 11/13
        ema26 = c * 2/27 + ema26 * 25/27
        dif_list.append(ema12 - ema26)
    
    dea = dif_list[0]
    result = []
    for i, dif in enumerate(dif_list):
        dea = dif * 2/10 + dea * 8/10
        macd = (dif - dea) * 2
        result.append({"date": klines[i]["date"], "dif": round(dif, 3), 
                       "dea": round(dea, 3), "macd": round(macd, 3)})
    return result


def calc_rsi(klines, period=14):
    """RSI指标"""
    if len(klines) < period + 1:
        return []
    closes = [k["close"] for k in klines]
    result = [{"date": klines[i]["date"], "rsi": None} for i in range(period)]
    gains = []
    losses = []
    for i in range(1, period + 1):
        diff = closes[i] - closes[i-1]
        gains.append(diff if diff > 0 else 0)
        losses.append(abs(diff) if diff < 0 else 0)
    
    avg_gain = statistics.mean(gains)
    avg_loss = statistics.mean(losses)
    rsi = 100 - 100 / (1 + avg_gain / avg_loss) if avg_loss else 100
    result.append({"date": klines[period]["date"], "rsi": round(rsi, 1)})
    
    for i in range(period + 1, len(closes)):
        diff = closes[i] - closes[i-1]
        gain = diff if diff > 0 else 0
        loss = abs(diff) if diff < 0 else 0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        rsi = 100 - 100 / (1 + avg_gain / avg_loss) if avg_loss else 100
        result.append({"date": klines[i]["date"], "rsi": round(rsi, 1)})
    return result


def calc_bollinger(klines, period=20):
    """布林带"""
    result = []
    for i in range(len(klines)):
        if i >= period - 1:
            window = [k["close"] for k in klines[i-period+1:i+1]]
            ma = statistics.mean(window)
            std = statistics.stdev(window)
            result.append({
                "date": klines[i]["date"],
                "middle": round(ma, 2),
                "upper": round(ma + 2*std, 2),
                "lower": round(ma - 2*std, 2),
            })
        else:
            result.append({"date": klines[i]["date"], "middle": None, "upper": None, "lower": None})
    return result


def calc_atr(klines, period=14):
    """ATR平均真实波幅"""
    result = []
    tr_list = []
    for i in range(1, len(klines)):
        h, l = klines[i]["high"], klines[i]["low"]
        pc = klines[i-1]["close"]
        tr = max(h - l, abs(h - pc), abs(l - pc))
        tr_list.append(tr)
    
    for i in range(len(klines)):
        if i == 0:
            result.append({"date": klines[i]["date"], "atr": None})
        elif i < period:
            result.append({"date": klines[i]["date"], "atr": round(statistics.mean(tr_list[:i]), 2)})
        else:
            result.append({"date": klines[i]["date"], "atr": round(statistics.mean(tr_list[i-period:i]), 2)})
    return result


def calc_volume_ma(klines, window=5):
    """成交量均线"""
    result = []
    for i in range(len(klines)):
        if i >= window - 1:
            avg = statistics.mean(k["volume"] for k in klines[i-window+1:i+1])
            result.append({"date": klines[i]["date"], "vol_ma": round(avg, 0)})
        else:
            result.append({"date": klines[i]["date"], "vol_ma": None})
    return result


# ════════════════════════════════════════════════════
# 模块4: 分析师一致预期 (东财F10)
# ════════════════════════════════════════════════════

def fetch_analyst_consensus(code="300750"):
    """一致预期EPS + 评级"""
    result = {"eps_forecast": [], "ratings": None}
    try:
        prefix = "SZ" if (code.startswith("0") or code.startswith("3")) else "SH"
        url = f"https://emweb.securities.eastmoney.com/PC_HSF10/ProfitForecast/PageAjax?code={prefix}{code}"
        d = get_json(url)
        
        # EPS预测
        chart = d.get("yctj_chart", [])
        for y in chart:
            eps = y.get("EPS")
            result["eps_forecast"].append({
                "year": y.get("YEAR", ""),
                "mark": y.get("YEAR_MARK", ""),  # A=实际 E=预测
                "eps": float(eps) if eps else None,
                "pe": float(y["PE"]) if y.get("PE") else None,
                "roe": float(y["ROE"]) if y.get("ROE") else None,
                "revenue": float(y["YYTZ"]) if y.get("YYTZ") else None,
            })
        
        # 评级汇总 (pjtj is an array, take the first item)
        pjtj = d.get("pjtj", [])
        if pjtj and isinstance(pjtj, list) and len(pjtj) > 0:
            pj = pjtj[0]
        else:
            pj = d.get("pj", {})
        if pj:
            result["ratings"] = {
                "total": pj.get("RATING_ORG_NUM") or pj.get("total", 0),
                "buy": pj.get("RATING_BUY_NUM") or pj.get("buy", 0),
                "add": pj.get("RATING_ADD_NUM", 0),
                "neutral": pj.get("RATING_NEUTRAL_NUM", 0),
                "reduce": pj.get("RATING_REDUCE_NUM", 0),
                "sell": 0,
                "compre_rating": pj.get("COMPRE_RATING", ""),
                "compre_num": pj.get("COMPRE_RATING_NUM"),
                "target_avg": pj.get("targetPriceAvg") or pj.get("mubjg"),
                "target_high": pj.get("targetPriceHigh") or pj.get("zgmub"),
                "target_low": pj.get("targetPriceLow") or pj.get("zdmub"),
            }
    except:
        pass
    return result


def calc_peg_from_analyst(analyst_eps, current_pe):
    """从一致预期计算PEG"""
    if not analyst_eps or len(analyst_eps) < 2 or not current_pe:
        return None
    
    actual_eps = forecast_eps = None
    for item in analyst_eps:
        eps = item.get("eps")
        if not eps or eps <= 0:
            continue
        if item.get("mark") == "A":
            actual_eps = eps
        elif item.get("mark") == "E" and forecast_eps is None:
            forecast_eps = eps
    
    if not actual_eps or not forecast_eps:
        valid = [i for i in analyst_eps if i.get("eps") and i["eps"] > 0]
        if len(valid) >= 2:
            actual_eps, forecast_eps = valid[0]["eps"], valid[1]["eps"]
        else:
            return None
    
    growth = (forecast_eps - actual_eps) / actual_eps * 100
    peg = round(current_pe / growth, 2) if growth > 0 else None
    return {"growth": round(growth, 1), "peg": peg, "actual_eps": actual_eps, "forecast_eps": forecast_eps}


# ════════════════════════════════════════════════════
# 模块5: 产业链 — 上游/竞争对手/板块
# ════════════════════════════════════════════════════

UPSTREAM = {
    "赣锋锂业": "sz002460", "天齐锂业": "sz002466",
    "华友钴业": "sh603799", "恩捷股份": "sz002812",
    "天赐材料": "sz002709", "当升科技": "sz300073",
}

COMPETITORS = {
    "比亚迪": "sz002594", "亿纬锂能": "sz300014", 
    "国轩高科": "sz002074",
}

PEERS = {
    "宁德时代": "sz300750", "比亚迪": "sz002594", "亿纬锂能": "sz300014",
    "国轩高科": "sz002074", "欣旺达": "sz300207", "孚能科技": "sh688567",
}

SECTORS = {
    "新能源车": "sz399417", "储能": "sh000688",
    "光伏产业": "sh000941", "锂电池": "sh000861",
}

def fetch_batch(stocks_dict):
    """批量获取股价"""
    codes = ",".join(stocks_dict.values())
    result = {}
    try:
        raw = get(f"https://hq.sinajs.cn/list={codes}", "gbk")
        for line in raw.strip().split("\n"):
            m = re.search(r'var hq_str_(\w+)="(.+?)"', line)
            if not m:
                continue
            code = m.group(1)
            name = next((k for k, v in stocks_dict.items() if v == code), code)
            p = m.group(2).split(",")
            if len(p) < 10:
                continue
            prev = float(p[2])
            price = float(p[3]) if p[3] else prev
            result[name] = {
                "price": price,
                "change_pct": round((price - prev) / prev * 100, 2) if prev else 0,
            }
    except:
        pass
    return result


def fetch_sectors():
    """板块指数"""
    codes = ",".join(SECTORS.values())
    result = {}
    try:
        raw = get(f"https://hq.sinajs.cn/list={codes}", "gbk")
        for line in raw.strip().split("\n"):
            m = re.search(r'var hq_str_(\w+)="(.+?)"', line)
            if not m:
                continue
            code = m.group(1)
            name = next((k for k, v in SECTORS.items() if v == code), code)
            p = m.group(2).split(",")
            if len(p) < 10:
                continue
            prev = float(p[2])
            price = float(p[3])
            result[name] = {
                "price": price,
                "change_pct": round((price - prev) / prev * 100, 2) if prev else 0,
            }
    except:
        pass
    return result


# ════════════════════════════════════════════════════
# 模块6: 资金面 (东方财富push2 — 主力资金)
# ════════════════════════════════════════════════════

def fetch_fund_flow():
    """主力资金流向"""
    result = {"today": None, "5day": None}
    try:
        # 当日资金
        url = "https://push2.eastmoney.com/api/qt/stock/fflow/kline/get?lmt=0&klt=1&secid=0.300750&fields1=f1,f2,f3&fields2=f51,f52,f53,f54,f55,f56"
        d = get_json(url)
        klines = d.get("data", {}).get("klines", [])
        if klines:
            today = klines[-1].split(",")
            result["today"] = {
                "date": today[0],
                "main_net": float(today[1]),
                "main_net_pct": float(today[2]) if len(today) > 2 else None,
                "super_large_net": float(today[3]) if len(today) > 3 else None,
                "large_net": float(today[4]) if len(today) > 4 else None,
                "mid_net": float(today[5]) if len(today) > 5 else None,
            }
        
        # 5日累计
        url5 = "https://push2.eastmoney.com/api/qt/stock/fflow/daykline/get?lmt=5&secid=0.300750&fields1=f1,f2&fields2=f51,f52,f53,f54,f55"
        d5 = get_json(url5)
        k5 = d5.get("data", {}).get("klines", [])
        total_main = 0
        for line in k5:
            parts = line.split(",")
            total_main += float(parts[1]) if len(parts) > 1 else 0
        result["5day"] = {"total_main_net": round(total_main, 2)}
    except:
        pass
    return result


# ════════════════════════════════════════════════════
# 模块7: 大宗交易 (新浪)
# ════════════════════════════════════════════════════

def fetch_block_trades():
    """大宗交易记录"""
    result = []
    try:
        raw = get(f"https://vip.stock.finance.sina.com.cn/q/go.php/vInvestConsult/kind/dzjy/index.phtml?symbol=sz300750", 
                  enc="gbk", headers=H_SINA)
        # 提取表格行
        rows = re.findall(r'<tr[^>]*>.*?</tr>', raw, re.DOTALL)
        for row in rows[-10:]:  # 最近10条
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            if len(cells) >= 6:
                try:
                    date_str = re.sub(r'<[^>]+>', '', cells[0]).strip()
                    price_str = re.sub(r'<[^>]+>', '', cells[2]).strip()
                    volume_str = re.sub(r'<[^>]+>', '', cells[3]).strip()
                    amount_str = re.sub(r'<[^>]+>', '', cells[4]).strip()
                    buyer_str = re.sub(r'<[^>]+>', '', cells[5]).strip()
                    seller_str = re.sub(r'<[^>]+>', '', cells[6]).strip() if len(cells) > 6 else ""
                    if date_str and price_str:
                        price = float(price_str.replace(",", ""))
                        volume = float(volume_str.replace(",", ""))
                        amount = float(amount_str.replace(",", ""))
                        result.append({
                            "date": date_str, "price": price,
                            "volume": volume, "amount": amount,
                            "buyer": buyer_str, "seller": seller_str,
                        })
                except:
                    pass
    except:
        pass
    return result[-5:] if result else []


# ════════════════════════════════════════════════════
# 模块8: 新闻资讯 (东方财富)
# ════════════════════════════════════════════════════

def fetch_news():
    """新闻采集 — 多关键词"""
    news = {}
    keywords = {
        "核心": ["宁德时代"],
        "机构": ["宁德时代 评级", "宁德时代 目标价"],
        "行业": ["锂电池 行业", "新能源车 销量"],
        "固态电池": ["固态电池"],
        "储能": ["储能 政策", "储能 项目"],
        "钠电换电": ["钠离子电池", "换电"],
    }
    
    for category, kws in keywords.items():
        items = []
        for kw in kws:
            try:
                url = f"https://search-api-web.eastmoney.com/search/jsonp?cb=jQuery&param=%7B%22uid%22%3A%22%22%2C%22keyword%22%3A%22{urllib.parse.quote(kw)}%22%2C%22type%22%3A%5B%22818%22%5D%2C%22pageIndex%22%3A1%2C%22pageSize%22%3A5%7D"
                raw = fetch_url(url)
                if raw:
                    j = re.search(r'\{.*\}', raw, re.DOTALL)
                    if j:
                        data = json.loads(j.group())
                        for item in data.get("Data", []):
                            items.append({
                                "title": item.get("Title", ""),
                                "time": item.get("ShowTime", ""),
                                "url": item.get("Url", ""),
                            })
            except:
                pass
        news[category] = items[:5]
    
    return news


# ════════════════════════════════════════════════════
# 模块9: 碳酸锂期货 (新浪期货)
# ════════════════════════════════════════════════════

def fetch_lithium():
    """碳酸锂期货价格"""
    result = {"lc": None}
    try:
        raw = get("https://hq.sinajs.cn/list=nf_LC0", "gbk")
        m = re.search(r'"(.+?)"', raw)
        if m:
            p = m.group(1).split(",")
            if len(p) >= 10:
                result["lc"] = {
                    "name": p[0], "price": float(p[3]) if p[3] else None,
                    "prev_close": float(p[7]) if p[7] else None,
                    "open": float(p[5]) if p[5] else None,
                    "high": float(p[6]) if p[6] else None,
                    "low": float(p[8]) if p[8] else None,
                }
                if result["lc"]["price"] and result["lc"]["prev_close"]:
                    result["lc"]["change_pct"] = round(
                        (result["lc"]["price"] - result["lc"]["prev_close"]) / 
                        result["lc"]["prev_close"] * 100, 2)
    except:
        pass
    return result


# ════════════════════════════════════════════════════
# 模块10: 财务数据 (东财F10)
# ════════════════════════════════════════════════════

def fetch_financial_data(code="300750"):
    """财务指标 — ROE/毛利率/净利率/负债率/现金流等 (东财F10新接口)"""
    result = {}
    try:
        prefix = "SZ" if (code.startswith("0") or code.startswith("3")) else "SH"
        # 新F10接口: 主要财务指标
        url = f"https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/ZYZBAjaxNew?type=0&code={prefix}{code}"
        d = get_json(url)
        data_list = d.get("data", [])
        if data_list:
            latest = data_list[0]
            result["report_date"] = latest.get("REPORT_DATE_NAME", "N/A")
            result["report_year"] = latest.get("REPORT_YEAR", "")
            result["roe"] = float(latest["ROEJQ"]) if latest.get("ROEJQ") else None
            result["gross_margin"] = float(latest["XSMLL"]) if latest.get("XSMLL") else None
            result["net_margin"] = float(latest["XSJLL"]) if latest.get("XSJLL") else None
            result["debt_ratio"] = float(latest["ZCFZL"]) if latest.get("ZCFZL") else None
            result["current_ratio"] = float(latest["LD"]) if latest.get("LD") else None
            result["revenue_growth"] = float(latest["TOTALOPERATEREVETZ"]) if latest.get("TOTALOPERATEREVETZ") else None
            result["profit_growth"] = float(latest["PARENTNETPROFITTZ"]) if latest.get("PARENTNETPROFITTZ") else None
            result["eps"] = float(latest["EPSJB"]) if latest.get("EPSJB") else None
            result["bps"] = float(latest["BPS"]) if latest.get("BPS") else None
            result["fcff"] = float(latest["MGJYXJJE"]) if latest.get("MGJYXJJE") else None
            result["revenue"] = float(latest["TOTALOPERATEREVE"]) if latest.get("TOTALOPERATEREVE") else None
            result["net_profit"] = float(latest["PARENTNETPROFIT"]) if latest.get("PARENTNETPROFIT") else None
    except Exception as e:
        pass
    return result


# ════════════════════════════════════════════════════
# 模块11: 北向资金 (东财沪股通)
# ════════════════════════════════════════════════════

def fetch_northbound():
    """北向资金 — CATL持股变化"""
    result = {}
    try:
        # 沪股通 / 深股通持股
        url = "https://push2his.eastmoney.com/api/qt/stock/hsgt10/get?secid=0.300750&fields1=f2,f3&fields2=f12,f14,f3,f2,f9,f17,f18,f121"
        d = get_json(url)
        data = d.get("data", {})
        if data:
            result["hold_shares"] = data.get("f2")  # 持股数量
            result["hold_pct"] = data.get("f3")  # 持股比例
            result["market_cap"] = data.get("f9")  # 持股市值
            result["change_shares"] = data.get("f17")  # 持股变化
            result["change_pct"] = data.get("f18")  # 变化比例
    except:
        pass
    return result


# ════════════════════════════════════════════════════
# 汇总
# ════════════════════════════════════════════════════

def collect_all():
    """采集全部数据"""
    data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "mode": "早报 ☀️" if datetime.now().hour < 14 else "晚报 🌙",
    }
    
    print("📡 核心行情...")
    data["core"] = fetch_core()
    
    print("📊 基本面估值...")
    data["fundamentals"] = fetch_fundamentals()
    
    print("📈 K线+技术指标...")
    klines = fetch_kline(90)
    data["klines"] = klines
    data["ma5"] = calc_ma(klines, 5)
    data["ma20"] = calc_ma(klines, 20)
    data["ma60"] = calc_ma(klines, 60)
    data["macd"] = calc_macd(klines)
    data["rsi"] = calc_rsi(klines)
    data["bollinger"] = calc_bollinger(klines)
    data["atr"] = calc_atr(klines)
    data["volume_ma"] = calc_volume_ma(klines)
    
    print("🔮 分析师一致预期...")
    data["analyst"] = fetch_analyst_consensus()
    if data["analyst"]["eps_forecast"] and data["fundamentals"].get("pe"):
        data["peg"] = calc_peg_from_analyst(data["analyst"]["eps_forecast"], data["fundamentals"]["pe"])
    
    print("🏭 产业链...")
    data["upstream"] = fetch_batch(UPSTREAM)
    data["competitors"] = fetch_batch(COMPETITORS)
    data["peers"] = fetch_batch(PEERS)
    data["sectors"] = fetch_sectors()
    
    print("💰 资金面...")
    data["fund_flow"] = fetch_fund_flow()
    
    print("📦 大宗交易...")
    data["block_trades"] = fetch_block_trades()
    
    print("📰 新闻...")
    data["news"] = fetch_news()
    
    print("⛏️ 碳酸锂...")
    data["lithium"] = fetch_lithium()
    
    print("📋 财务数据...")
    data["financials"] = fetch_financial_data()
    
    print("🌍 北向资金...")
    data["northbound"] = fetch_northbound()
    
    # 保存
    output = os.path.join(os.path.dirname(__file__), "data.json")
    with open(output, "w") as f:
        json.dump(data, f, ensure_ascii=False, default=str)
    
    print(f"\n✅ 数据采集完成 → {output}")
    return data


if __name__ == "__main__":
    import urllib.parse
    collect_all()
