import { useEffect, useState } from "react";
import { getCampaigns, createCampaign, updateCampaign, deleteCampaign, triggerCampaign } from "../api/client";
import { Plus, Play, Trash2, CheckCircle, XCircle, Pencil, X, Clock, ChevronDown, LayoutDashboard, Briefcase, Globe } from "lucide-react";

const PRESETS = [
  { label: "Every 5 minutes", value: "*/5 * * * *" },
  { label: "Every 15 minutes", value: "*/15 * * * *" },
  { label: "Every 30 minutes", value: "*/30 * * * *" },
  { label: "Hourly", value: "0 * * * *" },
  { label: "Every 6 hours", value: "0 */6 * * *" },
  { label: "Daily at 9am", value: "0 9 * * *" },
  { label: "Weekdays at 9am", value: "0 9 * * 1-5" },
  { label: "Weekly Monday", value: "0 9 * * 1" },
  { label: "Custom CRON", value: "custom" },
];

// Empty LinkedIn campaign
const EMPTY_LINKEDIN = {
  campaign_name: "",
  cron_expression: "0 9 * * 1-5",
  cron_preset: "0 9 * * 1-5",
  keywords: "python developer",
  location: "United States",
  count: 10,
  extract_jobs: true,
  extract_profiles: true,
  is_active: true,
};

// Empty Upwork campaign
const EMPTY_UPWORK = {
  campaign_name: "",
  cron_expression: "0 9 * * 1-5",
  cron_preset: "0 9 * * 1-5",
  query: "",
  location: "",
  minBudget: "",
  maxBudget: "",
  experienceLevel: [],
  jobType: "hourly",
  clientHistory: [],
  paymentVerified: false,
  maxJobAgeValue: 24,
  maxJobAgeUnit: "hours",
  is_active: true,
};

function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-[#13121f] border border-white/10 rounded-2xl w-full max-w-xl shadow-2xl shadow-black/60 flex flex-col max-h-[90vh]">
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/5 shrink-0">
          <h3 className="font-semibold text-white text-sm">{title}</h3>
          <button onClick={onClose} className="text-gray-600 hover:text-white transition-colors w-7 h-7 flex items-center justify-center rounded-lg hover:bg-white/5">
            <X size={16} />
          </button>
        </div>
        <div className="p-6 overflow-auto">{children}</div>
      </div>
    </div>
  );
}

function Field({ label, hint, children }) {
  return (
    <div>
      <label className="block text-[11px] font-semibold text-gray-500 uppercase tracking-wider mb-1.5">{label}</label>
      {children}
      {hint && <p className="text-[11px] text-gray-600 mt-1">{hint}</p>}
    </div>
  );
}

function Input({ value, onChange, placeholder, type = "text" }) {
  return (
    <input
      type={type} value={value}
      onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full bg-[#0f0e17] border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-violet-500/60 focus:ring-1 focus:ring-violet-500/20 transition-all"
    />
  );
}

function Select({ value, onChange, options }) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      className="w-full bg-[#0f0e17] border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white appearance-none focus:outline-none focus:border-violet-500/60 transition-all"
    >
      {options.map(opt => (
        <option key={opt.value} value={opt.value}>{opt.label}</option>
      ))}
    </select>
  );
}

