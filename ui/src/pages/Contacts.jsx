import { useEffect, useState, useCallback, useRef } from "react";
import { getCrmContacts, getCrmContact, uploadContactsCSV } from "../api/client";
import { Search, User, X, ExternalLink, RefreshCw, ChevronLeft, ChevronRight, Upload, Download, AlertCircle, CheckCircle, Loader } from "lucide-react";

const STAGE_COLORS = {
  subscriber:  "bg-gray-800 text-gray-400",
  lead:        "bg-blue-900/50 text-blue-300",
  mql:         "bg-indigo-900/50 text-indigo-300",
  sql:         "bg-purple-900/50 text-purple-300",
  opportunity: "bg-amber-900/50 text-amber-300",
  customer:    "bg-green-900/50 text-green-300",
};

function ScoreBadge({ score, size = "sm" }) {
  const color = score >= 70 ? "text-green-400 bg-green-900/30"
              : score >= 40 ? "text-yellow-400 bg-yellow-900/30"
              : "text-gray-500 bg-gray-800";
  return (
    <span className={`font-bold font-mono rounded px-1.5 py-0.5 ${size === "lg" ? "text-base" : "text-xs"} ${color}`}>
      {score ?? "—"}
    </span>
  );
}

function UploadModal({ isOpen, onClose, onUpload, campaignId }) {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const fileInputRef = useRef(null);

  if (!isOpen) return null;

  const handleUpload = async () => {
    if (!file) return;
    
    setUploading(true);
    try {
      const response = await uploadContactsCSV(file);
      setResult(response.data);
      if (response.data.success) {
        setTimeout(() => {
          onUpload();
          onClose();
          setFile(null);
          setResult(null);
        }, 2000);
      }
    } catch (error) {
      console.log("error => ", error)
      setResult({ error: error.response?.data?.detail || "Upload failed" });
    } finally {
      setUploading(false);
    }
  };

  const downloadTemplate = () => {
    const csvContent = "email,first_name,last_name,phone,company,job_title,city,country\njohn.doe@example.com,John,Doe,+1234567890,Acme Corp,CEO,New York,USA\njane.smith@example.com,Jane,Smith,+1234567891,Tech Solutions,CTO,San Francisco,USA";
    const blob = new Blob([csvContent], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "contacts_template.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />
      <div className="relative bg-gray-900 rounded-xl shadow-2xl w-full max-w-lg border border-gray-700">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800">
          <h3 className="text-lg font-semibold text-white">Upload Contacts (CSV)</h3>
          <button onClick={onClose} className="text-gray-500 hover:text-white">
            <X size={20} />
          </button>
        </div>
        
        <div className="p-6 space-y-4">
          <div className="bg-blue-900/20 border border-blue-800 rounded-lg p-3">
            <p className="text-xs text-blue-300 mb-2">📋 CSV Requirements:</p>
            <ul className="text-xs text-gray-400 space-y-1 list-disc list-inside">
              <li><span className="text-blue-300">email</span> (required) - Contact's email address</li>
              <li><span className="text-gray-400">first_name, last_name</span> - Contact's name</li>
              <li><span className="text-gray-400">phone, company, job_title</span> - Contact details</li>
              <li><span className="text-gray-400">city, country</span> - Location information</li>
            </ul>
            <button 
              onClick={downloadTemplate}
              className="mt-2 text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
            >
              <Download size={12} /> Download template CSV
            </button>
          </div>

          <div 
            className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
              file ? "border-green-500 bg-green-900/10" : "border-gray-700 hover:border-indigo-500"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              onChange={(e) => setFile(e.target.files[0])}
              className="hidden"
            />
            {!file ? (
              <>
                <Upload className="mx-auto mb-3 text-gray-500" size={40} />
                <p className="text-sm text-gray-400 mb-2">Drag & drop or click to upload CSV</p>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 rounded-lg text-sm transition-colors"
                >
                  Select File
                </button>
              </>
            ) : (
              <>
                <CheckCircle className="mx-auto mb-3 text-green-500" size={40} />
                <p className="text-sm text-green-400 mb-1">{file.name}</p>
                <p className="text-xs text-gray-500">{(file.size / 1024).toFixed(2)} KB</p>
                <button
                  onClick={() => setFile(null)}
                  className="mt-3 text-xs text-red-400 hover:text-red-300"
                >
                  Remove
                </button>
              </>
            )}
          </div>

          {result && (
            <div className={`rounded-lg p-3 ${
              result.error ? "bg-red-900/20 border border-red-800" : "bg-green-900/20 border border-green-800"
            }`}>
              {result.error ? (
                <div className="flex items-start gap-2">
                  <AlertCircle size={16} className="text-red-400 mt-0.5" />
                  <div>
                    <p className="text-sm text-red-400 font-medium">Upload Failed</p>
                    <p className="text-xs text-red-300 mt-1">{result.error}</p>
                  </div>
                </div>
              ) : (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <CheckCircle size={16} className="text-green-400" />
                    <p className="text-sm text-green-400 font-medium">Upload Complete!</p>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="bg-gray-800 rounded p-2">
                      <p className="text-gray-500">Total</p>
                      <p className="text-white font-semibold">{result.data?.total || 0}</p>
                    </div>
                    <div className="bg-gray-800 rounded p-2">
                      <p className="text-green-400">Success</p>
                      <p className="text-white font-semibold">{result.data?.success || 0}</p>
                    </div>
                    {result.data?.failed > 0 && (
                      <div className="col-span-2 bg-red-900/20 rounded p-2 mt-1">
                        <p className="text-red-400 text-xs">Failed: {result.data.failed}</p>
                        {result.data.errors?.slice(0, 3).map((err, i) => (
                          <p key={i} className="text-red-300 text-xs mt-1">Row {err.row}: {err.error}</p>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="flex-1 px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleUpload}
              disabled={!file || uploading}
              className="flex-1 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 rounded-lg text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {uploading ? (
                <>
                  <Loader size={16} className="animate-spin" />
                  Uploading...
                </>
              ) : (
                <>
                  <Upload size={16} />
                  Upload Contacts
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ContactDrawer({ contactId, onClose }) {
  const [contact, setContact] = useState(null);
  useEffect(() => {
    if (contactId) getCrmContact(contactId).then(r => setContact(r.data));
  }, [contactId]);

  if (!contactId) return null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/60" onClick={onClose}/>
      <div className="relative w-full max-w-md bg-gray-900 border-l border-gray-700 h-full overflow-auto shadow-2xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800 sticky top-0 bg-gray-900">
          <h3 className="font-semibold text-white">Contact Detail</h3>
          <button onClick={onClose} className="text-gray-500 hover:text-white"><X size={18}/></button>
        </div>
        {!contact ? (
          <div className="p-8 text-center text-gray-600">Loading...</div>
        ) : (
          <div className="p-5 space-y-5">
            {/* Header */}
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-full bg-indigo-700 flex items-center justify-center text-white font-bold text-lg shrink-0">
                {contact.first_name?.[0]}{contact.last_name?.[0]}
              </div>
              <div>
                <h4 className="font-bold text-white text-lg">{contact.first_name} {contact.last_name}</h4>
                <p className="text-gray-400 text-sm">{contact.job_title || "—"}</p>
                <p className="text-gray-500 text-xs mt-0.5">{contact.company_name || "—"}</p>
              </div>
            </div>

            {/* Scores */}
            <div className="grid grid-cols-4 gap-2">
              {[["Intent", contact.intent_score != null ? Math.round(contact.intent_score * 100) : null],
                ["Lead",   contact.lead_score],
                ["Fit",    contact.fit_score],
                ["Overall",contact.overall_score]
              ].map(([label, val]) => (
                <div key={label} className="bg-gray-800 rounded-lg p-2.5 text-center">
                  <div className="text-xs text-gray-500 mb-1">{label}</div>
                  <ScoreBadge score={val} size="lg"/>
                </div>
              ))}
            </div>

            {/* Details */}
            <div className="space-y-2 text-sm">
              {[["Email",    contact.email],
                ["Platform", contact.source_platform],
                ["Stage",    contact.lifecycle_stage],
                ["Type",     contact.contact_type],
                ["City",     contact.city],
                ["Country",  contact.country],
              ].map(([k, v]) => v && (
                <div key={k} className="flex gap-2">
                  <span className="text-gray-500 w-20 shrink-0 text-xs">{k}:</span>
                  <span className="text-gray-300 text-xs break-all">{v}</span>
                </div>
              ))}
              {contact.linkedin_url && (
                <a href={contact.linkedin_url} target="_blank" rel="noreferrer"
                  className="flex items-center gap-1 text-indigo-400 text-xs hover:underline mt-1">
                  <ExternalLink size={11}/> LinkedIn Profile
                </a>
              )}
            </div>

            {/* Tags */}
            {contact.tags?.length > 0 && (
              <div>
                <p className="text-xs text-gray-500 mb-2">Tags</p>
                <div className="flex flex-wrap gap-1.5">
                  {contact.tags.map(t => (
                    <span key={t} className="text-xs bg-indigo-900/40 text-indigo-300 px-2 py-0.5 rounded-full">{t}</span>
                  ))}
                </div>
              </div>
            )}

            {/* Created */}
            <p className="text-xs text-gray-600">
              Created: {new Date(contact.created_at).toLocaleString()} · by {contact.created_by_agent}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function Contacts() {
  const [records, setRecords]     = useState([]);
  const [total, setTotal]         = useState(0);
  const [loading, setLoading]     = useState(false);
  const [search, setSearch]       = useState("");
  const [stage, setStage]         = useState("");
  const [offset, setOffset]       = useState(0);
  const [selectedId, setSelectedId] = useState(null);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const limit = 20;

  const load = useCallback(() => {
    setLoading(true);
    getCrmContacts({ search: search || undefined, stage: stage || undefined, limit, offset })
      .then(r => { setRecords(r.data.records); setTotal(r.data.total); })
      .finally(() => setLoading(false));
  }, [search, stage, offset]);

  useEffect(() => { setOffset(0); }, [search, stage]);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-white">Contacts</h2>
          <p className="text-sm text-gray-500 mt-0.5">Structured contacts promoted from landing zone · {total} total</p>
        </div>
        <div className="flex gap-2">
          <button 
            onClick={() => setShowUploadModal(true)} 
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 px-4 py-2 rounded-lg text-sm transition-colors"
          >
            <Upload size={14}/> Upload CSV
          </button>
          <button onClick={load} className="flex items-center gap-2 bg-gray-800 hover:bg-gray-700 px-3 py-2 rounded-lg text-sm transition-colors">
            <RefreshCw size={14}/> Refresh
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <div className="relative flex-1 min-w-48">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500"/>
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search by name, email, title..."
            className="w-full bg-gray-900 border border-gray-700 rounded-lg pl-8 pr-4 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"/>
        </div>
        <select value={stage} onChange={e => setStage(e.target.value)}
          className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500">
          <option value="">All stages</option>
          {["subscriber","lead","mql","sql","opportunity","customer"].map(s => (
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
              <th className="text-left px-4 py-3">Designation</th>
              <th className="text-left px-4 py-3">Tags</th>
              <th className="text-left px-4 py-3">Intent</th>
              <th className="text-left px-4 py-3">Score</th>
              <th className="text-left px-4 py-3">Source</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-600 text-sm">Loading...</td></tr>
            ) : records.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-600 text-sm">No contacts found.</td></tr>
            ) : records.map(c => (
              <tr key={c.contact_id}
                onClick={() => setSelectedId(c.contact_id)}
                className="border-b border-gray-800/50 hover:bg-gray-800/40 transition-colors cursor-pointer">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-indigo-800 flex items-center justify-center text-white text-xs font-bold shrink-0">
                      {c.first_name?.[0]}{c.last_name?.[0]}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-white">{c.first_name} {c.last_name}</p>
                      <p className="text-xs text-gray-500 truncate max-w-36">{c.job_title || c.email}</p>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <p className="text-xs text-gray-300 truncate max-w-28">{c.company_name || "—"}</p>
                  <p className="text-xs text-gray-600">{c.city || ""}</p>
                </td>
                <td className="px-4 py-3">
                  <span className="text-xs text-gray-300">{c.job_title || "—"}</span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-1 flex-wrap max-w-32">
                    {(c.tags || []).slice(0,3).map(t => (
                      <span key={t} className="text-xs bg-indigo-900/30 text-indigo-400 px-1.5 py-0.5 rounded">{t}</span>
                    ))}
                  </div>
                </td>
                <td className="px-4 py-3">
                  {c.intent_score != null
                    ? <span className={`text-xs font-mono font-bold ${c.intent_score >= 0.7 ? "text-green-400" : c.intent_score >= 0.4 ? "text-yellow-400" : "text-gray-500"}`}>
                        {c.intent_score.toFixed(1)}
                      </span>
                    : <span className="text-gray-600 text-xs">—</span>}
                </td>
                <td className="px-4 py-3"><ScoreBadge score={c.overall_score}/></td>
                <td className="px-4 py-3 text-xs text-gray-500 capitalize">{c.source_platform}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && records.length > 0 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-800">
            <p className="text-xs text-gray-500">Page {Math.floor(offset/limit)+1} · {total} total</p>
            <div className="flex gap-2">
              <button onClick={() => setOffset(o => Math.max(0,o-limit))} disabled={offset===0}
                className="flex items-center gap-1 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded text-xs disabled:opacity-40 transition-colors">
                <ChevronLeft size={12}/> Prev
              </button>
              <button onClick={() => setOffset(o => o+limit)} disabled={records.length < limit}
                className="flex items-center gap-1 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded text-xs disabled:opacity-40 transition-colors">
                Next <ChevronRight size={12}/>
              </button>
            </div>
          </div>
        )}
      </div>
      
      <ContactDrawer contactId={selectedId} onClose={() => setSelectedId(null)}/>
      <UploadModal 
        isOpen={showUploadModal}
        onClose={() => {
          setShowUploadModal(false);
          load(); // Reload contacts after closing
        }}
        onUpload={load}
        campaignId="default-campaign-id" // Replace with actual campaign ID from props or context
      />
    </div>
  );
}