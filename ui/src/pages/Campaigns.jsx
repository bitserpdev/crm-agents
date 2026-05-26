import { useEffect, useState } from "react";
import { getCampaigns, createCampaign, updateCampaign, deleteCampaign, triggerCampaign, validateFilters } from "../api/client";
import { Plus, Play, Trash2, CheckCircle, XCircle, Pencil, X, Clock, ChevronDown, LayoutDashboard } from "lucide-react";

const PRESETS = [
  { label: "Every 5 minutes",  value: "*/5 * * * *" },
  { label: "Every 15 minutes", value: "*/15 * * * *" },
  { label: "Every 30 minutes", value: "*/30 * * * *" },
  { label: "Hourly",           value: "0 * * * *" },
  { label: "Every 6 hours",    value: "0 */6 * * *" },
  { label: "Daily at 9am",     value: "0 9 * * *" },
  { label: "Weekdays at 9am",  value: "0 9 * * 1-5" },
  { label: "Weekly Monday",    value: "0 9 * * 1" },
  { label: "Custom CRON",      value: "custom" },
];

const MANAGEMENT_TIERS = [
  { value: "", label: "Any tier" },
  { value: "c_suite",    label: "C-Suite (CEO, CTO, CFO...)" },
  { value: "vp",         label: "VP / SVP / EVP" },
  { value: "director",   label: "Director" },
  { value: "manager",    label: "Manager / Head of" },
  { value: "individual", label: "Individual Contributor" },
];

const EMPTY = {
  campaign_name: "",
  cron_expression: "0 9 * * 1-5",
  cron_preset: "0 9 * * 1-5",
  keywords: "",
  location: "",
  count: 10,
  extract_jobs: false,
  extract_profiles: true,
  is_active: true,
  lf_industry: "",
  lf_region: "",
  lf_management_tier: "",
  lf_email: false,
  lf_phone: false,
  lf_domain: "",
  filter_match_mode: "all",
};

