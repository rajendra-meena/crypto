import { Watchlist } from '../components/watchlist/Watchlist';
import { TradingChart } from '../components/chart/TradingChart';
import { AlgoAnalysisPanel } from '../components/analysis/AlgoAnalysisPanel';
import { SignalSection } from '../components/signals/SignalSection';
import { PnlOverview } from '../components/pnl/PnlOverview';
import { ActiveTradePanel } from '../components/positions/ActiveTradePanel';

export default function DashboardPage() {
  return (
    <div className="p-6 space-y-5 max-w-[1700px] mx-auto">
      {/* PnL Stats Bar */}
      <PnlOverview />

      {/* Top 5 Market Watchlist */}
      <Watchlist />

      {/* Main Workspace (Chart + AI Analysis) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2">
          <TradingChart />
        </div>
        <div className="lg:col-span-1">
          <AlgoAnalysisPanel />
        </div>
      </div>

      {/* Active Position Tracking */}
      <ActiveTradePanel />

      {/* 24/7 Algo Signals */}
      <SignalSection />
    </div>
  );
}