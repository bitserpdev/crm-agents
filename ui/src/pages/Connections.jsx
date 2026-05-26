import { useEffect, useState } from "react";
import { getConnectors } from "../api/client";
import { CheckCircle, XCircle, RefreshCw, ExternalLink } from "lucide-react";

const PLATFORM_ICONS = { linkedin: "🔵", upwork: "🟢", gmail: "🔴", outlook: "🔷" };

export default function Connections() {
  const [connectors, setConnectors] = useState([]);
  const [loading, setLoading]       = useState(true);

  const load = () => {
    setLoading(true);
    getConnectors().then(r => { setConnectors(r.data); setLoading(false); });
  };
  useEffect(() => { load(); }, []);

  const connect = (platform) => {
    window.location.href = `${import.meta.env.VITE_API_URL || "http://localhost:8000"}/api/connectors/${platform}/auth`;
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Connections</h2>
        <button onClick={load}
          className="flex items-center gap-2 bg-gray-800 hover:bg-gray-700 px-3 py-2 rounded-lg text-sm transition-colors">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {loading ? (
        <div className="text-gray-500 text-sm">Loading...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {connectors.map(c => (
            <div key={c.platform_name}
              className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">{PLATFORM_ICONS[c.platform_name] || "⚪"}</span>
                  <div>
                    <h3 className="font-semibold capitalize">{c.platform_name}</h3>
                    <p className="text-xs text-gray-500 uppercase">{c.auth_type}</p>
                  </div>
                </div>
                {c.auth_status === "connected"
                  ? <span className="flex items-center gap-1 text-green-400 text-xs bg-green-900/40 px-2 py-1 rounded-full">
                      <CheckCircle size={11}/> Connected
                    </span>
                  : <span className="flex items-center gap-1 text-red-400 text-xs bg-red-900/40 px-2 py-1 rounded-full">
                      <XCircle size={11}/> Disconnected
                    </span>
                }
              </div>
              <div className="text-xs text-gray-500 space-y-1 mb-4">
                <div>Poll interval: {c.polling_interval_sec}s</div>
                {c.last_synced_at && <div>Last sync: {new Date(c.last_synced_at).toLocaleString()}</div>}
                {c.oauth_expires_at && <div>Token expires: {new Date(c.oauth_expires_at).toLocaleString()}</div>}
              </div>
              {c.auth_status !== "connected" && (
                <button onClick={() => connect(c.platform_name)}
                  className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 px-3 py-2 rounded-lg text-xs font-medium transition-colors w-full justify-center">
                  <ExternalLink size={12}/> Connect {c.platform_name}
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
