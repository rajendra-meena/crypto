import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from app.core.database import paper_db

DEFAULT_TRADING_SETTINGS: Dict[str, Any] = {
    "capital": 10000.0, "riskPerTradePct": 0.75, "maxDailyLossPct": 2.5,
    "maxPortfolioRiskPct": 1.5, "maxConcurrentTrades": 2, "maxSameDirection": 2,
    "maxLeverage": 3.0, "minSetupScore": 68, "maxTradesPerDay": 6,
    "maxConsecutiveLosses": 3, "cooldownMinutes": 20, "atrStopMultiplier": 1.35,
    "minStopPct": 0.20, "maxStopPct": 1.50, "targetRR": 2.0, "breakevenAtR": 1.0,
    "trailingStartR": 1.5, "trailingDistanceR": 0.70, "maxHoldMinutes": 240,
    "minAtrPct": 0.04, "maxAtrPct": 2.50, "minVolumeRatio": 1.0,
    "btcTrendFilter": True, "feeRatePct": 0.05, "slippagePct": 0.02,
    "maxEntryDriftPct": 0.30, "signalRetentionMinutes": 15,
}
TF_MS = {"1m": 60000, "5m": 300000, "15m": 900000}

def now_ms(): return int(time.time() * 1000)
def today_ms():
    n = datetime.now(timezone.utc)
    return int(datetime(n.year, n.month, n.day, tzinfo=timezone.utc).timestamp() * 1000)
def ema(v: List[float], p: int) -> List[float]:
    if not v: return []
    a, out = 2/(p+1), [v[0]]
    for x in v[1:]: out.append(x*a + out[-1]*(1-a))
    return out
def rsi(v: List[float], p=14):
    if len(v) <= p: return 50.0
    g=l=0.0
    for i in range(len(v)-p, len(v)):
        d=v[i]-v[i-1]
        if d>=0: g+=d
        else: l+=abs(d)
    return 100.0 if l==0 else 100-(100/(1+g/max(l,1e-12)))
def atr(c: List[Any], p=14):
    if len(c)<2: return 0.0
    tr=[]
    for i in range(max(1,len(c)-p),len(c)):
        x,y=c[i],c[i-1]
        tr.append(max(float(x.high)-float(x.low),abs(float(x.high)-float(y.close)),abs(float(x.low)-float(y.close))))
    return sum(tr)/len(tr) if tr else 0.0
def price(v):
    return round(v,6) if v<1 else round(v,4) if v<100 else round(v,2)
def trend(closes, fast, slow, slope_n):
    if len(closes)<slow+slope_n: return "NEUTRAL"
    f,s=ema(closes,fast),ema(closes,slow)
    sl=f[-1]-f[-1-slope_n]
    if closes[-1]>f[-1]>s[-1] and sl>0: return "BULLISH"
    if closes[-1]<f[-1]<s[-1] and sl<0: return "BEARISH"
    return "NEUTRAL"

