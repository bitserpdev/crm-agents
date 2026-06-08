import { useEffect, useState } from "react";
import { 
  getDigestConfig, 
  updateDigestConfig, 
  previewDigest, 
  triggerDigest,
  getDigestStatus 
} from "../api/client";
import { 
  RefreshCw, 
  Mail, 
  Settings, 
  Eye, 
  Send, 
  CheckCircle, 
  XCircle, 
  Loader2,
  Clock,
  Calendar,
  TrendingUp
} from "lucide-react";

const JOB_TYPES = [
  { value: "hourly", label: "Hourly" },
  { value: "fixed", label: "Fixed Price" }
];

const EXPERIENCE_LEVELS = [
  { value: "entry", label: "Entry Level" },
  { value: "intermediate", label: "Intermediate" },
  { value: "expert", label: "Expert" }
];

export default function DailyDigest() {
  const [config, setConfig] = useState(null);
  const [status, setStatus] = useState(null);
  const [previewJobs, setPreviewJobs] = useState([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState("config");
  const [message, setMessage] = useState({ text: "", type: "" });

  const loadData = async () => {
    try {
      const [configRes, statusRes] = await Promise.all([
        getDigestConfig(),
        getDigestStatus()
      ]);
      setConfig(configRes.data);
      setStatus(statusRes.data);
    } catch (error) {
      console.error("Failed to load data:", error);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handlePreview = async () => {
    setPreviewLoading(true);
    try {
      const response = await previewDigest(config.filters);
      setPreviewJobs(response.data.jobs || []);
      setMessage({ text: `Found ${response.data.count} jobs`, type: "success" });
    } catch (error) {
      setMessage({ text: "Preview failed", type: "error" });
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleSaveConfig = async () => {
    setSaving(true);
    try {
      await updateDigestConfig(config);
      setMessage({ text: "Configuration saved", type: "success" });
    } catch (error) {
      setMessage({ text: "Failed to save", type: "error" });
    } finally {
      setSaving(false);
    }
  };

  const handleTrigger = async () => {
    setTriggering(true);
    try {
      await triggerDigest();
      setMessage({ text: "Digest triggered! Check email in a few minutes.", type: "success" });
      setTimeout(() => loadData(), 5000);
    } catch (error) {
      setMessage({ text: "Failed to trigger", type: "error" });
    } finally {
      setTriggering(false);
    }
  };

  const updateFilter = (key, value) => {
    setConfig(prev => ({
      ...prev,
      filters: { ...prev.filters, [key]: value }
    }));
  };

  if (!config) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 size={32} className="animate-spin text-violet-400" />
      </div>
    );
  }

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-white">Daily Job Digest</h2>
          <p className="text-sm text-gray-500 mt-1">
            Automatically fetch Upwork jobs and receive daily email summaries
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={handlePreview}
            disabled={previewLoading}
            className="flex items-center gap-2 bg-gray-800 hover:bg-gray-700 px-4 py-2 rounded-lg text-sm transition-colors"
          >
            {previewLoading ? <Loader2 size={14} className="animate-spin" /> : <Eye size={14} />}
            Preview Jobs
          </button>
          <button
            onClick={handleTrigger}
            disabled={triggering}
            className="flex items-center gap-2 bg-violet-600 hover:bg-violet-500 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            {triggering ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
            Run Now
          </button>
          <button onClick={loadData} className="flex items-center gap-2 bg-gray-800 hover:bg-gray-700 px-3 py-2 rounded-lg text-sm">
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      {status && (
        <div className="grid grid-cols-4 gap-4 mb-6">
          {[
            { label: "Last Run", value: status.last_run_date || "Never", icon: Calendar, color: "text-blue-400" },
            { label: "Today's Jobs", value: status.today_jobs_count, icon: TrendingUp, color: "text-green-400" },
            { label: "Recipient", value: config.recipient_email?.split("@")[0] || "Not set", icon: Mail, color: "text-purple-400" },
            { label: "Schedule", value: `${config.send_time_hour}:${config.send_time_minute.toString().padStart(2, '0')}`, icon: Clock, color: "text-orange-400" },
          ].map(stat => (
            <div key={stat.label} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <stat.icon size={14} className={stat.color} />
                <p className="text-xs text-gray-500 uppercase tracking-wider">{stat.label}</p>
              </div>
              <p className={`text-xl font-bold ${stat.color}`}>{stat.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-800 mb-6">
        {[
          { id: "config", label: "⚙️ Configuration", icon: Settings },
          { id: "preview", label: "🔍 Job Preview", icon: Eye },
          { id: "history", label: "📊 History", icon: Calendar },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? "text-violet-400 border-b-2 border-violet-400"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Message */}
      {message.text && (
        <div className={`mb-6 px-4 py-3 rounded-xl text-sm flex items-center gap-2 border ${
          message.type === "success" 
            ? "bg-green-500/10 border-green-500/20 text-green-400"
            : "bg-red-500/10 border-red-500/20 text-red-400"
        }`}>
          {message.type === "success" ? <CheckCircle size={14} /> : <XCircle size={14} />}
          {message.text}
        </div>
      )}

      {/* Configuration Tab */}
      {activeTab === "config" && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Digest Settings</h3>
          
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                  Recipient Email
                </label>
                <input
                  type="email"
                  value={config.recipient_email || ""}
                  onChange={(e) => setConfig(prev => ({ ...prev, recipient_email: e.target.value }))}
                  className="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm text-white"
                  placeholder="email@example.com"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                  Search Query
                </label>
                <input
                  type="text"
                  value={config.filters?.query || ""}
                  onChange={(e) => updateFilter("query", e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm text-white"
                  placeholder="python developer, data engineer"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                  Job Types
                </label>
                <div className="flex gap-3">
                  {JOB_TYPES.map(type => (
                    <label key={type.value} className="flex items-center gap-2 text-sm text-gray-300">
                      <input
                        type="checkbox"
                        checked={config.filters?.jobType?.includes(type.value)}
                        onChange={(e) => {
                          const current = config.filters?.jobType || [];
                          const newValue = e.target.checked
                            ? [...current, type.value]
                            : current.filter(v => v !== type.value);
                          updateFilter("jobType", newValue);
                        }}
                        className="accent-violet-500"
                      />
                      {type.label}
                    </label>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                  Experience Level
                </label>
                <div className="flex gap-3 flex-wrap">
                  {EXPERIENCE_LEVELS.map(level => (
                    <label key={level.value} className="flex items-center gap-2 text-sm text-gray-300">
                      <input
                        type="checkbox"
                        checked={config.filters?.experienceLevel?.includes(level.value)}
                        onChange={(e) => {
                          const current = config.filters?.experienceLevel || [];
                          const newValue = e.target.checked
                            ? [...current, level.value]
                            : current.filter(v => v !== level.value);
                          updateFilter("experienceLevel", newValue);
                        }}
                        className="accent-violet-500"
                      />
                      {level.label}
                    </label>
                  ))}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                  Min Budget ($)
                </label>
                <input
                  type="number"
                  value={config.filters?.minBudget || ""}
                  onChange={(e) => updateFilter("minBudget", e.target.value ? parseFloat(e.target.value) : null)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm text-white"
                  placeholder="30"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                  Max Budget ($)
                </label>
                <input
                  type="number"
                  value={config.filters?.maxBudget || ""}
                  onChange={(e) => updateFilter("maxBudget", e.target.value ? parseFloat(e.target.value) : null)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm text-white"
                  placeholder="100"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                  Location (Optional)
                </label>
                <input
                  type="text"
                  value={config.filters?.location || ""}
                  onChange={(e) => updateFilter("location", e.target.value || null)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm text-white"
                  placeholder="United States, Europe, Remote"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                  Max Job Age (hours)
                </label>
                <input
                  type="number"
                  value={config.filters?.maxJobAgeHours || 24}
                  onChange={(e) => updateFilter("maxJobAgeHours", parseInt(e.target.value))}
                  className="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm text-white"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                  Max Results per Run
                </label>
                <input
                  type="number"
                  value={config.filters?.maxResults || 50}
                  onChange={(e) => updateFilter("maxResults", parseInt(e.target.value))}
                  className="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2 text-sm text-white"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
                  Payment Verified
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-300 mt-2">
                  <input
                    type="checkbox"
                    checked={config.filters?.paymentVerified || false}
                    onChange={(e) => updateFilter("paymentVerified", e.target.checked)}
                    className="accent-violet-500"
                  />
                  Only show clients with verified payment
                </label>
              </div>
            </div>

            <div className="flex justify-end pt-4">
              <button
                onClick={handleSaveConfig}
                disabled={saving}
                className="px-6 py-2 bg-violet-600 hover:bg-violet-500 rounded-lg text-sm font-medium transition-colors"
              >
                {saving ? <Loader2 size={14} className="animate-spin" /> : "Save Configuration"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Preview Tab */}
      {activeTab === "preview" && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          {previewLoading ? (
            <div className="flex items-center justify-center p-12">
              <Loader2 size={32} className="animate-spin text-violet-400" />
            </div>
          ) : previewJobs.length === 0 ? (
            <div className="text-center p-12">
              <p className="text-gray-500">Click "Preview Jobs" to see matching jobs</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-800">
              {previewJobs.map((job, idx) => (
                <div key={idx} className="p-4 hover:bg-gray-800/50 transition-colors">
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <a 
                        href={job.url} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="text-sm font-medium text-violet-400 hover:underline"
                      >
                        {job.title}
                      </a>
                      <div className="flex gap-3 mt-2 text-xs text-gray-500">
                        <span className="flex items-center gap-1">
                          💰 {typeof job.budget === 'string' ? job.budget : JSON.stringify(job.budget)}
                        </span>
                        <span>⭐ {job.experience_level || "Any"}</span>
                      </div>
                      <div className="flex flex-wrap gap-1 mt-2">
                        {(job.skills || []).slice(0, 5).map((skill, i) => (
                          <span key={i} className="text-xs bg-gray-800 px-2 py-0.5 rounded-full text-gray-400">
                            {skill}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* History Tab */}
      {activeTab === "history" && status && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <div className="p-4 border-b border-gray-800">
            <h3 className="font-semibold text-white">Last 7 Days</h3>
          </div>
          <div className="divide-y divide-gray-800">
            {status.weekly_stats?.map(stat => (
              <div key={stat.date} className="flex justify-between items-center p-4">
                <span className="text-sm text-gray-300">{stat.date}</span>
                <span className="text-sm font-medium text-violet-400">{stat.jobs_count} jobs</span>
              </div>
            ))}
          </div>
          
          {status.last_manual && (
            <div className="p-4 border-t border-gray-800 bg-gray-800/30">
              <p className="text-xs text-gray-500">Last Manual Trigger</p>
              <p className="text-sm text-gray-300 mt-1">
                {new Date(status.last_manual.timestamp).toLocaleString()}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Jobs sent: {status.last_manual.jobs_count} | 
                Status: {status.last_manual.email_sent ? "✅ Sent" : "❌ Failed"}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}