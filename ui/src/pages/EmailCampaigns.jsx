import { useEffect, useState } from "react";
import { Mail, Plus, RefreshCw, XCircle, CheckCircle } from "lucide-react";
import axios from "axios";

// Components
import CampaignCard from "../components/EmailCampaign/EmailCampaignCard";
import CreateCampaignModal from "../components/EmailCampaign/CreateEmailCampaignModal";
import EditCampaignModal from "../components/EmailCampaign/EditEmailCampaignModal";
import PreviewContactsModal from "../components/EmailCampaign/PreviewEmailContactsModal";
import CustomizeEmailModal from "../components/EmailCampaign/CustomizeEmailCampaignModal";
import PreviewEmailModal from "../components/EmailCampaign/PreviewEmailCampaignModal";
import CampaignDetailModal from "../components/EmailCampaign/EmailCampaignDetailModal";
import Modal from "../components/shared/Modal";

const API = axios.create({ baseURL: import.meta.env.VITE_API_URL, withCredentials: true });
API.defaults.timeout = 120000;

const getCampaigns = () => API.get("/api/campaigns/emails");
const createCampaign = (d) => API.post("/api/campaigns/emails", d);
const updateCampaign = (id, d) => API.put(`/api/campaigns/emails/${id}`, d);
const deleteCampaign = (id) => API.delete(`/api/campaigns/emails/${id}`);
const triggerCampaign = (id, sel) => API.post(`/api/campaigns/${id}/trigger`, { selected_contacts: sel });
const previewContacts = (id, filters) => API.post(`/api/campaigns/emails/${id}/preview-contacts`, filters);
const startPreview = (id, cid) => API.post(`/api/campaigns/emails/${id}/preview/start`, { contact_id: cid }, { timeout: 10000 });
const pollPreview = (jobId) => API.get(`/api/campaigns/emails/preview/job/${jobId}`, { timeout: 10000 });
const sendCustomizedEmail = (data) => API.post("/api/campaigns/emails/send-customized", data);
const getRuns = (id) => API.get(`/api/campaigns/runs/campaign/${id}`);
const getRecipients = (runId) => API.get(`/api/campaigns/emails/runs/${runId}/recipients`);
const getReplies = (id) => API.get(`/api/campaigns/emails/replies`, { params: { campaign_id: id } });


