import { useEffect, useState, useCallback } from "react";
import { getCrmLeads } from "../api/client";
import { Search, TrendingUp, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";

const STATUS_COLORS = {
  new:          "bg-blue-900/50 text-blue-300",
  contacted:    "bg-indigo-900/50 text-indigo-300",
  qualified:    "bg-green-900/50 text-green-300",
  unqualified:  "bg-red-900/50 text-red-300",
  converted:    "bg-purple-900/50 text-purple-300",
};

export default function Leads() {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch]   = useState("");
  const [status, setStatus]   = useState("");
  const [expanded, setExpanded] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    getCrmLeads({ search: search || undefined, status: status || undefined, limit: 50 })
      .then(r => setRecords(r.data.records))
      .finally(() => setLoading(false));
  }, [search, status]);

  useEffect(() => { load(); }, [load]);

  const avgScore = records.length
    ? Math.round(records.reduce((a,r) => a + (r.lead_score||0), 0) / records.length)
    : 0;
  const highIntent = records.filter(r => (r.intent_score||0) >= 0.7).length;

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-white">Leads</h2>
          <p className="text-sm text-gray-500 mt-0.5">Leads created from LinkedIn jobs and profiles</p>
        </div>
        <button onClick={load} className="flex items-center gap-2 bg-gray-800 hover:bg-gray-700 px-3 py-2 rounded-lg text-sm transition-colors">
          <RefreshCw size={14}/> Refresh
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          ["Total Leads",   records.length,  "text-white"],
          ["New",           records.filter(r=>r.lead_status==="new").length, "text-blue-400"],
          ["High Intent",   highIntent,       "text-green-400"],
          ["Avg Score",     avgScore,         "text-indigo-400"],
        ].map(([label, val, color]) => (
          <div key={label} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <p className="text-xs text-gray-500 mb-1">{label}</p>
            <p className={`text-2xl font-bold ${color}`}>{val}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <div className="relative flex-1">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500"/>
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search by name or title..."
            className="w-full bg-gray-900 border border-gray-700 rounded-lg pl-8 pr-4 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"/>
        </div>
        <select value={status} onChange={e => setStatus(e.target.value)}
          className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500">
          <option value="">All statuses</option>
          {["new","contacted","qualified","unqualified","converted"].map(s => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-800 text-xs text-gray-500 uppercase tracking-wider">
              <th className="text-left px-4 py-3">Contact</th>
              <th className="text-left px-4 py-3">Company</th>
              <th className="text-left px-4 py-3">Status</th>
              <th className="text-left px-4 py-3">Score</th>
              <th className="text-left px-4 py-3">Intent</th>
              <th className="text-left px-4 py-3">Platform</th>
              <th className="text-left px-4 py-3">Created</th>
              <th className="text-left px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-600 text-sm">Loading...</td></tr>
            ) : records.length === 0 ? (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-600 text-sm">No leads found.</td></tr>
            ) : records.map(l => {
              const isExp = expanded === l.lead_id;
              const intentColor = (l.intent_score||0) >= 0.7 ? "text-green-400"
                                : (l.intent_score||0) >= 0.4 ? "text-yellow-400"
                                : "text-gray-500";
              return [
                <tr key={l.lead_id}
                  onClick={() => setExpanded(isExp ? null : l.lead_id)}
                  className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors cursor-pointer">
                  <td className="px-4 py-3">
                    <p className="text-sm font-medium text-white">{l.first_name} {l.last_name}</p>
                    <p className="text-xs text-gray-500 truncate max-w-36">{l.job_title || l.email}</p>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-400 truncate max-w-28">{l.company_name || "—"}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[l.lead_status] || "bg-gray-800 text-gray-400"}`}>
                      {l.lead_status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      <div className="h-1.5 w-16 bg-gray-800 rounded-full overflow-hidden">
                        <div className="h-full bg-indigo-500 rounded-full"
                          style={{width:`${l.lead_score||0}%`}}/>
                      </div>
                      <span className="text-xs text-gray-400 font-mono">{l.lead_score||0}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-mono font-bold ${intentColor}`}>
                      {l.intent_score != null ? l.intent_score.toFixed(1) : "—"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500 capitalize">{l.source_platform}</td>
                  <td className="px-4 py-3 text-xs text-gray-600">{new Date(l.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3 text-gray-600 text-xs">{isExp ? <ChevronUp size={12}/> : <ChevronDown size={12}/>}</td>
                </tr>,
                isExp && (
                  <tr key={`${l.lead_id}-detail`} className="border-b border-gray-800">
                    <td colSpan={8} className="px-4 pb-4 pt-2 bg-gray-800/30">
                      <div className="grid grid-cols-2 gap-4 text-xs">
                        <div className="space-y-1.5">
                          <p className="font-semibold text-gray-300 mb-2">Lead Details</p>
                          {[["Lead ID", l.lead_id],["Email", l.email],
                            ["Source Detail", l.source_detail],
                          ].map(([k,v]) => v && (
                            <div key={k} className="flex gap-2">
                              <span className="text-gray-500 w-24 shrink-0">{k}:</span>
                              <span className="text-gray-300 break-all">{v}</span>
                            </div>
                          ))}
                        </div>
                        <div className="space-y-1.5">
                          <p className="font-semibold text-gray-300 mb-2">Initial Message</p>
                          <p className="text-gray-400 leading-relaxed">
                            {l.initial_message || "No message"}
                          </p>
                        </div>
                      </div>
                    </td>
                  </tr>
                )
              ];
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