function MultiSelect({ options, selected, onChange }) {
  const toggle = (val) => {
    if (selected.includes(val)) {
      onChange(selected.filter(v => v !== val));
    } else {
      onChange([...selected, val]);
    }
  };
  return (
    <div className="flex flex-wrap gap-2">
      {options.map(opt => (
        <button
          key={opt.value}
          type="button"
          onClick={() => toggle(opt.value)}
          className={`text-xs px-3 py-1.5 rounded-full border transition-all ${selected.includes(opt.value)
            ? "bg-violet-500/20 border-violet-500/50 text-violet-300"
            : "bg-white/5 border-white/10 text-gray-400 hover:border-white/30"
            }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

export default function Campaigns() {
  const [campaigns, setCampaigns] = useState([]);
  const [formLinkedIn, setFormLinkedIn] = useState(EMPTY_LINKEDIN);
  const [formUpwork, setFormUpwork] = useState(EMPTY_UPWORK);
  const [editId, setEditId] = useState(null);
  const [showTypeChoice, setShowTypeChoice] = useState(false);
  const [showLinkedInModal, setShowLinkedInModal] = useState(false);
  const [showUpworkModal, setShowUpworkModal] = useState(false);
  const [msg, setMsg] = useState({ text: "", type: "ok" });
  const [running, setRunning] = useState({});
  const [loading, setLoading] = useState(true);

  const load = () => getCampaigns().then(r => { setCampaigns(r.data); setLoading(false); });
  useEffect(() => { load(); }, []);

  const flash = (text, type = "ok") => { setMsg({ text, type }); setTimeout(() => setMsg({ text: "", type: "ok" }), 3000); };

  // LinkedIn helpers
  const buildLinkedInSourceConfigs = (f) => [{
    type: "linkedin",
    extract_types: [...(f.extract_jobs ? ["jobs"] : []), ...(f.extract_profiles ? ["profiles"] : [])],
    filters: { keywords: f.keywords, location: f.location, count: Number(f.count) },
  }];

  // Upwork helpers
  const buildUpworkSourceConfigs = (f) => [{
    type: "upwork",
    filters: {
      query: f.query,
      location: f.location || undefined,
      minBudget: f.minBudget ? Number(f.minBudget) : undefined,
      maxBudget: f.maxBudget ? Number(f.maxBudget) : undefined,
      experienceLevel: f.experienceLevel,
      jobType: f.jobType,
      clientHistory: f.clientHistory,
      paymentVerified: f.paymentVerified,
      maxJobAge: { value: Number(f.maxJobAgeValue), unit: f.maxJobAgeUnit },
    },
  }];

  const openCreateChoice = () => {
    setShowTypeChoice(true);
  };

  const selectLinkedIn = () => {
    setShowTypeChoice(false);
    setFormLinkedIn(EMPTY_LINKEDIN);
    setEditId(null);
    setShowLinkedInModal(true);
  };

  const selectUpwork = () => {
    setShowTypeChoice(false);
    setFormUpwork(EMPTY_UPWORK);
    setEditId(null);
    setShowUpworkModal(true);
  };

  const openEdit = (c) => {
    const sc = c.source_configs?.[0] || {};
    if (sc.type === "linkedin") {
      const et = sc.extract_types || [];
      const f = sc.filters || {};
      const preset = PRESETS.find(p => p.value === c.cron_expression && p.value !== "custom");
      setFormLinkedIn({
        campaign_name: c.campaign_name,
        cron_expression: c.cron_expression,
        cron_preset: preset ? c.cron_expression : "custom",
        keywords: f.keywords || "",
        location: f.location || "",
        count: f.count || 10,
        extract_jobs: et.includes("jobs"),
        extract_profiles: et.includes("profiles"),
        is_active: c.is_active,
      });
      setEditId(c.campaign_id);
      setShowLinkedInModal(true);
    } else if (sc.type === "upwork") {
      const f = sc.filters || {};
      const maxAge = f.maxJobAge || { value: 24, unit: "hours" };
      const preset = PRESETS.find(p => p.value === c.cron_expression && p.value !== "custom");
      setFormUpwork({
        campaign_name: c.campaign_name,
        cron_expression: c.cron_expression,
        cron_preset: preset ? c.cron_expression : "custom",
        query: f.query || "",
        location: f.location || undefined,
        minBudget: f.minBudget ? Number(f.minBudget) : undefined,
        maxBudget: f.maxBudget ? Number(f.maxBudget) : undefined,
        experienceLevel: f.experienceLevel || [],
        jobType: f.jobType || "hourly",
        clientHistory: f.clientHistory || [],
        paymentVerified: f.paymentVerified || false,
        maxJobAgeValue: maxAge.value,
        maxJobAgeUnit: maxAge.unit,
        is_active: c.is_active,
      });
      setEditId(c.campaign_id);
      setShowUpworkModal(true);
    }
  };

  const submitLinkedIn = async () => {
    if (!formLinkedIn.campaign_name.trim()) { flash("Campaign name is required", "err"); return; }
    if (!formLinkedIn.extract_jobs && !formLinkedIn.extract_profiles) { flash("Select at least one extract type", "err"); return; }
    const payload = {
      campaign_name: formLinkedIn.campaign_name,
      cron_expression: formLinkedIn.cron_expression,
      source_configs: buildLinkedInSourceConfigs(formLinkedIn),
      is_active: formLinkedIn.is_active,
    };
    try {
      if (editId) {
        await updateCampaign(editId, payload);
        flash("Campaign updated!");
      } else {
        await createCampaign(payload);
        flash("Campaign created!");
      }
      setShowLinkedInModal(false);
      setEditId(null);
      load();
    } catch (e) {
      flash("Error: " + (e.response?.data?.detail || e.message), "err");
    }
  };

  const submitUpwork = async () => {
    if (!formUpwork.campaign_name.trim()) { flash("Campaign name is required", "err"); return; }
    if (!formUpwork.query.trim()) { flash("Search query is required", "err"); return; }
    const payload = {
      campaign_name: formUpwork.campaign_name,
      cron_expression: formUpwork.cron_expression,
      source_configs: buildUpworkSourceConfigs(formUpwork),
      is_active: formUpwork.is_active,
    };
    try {
      if (editId) {
        await updateCampaign(editId, payload);
        flash("Campaign updated!");
      } else {
        await createCampaign(payload);
        flash("Campaign created!");
      }
      setShowUpworkModal(false);
      setEditId(null);
      load();
    } catch (e) {
      flash("Error: " + (e.response?.data?.detail || e.message), "err");
    }
  };

  const trigger = async (id, name) => {
    setRunning(r => ({ ...r, [id]: true }));
    try {
      await triggerCampaign(id);
      flash(`Campaign "${name}" triggered!`);
    } catch (e) {
      flash("Trigger failed", "err");
    }
    setTimeout(() => setRunning(r => ({ ...r, [id]: false })), 3000);
  };

  const remove = async (id, name) => {
    if (!confirm(`Deactivate campaign "${name}"?`)) return;
    await deleteCampaign(id);
    flash("Campaign deactivated");
    load();
  };

  const presetLabel = (cron) => PRESETS.find(p => p.value === cron)?.label || cron;
  const activeCampaigns = campaigns.filter(c => c.is_active).length;

  return (
    <div className="p-8 max-w-7xl mx-auto">

      {/* Header */}
      <div className="flex items-start justify-between mb-8 relative">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight">Campaigns</h2>
          <p className="text-sm text-gray-500 mt-1">Define what data to extract, from where, and how often</p>
        </div>
        <div className="relative">
          <button
            onClick={openCreateChoice}
            className="flex items-center gap-2 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all shadow-lg shadow-indigo-900/30 hover:shadow-indigo-900/50"
          >
            <Plus size={15} /> New Campaign
          </button>
          {showTypeChoice && (
            <div className="absolute right-0 mt-2 w-48 bg-[#1c1b2b] border border-white/10 rounded-xl shadow-xl z-50 overflow-hidden">
              <button
                onClick={selectLinkedIn}
                className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-gray-200 hover:bg-white/5 transition-colors"
              >
                <Globe size={14} /> LinkedIn Campaign
              </button>
              <button
                onClick={selectUpwork}
                className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-gray-200 hover:bg-white/5 transition-colors border-t border-white/5"
              >
                <Briefcase size={14} /> Upwork Campaign
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        {[
          { label: "Total Campaigns", value: campaigns.length, color: "text-violet-400", bg: "bg-violet-500/10 border-violet-500/20" },
          { label: "Active", value: activeCampaigns, color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/20" },
          { label: "Inactive", value: campaigns.length - activeCampaigns, color: "text-gray-400", bg: "bg-white/5 border-white/10" },
        ].map(({ label, value, color, bg }) => (
          <div key={label} className={`rounded-2xl border p-5 ${bg}`}>
            <p className="text-xs text-gray-500 font-medium uppercase tracking-wider mb-2">{label}</p>
            <p className={`text-3xl font-bold ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Flash message */}
      {msg.text && (
        <div className={`mb-6 px-4 py-3 rounded-xl text-sm flex items-center gap-2 border
          ${msg.type === "err"
            ? "bg-red-500/10 border-red-500/20 text-red-300"
            : "bg-emerald-500/10 border-emerald-500/20 text-emerald-300"}`}>
          {msg.type === "err" ? <XCircle size={14} /> : <CheckCircle size={14} />}
          {msg.text}
        </div>
      )}

      {/* Campaigns Table */}
      <div className="bg-[#13121f] border border-white/5 rounded-2xl overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-gray-600 text-sm">Loading campaigns...</div>
        ) : campaigns.length === 0 ? (
          <div className="p-16 text-center">
            <LayoutDashboard size={36} className="text-gray-700 mx-auto mb-4" />
            <p className="text-gray-500 text-sm mb-3">No campaigns yet</p>
            <button onClick={openCreateChoice} className="text-violet-400 text-sm hover:text-violet-300 underline underline-offset-2">
              Create your first campaign
            </button>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/5">
                {["Campaign", "Frequency", "Source", "Details", "Status", "Last Run", "Actions"].map(h => (
                  <th key={h} className="text-left px-5 py-3.5 text-[11px] font-semibold text-gray-600 uppercase tracking-wider">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {campaigns.map(c => {
                const sc = c.source_configs?.[0] || {};
                const sourceType = sc.type === "linkedin" ? "LinkedIn" : (sc.type === "upwork" ? "Upwork" : sc.type);
                let details = "";
                if (sc.type === "linkedin") {
                  const f = sc.filters || {};
                  details = `${f.keywords || "—"} · ${f.location || "—"} · ${f.count || 10} records`;
                } else if (sc.type === "upwork") {
                  const f = sc.filters || {};
                  details = `${f.query || "—"} · ${(f.experienceLevel || []).join(", ") || "any"} · ${f.jobType || "any"}`;
                }
                return (
                  <tr key={c.campaign_id} className="hover:bg-white/[0.02] transition-colors group">
                    <td className="px-5 py-4">
                      <p className="text-sm font-semibold text-white">{c.campaign_name}</p>
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-1.5 text-gray-300 text-xs">
                        <Clock size={11} className="text-gray-600" />
                        {presetLabel(c.cron_expression)}
                      </div>
                      <code className="text-[11px] text-gray-600 mt-0.5 block">{c.cron_expression}</code>
                    </td>
                    <td className="px-5 py-4">
                      <span className="inline-flex items-center gap-1.5 text-xs bg-white/5 border border-white/10 px-2.5 py-1 rounded-full">
                        {sourceType === "LinkedIn" ? <Globe size={10} /> : <Briefcase size={10} />}
                        {sourceType}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-xs text-gray-300 max-w-xs truncate">
                      {details}
                    </td>
                    <td className="px-5 py-4">
                      {c.is_active
                        ? <span className="inline-flex items-center gap-1.5 text-emerald-400 text-xs font-medium bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded-full">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />Active
                        </span>
                        : <span className="inline-flex items-center gap-1.5 text-gray-500 text-xs font-medium bg-white/5 border border-white/10 px-2.5 py-1 rounded-full">
                          <span className="w-1.5 h-1.5 rounded-full bg-gray-600" />Inactive
                        </span>}
                    </td>
                    <td className="px-5 py-4 text-xs text-gray-600">
                      {c.last_run_at ? new Date(c.last_run_at).toLocaleString() : "Never"}
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex gap-1.5 opacity-70 group-hover:opacity-100 transition-opacity">
                        <button onClick={() => trigger(c.campaign_id, c.campaign_name)}
                          disabled={running[c.campaign_id]}
                          className="flex items-center gap-1.5 bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/20 text-emerald-400 px-3 py-1.5 rounded-lg text-xs font-medium transition-all disabled:opacity-40">
                          <Play size={10} />{running[c.campaign_id] ? "Running..." : "Run"}
                        </button>
                        <button onClick={() => openEdit(c)}
                          className="flex items-center gap-1.5 bg-white/5 hover:bg-white/10 border border-white/10 text-gray-300 px-3 py-1.5 rounded-lg text-xs font-medium transition-all">
                          <Pencil size={10} /> Edit
                        </button>
                        <button onClick={() => remove(c.campaign_id, c.campaign_name)}
                          className="flex items-center gap-1.5 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 text-red-400 px-2.5 py-1.5 rounded-lg text-xs transition-all">
                          <Trash2 size={10} />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* LinkedIn Modal */}
      {showLinkedInModal && (
        <Modal title={editId ? "Edit LinkedIn Campaign" : "New LinkedIn Campaign"} onClose={() => { setShowLinkedInModal(false); setEditId(null); }}>
          <div className="space-y-4">
            <Field label="Campaign Name" hint="Give it a descriptive name">
              <Input value={formLinkedIn.campaign_name} onChange={v => setFormLinkedIn(f => ({ ...f, campaign_name: v }))} placeholder="LinkedIn Python Developers Q3" />
            </Field>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Keywords" hint="Search terms for LinkedIn">
                <Input value={formLinkedIn.keywords} onChange={v => setFormLinkedIn(f => ({ ...f, keywords: v }))} placeholder="python developer" />
              </Field>
              <Field label="Location">
                <Input value={formLinkedIn.location} onChange={v => setFormLinkedIn(f => ({ ...f, location: v }))} placeholder="United States" />
              </Field>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Records per run" hint="Max records per campaign run">
                <Input type="number" value={formLinkedIn.count} onChange={v => setFormLinkedIn(f => ({ ...f, count: v }))} placeholder="10" />
              </Field>
              <Field label="Extract types">
                <div className="flex gap-4 mt-2.5">
                  {[["extract_jobs", "Jobs"], ["extract_profiles", "Profiles"]].map(([key, label]) => (
                    <label key={key} className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                      <input type="checkbox" checked={formLinkedIn[key]}
                        onChange={e => setFormLinkedIn(f => ({ ...f, [key]: e.target.checked }))}
                        className="accent-violet-500 w-4 h-4 rounded" />
                      {label}
                    </label>
                  ))}
                </div>
              </Field>
            </div>

            <Field label="Run Frequency">
              <div className="relative">
                <select value={formLinkedIn.cron_preset} onChange={e => {
                  const val = e.target.value;
                  if (val === "custom") {
                    setFormLinkedIn(f => ({ ...f, cron_preset: val }));
                  } else {
                    setFormLinkedIn(f => ({ ...f, cron_preset: val, cron_expression: val }));
                  }
                }} className="w-full bg-[#0f0e17] border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white appearance-none">
                  {PRESETS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
                </select>
                <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
              </div>
            </Field>

            {formLinkedIn.cron_preset === "custom" && (
              <Field label="Custom CRON Expression" hint="e.g. 0 9 * * 1-5 = weekdays at 9am">
                <Input value={formLinkedIn.cron_expression} onChange={v => setFormLinkedIn(f => ({ ...f, cron_expression: v }))} placeholder="0 9 * * 1-5" />
              </Field>
            )}

            <Field label="Status">
              <div className="flex gap-4 mt-1">
                {[["true", "Active"], ["false", "Inactive"]].map(([val, label]) => (
                  <label key={val} className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                    <input type="radio" name="status-linkedin" value={val}
                      checked={String(formLinkedIn.is_active) === val}
                      onChange={() => setFormLinkedIn(f => ({ ...f, is_active: val === "true" }))}
                      className="accent-violet-500" />
                    {label}
                  </label>
                ))}
              </div>
            </Field>

            <div className="bg-[#0f0e17] border border-white/5 rounded-xl p-4 text-xs text-gray-500 space-y-1.5">
              <p className="font-semibold text-gray-400 mb-2 text-[11px] uppercase tracking-wider">Campaign Preview</p>
              <p>Keywords: <span className="text-gray-200">{formLinkedIn.keywords || "—"}</span></p>
              <p>Location: <span className="text-gray-200">{formLinkedIn.location || "—"}</span></p>
              <p>Extracts: <span className="text-gray-200">{[formLinkedIn.extract_jobs && "Jobs", formLinkedIn.extract_profiles && "Profiles"].filter(Boolean).join(" + ") || "none"}</span></p>
              <p>Count: <span className="text-gray-200">{formLinkedIn.count} records per run</span></p>
              <p>Schedule: <span className="text-gray-200">{presetLabel(formLinkedIn.cron_preset === "custom" ? formLinkedIn.cron_expression : formLinkedIn.cron_preset)}</span></p>
              <p>CRON: <code className="text-violet-400">{formLinkedIn.cron_expression}</code></p>
            </div>

            <div className="flex gap-3 pt-1">
              <button onClick={submitLinkedIn}
                className="flex-1 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 py-2.5 rounded-xl text-sm font-semibold transition-all shadow-lg shadow-indigo-900/30">
                {editId ? "Save Changes" : "Create Campaign"}
              </button>
              <button onClick={() => { setShowLinkedInModal(false); setEditId(null); }}
                className="px-5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-sm text-gray-400 transition-all">
                Cancel
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Upwork Modal */}
      {showUpworkModal && (
        <Modal title={editId ? "Edit Upwork Campaign" : "New Upwork Campaign"} onClose={() => { setShowUpworkModal(false); setEditId(null); }}>
          <div className="space-y-4">
            <Field label="Campaign Name" hint="Give it a descriptive name">
              <Input value={formUpwork.campaign_name} onChange={v => setFormUpwork(f => ({ ...f, campaign_name: v }))} placeholder="Upwork Python Jobs" />
            </Field>

            <Field label="Search Query" hint="Keywords for Upwork job search">
              <Input value={formUpwork.query} onChange={v => setFormUpwork(f => ({ ...f, query: v }))} placeholder="web scraping, python developer" />
            </Field>

            <Field label="Location (optional)" hint="City, country, or remote">
              <Input value={formUpwork.location} onChange={v => setFormUpwork(f => ({ ...f, location: v }))} placeholder="United States, Europe, Remote" />
            </Field>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Min Budget" hint="Minimum hourly rate or fixed price">
                <Input type="number" value={formUpwork.minBudget} onChange={v => setFormUpwork(f => ({ ...f, minBudget: v }))} placeholder="30" />
              </Field>
              <Field label="Max Budget" hint="Maximum hourly rate or fixed price">
                <Input type="number" value={formUpwork.maxBudget} onChange={v => setFormUpwork(f => ({ ...f, maxBudget: v }))} placeholder="100" />
              </Field>
            </div>

            <Field label="Experience Level" hint="Select one or more">
              <MultiSelect
                options={[
                  { value: "entry", label: "Entry Level" },
                  { value: "intermediate", label: "Intermediate" },
                  { value: "expert", label: "Expert" },
                ]}
                selected={formUpwork.experienceLevel}
                onChange={v => setFormUpwork(f => ({ ...f, experienceLevel: v }))}
              />
            </Field>

            <Field label="Job Type">
              <div className="flex gap-4 mt-2">
                {["hourly", "fixed"].map(type => (
                  <label key={type} className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                    <input type="radio" name="jobType"
                      checked={formUpwork.jobType === type}
                      onChange={() => setFormUpwork(f => ({ ...f, jobType: type }))}
                      className="accent-violet-500" />
                    {type === "hourly" ? "Hourly" : "Fixed Price"}
                  </label>
                ))}
              </div>
            </Field>

            <Field label="Client History" hint="Past hiring activity">
              <MultiSelect
                options={[
                  { value: "noHires", label: "No hires yet" },
                  { value: "1to9Hires", label: "1–9 hires" },
                  { value: "10+Hires", label: "10+ hires" },
                ]}
                selected={formUpwork.clientHistory}
                onChange={v => setFormUpwork(f => ({ ...f, clientHistory: v }))}
              />
            </Field>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Payment Verified">
                <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer mt-2">
                  <input type="checkbox"
                    checked={formUpwork.paymentVerified}
                    onChange={e => setFormUpwork(f => ({ ...f, paymentVerified: e.target.checked }))}
                    className="accent-violet-500 w-4 h-4 rounded" />
                  Only show clients with verified payment
                </label>
              </Field>
              <Field label="Max Job Age" hint="Ignore jobs older than this">
                <div className="flex gap-2">
                  <Input type="number" value={formUpwork.maxJobAgeValue}
                    onChange={v => setFormUpwork(f => ({ ...f, maxJobAgeValue: v }))}
                    placeholder="24" className="flex-1" />
                  <select value={formUpwork.maxJobAgeUnit}
                    onChange={e => setFormUpwork(f => ({ ...f, maxJobAgeUnit: e.target.value }))}
                    className="bg-[#0f0e17] border border-white/10 rounded-xl px-3 py-2 text-sm text-white">
                    <option value="hours">Hours</option>
                    <option value="days">Days</option>
                  </select>
                </div>
              </Field>
            </div>

            <Field label="Run Frequency">
              <div className="relative">
                <select value={formUpwork.cron_preset} onChange={e => {
                  const val = e.target.value;
                  if (val === "custom") {
                    setFormUpwork(f => ({ ...f, cron_preset: val }));
                  } else {
                    setFormUpwork(f => ({ ...f, cron_preset: val, cron_expression: val }));
                  }
                }} className="w-full bg-[#0f0e17] border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white appearance-none">
                  {PRESETS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
                </select>
                <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
              </div>
            </Field>

            {formUpwork.cron_preset === "custom" && (
              <Field label="Custom CRON Expression" hint="e.g. 0 */2 * * * = every 2 hours">
                <Input value={formUpwork.cron_expression} onChange={v => setFormUpwork(f => ({ ...f, cron_expression: v }))} placeholder="0 */2 * * *" />
              </Field>
            )}

            <Field label="Status">
              <div className="flex gap-4 mt-1">
                {[["true", "Active"], ["false", "Inactive"]].map(([val, label]) => (
                  <label key={val} className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                    <input type="radio" name="status-upwork" value={val}
                      checked={String(formUpwork.is_active) === val}
                      onChange={() => setFormUpwork(f => ({ ...f, is_active: val === "true" }))}
                      className="accent-violet-500" />
                    {label}
                  </label>
                ))}
              </div>
            </Field>

            <div className="bg-[#0f0e17] border border-white/5 rounded-xl p-4 text-xs text-gray-500 space-y-1.5">
              <p className="font-semibold text-gray-400 mb-2 text-[11px] uppercase tracking-wider">Campaign Preview</p>
              <p>Query: <span className="text-gray-200">{formUpwork.query || "—"}</span></p>
              <p>Location: <span className="text-gray-200">{formUpwork.location || "any"}</span></p>
              <p>Budget: <span className="text-gray-200">
                {formUpwork.minBudget || "any"} - {formUpwork.maxBudget || "any"}
                {formUpwork.jobType === "hourly" ? " USD/hr" : " USD"}
              </span></p>
              <p>Experience: <span className="text-gray-200">{formUpwork.experienceLevel.join(", ") || "any"}</span></p>
              <p>Job Type: <span className="text-gray-200">{formUpwork.jobType === "hourly" ? "Hourly" : "Fixed"}</span></p>
              <p>Client History: <span className="text-gray-200">{formUpwork.clientHistory.join(", ") || "any"}</span></p>
              <p>Max Age: <span className="text-gray-200">{formUpwork.maxJobAgeValue} {formUpwork.maxJobAgeUnit}</span></p>
              <p>Schedule: <span className="text-gray-200">{presetLabel(formUpwork.cron_preset === "custom" ? formUpwork.cron_expression : formUpwork.cron_preset)}</span></p>
              <p>CRON: <code className="text-violet-400">{formUpwork.cron_expression}</code></p>
            </div>

            <div className="flex gap-3 pt-1">
              <button onClick={submitUpwork}
                className="flex-1 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 py-2.5 rounded-xl text-sm font-semibold transition-all shadow-lg shadow-indigo-900/30">
                {editId ? "Save Changes" : "Create Campaign"}
              </button>
              <button onClick={() => { setShowUpworkModal(false); setEditId(null); }}
                className="px-5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-sm text-gray-400 transition-all">
                Cancel
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}