export default function EmailCampaigns() {
  const [campaigns, setCampaigns] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [detail, setDetail] = useState(null);
  const [preview, setPreview] = useState(null);
  const [editTarget, setEditTarget] = useState(null);
  const [msg, setMsg] = useState({ text: "", type: "ok" });
  const [running, setRunning] = useState({});
  const [loading, setLoading] = useState(false);

  const [customizeLoading, setCustomizeLoading] = useState(
    false);
  const [customizeError, setCustomizeError] = useState(null);

  const [savedContactIds, setSavedContactIds] = useState([]);

  const [sending, setSending] = useState(false);


  // Modal states
  const [previewContactsModal, setPreviewContactsModal] = useState(null);
  const [filteredContacts, setFilteredContacts] = useState([]);
  const [customizeModal, setCustomizeModal] = useState(null);
  const [emailTemplate, setEmailTemplate] = useState(null);
  const [currentCampaign, setCurrentCampaign] = useState(null);

  const load = () => {
    setLoading(true);
    getCampaigns().then(r => setCampaigns(r.data)).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const flash = (text, type = "ok") => { setMsg({ text, type }); setTimeout(() => setMsg({ text: "", type: "ok" }), 3000); };

  const handleCreateCampaign = async (data) => {
    try {
      await createCampaign(data);
      flash("Campaign created!");
      load();
    } catch (e) { flash("Error: " + e.message, "err"); }
  };

  const handleUpdateCampaign = async (id, data) => {
    try {
      await updateCampaign(id, data);
      flash("Campaign updated!");
      setEditTarget(null);
      load();
    } catch (e) { flash("Error: " + e.message, "err"); }
  };

  const handleDeleteCampaign = async (id, name) => {
    if (!window.confirm(`Delete campaign "${name}"?`)) return;
    try {
      await deleteCampaign(id);
      flash("Campaign deleted!");
      load();
    } catch (e) { flash("Error: " + e.message, "err"); }
  };

  const handleTrigger = async (id, name, selectedContacts = null) => {
    setRunning(r => ({ ...r, [id]: true }));
    try {
      await triggerCampaign(id, selectedContacts);
      flash(`Campaign "${name}" triggered — emails sending...`);
    } catch (e) { flash("Trigger failed", "err"); }
    setTimeout(() => setRunning(r => ({ ...r, [id]: false })), 5000);
  };

  const handlePreviewContacts = async (campaign) => {
    setCurrentCampaign(campaign);
    setPreviewContactsModal("loading");
    try {
      const response = await previewContacts(campaign.campaign_id, {
        filter_region: campaign.filter_region,
        filter_industry: campaign.filter_industry,
        filter_company_size: campaign.filter_company_size,
        filter_min_score: campaign.filter_min_score,
        filter_max_score: campaign.filter_max_score,
        filter_stage: campaign.filter_stage,
      });
      const contacts = response.data?.contacts || [];
      setFilteredContacts(contacts);
      setPreviewContactsModal("preview");
    } catch (e) {
      setPreviewContactsModal({ error: "Failed to load contacts" });
    }
  };

  const handleSendToSelected = async (selectedIds) => {
    await handleTrigger(currentCampaign.campaign_id, currentCampaign.campaign_name, selectedIds);
    setPreviewContactsModal(null);
  };

  const handleCustomize = async (campaign, contact = null) => {

    setCustomizeLoading(true);
    setCustomizeError(null);
    setCurrentCampaign(campaign);

    try {
      const response = await startPreview(campaign.campaign_id, null);

      const { job_id } = response.data;

      let pollCount = 0;
      const MAX_POLLS = 30;

      const poll = async () => {
        pollCount++;
        try {
          const { data } = await pollPreview(job_id);
          if (data.status === "pending") {
            setTimeout(poll, 2000);
          } else if (data.status === "done") {
            setCustomizeLoading(false)
            setEmailTemplate({
              subject: data.email?.subject || "",
              body: data.email?.text || "",
              htmlBody: data.email?.html || "",
              contact: data.contact,
              job_id: job_id
            });
            setCustomizeModal("edit");
          } else {
            setCustomizeModal({ error: data.error || "Failed to generate preview" });
          }
        } catch (e) {
          console.error("Polling error:", e);
          if (pollCount < MAX_POLLS) {
            setTimeout(poll, 2000);
          } else {
            setCustomizeError("Polling failed. Please try again.");
            setCustomizeLoading(false);
          }
        }
      };
      setTimeout(poll, 2000);
    } catch (err) {
      console.error("Customize error:", err);
      setCustomizeError(err.response?.data?.detail || "Failed to generate email preview");
      setCustomizeLoading(false);
    }
  };

  const handleSaveCustomized = async (template) => {
    console.log("Save & Send clicked with template:", template);

    if (savedContactIds.length === 0) {
      flash("No contacts selected", "err");
      return;
    }

    setSending(true);

    try {
      // Call API to send emails to all saved contacts
      const response = await sendCustomizedEmail({
        campaign_id: currentCampaign.campaign_id,
        contact_ids: savedContactIds,
        subject: template.subject,
        body: template.body,
        html_body: template.htmlBody || template.body.replace(/\n/g, '<br>')
      });

      flash(`Email sent to ${response.data?.sent || savedContactIds.length} contacts!`, "ok");

      // Close modal and reset
      setCustomizeModal(null);
      setEmailTemplate(null);

    } catch (error) {
      console.error("Send failed:", error);
      flash("Failed to send emails: " + (error.response?.data?.detail || error.message), "err");
    } finally {
      setSending(false);
    }
  };

  const handleOpenDetail = async (campaign) => {
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
  };

  const handleLoadPreview = async (id) => {
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

  const handleSaveSelection = (selectedIds) => {
    setSavedContactIds(selectedIds);
    console.log("Saved contacts:", selectedIds);
    flash(`${selectedIds.length} contacts saved for email campaign`, "ok");
    setPreviewContactsModal(null);  // Close modal after save
  };

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <Mail size={22} className="text-indigo-400" /> Email Campaigns
          </h2>
          <p className="text-sm text-gray-500 mt-0.5">
            AI-personalized outreach · powered by llama3.2 · sent via Zoom
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={load} className="flex items-center gap-2 bg-gray-800 hover:bg-gray-700 px-3 py-2 rounded-lg text-sm transition-colors">
            <RefreshCw size={14} />
          </button>
          <button onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 px-4 py-2 rounded-lg text-sm font-medium transition-colors">
            <Plus size={16} /> New Campaign
          </button>
        </div>
      </div>

      {/* Flash message */}
      {msg.text && (
        <div className={`mb-4 px-4 py-2.5 rounded-lg text-sm flex items-center gap-2
          ${msg.type === "err" ? "bg-red-900/40 border border-red-700 text-red-300"
            : "bg-green-900/40 border border-green-700 text-green-300"}`}>
          {msg.type === "err" ? <XCircle size={14} /> : <CheckCircle size={14} />}
          {msg.text}
        </div>
      )}

      {/* Campaign cards */}
      {loading ? (
        <div className="text-center text-gray-600 py-12 text-sm">Loading campaigns...</div>
      ) : campaigns.length === 0 ? (
        <div className="text-center py-16">
          <Mail size={40} className="text-gray-700 mx-auto mb-3" />
          <p className="text-gray-500">No email campaigns yet.</p>
          <button onClick={() => setShowCreate(true)} className="mt-3 text-indigo-400 text-sm hover:underline">
            Create your first campaign
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {campaigns.map(c => (
            <CampaignCard
              key={c.campaign_id}
              campaign={c}
              onTrigger={(id, name) => handleTrigger(id, name)}
              onPreviewContacts={handlePreviewContacts}
              onCustomize={handleCustomize}
              onOpenDetail={handleOpenDetail}
              onLoadPreview={handleLoadPreview}
              onEdit={setEditTarget}
              onDelete={handleDeleteCampaign}
              isRunning={running[c.campaign_id]}
            />
          ))}
        </div>
      )}

      {customizeLoading && (
        <Modal title="Generating Email" onClose={() => setCustomizeLoading(false)} wide>
          <div className="text-center py-12">
            {/* Spinner */}
            <div className="relative w-24 h-24 mx-auto mb-6">
              <div className="absolute inset-0 border-4 border-indigo-500/20 rounded-full"></div>
              <div className="absolute inset-0 border-4 border-t-indigo-500 border-r-transparent border-b-transparent border-l-transparent rounded-full animate-spin"></div>
            </div>

            {/* Loading Text */}
            <p className="text-white font-medium text-lg mb-2">AI is writing your email...</p>
            <p className="text-gray-400 text-sm mb-6">This may take 20-30 seconds</p>

            {/* Progress Bar */}
            <div className="w-full max-w-md mx-auto bg-gray-800 rounded-full h-2 mb-6">
              <div className="bg-indigo-500 h-2 rounded-full animate-pulse" style={{ width: "60%" }}></div>
            </div>

            {/* Tips */}
            <div className="bg-gray-800 rounded-lg p-4 max-w-sm mx-auto">
              <p className="text-xs text-gray-400">
                <span className="text-indigo-400">💡 Tip:</span> The AI is personalizing the email based on the contact's role, company, and industry.
              </p>
            </div>

            {/* Cancel Button */}
            <button
              onClick={() => {
                setCustomizeLoading(false);
                setCustomizeError(null);
              }}
              className="mt-6 text-gray-500 hover:text-gray-400 text-sm transition-colors"
            >
              Cancel
            </button>
          </div>
        </Modal>
      )}

      {/* Customize Error Modal */}
      {customizeError && (
        <Modal title="Error" onClose={() => setCustomizeError(null)}>
          <div className="text-center py-6">
            <div className="w-16 h-16 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
              <XCircle size={32} className="text-red-400" />
            </div>
            <p className="text-red-400 mb-2">Failed to generate email</p>
            <p className="text-gray-400 text-sm mb-6">{customizeError}</p>
            <button
              onClick={() => setCustomizeError(null)}
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors"
            >
              Close
            </button>
          </div>
        </Modal>
      )}

      {/* Modals */}
      <CreateCampaignModal
        isOpen={showCreate}
        onClose={() => setShowCreate(false)}
        onCreate={handleCreateCampaign}
      />

      <EditCampaignModal
        isOpen={!!editTarget}
        onClose={() => setEditTarget(null)}
        campaign={campaigns.find(c => c.campaign_id === editTarget)}
        onSave={(data) => handleUpdateCampaign(editTarget, data)}
      />

      <PreviewContactsModal
        isOpen={previewContactsModal === "preview"}
        onClose={() => setPreviewContactsModal(null)}
        contacts={filteredContacts}
        campaign={currentCampaign}
        onSend={handleSendToSelected}
        onSaveSelection={handleSaveSelection}
      />

      <CustomizeEmailModal
        isOpen={customizeModal === "edit"}
        onClose={() => setCustomizeModal(null)}
        emailTemplate={emailTemplate}
        onSave={handleSaveCustomized}
      />

      <PreviewEmailModal
        isOpen={!!preview}
        onClose={() => setPreview(null)}
        preview={preview}
      />

      <CampaignDetailModal
        isOpen={!!detail}
        onClose={() => setDetail(null)}
        detail={detail}
      />
    </div>
  );
}