import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Search } from "@/components/icons";

const UBID_RE = /^ubid[-_ ]?[a-z0-9]+$/i;

export function GlobalSearch() {
  const [value, setValue] = useState("");
  const navigate = useNavigate();

  function submit(e: FormEvent) {
    e.preventDefault();
    const q = value.trim();
    if (!q) return;
    if (UBID_RE.test(q)) {
      navigate(`/businesses/${encodeURIComponent(q.toUpperCase())}`);
    } else {
      navigate(`/businesses?q=${encodeURIComponent(q)}`);
    }
    setValue("");
  }

  return (
    <form onSubmit={submit} className="relative w-full max-w-sm">
      <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-subtle" />
      <input
        type="search"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Search UBID, name, PAN or GSTIN…"
        aria-label="Global search"
        className="field h-9 pl-8"
      />
    </form>
  );
}
