import { useEffect, useState } from "react";
import { getRuns, getRunStats } from "../api/client";
import { CheckCircle, XCircle, MinusCircle, RefreshCw } from "lucide-react";

const STATUS_ICON = {
  success: <CheckCircle size={13} className="text-green-400"/>,
  failed:  <XCircle size={13} className="text-red-400"/>,
  skipped: <MinusCircle size={13} className="text-yellow-400"/>,
};

export default function Runs() {
  const [runs, setRuns]   = useState([]);
  const [stats, setStats] = useState([]);

  const load = () => {
    getRuns().then(r => setRuns(r.data));
    getRunStats().then(r => setStats(r.data));
  };
  useEffect(() => { load(); }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Run History</h2>
        <button onClick={load}
          className="flex items-center gap-2 bg-gray-800 hover:bg-gray-700 px-3 py-2 rounded-lg text-sm transition-colors">
          <RefreshCw size={14}/> Refresh
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {stats.map(s => (
          <div key={s.extraction_status} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-1">
              {STATUS_ICON[s.extraction_status]}
              <span className="text-xs text-gray-400 uppercase font-medium">{s.extraction_status}</span>
            </div>
            <div className="text-2xl font-bold">{s.count}</div>
            <div className="text-xs text-gray-500 mt-1">Avg {Math.round(s.avg_duration_ms || 0)}ms</div>
          </div>
        ))}
      </div>

      {/* Runs table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-800 text-xs text-gray-500 uppercase tracking-wider">
              <th className="text-left px-5 py-3">Status</th>
              <th className="text-left px-5 py-3">Platform</th>
              <th className="text-left px-5 py-3">Agent</th>
              <th className="text-left px-5 py-3">Duration</th>
              <th className="text-left px-5 py-3">Time</th>
              <th className="text-left px-5 py-3">Error</th>
            </tr>
          </thead>
          <tbody>
            {runs.map(r => (
              <tr key={r.log_id} className="border-b border-gray-800 hover:bg-gray-800/50 transition-colors">
                <td className="px-5 py-3">
                  <div className="flex items-center gap-2 text-xs">
                    {STATUS_ICON[r.extraction_status]}
                    <span className="capitalize">{r.extraction_status}</span>
                  </div>
                </td>
                <td className="px-5 py-3 text-xs text-gray-300 capitalize">{r.source_platform}</td>
                <td className="px-5 py-3 text-xs text-gray-400">{r.agent_id}</td>
                <td className="px-5 py-3 text-xs text-gray-400">{r.duration_ms}ms</td>
                <td className="px-5 py-3 text-xs text-gray-400">
                  {new Date(r.ran_at).toLocaleString()}
                </td>
                <td className="px-5 py-3 text-xs text-red-400 max-w-xs truncate">
                  {r.error_message || "—"}
                </td>
              </tr>
            ))}
            {runs.length === 0 && (
              <tr><td colSpan={6} className="px-5 py-8 text-center text-gray-600 text-sm">No runs yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
