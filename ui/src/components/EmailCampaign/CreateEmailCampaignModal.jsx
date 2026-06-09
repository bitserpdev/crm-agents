import { useState } from "react";
import Modal from "../shared/Modal";
import Field from "../shared/Field";
import Input from "../shared/Input";
import Select from "../shared/Select";

const STAGES = ["subscriber", "lead", "mql", "sql", "opportunity", "customer"];
const SIZES = ["1-10", "11-50", "51-200", "201-500", "500+"];

export default function CreateEmailCampaignModal({ isOpen, onClose, onCreate }) {
  const [form, setForm] = useState({
    campaign_name: "", service_description: "", from_address: "",
    filter_region: "", filter_industry: "", filter_company_size: "",
    filter_stage: "", scheduled_at: "",
  });

  const handleSubmit = async () => {
    if (!form.campaign_name || !form.service_description || !form.from_address) {
      alert("Name, service description and from address are required");
      return;
    }
    await onCreate({
      ...form,
      filter_min_score: Number(form.filter_min_score),
      filter_max_score: Number(form.filter_max_score),
      scheduled_at: form.scheduled_at || null,
    });
    setForm({
      campaign_name: "", service_description: "", from_address: "",
      filter_region: "", filter_industry: "", filter_company_size: "",
      filter_min_score: 0, filter_max_score: 100,
      filter_stage: "", scheduled_at: "",
    });
    onClose();
  };

  if (!isOpen) return null;

  return (
    <Modal title="New Email Campaign" onClose={onClose} wide>
      <div className="space-y-4">
        <Field label="Campaign Name" hint="Give your campaign a descriptive name">
          <Input value={form.campaign_name} onChange={v => setForm(f => ({ ...f, campaign_name: v }))} placeholder="BITS Analytics Outreach Q3" />
        </Field>

        <Field label="Service Description" hint="Llama 3.2 uses this to write personalized emails">
          <textarea
            value={form.service_description}
            onChange={e => setForm(f => ({ ...f, service_description: e.target.value }))}
            placeholder="We provide Big Data & Analytics solutions including data pipelines, BI dashboards, ML models..."
            rows={3}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 resize-none"
          />
        </Field>

        <Field label="From Email Address" hint="Email address that will appear as the sender">
          <Input value={form.from_address} onChange={v => setForm(f => ({ ...f, from_address: v }))} placeholder="analytics@bitscompany.com" />
        </Field>

        <div className="border-t border-gray-800 pt-4">
          <p className="text-xs font-medium text-gray-400 mb-3 uppercase tracking-wider">Audience Filters</p>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Region / Country Code" hint="e.g. US, GB, PK, IN">
              <Input value={form.filter_region} onChange={v => setForm(f => ({ ...f, filter_region: v }))} placeholder="US" />
            </Field>
            <Field label="Industry Keyword" hint="Filter by industry">
              <Input value={form.filter_industry} onChange={v => setForm(f => ({ ...f, filter_industry: v }))} placeholder="technology" />
            </Field>
            <Field label="Company Size" hint="Filter by number of employees">
              <Select value={form.filter_company_size} onChange={v => setForm(f => ({ ...f, filter_company_size: v }))} options={SIZES} placeholder="Any size" />
            </Field>
            <Field label="Lifecycle Stage" hint="Filter by CRM stage">
              <Select value={form.filter_stage} onChange={v => setForm(f => ({ ...f, filter_stage: v }))} options={STAGES} placeholder="Any stage" />
            </Field>
          </div>
        </div>

        <Field label="Schedule (Optional)" hint="Leave empty to send manually">
          <Input type="datetime-local" value={form.scheduled_at} onChange={v => setForm(f => ({ ...f, scheduled_at: v }))} />
        </Field>

        <div className="flex gap-3 pt-2">
          <button onClick={handleSubmit} className="flex-1 bg-indigo-600 hover:bg-indigo-500 py-2.5 rounded-lg text-sm font-medium transition-colors">
            Create Campaign
          </button>
          <button onClick={onClose} className="px-4 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm transition-colors">
            Cancel
          </button>
        </div>
      </div>
    </Modal>
  );
}