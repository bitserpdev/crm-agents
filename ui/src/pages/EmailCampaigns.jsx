import { useEffect, useState } from "react";
import { Mail, Plus, Play, Eye, X, CheckCircle,
         XCircle, Clock, TrendingUp, MessageSquare,
         ChevronDown, ChevronUp, RefreshCw } from "lucide-react";
import axios from "axios";

const API = axios.create({ baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000" });
API.defaults.timeout = 120000;
const getCampaigns   = ()   => API.get("/api/agent3/campaigns");
const createCampaign = (d)  => API.post("/api/agent3/campaigns", d);
const triggerCampaign= (id) => API.post(`/api/agent3/campaigns/${id}/trigger`);
const getRuns        = (id) => API.get(`/api/agent3/campaigns/${id}/runs`);
const getRecipients  = (id) => API.get(`/api/agent3/runs/${id}/recipients`);
const getReplies     = (id) => API.get(`/api/agent3/replies?campaign_id=${id}`);
const startPreview   = (id) => API.post(`/api/agent3/campaigns/${id}/preview/start`, {}, { timeout: 10000 });
const updateCampaign = (id, d) => API.put(`/api/agent3/campaigns/${id}`, d);
const deleteCampaign = (id) => API.delete(`/api/agent3/campaigns/${id}`);
const pollPreview  = (jobId) => API.get(`/api/agent3/preview/job/${jobId}`, { timeout: 10000 });

const STAGES = ["subscriber","lead","mql","sql","opportunity","customer"];
const SIZES   = ["1-10","11-50","51-200","201-500","500+"];
const INTENT  = {
  hot:         "bg-green-900/50 text-green-300",
  warm:        "bg-yellow-900/50 text-yellow-300",
  cold:        "bg-gray-800 text-gray-400",
  unsubscribe: "bg-red-900/50 text-red-300",
};

function Modal({ title, onClose, children, wide=false }) {
  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className={`bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl
        ${wide ? "w-full max-w-3xl" : "w-full max-w-xl"} max-h-[90vh] overflow-auto`}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800 sticky top-0 bg-gray-900">
          <h3 className="font-semibold text-white">{title}</h3>
          <button onClick={onClose} className="text-gray-500 hover:text-white"><X size={18}/></button>
        </div>
        <div className="p-6">{children}</div>
      </div>
    </div>
  );
}

function Field({ label, hint, children }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-400 mb-1.5">{label}</label>
      {children}
      {hint && <p className="text-xs text-gray-600 mt-1">{hint}</p>}
    </div>
  );
}

