import { useEffect, useState, useRef } from "react";
import {
  MessageSquare, Phone, RefreshCw, X, Video,
  ArrowUpRight, ArrowDownLeft, Flame, Thermometer,
  Snowflake, BellOff, Users, ChevronRight
} from "lucide-react";
import axios from "axios";

const API = axios.create({ baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000" });
const getConversations = (p) => API.get("/api/agent4/conversations", { params: p });
const getStats         = (p) => API.get("/api/agent4/conversations/stats", { params: p });
const getThread        = (id) => API.get(`/api/agent4/conversations/${id}/thread`);
const getCampaigns     = ()  => API.get("/api/agent3/campaigns");

const INTENT = {
  hot:         { color: "bg-green-900/50 text-green-300 border-green-700",    icon: Flame,       label: "Hot" },
  warm:        { color: "bg-yellow-900/50 text-yellow-300 border-yellow-700", icon: Thermometer, label: "Warm" },
  cold:        { color: "bg-gray-800 text-gray-400 border-gray-600",          icon: Snowflake,   label: "Cold" },
  unsubscribe: { color: "bg-red-900/50 text-red-300 border-red-700",          icon: BellOff,     label: "Unsub" },
};

const STATUS = {
  active:               { color: "bg-indigo-900/50 text-indigo-300",  label: "Active" },
  call_scheduled:       { color: "bg-green-900/50 text-green-300",    label: "Call Scheduled" },
  awaiting_availability:{ color: "bg-yellow-900/50 text-yellow-300",  label: "Awaiting Time" },
  unsubscribed:         { color: "bg-red-900/50 text-red-300",        label: "Unsubscribed" },
  exhausted:            { color: "bg-gray-800 text-gray-400",         label: "Exhausted" },
};

const TABS = [
  { key: "all",          label: "All",           icon: Users },
  { key: "hot",          label: "Hot",           icon: Flame },
  { key: "warm",         label: "Warm",          icon: Thermometer },
  { key: "cold",         label: "Cold",          icon: Snowflake },
  { key: "call_scheduled",label: "Call Scheduled",icon: Phone },
  { key: "unsubscribed", label: "Unsubscribed",  icon: BellOff },
];

function fmt(ts) {
  if (!ts) return "";
  return new Date(ts).toLocaleString([], { month:"short", day:"numeric", hour:"2-digit", minute:"2-digit" });
}
function timeAgo(ts) {
  if (!ts) return "";
  const diff = Date.now() - new Date(ts).getTime();
  const m = Math.floor(diff/60000);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m/60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h/24)}d ago`;
}

function Bubble({ msg, contactName }) {
  const isOut = msg.direction === "outbound";
  const intent = msg.intent_label ? INTENT[msg.intent_label] : null;
  const Icon = intent?.icon;
  return (
    <div className={`flex gap-3 ${isOut ? "flex-row-reverse" : "flex-row"}`}>
      <div className={`w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold
        ${isOut ? "bg-indigo-700 text-white" : "bg-gray-700 text-gray-300"}`}>
        {isOut ? "B" : (contactName?.[0] || "?")}
      </div>
      <div className={`max-w-[75%] flex flex-col gap-1 ${isOut ? "items-end" : "items-start"}`}>
        {msg.subject && (
          <p className={`text-xs font-medium ${isOut ? "text-indigo-300 text-right" : "text-gray-400"}`}>
            {msg.subject}
          </p>
        )}
        <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed
          ${isOut
            ? "bg-indigo-700/40 border border-indigo-600/40 text-gray-200 rounded-tr-sm"
            : "bg-gray-800 border border-gray-700 text-gray-300 rounded-tl-sm"}`}>
          <p className="whitespace-pre-wrap">{msg.body}</p>
        </div>
        <div className={`flex items-center gap-2 ${isOut ? "flex-row-reverse" : "flex-row"}`}>
          <span className="text-xs text-gray-600">{fmt(msg.ts)}</span>
          {intent && Icon && (
            <span className={`text-xs px-1.5 py-0.5 rounded-full border flex items-center gap-1 ${intent.color}`}>
              <Icon size={9}/>{intent.label}
            </span>
          )}
          {isOut
            ? <ArrowUpRight size={11} className="text-indigo-400"/>
            : <ArrowDownLeft size={11} className="text-green-400"/>}
        </div>
      </div>
    </div>
  );
}

