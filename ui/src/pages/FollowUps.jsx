import { useEffect, useState } from "react";
import { Clock, RefreshCw, Mail, Eye, EyeOff, Users, AlertCircle, Send } from "lucide-react";
import axios from "axios";

const API = axios.create({ baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000" });
const getFollowups = (p) => API.get("/api/campaigns/sequences/followups",       { params: p });
const getStats     = (p) => API.get("/api/campaigns/sequences/followups/stats", { params: p });
const getCampaigns = ()  => API.get("/api/campaigns/emails");

const TABS = [
  { key: "all",       label: "All",           icon: Users,       statKey: "total" },
  { key: "no_open",   label: "Never Opened",  icon: EyeOff,      statKey: "no_open" },
  { key: "opened",    label: "Opened",        icon: Eye,         statKey: "opened" },
  { key: "fu1",       label: "FU 1",          icon: Send,        statKey: "fu1" },
  { key: "fu2",       label: "FU 2",          icon: Send,        statKey: "fu2" },
  { key: "fu3",       label: "FU 3",          icon: Send,        statKey: "fu3" },
  { key: "fu4",       label: "FU 4",          icon: Send,        statKey: "fu4" },
  { key: "fu5",       label: "FU 5",          icon: Send,        statKey: "fu5" },
  { key: "exhausted", label: "Exhausted",     icon: AlertCircle, statKey: "exhausted" },
];

function fmt(ts) {
  if (!ts) return "—";
  return new Date(ts).toLocaleString([], { month:"short", day:"numeric", hour:"2-digit", minute:"2-digit" });
}
function timeAgo(ts) {
  if (!ts) return "";
  const diff = Date.now() - new Date(ts).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function StepDots({ current, max = 5, status }) {
  return (
    <div className="flex gap-1.5 items-center">
      {Array.from({ length: max }).map((_, i) => (
        <div key={i} className={`h-1.5 flex-1 rounded-full transition-all
          ${status === "exhausted"  ? "bg-gray-700" :
            i < current             ? "bg-indigo-500" :
            i === current - 1       ? "bg-indigo-400/70" :
                                      "bg-gray-700"}`}/>
      ))}
      <span className="text-xs text-gray-500 ml-1 whitespace-nowrap">{current}/{max}</span>
    </div>
  );
}

function FollowUpCard({ seq }) {
  const name       = `${seq.first_name || ""} ${seq.last_name || ""}`.trim();
  const opened     = !!seq.opened_at;
  const exhausted  = seq.status === "exhausted";
  const fuCount    = Number(seq.followups_sent) || 0;

  return (
    <div className={`bg-gray-900 border rounded-xl p-4 transition-all
      ${exhausted ? "border-gray-800 opacity-70" : "border-gray-800 hover:border-gray-700"}`}>

      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`w-9 h-9 rounded-full flex items-center justify-center font-bold text-sm flex-shrink-0
            ${exhausted ? "bg-gray-800 text-gray-500" : "bg-gray-700 text-gray-300"}`}>
            {name[0]?.toUpperCase() || "?"}
          </div>
          <div className="min-w-0">
            <p className={`font-medium text-sm truncate ${exhausted ? "text-gray-500" : "text-white"}`}>
              {name}
            </p>
            <p className="text-xs text-gray-600 truncate">
              {seq.job_title}{seq.job_title && seq.company_name ? " · " : ""}{seq.company_name}
            </p>
          </div>
        </div>

        {/* Open status */}
        <span className={`text-xs px-2 py-0.5 rounded-full flex items-center gap-1 flex-shrink-0
          ${opened
            ? "bg-blue-900/40 text-blue-300 border border-blue-700/40"
            : "bg-gray-800 text-gray-500 border border-gray-700"}`}>
          {opened ? <><Eye size={9}/> Opened</> : <><EyeOff size={9}/> Not Opened</>}
        </span>
      </div>

      {/* Progress bar */}
      <div className="mb-3">
        <StepDots current={seq.current_step} max={seq.max_steps || 5} status={seq.status}/>
      </div>

      {/* Status badge */}
      <div className="mb-3">
        {exhausted ? (
          <span className="text-xs px-2 py-1 rounded-lg bg-gray-800 text-gray-500 flex items-center gap-1 w-fit">
            <AlertCircle size={9}/> Exhausted — {seq.max_steps} follow-ups sent, no reply
          </span>
        ) : fuCount > 0 ? (
          <span className="text-xs px-2 py-1 rounded-lg bg-indigo-900/30 text-indigo-400 border border-indigo-700/30 flex items-center gap-1 w-fit">
            <Send size={9}/> Follow-up {fuCount} sent
          </span>
        ) : (
          <span className="text-xs px-2 py-1 rounded-lg bg-gray-800 text-gray-400 flex items-center gap-1 w-fit">
            <Mail size={9}/> Initial email sent
          </span>
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-600 truncate max-w-[50%]">{seq.campaign_name}</span>
        <div className="text-right">
          {!exhausted && seq.next_followup_at ? (
            <p className="text-xs text-gray-500 flex items-center gap-1 justify-end">
              <Clock size={9}/> Next: {fmt(seq.next_followup_at)}
            </p>
          ) : seq.initial_sent_at ? (
            <p className="text-xs text-gray-600">Sent {timeAgo(seq.initial_sent_at)}</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export default function FollowUps() {
  const [tab,        setTab]        = useState("all");
  const [sequences,  setSequences]  = useState([]);
  const [stats,      setStats]      = useState({});
  const [campaigns,  setCampaigns]  = useState([]);
  const [campFilter, setCampFilter] = useState("");
  const [loading,    setLoading]    = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [seqRes, statsRes, campRes] = await Promise.all([
        getFollowups({ campaign_id: campFilter || undefined, tab }),
        getStats({ campaign_id: campFilter || undefined }),
        getCampaigns(),
      ]);
      setSequences(seqRes.data);
      setStats(statsRes.data);
      setCampaigns(campRes.data);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [tab, campFilter]);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <Clock size={22} className="text-indigo-400"/> Follow-ups
          </h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Contacts who haven't replied · automated every 3 days · up to 5 attempts
          </p>
        </div>
        <div className="flex gap-2">
          <select value={campFilter} onChange={e => setCampFilter(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500">
            <option value="">All Campaigns</option>
            {campaigns.map(c => <option key={c.campaign_id} value={c.campaign_id}>{c.campaign_name}</option>)}
          </select>
          <button onClick={load} className="bg-gray-800 hover:bg-gray-700 px-3 py-2 rounded-lg text-sm transition-colors">
            <RefreshCw size={14}/>
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        {[
          { label: "Total",        value: stats.total     || 0, color: "text-white" },
          { label: "Never Opened", value: stats.no_open   || 0, color: "text-gray-400" },
          { label: "Opened",       value: stats.opened    || 0, color: "text-blue-400" },
          { label: "Exhausted",    value: stats.exhausted || 0, color: "text-red-400" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
            <p className="text-xs text-gray-500 mb-1">{label}</p>
            <p className={`text-2xl font-bold ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-5 border-b border-gray-800 pb-3 overflow-x-auto">
        {TABS.map(({ key, label, icon: Icon, statKey }) => (
          <button key={key} onClick={() => setTab(key)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors whitespace-nowrap
              ${tab === key ? "bg-indigo-600 text-white" : "text-gray-400 hover:text-white hover:bg-gray-800"}`}>
            <Icon size={13}/>{label}
            {(stats[statKey] || 0) > 0 && (
              <span className={`text-xs px-1.5 py-0.5 rounded-full ml-0.5
                ${tab === key ? "bg-white/20 text-white" : "bg-gray-700 text-gray-400"}`}>
                {stats[statKey]}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Grid */}
      {loading ? (
        <div className="text-center text-gray-600 py-12 text-sm">Loading follow-ups...</div>
      ) : sequences.length === 0 ? (
        <div className="text-center py-16">
          <Clock size={40} className="text-gray-700 mx-auto mb-3"/>
          <p className="text-gray-500 text-sm">No pending follow-ups.</p>
          <p className="text-gray-600 text-xs mt-1">Follow-ups appear here when contacts don't reply to your campaigns.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {sequences.map(seq => <FollowUpCard key={seq.sequence_id} seq={seq}/>)}
        </div>
      )}
    </div>
  );
}
