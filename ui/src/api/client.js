import axios from "axios";
const API = axios.create({
  baseURL: "",
  timeout: 180000,
});
export const getCampaigns    = ()       => API.get("/api/campaigns");
export const createCampaign  = (data)   => API.post("/api/campaigns", data);
export const updateCampaign  = (id, d)  => API.put(`/api/campaigns/${id}`, d);
export const deleteCampaign  = (id)     => API.delete(`/api/campaigns/${id}`);
export const triggerCampaign = (id)     => API.post(`/api/campaigns/${id}/trigger`);
export const getConnectors   = ()       => API.get("/api/connectors");
export const getRuns         = ()       => API.get("/api/runs");
export const getRunsByCampaign = (id)   => API.get(`/api/runs/campaign/${id}`);
export const getRunStats     = ()       => API.get("/api/runs/stats/summary");
export const getRawEvents    = (params) => API.get("/api/data/raw", { params });
export const semanticSearch  = (q)      => API.get("/api/data/search", { params: { q } });
export const getDataStats    = ()       => API.get("/api/data/stats");
export const getHealth       = ()       => API.get("/health");
// CRM — Operational layer
export const getCrmStats    = ()       => API.get("/api/crm/stats");
export const getCrmContacts = (params) => API.get("/api/crm/contacts", { params });
export const getCrmLeads    = (params) => API.get("/api/crm/leads",    { params });
export const getCrmContact  = (id)     => API.get(`/api/crm/contacts/${id}`);
// Agent 3 — Email Campaigns
export const getEmailCampaigns    = ()        => API.get("/api/email-campaigns");
export const createEmailCampaign  = (data)    => API.post("/api/email-campaigns", data);
export const deleteEmailCampaign  = (id)      => API.delete(`/api/email-campaigns/${id}`);
//export const previewEmailCampaign = (id)      => API.get(`/api/agent3/campaigns/${id}/preview`, { timeout: 120000 });
export const previewEmailCampaign = (id)      => API.get(`/api/agent3/campaigns/${id}/preview`, { timeout: 120000 });
export const sendEmailCampaign    = (id)      => API.post(`/api/agent3/campaigns/${id}/send`);

export const validateFilters = (payload) => API.post("/api/campaigns/validate-filters", payload, { timeout: 30000 });