function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-[#13121f] border border-white/10 rounded-2xl w-full max-w-xl shadow-2xl shadow-black/60 max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
          <h3 className="font-semibold text-white text-sm">{title}</h3>
          <button onClick={onClose} className="text-gray-600 hover:text-white transition-colors w-7 h-7 flex items-center justify-center rounded-lg hover:bg-white/5">
            <X size={16}/>
          </button>
        </div>
        <div className="p-6 overflow-y-auto flex-1">{children}</div>
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

export default function Campaigns() {
  const [campaigns, setCampaigns] = useState([]);
  const [form, setForm]           = useState(EMPTY);
  const [editId, setEditId]       = useState(null);
  const [showForm, setShowForm]   = useState(false);
  const [msg, setMsg]             = useState({ text: "", type: "ok" });
  const [running, setRunning]     = useState({});
  const [loading, setLoading]     = useState(true);
  const [filterErrors, setFilterErrors] = useState({});
  const [validating, setValidating]     = useState(false);

  const load = () => getCampaigns().then(r => { setCampaigns(r.data); setLoading(false); });
  useEffect(() => { load(); }, []);

  const flash = (text, type = "ok") => { setMsg({ text, type }); setTimeout(() => setMsg({ text: "", type: "ok" }), 3000); };

  const buildLinkedInFilters = (f) => {
    const lf = {};
    if (f.lf_industry)        lf.industry        = f.lf_industry;
    if (f.lf_region)          lf.region          = f.lf_region;
    if (f.lf_management_tier) lf.management_tier = f.lf_management_tier;
    if (f.lf_email)           lf.email           = true;
    if (f.lf_phone)           lf.phone           = true;
    if (f.lf_domain)          lf.domain          = f.lf_domain;
    return lf;
  };

  const buildSourceConfigs = (f) => {
    const lf = buildLinkedInFilters(f);
    // Auto-build keywords from filters if not manually set
    const parts = [];
    if (f.lf_management_tier) parts.push(f.lf_management_tier.replace("_", " "));
    if (f.lf_industry) parts.push(f.lf_industry);
    const autoKeywords = parts.join(" ") || f.lf_industry || "professional";
    const autoLocation = f.lf_region || "United States";
    return [{
      type: "linkedin",
      extract_types: [...(f.extract_jobs ? ["jobs"] : []), ...(f.extract_profiles ? ["profiles"] : [])],
      filters: { keywords: autoKeywords, location: autoLocation, count: Number(f.count) },
      linkedin_filters: lf,
      filter_match_mode: f.filter_match_mode,
    }];
  };

  const openCreate = () => { setForm(EMPTY); setEditId(null); setShowForm(true); };

  const openEdit = (c) => {
    const sc = c.source_configs?.[0] || {};
    const et = sc.extract_types || [];
    const f  = sc.filters || {};
    const lf = c.linkedin_filters || sc.linkedin_filters || {};
    const preset = PRESETS.find(p => p.value === c.cron_expression && p.value !== "custom");
    setForm({
      campaign_name: c.campaign_name,
      cron_expression: c.cron_expression,
      cron_preset: preset ? c.cron_expression : "custom",
      keywords: "",
      location: "",
      count: f.count || 10,
      extract_jobs: et.includes("jobs"),
      extract_profiles: et.includes("profiles"),
      is_active: c.is_active,
      lf_industry: lf.industry || "",
      lf_region: lf.region || "",
      lf_management_tier: lf.management_tier || "",
      lf_email: lf.email || false,
      lf_phone: lf.phone || false,
      lf_domain: lf.domain || "",
      filter_match_mode: c.filter_match_mode || "all",
    });
    setEditId(c.campaign_id);
    setShowForm(true);
  };

  const handlePreset = (val) => {
    if (val === "custom") {
      setForm(f => ({ ...f, cron_preset: "custom" }));
    } else {
      setForm(f => ({ ...f, cron_preset: val, cron_expression: val }));
    }
  };

  const submit = async () => {
    if (!form.campaign_name.trim()) { flash("Campaign name is required", "err"); return; }


    // Validate filters with LLM
    const hasFilters = form.lf_industry || form.lf_region || form.lf_management_tier || form.lf_domain;
    if (hasFilters) {
      setValidating(true);
      setFilterErrors({});
      let filtersOk = true;
      try {
        const { data: val } = await validateFilters({
          industry:        form.lf_industry || null,
          region:          form.lf_region || null,
          management_tier: form.lf_management_tier || null,
          domain:          form.lf_domain || null,
        });
        setFilterErrors(val.checks || {});
        if (!val.valid) {
          filtersOk = false;
          flash("Some filters are invalid — check the highlighted fields below", "err");
        }
      } catch (e) {
        filtersOk = false;
        flash("Validation service busy — please try again in a moment", "err");
      } finally {
        setValidating(false);
      }
      if (!filtersOk) return;
    }

    const lf = buildLinkedInFilters(form);
    const payload = {
      campaign_name:     form.campaign_name,
      cron_expression:   form.cron_expression,
      source_configs:    buildSourceConfigs(form),
      is_active:         form.is_active,
      linkedin_filters:  Object.keys(lf).length ? lf : undefined,
      filter_match_mode: form.filter_match_mode,
    };
    try {
      if (editId) {
        await updateCampaign(editId, payload);
        flash("Campaign updated!");
      } else {
        await createCampaign(payload);
        flash("Campaign created!");
      }
      setShowForm(false);
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
      <div className="flex items-start justify-between mb-8">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight">Campaigns</h2>
          <p className="text-sm text-gray-500 mt-1">Define what data to extract, from where, and how often</p>
        </div>
        <button onClick={openCreate}
          className="flex items-center gap-2 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all shadow-lg shadow-indigo-900/30 hover:shadow-indigo-900/50">
          <Plus size={15}/> New Campaign
        </button>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        {[
          { label: "Total Campaigns", value: campaigns.length,  color: "text-violet-400", bg: "bg-violet-500/10 border-violet-500/20" },
          { label: "Active",          value: activeCampaigns,   color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/20" },
          { label: "Inactive",        value: campaigns.length - activeCampaigns, color: "text-gray-400", bg: "bg-white/5 border-white/10" },
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
          {msg.type === "err" ? <XCircle size={14}/> : <CheckCircle size={14}/>}
          {msg.text}
        </div>
      )}

      {/* Table */}
      <div className="bg-[#13121f] border border-white/5 rounded-2xl overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-gray-600 text-sm">Loading campaigns...</div>
        ) : campaigns.length === 0 ? (
          <div className="p-16 text-center">
            <LayoutDashboard size={36} className="text-gray-700 mx-auto mb-4"/>
            <p className="text-gray-500 text-sm mb-3">No campaigns yet</p>
            <button onClick={openCreate} className="text-violet-400 text-sm hover:text-violet-300 underline underline-offset-2">
              Create your first campaign
            </button>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/5">
                {["Campaign", "Frequency", "Extracts", "Keywords", "Status", "Last Run", "Actions"].map(h => (
                  <th key={h} className="text-left px-5 py-3.5 text-[11px] font-semibold text-gray-600 uppercase tracking-wider">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {campaigns.map(c => {
                const sc = c.source_configs?.[0] || {};
                const et = sc.extract_types || [];
                const kw = sc.filters?.keywords || "—";
                return (
                  <tr key={c.campaign_id} className="hover:bg-white/[0.02] transition-colors group">
                    <td className="px-5 py-4">
                      <p className="text-sm font-semibold text-white">{c.campaign_name}</p>
                      <p className="text-xs text-gray-600 mt-0.5">{sc.filters?.location || "—"}</p>
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-1.5 text-gray-300 text-xs">
                        <Clock size={11} className="text-gray-600"/>
                        {presetLabel(c.cron_expression)}
                      </div>
                      <code className="text-[11px] text-gray-600 mt-0.5 block">{c.cron_expression}</code>
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex gap-1.5 flex-wrap">
                        {et.map(t => (
                          <span key={t} className="text-[11px] bg-violet-500/15 text-violet-300 border border-violet-500/20 px-2 py-0.5 rounded-full capitalize font-medium">
                            {t}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <span className="text-xs text-gray-300 font-medium">{kw}</span>
                      <span className="text-xs text-gray-600 ml-1">×{sc.filters?.count || 10}</span>
                    </td>
                    <td className="px-5 py-4">
                      {c.is_active
                        ? <span className="inline-flex items-center gap-1.5 text-emerald-400 text-xs font-medium bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded-full">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"/>Active
                          </span>
                        : <span className="inline-flex items-center gap-1.5 text-gray-500 text-xs font-medium bg-white/5 border border-white/10 px-2.5 py-1 rounded-full">
                            <span className="w-1.5 h-1.5 rounded-full bg-gray-600"/>Inactive
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
                          <Play size={10}/>{running[c.campaign_id] ? "Running..." : "Run"}
                        </button>
                        <button onClick={() => openEdit(c)}
                          className="flex items-center gap-1.5 bg-white/5 hover:bg-white/10 border border-white/10 text-gray-300 px-3 py-1.5 rounded-lg text-xs font-medium transition-all">
                          <Pencil size={10}/> Edit
                        </button>
                        <button onClick={() => remove(c.campaign_id, c.campaign_name)}
                          className="flex items-center gap-1.5 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 text-red-400 px-2.5 py-1.5 rounded-lg text-xs transition-all">
                          <Trash2 size={10}/>
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

      {/* Modal */}
      {showForm && (
        <Modal title={editId ? "Edit Campaign" : "New Campaign"} onClose={() => { setShowForm(false); setEditId(null); }}>
          <div className="space-y-4">
            <Field label="Campaign Name" hint="Give it a descriptive name you'll recognize">
              <Input value={form.campaign_name} onChange={v => setForm(f => ({ ...f, campaign_name: v }))} placeholder="LinkedIn Python Developers Q3"/>
            </Field>

{/* LinkedIn Filters */}
            <div className="border border-violet-500/20 rounded-xl p-4 space-y-3 bg-violet-500/5">
              <div className="flex items-center justify-between">
                <p className="text-[11px] font-semibold text-violet-400 uppercase tracking-wider">LinkedIn Filters</p>
                <div className="flex gap-3">
                  {["all", "any"].map(mode => (
                    <label key={mode} className="flex items-center gap-1.5 text-xs text-gray-400 cursor-pointer">
                      <input type="radio" name="filter_match_mode" value={mode}
                        checked={form.filter_match_mode === mode}
                        onChange={() => setForm(f => ({ ...f, filter_match_mode: mode }))}
                        className="accent-violet-500"/>
                      <span className={form.filter_match_mode === mode ? "text-violet-400 font-semibold" : ""}>
                        {mode === "all" ? "Match ALL (AND)" : "Match ANY (OR)"}
                      </span>
                    </label>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Industry">
                  <Input value={form.lf_industry} onChange={v => { setForm(f => ({ ...f, lf_industry: v })); setFilterErrors(e => ({...e, industry: null})); }} placeholder="e.g. Telecom, Finance"/>
                  {filterErrors.industry && !filterErrors.industry.valid && (
                    <p className="text-red-400 text-xs mt-1">⚠ {filterErrors.industry.reason}{filterErrors.industry.suggestion ? ` — try "${filterErrors.industry.suggestion}"` : ""}</p>
                  )}
                </Field>
                <Field label="Region">
                  <Input value={form.lf_region} onChange={v => { setForm(f => ({ ...f, lf_region: v })); setFilterErrors(e => ({...e, region: null})); }} placeholder="e.g. United States, UK"/>
                  {filterErrors.region && !filterErrors.region.valid && (
                    <p className="text-red-400 text-xs mt-1">⚠ {filterErrors.region.reason}{filterErrors.region.suggestion ? ` — try "${filterErrors.region.suggestion}"` : ""}</p>
                  )}
                </Field>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Management Tier">
                  <div className="relative">
                    <select value={form.lf_management_tier}
                      onChange={e => setForm(f => ({ ...f, lf_management_tier: e.target.value }))}
                      className="w-full bg-[#0f0e17] border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white appearance-none focus:outline-none focus:border-violet-500/60 transition-all">
                      {MANAGEMENT_TIERS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                    </select>
                  </div>
                </Field>
                <Field label="Domain">
                  <Input value={form.lf_domain} onChange={v => { setForm(f => ({ ...f, lf_domain: v })); setFilterErrors(e => ({...e, domain: null})); }} placeholder="e.g. company.com"/>
                  {filterErrors.domain && !filterErrors.domain.valid && (
                    <p className="text-red-400 text-xs mt-1">⚠ {filterErrors.domain.reason}{filterErrors.domain.suggestion ? ` — try "${filterErrors.domain.suggestion}"` : ""}</p>
                  )}
                </Field>
              </div>
              <div className="flex gap-5 pt-1">
                {[["lf_email", "Must have Email"], ["lf_phone", "Must have Phone"]].map(([key, label]) => (
                  <label key={key} className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                    <input type="checkbox" checked={form[key]}
                      onChange={e => setForm(f => ({ ...f, [key]: e.target.checked }))}
                      className="accent-violet-500 w-4 h-4 rounded"/>
                    {label}
                  </label>
                ))}
              </div>
            </div>


<div className="grid grid-cols-2 gap-4">
              <Field label="Records per run" hint="Max records per campaign run">
                <Input type="number" value={form.count} onChange={v => setForm(f => ({ ...f, count: v }))} placeholder="10"/>
              </Field>
              <Field label="Extract types">
                <div className="flex gap-4 mt-2.5">
                  {[["extract_profiles", "Profiles"]].map(([key, label]) => (
                    <label key={key} className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                      <input type="checkbox" checked={form[key]}
                        onChange={e => setForm(f => ({ ...f, [key]: e.target.checked }))}
                        className="accent-violet-500 w-4 h-4 rounded"/>
                      {label}
                    </label>
                  ))}
                </div>
              </Field>
            </div>

            <Field label="Run Frequency">
              <div className="relative">
                <select value={form.cron_preset} onChange={e => handlePreset(e.target.value)}
                  className="w-full bg-[#0f0e17] border border-white/10 rounded-xl px-3 py-2.5 text-sm text-white appearance-none focus:outline-none focus:border-violet-500/60 transition-all">
                  {PRESETS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
                </select>
                <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none"/>
              </div>
            </Field>

            {form.cron_preset === "custom" && (
              <Field label="Custom CRON Expression" hint="e.g. 0 9 * * 1-5 = weekdays at 9am">
                <Input value={form.cron_expression} onChange={v => setForm(f => ({ ...f, cron_expression: v }))} placeholder="0 9 * * 1-5"/>
              </Field>
            )}

            <Field label="Status">
              <div className="flex gap-4 mt-1">
                {[["true", "Active"], ["false", "Inactive"]].map(([val, label]) => (
                  <label key={val} className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                    <input type="radio" name="status" value={val}
                      checked={String(form.is_active) === val}
                      onChange={() => setForm(f => ({ ...f, is_active: val === "true" }))}
                      className="accent-violet-500"/>
                    {label}
                  </label>
                ))}
              </div>
            </Field>

{/* Preview */}
            <div className="bg-[#0f0e17] border border-white/5 rounded-xl p-4 text-xs text-gray-500 space-y-1.5">
              <p className="font-semibold text-gray-400 mb-2 text-[11px] uppercase tracking-wider">Campaign Preview</p>
              <p>Schedule: <span className="text-gray-200">{presetLabel(form.cron_preset === "custom" ? form.cron_expression : form.cron_preset)}</span></p>
              <p>CRON: <code className="text-violet-400">{form.cron_expression}</code></p>
              {(form.lf_industry || form.lf_region || form.lf_management_tier || form.lf_email || form.lf_phone || form.lf_domain) && (
                <div className="border-t border-white/5 pt-1.5 mt-1.5">
                  <p className="text-gray-500 font-semibold mb-1">Filters ({form.filter_match_mode.toUpperCase()}):</p>
                  {form.lf_industry && <p>Industry: <span className="text-gray-200">{form.lf_industry}</span></p>}
                  {form.lf_region && <p>Region: <span className="text-gray-200">{form.lf_region}</span></p>}
                  {form.lf_management_tier && <p>Tier: <span className="text-gray-200">{form.lf_management_tier}</span></p>}
                  {form.lf_domain && <p>Domain: <span className="text-gray-200">{form.lf_domain}</span></p>}
                  {form.lf_email && <p>Must have: <span className="text-gray-200">Email ✓</span></p>}
                  {form.lf_phone && <p>Must have: <span className="text-gray-200">Phone ✓</span></p>}
                </div>
              )}
            </div>

            <div className="flex gap-3 pt-1">
              {msg.text && (
                <div className={`px-4 py-3 rounded-xl text-sm flex items-center gap-2 border
                  ${msg.type === "err"
                    ? "bg-red-500/10 border-red-500/20 text-red-300"
                    : "bg-emerald-500/10 border-emerald-500/20 text-emerald-300"}`}>
                  {msg.type === "err" ? <XCircle size={14}/> : <CheckCircle size={14}/>}
                  {msg.text}
                </div>
              )}
              <button onClick={submit}
                className="flex-1 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 py-2.5 rounded-xl text-sm font-semibold transition-all shadow-lg shadow-indigo-900/30">
                {validating ? "Validating filters..." : editId ? "Save Changes" : "Create Campaign"}
              </button>
              <button onClick={() => { setShowForm(false); setEditId(null); }}
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