function ThreadModal({ seq, onClose }) {
  const [thread, setThread] = useState(null);
  const [loading, setLoading] = useState(true);
  const bottomRef = useRef(null);
  useEffect(() => {
    getThread(seq.sequence_id).then(r => { setThread(r.data); setLoading(false); });
  }, [seq.sequence_id]);
  useEffect(() => { thread && bottomRef.current?.scrollIntoView({ behavior:"smooth" }); }, [thread]);

  const name = `${seq.first_name||""} ${seq.last_name||""}`.trim();
  const statusCfg = STATUS[seq.status] || STATUS.active;
  const intentCfg = seq.last_intent_label ? INTENT[seq.last_intent_label] : null;
  const IntentIcon = intentCfg?.icon;

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-indigo-700 flex items-center justify-center font-bold text-white">
              {name[0]||"?"}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-white">{name}</h3>
                <span className={`text-xs px-2 py-0.5 rounded-full ${statusCfg.color}`}>{statusCfg.label}</span>
                {intentCfg && IntentIcon && (
                  <span className={`text-xs px-2 py-0.5 rounded-full border flex items-center gap-1 ${intentCfg.color}`}>
                    <IntentIcon size={9}/>{intentCfg.label}
                  </span>
                )}
              </div>
              <p className="text-xs text-gray-500">{seq.job_title}{seq.job_title && seq.company_name ? " · " : ""}{seq.company_name}</p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white"><X size={18}/></button>
        </div>

        {/* Teams meeting banner */}
        {thread?.meeting && (
          <div className="mx-6 mt-3 flex-shrink-0 bg-green-900/30 border border-green-700/50 rounded-xl px-4 py-3 flex items-center gap-3">
            <Video size={16} className="text-green-400 flex-shrink-0"/>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-green-300">Teams Meeting Scheduled</p>
              <p className="text-xs text-gray-500 truncate">{thread.meeting.subject}</p>
            </div>
            <a href={thread.meeting.join_url} target="_blank" rel="noreferrer"
              className="flex items-center gap-1 text-xs bg-green-700 hover:bg-green-600 px-3 py-1.5 rounded-lg text-white">
              Join <ArrowUpRight size={11}/>
            </a>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-auto px-6 py-4 space-y-4">
          {loading
            ? <div className="text-center text-gray-600 py-8 text-sm">Loading conversation...</div>
            : !thread?.messages?.length
              ? <div className="text-center text-gray-600 py-8 text-sm">No messages yet</div>
              : thread.messages.map((msg, i) => <Bubble key={i} msg={msg} contactName={name}/>)
          }
          <div ref={bottomRef}/>
        </div>

        <div className="px-6 py-3 border-t border-gray-800 flex-shrink-0 flex items-center justify-between">
          <span className="text-xs text-gray-500">{seq.campaign_name}</span>
          <span className="text-xs text-gray-600">{thread?.messages?.length||0} messages</span>
        </div>
      </div>
    </div>
  );
}

function ConvCard({ seq, onClick }) {
  const name = `${seq.first_name||""} ${seq.last_name||""}`.trim();
  const intentCfg = seq.last_intent_label ? INTENT[seq.last_intent_label] : null;
  const IntentIcon = intentCfg?.icon;
  const statusCfg = STATUS[seq.status] || STATUS.active;

  return (
    <div onClick={onClick}
      className="bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-indigo-700/50 hover:bg-gray-800/50 cursor-pointer transition-all group">
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-indigo-800/60 flex items-center justify-center font-bold text-indigo-300 text-sm flex-shrink-0">
            {name[0]||"?"}
          </div>
          <div className="min-w-0">
            <p className="font-medium text-white text-sm truncate">{name}</p>
            <p className="text-xs text-gray-500 truncate">{seq.job_title}{seq.job_title && seq.company_name ? " · ":""}{seq.company_name}</p>
          </div>
        </div>
        <ChevronRight size={14} className="text-gray-600 group-hover:text-indigo-400 flex-shrink-0 mt-1"/>
      </div>

      <div className="flex items-center gap-2 mb-2 flex-wrap">
        {intentCfg && IntentIcon && (
          <span className={`text-xs px-2 py-0.5 rounded-full border flex items-center gap-1 ${intentCfg.color}`}>
            <IntentIcon size={9}/>{intentCfg.label}
          </span>
        )}
        <span className={`text-xs px-2 py-0.5 rounded-full ${statusCfg.color}`}>{statusCfg.label}</span>
        {seq.teams_join_url && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-green-900/30 text-green-400 border border-green-700/40 flex items-center gap-1">
            <Video size={9}/> Teams
          </span>
        )}
      </div>

      {seq.last_reply_preview && (
        <p className="text-xs text-gray-500 line-clamp-2 mb-2 bg-gray-800 rounded-lg px-3 py-2">
          "{seq.last_reply_preview}"
        </p>
      )}

      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-600">{seq.campaign_name}</span>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-600 flex items-center gap-1">
            <MessageSquare size={9}/>{seq.total_messages}
          </span>
          <span className="text-xs text-indigo-400">{timeAgo(seq.last_reply_at)}</span>
        </div>
      </div>
    </div>
  );
}