class CryptoStrategyEngine:
    """Single-source backend PAPER strategy. No live exchange order submission."""
    STRATEGY_VERSION = "PA_MTF_V4"
    def __init__(self, market_data_service: Any):
        self.market_data_service=market_data_service
        self.analyses: Dict[str,Dict[str,Any]]={}
        self.latest_signals: Dict[str,Dict[str,Any]]={}
        self.last_trigger: Dict[str,int]={}
        self.positions_by_symbol={str(p.get("symbol")):p for p in paper_db.list_positions()}
        self.last_persist: Dict[str,int]={}
        self.last_scan_ms=0

    def get_settings(self):
        out=dict(DEFAULT_TRADING_SETTINGS); saved=paper_db.get_trading_settings()
        if "minConfidence" in saved and "minSetupScore" not in saved: saved={**saved,"minSetupScore":saved["minConfidence"]}
        out.update({k:v for k,v in saved.items() if k in out}); return out
    def get_analyses(self): return [self.analyses[k] for k in sorted(self.analyses)]
    def get_signals(self):
        cutoff=now_ms()-int(float(self.get_settings()["signalRetentionMinutes"])*60000)
        self.latest_signals={k:v for k,v in self.latest_signals.items() if int(v.get("generatedAt",0))>=cutoff or v.get("status")=="EXECUTED"}
        return sorted(self.latest_signals.values(),key=lambda x:int(x.get("generatedAt",0)),reverse=True)[:20]
    def get_risk_snapshot(self):
        s=self.get_settings(); t=paper_db.list_closed_trades_since(today_ms()); pnl=sum(float(x.get("realizedPnL",0)) for x in t)
        losses=0
        for x in t:
            if float(x.get("realizedPnL",0))<0: losses+=1
            else: break
        open_risk=sum(float(x.get("initialRiskAmount",0)) for x in self.positions_by_symbol.values())
        mdl=float(s["capital"])*float(s["maxDailyLossPct"])/100; mpr=float(s["capital"])*float(s["maxPortfolioRiskPct"])/100
        return {"todayTrades":len(t),"todayRealizedPnL":round(pnl,2),"consecutiveLosses":losses,"openPositions":len(self.positions_by_symbol),"openRisk":round(open_risk,2),"maxDailyLoss":round(mdl,2),"dailyLossRemaining":round(max(0,mdl+pnl),2),"maxPortfolioRisk":round(mpr,2),"engineRunning":paper_db.get_engine_running(),"lastScan":self.last_scan_ms}
    def build_state(self):
        return {"engine_running":paper_db.get_engine_running(),"mode":"PAPER_ONLY","strategy":self.STRATEGY_VERSION,"scanner":{"status":"ACTIVE","lastScan":self.last_scan_ms,"symbols":sorted(self.market_data_service.symbol_states.keys())},"positions":list(self.positions_by_symbol.values()),"closed_trades":paper_db.list_closed_trades(),"executed_signal_ids":paper_db.list_executed_signal_ids(),"analyses":self.get_analyses(),"signals":self.get_signals(),"risk":self.get_risk_snapshot(),"settings":self.get_settings()}

    def _candles(self,symbol,tf,limit):
        st=self.market_data_service.symbol_states.get(symbol)
        if not st: return []
        raw=[c for c in st.get_candles(tf,limit+20) if bool(getattr(c,"is_complete",False))]
        d={int(c.timestamp):c for c in raw}; return [d[k] for k in sorted(d)][-limit:]
    def _fresh(self,c,tf): return bool(c) and now_ms()-int(c[-1].timestamp)<=TF_MS[tf]*2.5
    def _btc(self):
        c=self._candles("BTCUSDT","15m",60)
        return trend([float(x.close) for x in c],20,50,4) if len(c)>=55 else "NEUTRAL"

    def analyze_symbol(self,symbol):
        base={"symbol":symbol,"bias":"WAIT","status":"WATCHING","setupScore":0,"timeframe":"15m/5m/1m","trend":"NEUTRAL","mtfTrend":"NEUTRAL","setup":"NONE","trigger":"NONE","rsi":50.0,"atrPct":0.0,"volumeRatio":0.0,"bodyQuality":0.0,"support":0.0,"resistance":0.0,"blockers":[],"reason":"Waiting for enough completed candles","triggerCandleTime":0,"referencePrice":0.0,"atr":0.0,"updatedAt":now_ms()}
        c15,c5,c1=self._candles(symbol,"15m",60),self._candles(symbol,"5m",50),self._candles(symbol,"1m",35)
        if len(c15)<55 or len(c5)<30 or len(c1)<22: return base
        if not (self._fresh(c15,"15m") and self._fresh(c5,"5m") and self._fresh(c1,"1m")): return {**base,"status":"BLOCKED","blockers":["STALE_COMPLETED_CANDLES"],"reason":"Completed candle data is stale"}
        cl15,cl5=[float(x.close) for x in c15],[float(x.close) for x in c5]
        t15,t5=trend(cl15,20,50,4),trend(cl5,9,21,3)
        side="BUY" if t15==t5=="BULLISH" else "SELL" if t15==t5=="BEARISH" else "WAIT"
        cur,prev=c1[-1],c1[-2]; w=c1[-9:-1]; ph=max(float(x.high) for x in w); pl=min(float(x.low) for x in w)
        e9,e21=ema(cl5,9),ema(cl5,21); zone=(min(e9[-1],e21[-1]),max(e9[-1],e21[-1])); touched=any(float(x.low)<=zone[1] and float(x.high)>=zone[0] for x in c1[-3:])
        bull_bo=float(cur.close)>ph and float(cur.close)>float(prev.high); bear_bo=float(cur.close)<pl and float(cur.close)<float(prev.low)
        bull_pb=touched and float(cur.close)>float(cur.open) and float(cur.close)>float(prev.high); bear_pb=touched and float(cur.close)<float(cur.open) and float(cur.close)<float(prev.low)
        setup=trigger_name="NONE"
        if side=="BUY" and bull_bo: setup,trigger_name="BREAKOUT","LONG_CONFIRM"
        elif side=="SELL" and bear_bo: setup,trigger_name="BREAKDOWN","SHORT_CONFIRM"
        elif side=="BUY" and bull_pb: setup,trigger_name="PULLBACK_RECLAIM","LONG_CONFIRM"
        elif side=="SELL" and bear_pb: setup,trigger_name="PULLBACK_REJECT","SHORT_CONFIRM"
        a=atr(c5,14); ap=a/max(float(c5[-1].close),1e-12)*100; rv=rsi(cl5,14); sup=min(float(x.low) for x in c5[-12:]); res=max(float(x.high) for x in c5[-12:])
        vols=[float(x.volume or 0) for x in c1[-21:-1]]; av=sum(vols)/len(vols) if vols else 0; vr=float(cur.volume or 0)/av if av>0 else 1.0
        rng=max(float(cur.high)-float(cur.low),1e-12); bq=abs(float(cur.close)-float(cur.open))/rng; db=(side=="BUY" and float(cur.close)>float(cur.open)) or (side=="SELL" and float(cur.close)<float(cur.open))
        s=self.get_settings(); score=0; reasons=[]; blockers=[]
        if t15!="NEUTRAL": score+=20; reasons.append("15m regime")
        else: blockers.append("15M_REGIME_NEUTRAL")
        if side!="WAIT": score+=20; reasons.append("5m trend aligned")
        else: blockers.append("5M_TREND_NOT_ALIGNED")
        if trigger_name!="NONE": score+=25; reasons.append("1m completed trigger")
        else: blockers.append("NO_1M_TRIGGER")
        rok=(50<=rv<=74) if side=="BUY" else (26<=rv<=50) if side=="SELL" else False
        if rok: score+=10; reasons.append("RSI confirms")
        if vr>=float(s["minVolumeRatio"]): score+=10; reasons.append("volume confirms")
        elif vr>=0.8: score+=5; reasons.append("volume acceptable")
        if bq>=0.55 and db: score+=10; reasons.append("strong trigger body")
        elif bq>=0.35 and db: score+=5; reasons.append("acceptable trigger body")
        vok=float(s["minAtrPct"])<=ap<=float(s["maxAtrPct"])
        if vok: score+=5; reasons.append("ATR regime valid")
        else: blockers.append("VOLATILITY_OUT_OF_RANGE")
        if bool(s["btcTrendFilter"]) and symbol!="BTCUSDT" and side!="WAIT":
            bt=self._btc()
            if (side=="BUY" and bt=="BEARISH") or (side=="SELL" and bt=="BULLISH"): blockers.append("BTC_REGIME_CONFLICT")
        hard={"15M_REGIME_NEUTRAL","5M_TREND_NOT_ALIGNED","NO_1M_TRIGGER","VOLATILITY_OUT_OF_RANGE","BTC_REGIME_CONFLICT"}
        ready=side!="WAIT" and trigger_name!="NONE" and score>=int(s["minSetupScore"]) and not any(x in hard for x in blockers)
        status="READY" if ready else "FILTERED" if side!="WAIT" or trigger_name!="NONE" else "WATCHING"
        reason=" · ".join(reasons) if reasons else "Waiting for multi-timeframe alignment"
        if blockers: reason+=" | "+", ".join(blockers)
        return {**base,"bias":side,"status":status,"setupScore":min(100,score),"trend":t15,"mtfTrend":t5,"setup":setup,"trigger":trigger_name,"rsi":round(rv,1),"atrPct":round(ap,3),"volumeRatio":round(vr,2),"bodyQuality":round(bq,2),"support":price(sup),"resistance":price(res),"blockers":blockers,"reason":reason,"triggerCandleTime":int(cur.timestamp),"referencePrice":float(cur.close),"atr":a,"updatedAt":now_ms()}

    def _risk(self,symbol,side)->Tuple[Optional[str],Dict[str,Any]]:
        s=self.get_settings(); r=self.get_risk_snapshot()
        if float(r["todayRealizedPnL"])<=-float(r["maxDailyLoss"]): paper_db.set_engine_running(False,now_ms()); return "MAX_DAILY_LOSS",r
        if int(r["consecutiveLosses"])>=int(s["maxConsecutiveLosses"]): paper_db.set_engine_running(False,now_ms()); return "MAX_CONSECUTIVE_LOSSES",r
        if int(r["todayTrades"])>=int(s["maxTradesPerDay"]): return "MAX_TRADES_PER_DAY",r
        if symbol in self.positions_by_symbol: return "POSITION_ALREADY_OPEN",r
        if len(self.positions_by_symbol)>=int(s["maxConcurrentTrades"]): return "MAX_CONCURRENT_TRADES",r
        if sum(1 for p in self.positions_by_symbol.values() if str(p.get("side"))==side)>=int(s["maxSameDirection"]): return "MAX_SAME_DIRECTION_EXPOSURE",r
        if float(r["openRisk"])>=float(r["maxPortfolioRisk"]): return "MAX_PORTFOLIO_RISK",r
        last=paper_db.get_last_closed_trade(symbol); cd=int(float(s["cooldownMinutes"])*60000)
        if last and now_ms()-int(last.get("closedAt",0))<cd: return "COOLDOWN",r
        return None,r

    def _signal(self,a,status,suffix=None):
        s=self.get_settings(); symbol=str(a["symbol"]); side=str(a["bias"]); st=self.market_data_service.symbol_states.get(symbol); raw=float(st.current_price) if st else 0.0
        slip=float(s["slippagePct"])/100; entry=raw*(1+slip if side=="BUY" else 1-slip)
        sd=max(float(a["atr"])*float(s["atrStopMultiplier"]),raw*float(s["minStopPct"])/100)
        maxd=raw*float(s["maxStopPct"])/100; final=status; extra=suffix
        if raw<=0: final,extra="BLOCKED","NO_LIVE_PRICE"
        elif sd<=0: final,extra="FILTERED","INVALID_STOP_DISTANCE"
        elif maxd>0 and sd>maxd: final,extra="FILTERED","STOP_TOO_WIDE"
        stop=entry-sd if side=="BUY" else entry+sd; target=entry+sd*float(s["targetRR"]) if side=="BUY" else entry-sd*float(s["targetRR"])
        reason=str(a["reason"])+(f" | {extra}" if extra else "")
        return {"id":f"{self.STRATEGY_VERSION}-{symbol}-{a['triggerCandleTime']}-{side}","symbol":symbol,"side":side,"timeframe":"15m/5m/1m","entry":price(entry),"stopLoss":price(stop),"target1":price(target),"target2":price(target),"riskReward":f"1:{float(s['targetRR']):g}","confidence":int(a["setupScore"]),"setupScore":int(a["setupScore"]),"generatedTime":datetime.fromtimestamp(int(a["triggerCandleTime"])/1000,tz=timezone.utc).strftime("%H:%M:%S UTC"),"generatedAt":int(a["triggerCandleTime"]),"reason":reason,"status":final,"initialRisk":price(sd)}

    async def scan_all_symbols(self):
        self.last_scan_ms=now_ms()
        for symbol in list(self.market_data_service.symbol_states.keys()): await self.evaluate_symbol(symbol)
    async def on_completed_candle(self,symbol): await self.evaluate_symbol(symbol)
    async def evaluate_symbol(self,symbol):
        a=self.analyze_symbol(symbol); self.analyses[symbol]=a; trig=int(a.get("triggerCandleTime",0))
        if trig<=0 or a.get("trigger")=="NONE" or a.get("bias")=="WAIT" or self.last_trigger.get(symbol)==trig: return
        self.last_trigger[symbol]=trig; sig=self._signal(a,"READY" if a["status"]=="READY" else "FILTERED")
        if a["status"]!="READY": self.latest_signals[symbol]=sig; return
        if not paper_db.get_engine_running(): sig["status"]="BLOCKED"; sig["reason"]+=" | ENGINE_OFF"; self.latest_signals[symbol]=sig; return
        st=self.market_data_service.symbol_states.get(symbol)
        if not st or float(st.current_price)<=0: sig["status"]="BLOCKED"; sig["reason"]+=" | NO_LIVE_PRICE"; self.latest_signals[symbol]=sig; return
        ref=float(a["referencePrice"]); drift=abs(float(st.current_price)-ref)/max(ref,1e-12)*100
        if drift>float(self.get_settings()["maxEntryDriftPct"]): sig["status"]="FILTERED"; sig["reason"]+=" | ENTRY_DRIFT_TOO_LARGE"; self.latest_signals[symbol]=sig; return
        block,risk=self._risk(symbol,str(a["bias"]))
        if block: sig["status"]="BLOCKED"; sig["reason"]+=f" | {block}"; self.latest_signals[symbol]=sig; return
        if sig["status"]=="FILTERED": self.latest_signals[symbol]=sig; return
        if str(sig["id"]) in paper_db.list_executed_signal_ids(): sig["status"]="EXECUTED"; self.latest_signals[symbol]=sig; return
        s=self.get_settings(); entry=float(sig["entry"]); stop=float(sig["stopLoss"]); ir=abs(entry-stop)
        req=float(s["capital"])*float(s["riskPerTradePct"])/100; rem=max(0,float(risk["maxPortfolioRisk"])-float(risk["openRisk"])); ra=min(req,rem)
        if ir<=0 or ra<=0: sig["status"]="BLOCKED"; sig["reason"]+=" | INVALID_RISK_OR_PORTFOLIO_LIMIT"; self.latest_signals[symbol]=sig; return
        qty=ra/ir; notional=qty*entry; cap=float(s["capital"])*float(s["maxLeverage"])
        if notional>cap: notional=cap; qty=notional/max(entry,1e-12)
        actual=ir*qty; n=now_ms(); pos={"id":f"POS-{symbol}-{n}","signalId":sig["id"],"strategyVersion":self.STRATEGY_VERSION,"symbol":symbol,"side":a["bias"],"entryPrice":entry,"currentPrice":float(st.current_price),"stopLoss":stop,"initialStopLoss":stop,"target1":float(sig["target1"]),"target2":float(sig["target2"]),"initialRisk":price(ir),"initialRiskAmount":round(actual,2),"atrAtEntry":float(a["atr"]),"leverage":float(s["maxLeverage"]),"quantity":round(qty,8),"size":round(notional,2),"margin":round(notional/max(float(s["maxLeverage"]),1),2),"unrealizedPnL":0.0,"unrealizedPnLPercent":0.0,"rMultiple":0.0,"breakEvenActivated":False,"trailingActivated":False,"openedAt":n,"lastUpdated":n,"setupScore":int(a["setupScore"]),"reason":a["reason"]}
        self.positions_by_symbol[symbol]=pos; paper_db.upsert_position(pos); paper_db.mark_signal_executed(str(sig["id"]),symbol,n); sig["status"]="EXECUTED"; self.latest_signals[symbol]=sig

    def _close(self,symbol,raw,reason):
        p=self.positions_by_symbol.get(symbol)
        if not p: return None
        s=self.get_settings(); side=str(p["side"]); entry=float(p["entryPrice"]); qty=float(p.get("quantity",0)); slip=float(s["slippagePct"])/100; ex=raw*(1-slip if side=="BUY" else 1+slip)
        gross=(ex-entry)*qty if side=="BUY" else (entry-ex)*qty; fr=float(s["feeRatePct"])/100; fees=(entry*qty+ex*qty)*fr; realized=gross-fees; ira=max(float(p.get("initialRiskAmount",0)),1e-12); capital=max(float(s["capital"]),1e-12); n=now_ms()
        t={"id":f"CLOSED-{p['id']}","signalId":p.get("signalId"),"strategyVersion":p.get("strategyVersion",self.STRATEGY_VERSION),"symbol":symbol,"side":side,"entryPrice":entry,"exitPrice":price(ex),"size":float(p.get("size",entry*qty)),"quantity":qty,"leverage":float(p.get("leverage",1)),"realizedPnL":round(realized,2),"realizedPnLPercent":round(realized/capital*100,3),"realizedR":round(realized/ira,3),"fees":round(fees,2),"exitReason":reason,"openedAt":int(p["openedAt"]),"closedAt":n,"durationSeconds":max(0,(n-int(p["openedAt"]))//1000),"isWin":realized>0}
        paper_db.save_closed_trade(t); paper_db.delete_position(str(p["id"])); self.positions_by_symbol.pop(symbol,None); self.last_persist.pop(symbol,None); return t
    def close_position_manually(self,position_id):
        p=next((x for x in self.positions_by_symbol.values() if str(x.get("id"))==position_id),None)
        if not p: return None
        st=self.market_data_service.symbol_states.get(str(p["symbol"])); return self._close(str(p["symbol"]),float(st.current_price),"MANUAL") if st and float(st.current_price)>0 else None
    async def on_tick(self,symbol,px):
        p=self.positions_by_symbol.get(symbol)
        if not p: return
        s=self.get_settings(); side=str(p["side"]); entry=float(p["entryPrice"]); qty=float(p.get("quantity",0)); ir=max(float(p.get("initialRisk",abs(entry-float(p["stopLoss"])))),1e-12); fav=px-entry if side=="BUY" else entry-px; rm=fav/ir
        if rm>=float(s["breakevenAtR"]):
            fb=entry*float(s["feeRatePct"])/100*2; be=entry+fb if side=="BUY" else entry-fb
            if (side=="BUY" and be>float(p["stopLoss"])) or (side=="SELL" and be<float(p["stopLoss"])): p["stopLoss"]=price(be); p["breakEvenActivated"]=True
        if rm>=float(s["trailingStartR"]):
            tr=ir*float(s["trailingDistanceR"]); ts=px-tr if side=="BUY" else px+tr
            if (side=="BUY" and ts>float(p["stopLoss"])) or (side=="SELL" and ts<float(p["stopLoss"])): p["stopLoss"]=price(ts); p["trailingActivated"]=True
        stop,target=float(p["stopLoss"]),float(p["target1"])
        if (side=="BUY" and px<=stop) or (side=="SELL" and px>=stop): self._close(symbol,px,"TRAILING_STOP" if p.get("trailingActivated") else "BREAK_EVEN" if p.get("breakEvenActivated") else "STOP_LOSS"); return
        if (side=="BUY" and px>=target) or (side=="SELL" and px<=target): self._close(symbol,px,"TARGET"); return
        if now_ms()-int(p["openedAt"])>=int(float(s["maxHoldMinutes"])*60000): self._close(symbol,px,"TIME_EXIT"); return
        gross=(px-entry)*qty if side=="BUY" else (entry-px)*qty; fr=float(s["feeRatePct"])/100; unreal=gross-(entry*qty+px*qty)*fr; capital=max(float(s["capital"]),1e-12)
        p.update({"currentPrice":price(px),"unrealizedPnL":round(unreal,2),"unrealizedPnLPercent":round(unreal/capital*100,3),"rMultiple":round(rm,2),"lastUpdated":now_ms()})
        if now_ms()-self.last_persist.get(symbol,0)>=750: paper_db.upsert_position(p); self.last_persist[symbol]=now_ms()
