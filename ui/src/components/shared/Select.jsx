export default function Select({ value, onChange, options, placeholder }) {
  return (
    <select 
      value={value} 
      onChange={e => onChange(e.target.value)}
      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
    >
      <option value="">{placeholder || "Any"}</option>
      {options.map(o => <option key={o} value={o}>{o}</option>)}
    </select>
  );
}