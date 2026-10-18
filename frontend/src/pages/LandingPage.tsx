import { Navigate, Link } from "react-router-dom";
import {
  ArrowRight,
  Fingerprint,
  GitBranch,
  Network,
  ShieldCheck,
  SlidersHorizontal,
  Users,
  Zap,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { Button } from "@/components/ui/Button";

const PILLARS = [
  {
    icon: Fingerprint,
    title: "Explainable matching",
    body: "GSTIN, PAN, name, address, PIN and phone / email are weighted and scored against every candidate. Every decision — auto-link, send to review, or start a new identity — comes with the exact reasons behind it. No black box.",
  },
  {
    icon: Users,
    title: "Human-in-the-loop review",
    body: "Matches the engine isn't confident about land in a review queue with the full evidence trail attached. A reviewer approves or rejects with one click, and it's on the record who decided what, when.",
  },
  {
    icon: GitBranch,
    title: "Nothing is one-way",
    body: "Wrongly merged a record? Split it back out. Pinned a status that turned out wrong? Clear the override. Reassigned an event to the wrong business? Undo it. Every correction is reversible from a history view.",
  },
  {
    icon: Zap,
    title: "Real activity, not a guess",
    body: "A business's lifecycle status — active, dormant, closed — is inferred from the operational signals departments send in - power usage, filings, inspections, renewals - by file import or scheduled pull. Each inference ships with its own confidence score and reasoning.",
  },
];

const FOUNDATIONS = [
  {
    icon: ShieldCheck,
    title: "Role-based access",
    body: "Viewer, reviewer, admin — each capability gated to the role that should hold it, enforced on every endpoint.",
  },
  {
    icon: SlidersHorizontal,
    title: "Calibrated from feedback",
    body: "Matching weights aren't fixed constants. They're tunable, a calibration view shows how well thresholds line up with what reviewers decide, and a learned suggestion - never applied without an admin - proposes new weights from those decisions.",
  },
  {
    icon: Network,
    title: "No source-system changes",
    body: "Departments keep their own registries exactly as they are. ArthSetu takes their CSV or JSON exports - uploaded, or pulled read-only on a schedule - and resolves them. It never writes back and doesn't ask anyone to migrate anything.",
  },
];

export function LandingPage() {
  useDocumentTitle();
  const { user, loading } = useAuth();

  if (!loading && user) return <Navigate to="/dashboard" replace />;

  return (
    <div className="min-h-screen bg-canvas">
      {/* Nav */}
      <header className="sticky top-0 z-20 border-b border-line/70 bg-canvas/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-brand text-white">
              <Network className="h-4.5 w-4.5" />
            </div>
            <span className="text-[15px] font-semibold tracking-tight text-ink">
              ArthSetu
            </span>
          </div>
          <Link to="/login">
            <Button variant="secondary" size="sm">
              Sign in
            </Button>
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 -top-32 h-[560px] bg-[radial-gradient(ellipse_at_top,_rgb(var(--c-brand)/0.14),_transparent_65%)]"
        />
        <div className="relative mx-auto max-w-4xl px-6 pb-24 pt-20 text-center sm:pt-28">
          <div className="mb-6 inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 text-[12px] font-medium text-ink-muted shadow-sm">
            <span className="h-1.5 w-1.5 rounded-full bg-ok" />
            Business Identity &amp; Activity Intelligence
          </div>
          <h1 className="text-balance text-5xl font-extrabold tracking-tight text-ink sm:text-6xl">
            One business.
            <br />
            One identity. One truth.
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-balance text-[17px] leading-relaxed text-ink-muted">
            Every government department that touches a business — labour,
            municipal, pollution control, electricity — keeps its own record
            of it, under its own spelling, in its own silo. ArthSetu resolves
            those fragments into one canonical identity, explains exactly why
            it believes two records are the same business, and keeps a human
            in the loop for everything it isn't sure about.
          </p>
          <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
            <Link to="/login">
              <Button size="lg">
                Sign in to the console
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <a href="#how-it-works">
              <Button variant="secondary" size="lg">
                See how it works
              </Button>
            </a>
          </div>
        </div>
      </section>

      {/* The problem */}
      <section className="border-t border-line bg-surface">
        <div className="mx-auto max-w-4xl px-6 py-20 text-center">
          <h2 className="text-3xl font-bold tracking-tight text-ink sm:text-4xl">
            The same business, four different ghosts
          </h2>
          <p className="mx-auto mt-5 max-w-2xl text-balance text-[16px] leading-relaxed text-ink-muted">
            "Sharma Traders", "M/S Sharma Traders" and "SHARMA TRADERS" might
            be one shop — or three. Without a way to tell, every department
            sees a partial, disconnected picture of the same business, and
            nobody can answer a simple question: is this business still
            active? ArthSetu exists to answer that question, with evidence.
          </p>
        </div>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="mx-auto max-w-6xl px-6 py-24">
        <div className="mx-auto mb-14 max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight text-ink sm:text-4xl">
            How it works
          </h2>
          <p className="mt-4 text-[16px] leading-relaxed text-ink-muted">
            Four principles the whole platform is built around.
          </p>
        </div>
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-2">
          {PILLARS.map((p) => (
            <div
              key={p.title}
              className="rounded-xl border border-line bg-surface p-7 shadow-card transition-shadow hover:shadow-pop"
            >
              <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-lg bg-brand-soft text-brand">
                <p.icon className="h-5 w-5" />
              </div>
              <h3 className="text-lg font-semibold text-ink">{p.title}</h3>
              <p className="mt-2 text-[14.5px] leading-relaxed text-ink-muted">
                {p.body}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Built for government */}
      <section className="border-t border-line bg-surface">
        <div className="mx-auto max-w-6xl px-6 py-24">
          <div className="mx-auto mb-14 max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight text-ink sm:text-4xl">
              Built to be trusted with the record
            </h2>
            <p className="mt-4 text-[16px] leading-relaxed text-ink-muted">
              A platform government departments can actually rely on has to
              earn it structurally, not just promise it.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-10 sm:grid-cols-3">
            {FOUNDATIONS.map((f) => (
              <div key={f.title} className="text-center sm:text-left">
                <div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-brand-soft text-brand sm:mx-0">
                  <f.icon className="h-5 w-5" />
                </div>
                <h3 className="text-base font-semibold text-ink">
                  {f.title}
                </h3>
                <p className="mt-2 text-[14px] leading-relaxed text-ink-muted">
                  {f.body}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="mx-auto max-w-4xl px-6 py-24 text-center">
        <h2 className="text-3xl font-bold tracking-tight text-ink sm:text-4xl">
          See it resolve a real record
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-[16px] leading-relaxed text-ink-muted">
          Sign in to the console to walk through the dashboard, the review
          queue, and an explained match end to end.
        </p>
        <div className="mt-8">
          <Link to="/login">
            <Button size="lg">
              Sign in
              <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
        </div>
      </section>

      <footer className="border-t border-line px-6 py-8 text-center text-[12px] text-ink-subtle">
        ArthSetu — Unified Business Identity &amp; Activity Intelligence
      </footer>
    </div>
  );
}
