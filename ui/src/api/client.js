import axios from "axios";
const API = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  timeout: 180000,
});

// Campaign 

export const getCampaigns    = ()       => API.get("/api/campaigns");
export const createCampaign  = (data)   => API.post("/api/campaigns", data);
export const updateCampaign  = (id, d)  => API.put(`/api/campaigns/${id}`, d);
export const deleteCampaign  = (id)     => API.delete(`/api/campaigns/${id}`);
export const triggerCampaign = (id)     => API.post(`/api/campaigns/${id}/trigger`);


// Get Connectors
export const getConnectors   = ()       => API.get("/api/connectors");

// Run History
export const getRuns           = ()   => API.get("/api/campaigns/runs");
export const getRunsByCampaign = (id) => API.get(`/api/campaigns/runs/campaign/${id}`);
export const getRunStats       = ()   => API.get("/api/campaigns/runs/stats");

// Raw Data
export const getRawEvents    = (params) => API.get("/api/data/raw", { params });
export const getDataStats    = ()       => API.get("/api/data/stats");
export const semanticSearch  = (q)      => API.get("/api/data/search", { params: { q } });

// Check System Health
export const getHealth       = ()       => API.get("/health");

// CRM — Operational layer
export const getCrmStats    = ()       => API.get("/api/crm/stats");
export const getCrmContacts = (params) => API.get("/api/crm/contacts", { params });
export const getCrmLeads    = (params) => API.get("/api/crm/leads",    { params });
export const getCrmContact  = (id)     => API.get(`/api/crm/contacts/${id}`);

export const uploadContactsCSV = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await axios.post(
    `${import.meta.env.VITE_API_URL}/api/crm/contacts/upload-csv`,
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }
  );
  
  return response;
};

export const getCampaignContacts = async (campaignId, limit = 50, offset = 0) => {
  const response = await axios.get(
    `${import.meta.env.VITE_API_URL}/api/crm/campaign/${campaignId}/contacts`,
    {
      params: { limit, offset }
    }
  );
  return response;
};

// Agent 3 — Email Campaigns
export const getEmailCampaigns    = ()        => API.get("/api/crm/email-campaigns");
export const createEmailCampaign  = (data)    => API.post("/api/crm/email-campaigns", data);
export const deleteEmailCampaign  = (id)      => API.delete(`/api/email-campaigns/${id}`);

//export const previewEmailCampaign = (id)      => API.get(`/api/agent3/campaigns/${id}/preview`, { timeout: 120000 });
export const previewEmailCampaign = (id)      => API.get(`/api/crm/campaigns/${id}/preview`, { timeout: 120000 });
export const sendEmailCampaign    = (id)      => API.post(`/api/crm/campaigns/${id}/send`);


export const validateFilters = (payload) => API.post("/api/campaigns/validate-filters", payload, { timeout: 30000 });

// Upwork Jobs
export const getUpworkJobs = () => axios.get('/api/upwork/jobs/pending');

// Trigger proposal generation
export const triggerProposal = (eventId) => axios.post(`/api/upwork/jobs/${eventId}/trigger`);

// Get proposal status
export const getProposalStatus = (eventId) => axios.get(`/api/upwork/jobs/${eventId}/proposal`);

// Submit review
export const reviewProposal = (proposalId, status, feedback) => 
  axios.post(`/api/upwork/proposals/${proposalId}/review`, { status, feedback });

// Agent 6 - Daily Digest
export const getDigestConfig = () => axios.get('/api/upwork/digest/config');
export const updateDigestConfig = (config) => axios.post('/api/upwork/digest/config', config);
export const previewDigest = (filters) => axios.post('/api/upwork/digest/preview', filters);
export const triggerDigest = (recipient_email = null, filters = null) => 
  axios.post('/api/upwork/digest/trigger', { recipient_email, filters });
export const getDigestStatus = () => axios.get('/api/upwork/digest/status');
export const getPreviewJobs = (limit = 20) => axios.get(`/api/upwork/jobs/preview?limit=${limit}`);