export default function Conversations() {
  const [tab,        setTab]        = useState("all");
  const [sequences,  setSequences]  = useState([]);
  const [stats,      setStats]      = useState({});
  const [campaigns,  setCampaigns]  = useState([]);
  const [campFilter, setCampFilter] = useState("");
  const [selected,   setSelected]   = useState(null);
  const [loading,    setLoading]    = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const params = { campaign_id: campFilter || undefined, intent: tab };
      const [seqRes, statsRes, campRes] = await Promise.all([
        getConversations(params),
        getStats({ campaign_id: campFilter || undefined }),
        getCampaigns(),
      ]);
      setSequences(seqRes.data);
      setStats(statsRes.data);
      setCampaigns(campRes.data);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [tab, campFilter]);

  const statCards = [
    { label: "Total",         value: stats.total         || 0, color: "text-white" },
    { label: "Hot",           value: stats.hot           || 0, color: "text-green-400" },
    { label: "Warm",          value: stats.warm          || 0, color: "text-yellow-400" },
    { label: "Call Scheduled",value: stats.call_scheduled|| 0, color: "text-green-300" },
    { label: "Unsubscribed",  value: stats.unsubscribed  || 0, color: "text-red-400" },
  ];

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <MessageSquare size={22} className="text-indigo-400"/> Conversations
          </h2>
          <p className="text-sm text-gray-500 mt-0.5">Contacts who replied · AI-managed responses · Teams scheduling</p>
        </div>
        <div className="flex gap-2">
          <select value={campFilter} onChange={e=>setCampFilter(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500">
            <option value="">All Campaigns</option>
            {campaigns.map(c=><option key={c.campaign_id} value={c.campaign_id}>{c.campaign_name}</option>)}
          </select>
          <button onClick={load} className="bg-gray-800 hover:bg-gray-700 px-3 py-2 rounded-lg text-sm transition-colors">
            <RefreshCw size={14}/>
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-5 gap-3 mb-6">
        {statCards.map(({label,value,color})=>(
          <div key={label} className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
            <p className="text-xs text-gray-500 mb-1">{label}</p>
            <p className={`text-2xl font-bold ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-5 border-b border-gray-800 pb-3 overflow-x-auto">
        {TABS.map(({key,label,icon:Icon})=>(
          <button key={key} onClick={()=>setTab(key)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors whitespace-nowrap
              ${tab===key?"bg-indigo-600 text-white":"text-gray-400 hover:text-white hover:bg-gray-800"}`}>
            <Icon size={13}/>{label}
            {key!=="all" && stats[key]>0 && (
              <span className={`text-xs px-1.5 py-0.5 rounded-full ml-0.5 ${tab===key?"bg-white/20":"bg-gray-700 text-gray-400"}`}>
                {stats[key]}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Grid */}
      {loading ? (
        <div className="text-center text-gray-600 py-12 text-sm">Loading conversations...</div>
      ) : sequences.length===0 ? (
        <div className="text-center py-16">
          <MessageSquare size={40} className="text-gray-700 mx-auto mb-3"/>
          <p className="text-gray-500 text-sm">No conversations yet.</p>
          <p className="text-gray-600 text-xs mt-1">They appear here when contacts reply to your campaigns.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {sequences.map(seq=>(
            <ConvCard key={seq.sequence_id} seq={seq} onClick={()=>setSelected(seq)}/>
          ))}
        </div>
      )}

      {selected && <ThreadModal seq={selected} onClose={()=>setSelected(null)}/>}
    </div>
  );
}