function Input({ value, onChange, placeholder, type="text" }) {
  return (
    <input type={type} value={value} onChange={e=>onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"/>
  );
}

function Select({ value, onChange, options, placeholder }) {
  return (
    <select value={value} onChange={e=>onChange(e.target.value)}
      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500">
      <option value="">{placeholder || "Any"}</option>
      {options.map(o => <option key={o} value={o}>{o}</option>)}
    </select>
  );
}

const EMPTY_FORM = {
  campaign_name:"", service_description:"", from_address:"",
  filter_region:"", filter_industry:"", filter_company_size:"",
  filter_min_score:0, filter_max_score:100,
  filter_stage:"", scheduled_at:"",
};

export default function EmailCampaigns() {
  const [campaigns, setCampaigns] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm]     = useState(EMPTY_FORM);
  const [detail, setDetail] = useState(null);   // {campaign, runs, recipients, replies}
  const [preview, setPreview]= useState(null);
  const [editTarget, setEditTarget] = useState(null);
  const [editForm, setEditForm] = useState({});
  const [msg, setMsg]       = useState({text:"",type:"ok"});
  const [running, setRunning]= useState({});
  const [loading, setLoading]= useState(false);
  const [tab, setTab]       = useState("recipients");

  const load = () => {
    setLoading(true);
    getCampaigns().then(r => setCampaigns(r.data)).finally(()=>setLoading(false));
  };
  useEffect(()=>{ load(); },[]);

  const flash = (text,type="ok") => { setMsg({text,type}); setTimeout(()=>setMsg({text:"",type:"ok"}),3000); };

  const submit = async () => {
    if (!form.campaign_name || !form.service_description || !form.from_address) {
      flash("Name, service description and from address are required","err"); return;
    }
    try {
      await createCampaign({
        ...form,
        filter_min_score: Number(form.filter_min_score),
        filter_max_score: Number(form.filter_max_score),
        scheduled_at: form.scheduled_at || null,
      });
      flash("Campaign created!"); setShowCreate(false); setForm(EMPTY_FORM); load();
    } catch(e) { flash("Error: "+e.message,"err"); }
  };

  const trigger = async (id, name) => {
    setRunning(r=>({...r,[id]:true}));
    try {
      await triggerCampaign(id);
      flash(`Campaign "${name}" triggered — emails sending...`);
    } catch(e) { flash("Trigger failed","err"); }
    setTimeout(()=>setRunning(r=>({...r,[id]:false})),5000);
  };

  const openDetail = async (campaign) => {
    const [runs, replies] = await Promise.all([
      getRuns(campaign.campaign_id),
      getReplies(campaign.campaign_id),
    ]);
    let recipients = [];
    if (runs.data.length > 0) {
      const r = await getRecipients(runs.data[0].run_id);
      recipients = r.data;
    }
    setDetail({ campaign, runs: runs.data, recipients, replies: replies.data });
    setTab("recipients");
  };

  const handleDelete = async (id, name) => {
    if (!window.confirm(`Delete campaign "${name}"?`)) return;
    await deleteCampaign(id);
    setCampaigns(cs => cs.filter(c => c.campaign_id !== id));
  };

  const openEdit = (c) => {
    setEditTarget(c.campaign_id);
    setEditForm({
      campaign_name: c.campaign_name,
      service_description: c.service_description,
      from_address: c.from_address,
      filter_region: c.filter_region || "",
      filter_industry: c.filter_industry || "",
      filter_company_size: c.filter_company_size || "",
      filter_min_score: c.filter_min_score ?? 0,
      filter_max_score: c.filter_max_score ?? 100,
      filter_stage: c.filter_stage || "",
    });
  };

  const saveEdit = async () => {
    await updateCampaign(editTarget, editForm);
    setEditTarget(null);
    const { data } = await getCampaigns();
    setCampaigns(data);
  };

  const loadPreview = async (id) => {
    setPreview("loading");
    try {
      const { data: { job_id } } = await startPreview(id);
      const poll = async () => {
        try {
          const { data } = await pollPreview(job_id);
          if (data.status === "pending") {
            setTimeout(poll, 3000);
          } else if (data.status === "done") {
            setPreview(data);
          } else {
            setPreview({ error: data.error || "Preview generation failed." });
          }
        } catch (e) {
          setPreview({ error: "Polling failed." });
        }
      };
      setTimeout(poll, 3000);
    } catch (err) {
      setPreview({ error: err.response?.data?.detail || "Preview generation failed. Check backend logs." });
    }
  };

  const connectOutlook = (id) => {
    window.location.href = `${import.meta.env.VITE_API_URL || "http://localhost:8000"}/api/agent3/auth/${id}/start`;
  };

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <Mail size={22} className="text-indigo-400"/> Email Campaigns
          </h2>
          <p className="text-sm text-gray-500 mt-0.5">
            AI-personalized outreach · powered by llama3.2 · sent via Microsoft 365
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={load} className="flex items-center gap-2 bg-gray-800 hover:bg-gray-700 px-3 py-2 rounded-lg text-sm transition-colors">
            <RefreshCw size={14}/>
          </button>
          <button onClick={()=>setShowCreate(true)}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 px-4 py-2 rounded-lg text-sm font-medium transition-colors">
            <Plus size={16}/> New Campaign
          </button>
        </div>
      </div>

      {msg.text && (
        <div className={`mb-4 px-4 py-2.5 rounded-lg text-sm flex items-center gap-2
          ${msg.type==="err" ? "bg-red-900/40 border border-red-700 text-red-300"
                             : "bg-green-900/40 border border-green-700 text-green-300"}`}>
          {msg.type==="err" ? <XCircle size={14}/> : <CheckCircle size={14}/>}
          {msg.text}
        </div>
      )}

      {/* Campaign cards */}
      {loading ? (
        <div className="text-center text-gray-600 py-12 text-sm">Loading campaigns...</div>
      ) : campaigns.length === 0 ? (
        <div className="text-center py-16">
          <Mail size={40} className="text-gray-700 mx-auto mb-3"/>
          <p className="text-gray-500">No email campaigns yet.</p>
          <button onClick={()=>setShowCreate(true)} className="mt-3 text-indigo-400 text-sm hover:underline">
            Create your first campaign
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {campaigns.map(c => (
            <div key={c.campaign_id}
              className="bg-gray-900 border border-gray-800 rounded-xl p-5 hover:border-gray-700 transition-colors">
              {/* Card header */}
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="font-semibold text-white">{c.campaign_name}</h3>
                  <p className="text-xs text-gray-500 mt-0.5 truncate max-w-56">
                    {c.service_description}
                  </p>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium
                  ${c.campaign_status==="running" ? "bg-green-900/50 text-green-300"
                  : c.campaign_status==="completed" ? "bg-blue-900/50 text-blue-300"
                  : "bg-gray-800 text-gray-400"}`}>
                  {c.campaign_status}
                </span>
              </div>

              {/* Stats row */}
              <div className="grid grid-cols-4 gap-2 mb-4">
                {[["Sent",c.total_sent||0,"text-white"],
                  ["Runs",c.run_count||0,"text-indigo-400"],
                  ["Score",`${c.filter_min_score||0}-${c.filter_max_score||100}`,"text-yellow-400"],
                  ["Stage",c.filter_stage||"all","text-gray-400"],
                ].map(([label,val,color])=>(
                  <div key={label} className="bg-gray-800 rounded-lg p-2 text-center">
                    <p className="text-xs text-gray-500">{label}</p>
                    <p className={`text-sm font-bold ${color} truncate`}>{val}</p>
                  </div>
                ))}
              </div>

              {/* Filters */}
              <div className="flex flex-wrap gap-1.5 mb-4">
                {c.filter_region && <span className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded">🌍 {c.filter_region}</span>}
                {c.filter_industry && <span className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded">🏭 {c.filter_industry}</span>}
                {c.filter_company_size && <span className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded">👥 {c.filter_company_size}</span>}
                {c.scheduled_at && <span className="text-xs bg-amber-900/30 text-amber-400 px-2 py-0.5 rounded">⏰ {new Date(c.scheduled_at).toLocaleString()}</span>}
                {c.from_address && <span className="text-xs bg-indigo-900/30 text-indigo-400 px-2 py-0.5 rounded truncate max-w-36">✉ {c.from_address}</span>}
              </div>

              {/* Actions */}
              <div className="flex gap-2 flex-wrap">
                <button onClick={()=>trigger(c.campaign_id,c.campaign_name)}
                  disabled={running[c.campaign_id]}
                  className="flex items-center gap-1.5 bg-indigo-700 hover:bg-indigo-600 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors disabled:opacity-50">
                  <Play size={11}/>{running[c.campaign_id]?"Sending...":"Send Now"}
                </button>
                <button onClick={()=>openDetail(c)}
                  className="flex items-center gap-1.5 bg-gray-700 hover:bg-gray-600 px-3 py-1.5 rounded-lg text-xs transition-colors">
                  <TrendingUp size={11}/> Results
                </button>
                <button onClick={()=>loadPreview(c.campaign_id)}
                  className="flex items-center gap-1.5 bg-gray-700 hover:bg-gray-600 px-3 py-1.5 rounded-lg text-xs transition-colors">
                  <Eye size={11}/> Preview
                </button>
                <button onClick={()=>openEdit(c)}
                  className="flex items-center gap-1.5 bg-yellow-700 hover:bg-yellow-600 px-3 py-1.5 rounded-lg text-xs transition-colors">
                  ✏️ Edit
                </button>
                <button onClick={()=>handleDelete(c.campaign_id, c.campaign_name)}
                  className="flex items-center gap-1.5 bg-red-800 hover:bg-red-700 px-3 py-1.5 rounded-lg text-xs transition-colors">
                  🗑️ Delete
                </button>
                {!c.azure_token && (
                  <button onClick={()=>connectOutlook(c.campaign_id)}
                    className="flex items-center gap-1.5 bg-blue-800 hover:bg-blue-700 px-3 py-1.5 rounded-lg text-xs transition-colors">
                    <Mail size={11}/> Connect Outlook
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Campaign Modal */}
      {showCreate && (
        <Modal title="New Email Campaign" onClose={()=>setShowCreate(false)} wide>
          <div className="space-y-4">
            <Field label="Campaign Name">
              <Input value={form.campaign_name} onChange={v=>setForm(f=>({...f,campaign_name:v}))} placeholder="BITS Analytics Outreach Q3"/>
            </Field>
            <Field label="Service Description" hint="llama3.2 uses this to write personalized emails">
              <textarea value={form.service_description}
                onChange={e=>setForm(f=>({...f,service_description:e.target.value}))}
                placeholder="We provide Big Data & Analytics solutions including data pipelines, BI dashboards, ML models, and real-time analytics platforms for enterprise clients..."
                rows={3}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 resize-none"/>
            </Field>
            <Field label="From Email Address">
              <Input value={form.from_address} onChange={v=>setForm(f=>({...f,from_address:v}))} placeholder="analytics@bitscompany.com"/>
            </Field>

            <div className="border-t border-gray-800 pt-4">
              <p className="text-xs font-medium text-gray-400 mb-3 uppercase tracking-wider">
                Audience Filters
              </p>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Region / Country code" hint="e.g. US, GB, PK, IN">
                  <Input value={form.filter_region} onChange={v=>setForm(f=>({...f,filter_region:v}))} placeholder="US"/>
                </Field>
                <Field label="Industry keyword">
                  <Input value={form.filter_industry} onChange={v=>setForm(f=>({...f,filter_industry:v}))} placeholder="technology"/>
                </Field>
                <Field label="Company size">
                  <Select value={form.filter_company_size} onChange={v=>setForm(f=>({...f,filter_company_size:v}))} options={SIZES} placeholder="Any size"/>
                </Field>
                <Field label="Lifecycle stage">
                  <Select value={form.filter_stage} onChange={v=>setForm(f=>({...f,filter_stage:v}))} options={STAGES} placeholder="Any stage"/>
                </Field>
                <Field label="Min score (0-100)">
                  <Input type="number" value={form.filter_min_score} onChange={v=>setForm(f=>({...f,filter_min_score:v}))} placeholder="0"/>
                </Field>
                <Field label="Max score (0-100)">
                  <Input type="number" value={form.filter_max_score} onChange={v=>setForm(f=>({...f,filter_max_score:v}))} placeholder="100"/>
                </Field>
              </div>
            </div>

            <Field label="Schedule (optional)" hint="Leave empty to send manually">
              <Input type="datetime-local" value={form.scheduled_at} onChange={v=>setForm(f=>({...f,scheduled_at:v}))}/>
            </Field>

            <div className="flex gap-3 pt-2">
              <button onClick={submit}
                className="flex-1 bg-indigo-600 hover:bg-indigo-500 py-2.5 rounded-lg text-sm font-medium transition-colors">
                Create Campaign
              </button>
              <button onClick={()=>setShowCreate(false)}
                className="px-4 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm transition-colors">
                Cancel
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Campaign Detail Modal */}
      {detail && (
        <Modal title={detail.campaign.campaign_name} onClose={()=>setDetail(null)} wide>
          {/* Run stats */}
          {detail.runs.length > 0 && (
            <div className="grid grid-cols-5 gap-2 mb-5">
              {[["Total",detail.runs[0].total_recipients,"text-white"],
                ["Sent", detail.runs[0].sent_count,       "text-green-400"],
                ["Failed",detail.runs[0].failed_count,    "text-red-400"],
                ["Opens",detail.runs[0].open_count,       "text-yellow-400"],
                ["Replies",detail.replies.length,         "text-indigo-400"],
              ].map(([l,v,c])=>(
                <div key={l} className="bg-gray-800 rounded-lg p-3 text-center">
                  <p className="text-xs text-gray-500">{l}</p>
                  <p className={`text-xl font-bold ${c}`}>{v}</p>
                </div>
              ))}
            </div>
          )}

          {/* Tabs */}
          <div className="flex gap-2 mb-4 border-b border-gray-800 pb-2">
            {["recipients","replies"].map(t=>(
              <button key={t} onClick={()=>setTab(t)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors capitalize
                  ${tab===t?"bg-indigo-600 text-white":"text-gray-400 hover:text-white"}`}>
                {t} ({t==="recipients" ? detail.recipients.length : detail.replies.length})
              </button>
            ))}
          </div>

          {tab==="recipients" && (
            <div className="space-y-1 max-h-80 overflow-auto">
              {detail.recipients.length===0
                ? <p className="text-gray-600 text-sm text-center py-4">No emails sent yet</p>
                : detail.recipients.map(r=>(
                <div key={r.recipient_id} className="flex items-center justify-between py-2 border-b border-gray-800/50">
                  <div>
                    <p className="text-sm text-white">{r.first_name} {r.last_name}</p>
                    <p className="text-xs text-gray-500">{r.company_name} · {r.email}</p>
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded-full
                    ${r.delivery_status==="sent" ? "bg-green-900/50 text-green-300"
                    : r.delivery_status==="failed" ? "bg-red-900/50 text-red-300"
                    : "bg-gray-800 text-gray-400"}`}>
                    {r.delivery_status}
                  </span>
                </div>
              ))}
            </div>
          )}

          {tab==="replies" && (
            <div className="space-y-2 max-h-80 overflow-auto">
              {detail.replies.length===0
                ? <p className="text-gray-600 text-sm text-center py-4">No replies yet</p>
                : detail.replies.map(r=>(
                <div key={r.response_id} className="bg-gray-800 rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm font-medium text-white">{r.first_name} {r.last_name}</p>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${INTENT[r.intent_label]||"bg-gray-700 text-gray-400"}`}>
                      {r.intent_label} · {r.intent_score?.toFixed(1)}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400 line-clamp-2">{r.reply_body}</p>
                  <p className="text-xs text-gray-600 mt-1">{new Date(r.responded_at).toLocaleString()}</p>
                </div>
              ))}
            </div>
          )}
        </Modal>
      )}

      {/* Edit Modal */}
      {editTarget && (
        <Modal title="Edit Campaign" onClose={()=>setEditTarget(null)} wide>
          <div className="space-y-3">
            <input className="w-full bg-gray-800 text-white rounded px-3 py-2 text-sm" placeholder="Campaign name" value={editForm.campaign_name||""} onChange={e=>setEditForm({...editForm,campaign_name:e.target.value})}/>
            <textarea className="w-full bg-gray-800 text-white rounded px-3 py-2 text-sm" rows={2} placeholder="Service description" value={editForm.service_description||""} onChange={e=>setEditForm({...editForm,service_description:e.target.value})}/>
            <input className="w-full bg-gray-800 text-white rounded px-3 py-2 text-sm" placeholder="From email" value={editForm.from_address||""} onChange={e=>setEditForm({...editForm,from_address:e.target.value})}/>
            <div className="flex gap-2">
              <input className="flex-1 bg-gray-800 text-white rounded px-3 py-2 text-sm" placeholder="Region (US, GB...)" value={editForm.filter_region||""} onChange={e=>setEditForm({...editForm,filter_region:e.target.value})}/>
              <input className="flex-1 bg-gray-800 text-white rounded px-3 py-2 text-sm" placeholder="Industry" value={editForm.filter_industry||""} onChange={e=>setEditForm({...editForm,filter_industry:e.target.value})}/>
            </div>
            <div className="flex gap-2">
              <input className="flex-1 bg-gray-800 text-white rounded px-3 py-2 text-sm" placeholder="Min score" type="number" value={editForm.filter_min_score??0} onChange={e=>setEditForm({...editForm,filter_min_score:+e.target.value})}/>
              <input className="flex-1 bg-gray-800 text-white rounded px-3 py-2 text-sm" placeholder="Max score" type="number" value={editForm.filter_max_score??100} onChange={e=>setEditForm({...editForm,filter_max_score:+e.target.value})}/>
            </div>
            <div className="flex gap-2 pt-2">
              <button onClick={saveEdit} className="flex-1 bg-indigo-700 hover:bg-indigo-600 text-white rounded px-4 py-2 text-sm">Save Changes</button>
              <button onClick={()=>setEditTarget(null)} className="flex-1 bg-gray-700 hover:bg-gray-600 text-white rounded px-4 py-2 text-sm">Cancel</button>
            </div>
          </div>
        </Modal>
      )}

      {/* Preview Modal */}
      {preview && (
        <Modal title="Email Preview" onClose={()=>setPreview(null)} wide>
          {preview==="loading" ? (
            <div className="text-center py-8 text-gray-500">
              Generating personalized email with llama3.2...
            </div>
          ) : preview.error ? (
            <p className="text-red-400 text-sm">{preview.error}</p>
          ) : (
            <div className="space-y-4">
              <div>
                <p className="text-xs text-gray-500 mb-1">To</p>
                <p className="text-sm text-white">{preview.contact?.first_name} {preview.contact?.last_name} · {preview.contact?.email}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-1">Subject</p>
                <p className="text-sm font-medium text-indigo-300">{preview.email?.subject}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-2">Email Body</p>
                <div className="bg-gray-800 rounded-lg p-4 text-sm text-gray-300 leading-relaxed"
                  dangerouslySetInnerHTML={{__html: preview.email?.html || preview.email?.text}}/>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-1">Plain text version</p>
                <pre className="bg-gray-800 rounded-lg p-3 text-xs text-gray-400 whitespace-pre-wrap max-h-32 overflow-auto">
                  {preview.email?.text}
                </pre>
              </div>
            </div>
          )}
        </Modal>
      )}
    </div>
  );
}
