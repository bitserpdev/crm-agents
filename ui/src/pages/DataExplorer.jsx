import { useEffect, useState, useCallback } from "react";
import { getRawEvents, getDataStats } from "../api/client";
import { Search, Database, RefreshCw, ChevronLeft, ChevronRight, Filter } from "lucide-react";

const STATUS_COLORS = {
  done:      "bg-green-900/50 text-green-300",
  duplicate: "bg-yellow-900/50 text-yellow-300",
  new:       "bg-blue-900/50 text-blue-300",
  failed:    "bg-red-900/50 text-red-300",
  skipped:   "bg-gray-800 text-gray-400",
};

export default function DataExplorer() {
  const [records, setRecords]   = useState([]);
  const [stats, setStats]       = useState([]);
  const [total, setTotal]       = useState(0);
  const [loading, setLoading]   = useState(false);
  const [expanded, setExpanded] = useState(null);

  // Filters
  const [platform, setPlatform] = useState("");
  const [status, setStatus]     = useState("");
  const [search, setSearch]     = useState("");
  const [limit]                 = useState(20);
  const [offset, setOffset]     = useState(0);

  const loadStats   = () => getDataStats().then(r => setStats(r.data));
  const loadRecords = useCallback(() => {
    setLoading(true);
    getRawEvents({ platform: platform||undefined, status: status||undefined, limit, offset })
      .then(r => { setRecords(r.data.records); setTotal(r.data.total); })
      .finally(() => setLoading(false));
  }, [platform, status, limit, offset]);

  useEffect(() => { loadStats(); }, []);
  useEffect(() => { setOffset(0); }, [platform, status]);
  useEffect(() => { loadRecords(); }, [loadRecords]);

  const filtered = search.trim()
    ? records.filter(r => {
        const p = r.raw_payload || {};
        const text = [p.name, p.title, p.headline, p.company, p.email, r.source_platform]
          .filter(Boolean).join(" ").toLowerCase();
        return text.includes(search.toLowerCase());
      })
    : records;

  const page     = Math.floor(offset / limit) + 1;
  const prevPage = () => setOffset(o => Math.max(0, o - limit));
  const nextPage = () => setOffset(o => o + limit);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-white">Data Explorer</h2>
          <p className="text-sm text-gray-500 mt-0.5">Browse and filter all extracted records</p>
        </div>
        <button onClick={() => { loadRecords(); loadStats(); }}
          className="flex items-center gap-2 bg-gray-800 hover:bg-gray-700 px-3 py-2 rounded-lg text-sm transition-colors">
          <RefreshCw size={14}/> Refresh
        </button>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {stats.length === 0 ? (
          <div className="col-span-3 bg-gray-900 border border-gray-800 rounded-xl p-4 text-center text-gray-600 text-sm">No data yet</div>
        ) : stats.map(s => (
          <div key={s.source_platform} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <Database size={14} className="text-indigo-400"/>
              <span className="text-xs text-gray-400 uppercase font-medium capitalize">{s.source_platform}</span>
            </div>
            <div className="text-3xl font-bold text-white">{s.total_events}</div>
            <div className="flex gap-3 mt-2 text-xs text-gray-500">
              <span className="text-green-400">{s.done} done</span>
              <span className="text-yellow-400">{s.duplicates} dupes</span>
            </div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <div className="relative flex-1 min-w-48">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500"/>
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search by name, title, company..."
            className="w-full bg-gray-900 border border-gray-700 rounded-lg pl-8 pr-4 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"/>
        </div>
        <div className="flex items-center gap-2">
          <Filter size={13} className="text-gray-500"/>
          <select value={platform} onChange={e => setPlatform(e.target.value)}
            className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500">
            <option value="">All platforms</option>
            <option value="linkedin">LinkedIn</option>
          </select>
          <select value={status} onChange={e => setStatus(e.target.value)}
            className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500">
            <option value="">All statuses</option>
            <option value="done">Done</option>
            <option value="new">New</option>
            <option value="duplicate">Duplicate</option>
            <option value="failed">Failed</option>
          </select>
        </div>
      </div>

      {/* Records table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-800 text-xs text-gray-500 uppercase tracking-wider">
              <th className="text-left px-4 py-3">Type</th>
              <th className="text-left px-4 py-3">Name / Title</th>
              <th className="text-left px-4 py-3">Company</th>
              <th className="text-left px-4 py-3">Location</th>
              <th className="text-left px-4 py-3">Intent</th>
              <th className="text-left px-4 py-3">Status</th>
              <th className="text-left px-4 py-3">Received</th>
              <th className="text-left px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-600 text-sm">Loading...</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-600 text-sm">No records found.</td></tr>
            ) : filtered.map(r => {
              const p = r.raw_payload || {};
              const isExp = expanded === r.event_id;
              const intent = p.intent_score;
              const intentColor = intent >= 0.7 ? "text-green-400" : intent >= 0.4 ? "text-yellow-400" : "text-gray-500";
              return [
                <tr key={r.event_id}
                  className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors cursor-pointer"
                  onClick={() => setExpanded(isExp ? null : r.event_id)}>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize
                      ${p.type === "job" ? "bg-purple-900/50 text-purple-300" : "bg-blue-900/50 text-blue-300"}`}>
                      {p.type || "unknown"}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <p className="text-sm text-white font-medium truncate max-w-48">
                      {p.name || p.clean_title || p.title || "—"}
                    </p>
                    <p className="text-xs text-gray-500 truncate max-w-48">{p.headline || p.title || ""}</p>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-400 truncate max-w-32">{p.company || "—"}</td>
                  <td className="px-4 py-3 text-xs text-gray-500 truncate max-w-28">
                    {typeof p.location === "object" ? p.location?.city || p.location?.raw || "—" : p.location || "—"}
                  </td>
                  <td className="px-4 py-3">
                    {intent != null
                      ? <span className={`text-xs font-mono font-bold ${intentColor}`}>{Number(intent).toFixed(1)}</span>
                      : <span className="text-gray-600 text-xs">—</span>}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[r.processing_status] || "bg-gray-800 text-gray-400"}`}>
                      {r.processing_status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">{new Date(r.received_at).toLocaleString()}</td>
                  <td className="px-4 py-3 text-gray-600 text-xs">{isExp ? "▲" : "▼"}</td>
                </tr>,
                isExp && (
                  <tr key={`${r.event_id}-detail`} className="border-b border-gray-800">
                    <td colSpan={8} className="px-4 pb-4 pt-2 bg-gray-800/40">
                      <div className="grid grid-cols-2 gap-4 text-xs">
                        <div className="space-y-1.5">
                          <p className="font-semibold text-gray-300 mb-2">Record Details</p>
                          {[["Event ID", r.event_id],["Platform", r.source_platform],["Type", p.type],
                            ["Name", p.name],["Email", p.email || "—"],["Company", p.company],
                            ["Headline", p.headline],["Summary", p.summary]
                          ].map(([k,v]) => v && (
                            <div key={k} className="flex gap-2">
                              <span className="text-gray-500 w-20 shrink-0">{k}:</span>
                              <span className="text-gray-300 break-all">{v}</span>
                            </div>
                          ))}
                        </div>
                        <div className="space-y-1.5">
                          <p className="font-semibold text-gray-300 mb-2">AI Enrichment</p>
                          {[["Intent Score", intent != null ? Number(intent).toFixed(2) : "—"],
                            ["Clean Title", p.clean_title],
                            ["Tags", Array.isArray(p.tags) ? p.tags.join(", ") : p.tags],
                            ["Skills", Array.isArray(p.skills) ? p.skills.slice(0,5).join(", ") : "—"],
                            ["Open to Work", p.open_to_work != null ? String(p.open_to_work) : "—"],
                            ["Connections", p.connections],
                            ["Profile URL", p.profile_url || p.url]
                          ].map(([k,v]) => v && (
                            <div key={k} className="flex gap-2">
                              <span className="text-gray-500 w-24 shrink-0">{k}:</span>
                              <span className="text-gray-300 break-all">{String(v)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </td>
                  </tr>
                )
              ];
            })}
          </tbody>
        </table>

        {/* Pagination */}
        {!loading && filtered.length > 0 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-800">
            <p className="text-xs text-gray-500">
              Showing {offset + 1}–{Math.min(offset + limit, offset + filtered.length)} · Page {page}
            </p>
            <div className="flex gap-2">
              <button onClick={prevPage} disabled={offset === 0}
                className="flex items-center gap-1 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded text-xs transition-colors disabled:opacity-40">
                <ChevronLeft size={12}/> Prev
              </button>
              <button onClick={nextPage} disabled={filtered.length < limit}
                className="flex items-center gap-1 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded text-xs transition-colors disabled:opacity-40">
                Next <ChevronRight size={12}/>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
