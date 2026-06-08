import { useState } from "react";
import Modal from "../shared/Modal";
import Field from "../shared/Field";
import Input from "../shared/Input";
import Select from "../shared/Select";

const STAGES = ["subscriber", "lead", "mql", "sql", "opportunity", "customer"];
const SIZES = ["1-10", "11-50", "51-200", "201-500", "500+"];

export default function EditEmailCampaignModal({ isOpen, onClose, campaign, onSave }) {
  const [form, setForm] = useState({
    campaign_name: campaign?.campaign_name || "",
    service_description: campaign?.service_description || "",
    from_address: campaign?.from_address || "",
    filter_region: campaign?.filter_region || "",
    filter_industry: campaign?.filter_industry || "",
    filter_company_size: campaign?.filter_company_size || "",
    filter_min_score: campaign?.filter_min_score ?? 0,
    filter_max_score: campaign?.filter_max_score ?? 100,
    filter_stage: campaign?.filter_stage || "",
  });

  if (!isOpen || !campaign) return null;

  return (
    <Modal title="Edit Campaign" onClose={onClose} wide>
      <div className="space-y-4">
        <Field label="Campaign Name">
          <Input value={form.campaign_name} onChange={v => setForm(f => ({ ...f, campaign_name: v }))} placeholder="Campaign name" />
        </Field>

        <Field label="Service Description">
          <textarea
            value={form.service_description}
            onChange={e => setForm(f => ({ ...f, service_description: e.target.value }))}
            rows={2}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
          />
        </Field>

        <Field label="From Email Address">
          <Input value={form.from_address} onChange={v => setForm(f => ({ ...f, from_address: v }))} placeholder="From email" />
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Region / Country Code">
            <Input value={form.filter_region} onChange={v => setForm(f => ({ ...f, filter_region: v }))} placeholder="US, GB, PK..." />
          </Field>
          <Field label="Industry">
            <Input value={form.filter_industry} onChange={v => setForm(f => ({ ...f, filter_industry: v }))} placeholder="technology" />
          </Field>
          <Field label="Minimum Score">
            <Input type="number" value={form.filter_min_score} onChange={v => setForm(f => ({ ...f, filter_min_score: v }))} placeholder="0" />
          </Field>
          <Field label="Maximum Score">
            <Input type="number" value={form.filter_max_score} onChange={v => setForm(f => ({ ...f, filter_max_score: v }))} placeholder="100" />
          </Field>
          <Field label="Company Size">
            <Select value={form.filter_company_size} onChange={v => setForm(f => ({ ...f, filter_company_size: v }))} options={SIZES} placeholder="Any size" />
          </Field>
          <Field label="Lifecycle Stage">
            <Select value={form.filter_stage} onChange={v => setForm(f => ({ ...f, filter_stage: v }))} options={STAGES} placeholder="Any stage" />
          </Field>
        </div>

        <div className="flex gap-3 pt-2">
          <button onClick={() => onSave(form)} className="flex-1 bg-indigo-700 hover:bg-indigo-600 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors">
            Save Changes
          </button>
          <button onClick={onClose} className="flex-1 bg-gray-700 hover:bg-gray-600 text-white rounded-lg px-4 py-2 text-sm transition-colors">
            Cancel
          </button>
        </div>
      </div>
    </Modal>
  );
}