import React, { useState, useEffect, useMemo } from 'react';

export default function App() {
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState('ALL');
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedChart, setSelectedChart] = useState(null);

  const ITEMS_PER_PAGE = 8;
  
  // Replace with your API Gateway endpoint or local mock URL
  const API_ENDPOINT = "https://YOURAPIIDHERE.execute-api.us-east-2.amazonaws.com/signals";

  useEffect(() => {
    fetchSignals();
  }, []);

  const fetchSignals = async () => {
    setLoading(true);
    try {
      const res = await fetch(API_ENDPOINT);
      const data = await res.json();
      // Handle both a raw array and wrapped responses like { signals: [] } or { Items: [] }
      const items = Array.isArray(data)
        ? data
        : data.signals ?? data.Items ?? data.items ?? data.data ?? [];
      setSignals(items);
    } catch (err) {
      console.error("Failed to load signals:", err);
    } finally {
      setLoading(false);
    }
  };

  // Filter & Search Logic
  const filteredSignals = useMemo(() => {
    return signals
      .filter((item) => {
        const matchesSymbol = item.Symbol.toLowerCase().includes(searchTerm.toLowerCase());
        const isBuy = item.SignalType?.toUpperCase().includes('BUY');
        const isSell = item.SignalType?.toUpperCase().includes('SELL');

        if (filterType === 'BUY') return matchesSymbol && isBuy;
        if (filterType === 'SELL') return matchesSymbol && isSell;
        return matchesSymbol;
      })
      .sort((a, b) => (b.Date || '').localeCompare(a.Date || ''));
  }, [signals, searchTerm, filterType]);

  // Pagination Logic
  const totalPages = Math.ceil(filteredSignals.length / ITEMS_PER_PAGE) || 1;
  const paginatedSignals = useMemo(() => {
    const start = (currentPage - 1) * ITEMS_PER_PAGE;
    return filteredSignals.slice(start, start + ITEMS_PER_PAGE);
  }, [filteredSignals, currentPage]);

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 p-6 font-sans">
      <div className="max-w-7xl mx-auto">
        
        {/* Header */}
        <header className="flex flex-col md:flex-row justify-between items-start md:items-center pb-6 border-b border-slate-800 gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-white flex items-center gap-2">
              Trading Signals Dashboard
            </h1>
            <p className="text-slate-400 text-sm mt-1">
              Automated end-of-day scanner
            </p>
          </div>
          <button 
            onClick={fetchSignals} 
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg font-medium transition text-sm flex items-center gap-2 shadow-lg shadow-indigo-600/20"
          >
            Refresh ⭮
          </button>
        </header>

        {/* Controls: Search & Filters */}
        <div className="flex flex-col sm:flex-row gap-4 my-6 justify-between items-center bg-slate-800/60 p-4 rounded-xl border border-slate-700/50">
          <div className="flex items-center gap-3 w-full sm:w-auto">
            <input
              type="text"
              placeholder="Search ticker (e.g. SPY)..."
              value={searchTerm}
              onChange={(e) => { setSearchTerm(e.target.value); setCurrentPage(1); }}
              className="bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 w-full sm:w-64"
            />
            <div className="flex bg-slate-900 rounded-lg p-1 border border-slate-700 text-xs font-semibold">
              {['ALL', 'BUY', 'SELL'].map((type) => (
                <button
                  key={type}
                  onClick={() => { setFilterType(type); setCurrentPage(1); }}
                  className={`px-3 py-1.5 rounded-md transition ${
                    filterType === type ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {type}
                </button>
              ))}
            </div>
          </div>
          <div className="text-xs text-slate-400">
            Showing <span className="text-white font-medium">{filteredSignals.length}</span> total signals
          </div>
        </div>

        {/* Table / Results Grid */}
        {loading ? (
          <div className="flex justify-center items-center h-64 text-slate-400">
            <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-indigo-500 mr-3"></div>
            Loading database records...
          </div>
        ) : paginatedSignals.length === 0 ? (
          <div className="text-center py-20 bg-slate-800/30 rounded-xl border border-dashed border-slate-700 text-slate-500">
            No signals match your filter criteria.
          </div>
        ) : (
          <div className="overflow-x-auto bg-slate-800/40 rounded-xl border border-slate-800 shadow-xl">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-700/60 bg-slate-800/80 text-xs uppercase tracking-wider text-slate-400">
                  <th className="py-3 px-4">Symbol</th>
                  <th className="py-3 px-4">Date</th>
                  <th className="py-3 px-4">Signal</th>
                  <th className="py-3 px-4">Close</th>
                  <th className="py-3 px-4 text-center">Technical Chart</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-sm">
                {paginatedSignals.map((item, idx) => {
                  const isBuy = item.SignalType?.toUpperCase().includes('BUY');
                  const cleanSignal = item.SignalType?.replace(/[-_]/g, '').trim();

                  return (
                    <tr key={`${item.Symbol}-${item.Date}-${idx}`} className="hover:bg-slate-800/50 transition">
                      <td className="py-3 px-4 font-bold text-white tracking-wide">{item.Symbol}</td>
                      <td className="py-3 px-4 text-slate-400 font-mono text-xs">{item.Date}</td>
                      <td className="py-3 px-4">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${
                          isBuy 
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                            : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                        }`}>
                          {
                          isBuy 
                            ? 'BUY' 
                            : 'SELL'
                          }
                        </span>
                      </td>
                      <td className="py-3 px-4 font-mono text-slate-200">${item.ClosePrice}</td>
                      <td className="py-3 px-4 text-center">
                        {item.ChartImageURL && item.ChartImageURL !== 'None' ? (
                          <button
                            onClick={() => setSelectedChart({ symbol: item.Symbol, url: item.ChartImageURL, date: item.Date, signal: cleanSignal })}
                            className="inline-flex items-center gap-1 text-xs bg-slate-700 hover:bg-slate-600 text-slate-200 px-3 py-1.5 rounded-md transition border border-slate-600"
                          >
                            Chart 🔎︎
                          </button>
                        ) : (
                          <span className="text-slate-600 text-xs italic">N/A</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Navigation */}
        {totalPages > 1 && (
          <div className="flex justify-between items-center mt-6">
            <button
              disabled={currentPage === 1}
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              className="px-3 py-1.5 text-xs bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg border border-slate-700 transition"
            >
              ⮜ Previous
            </button>
            <span className="text-xs text-slate-400">
              Page <span className="text-white font-medium">{currentPage}</span> of <span className="text-white font-medium">{totalPages}</span>
            </span>
            <button
              disabled={currentPage === totalPages}
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              className="px-3 py-1.5 text-xs bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg border border-slate-700 transition"
            >
              Next ⮞
            </button>
          </div>
        )}

        {/* Modal for Chart Previews */}
        {selectedChart && (
          <div 
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
            onClick={() => setSelectedChart(null)}
          >
            <div 
              className="bg-slate-900 border border-slate-700 rounded-2xl max-w-4xl w-full p-6 shadow-2xl relative flex flex-col gap-4"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex justify-between items-center border-b border-slate-800 pb-3">
                <div>
                  <h3 className="text-lg font-bold text-white flex items-center gap-2">
                    {selectedChart.symbol} <span className="text-xs text-slate-400 font-mono">({selectedChart.date})</span>
                  </h3>
                  <span className="text-xs text-indigo-400 font-semibold">{
                  selectedChart.signal?.toUpperCase().includes('BUY')
                  ? 'BUY: RSI(4) Oversold' 
                  : 'SELL: RSI(4) Overbought'
                  }</span>
                </div>
                <button 
                  onClick={() => setSelectedChart(null)} 
                  className="text-slate-400 hover:text-white text-xl p-1"
                >
                  ✖
                </button>
              </div>

              <div className="overflow-hidden rounded-lg bg-black flex justify-center items-center border border-slate-800 max-h-[70vh]">
                <img 
                  src={selectedChart.url} 
                  alt={`${selectedChart.symbol} chart`}
                  className="w-full h-auto object-contain max-h-[70vh]" 
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <a
                  href={selectedChart.url}
                  target="_blank"
                  rel="noreferrer"
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-xs font-medium rounded-lg border border-slate-700 transition"
                >
                  New Tab 🗖
                </a>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}