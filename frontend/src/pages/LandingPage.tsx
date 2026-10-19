import { Navigate, Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { Button } from "@/components/ui/Button";
import { LegalFooter } from "@/pages/LegalPages";

interface Feature {
  id: string;
  title: string;
  body: string[];
  image: string;
  alt: string;
  caption: string;
}

const FEATURES: Feature[] = [
  {
    id: "review",
    title: "Every match comes with its evidence",
    body: [
      "GSTIN, PAN, name, address, PIN code and phone or email are weighted and scored against each candidate business. The score and the reasons behind it are stored with the decision.",
      "Records the engine is unsure about go to a review queue. A reviewer approves or rejects with one click, and the console records who decided and when. A rejected record gets its own business identity instead of staying in limbo.",
    ],
    image: "/screens/review.webp",
    alt: "The review queue listing uncertain matches with confidence scores and the evidence for each",
    caption: "Review queue on the demo dataset.",
  },
  {
    id: "profile",
    title: "One page per business",
    body: [
      "A business profile lists every departmental record linked to it, the matching evidence, a timeline of filings, renewals and inspections, and the status the engine inferred with its confidence and reasons.",
      "A wrong merge can be split back out, a status can be pinned by a reviewer, and every correction can be undone from the history.",
    ],
    image: "/screens/profile.webp",
    alt: "A business profile with linked records, activity timeline, status reasoning and audit trail",
    caption: "Business profile on the demo dataset.",
  },
  {
    id: "feeds",
    title: "Takes the exports departments already have",
    body: [
      "Upload a CSV of records or of activity events, or point a source system at a CSV or JSON export it publishes and let the scheduled sync pull it. Column names are matched loosely, so each department keeps its own format.",
      "ArthSetu only reads. It never writes back to a department system, and a connector can reach public https addresses only.",
    ],
    image: "/screens/ingest.webp",
    alt: "The ingestion page with CSV import, activity event import and connector settings",
    caption: "Data ingestion page.",
  },
  {
    id: "tuning",
    title: "Weights that follow what reviewers decide",
    body: [
      "The matching weights and thresholds are editable by an administrator. A calibration view shows how confidence lines up with approvals and rejections.",
      "A small logistic regression over the decided cases suggests new weights and shows the numbers behind each suggestion. It never scores a record itself, and nothing changes until an administrator applies it.",
    ],
    image: "/screens/tuning.webp",
    alt: "Matching tuning page with editable weights and a table of learned weight suggestions",
    caption: "Matching tuning page. The demo reviews are synthetic, so the suggested weights are illustrative.",
  },
];

const STEPS = [
  "A department file or connector delivers business records.",
  "Each record is normalised and scored against candidate businesses.",
  "High scores link automatically, middle scores wait for a reviewer, low scores open a new identity.",
  "Activity events from the departments decide whether each business reads as active, dormant or closed.",
];

export function LandingPage() {
  useDocumentTitle();
  const { user, loading } = useAuth();

  if (!loading && user) return <Navigate to="/dashboard" replace />;

  return (
    <div className="min-h-screen bg-canvas">
      <header className="sticky top-0 z-20 border-b border-line bg-canvas">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
          <span className="text-[15px] font-semibold tracking-tight text-ink">ArthSetu</span>
          <Link to="/login">
            <Button variant="secondary" size="sm">
              Sign in
            </Button>
          </Link>
        </div>
      </header>

      <main>
        <section className="mx-auto max-w-6xl px-6 pb-10 pt-16 sm:pt-20">
          <h1 className="max-w-3xl text-4xl font-semibold leading-[1.1] tracking-tight text-ink sm:text-5xl">
            One business, one identity, across every department.
          </h1>
          <p className="mt-5 max-w-2xl text-[16px] leading-relaxed text-ink-muted">
            Labour, municipal, pollution control and electricity each keep their own record of the same business, under
            slightly different names. ArthSetu resolves those records into a single identity, shows exactly why it
            believes they match, and leaves the uncertain cases to a person.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/login">
              <Button size="lg">Sign in to the console</Button>
            </Link>
            <a href="#review">
              <Button variant="secondary" size="lg">
                See the console
              </Button>
            </a>
          </div>
          <figure className="mt-12">
            <img
              src="/screens/dashboard.webp"
              alt="The ArthSetu dashboard with business counts, activity trend and status breakdown"
              width={1440}
              height={900}
              className="w-full rounded-md border border-line"
            />
            <figcaption className="mt-2 text-[12px] text-ink-subtle">
              Dashboard on the demo dataset. All data in these screenshots is synthetic.
            </figcaption>
          </figure>
        </section>

        {FEATURES.map((f, i) => (
          <section key={f.id} id={f.id} className="border-t border-line">
            <div className="mx-auto grid max-w-6xl gap-10 px-6 py-16 lg:grid-cols-5 lg:items-center">
              <div className={i % 2 === 1 ? "lg:order-2 lg:col-span-2" : "lg:col-span-2"}>
                <h2 className="text-2xl font-semibold tracking-tight text-ink">{f.title}</h2>
                <div className="mt-4 space-y-3 text-[15px] leading-relaxed text-ink-muted">
                  {f.body.map((p) => (
                    <p key={p}>{p}</p>
                  ))}
                </div>
              </div>
              <figure className={i % 2 === 1 ? "lg:col-span-3" : "lg:col-span-3"}>
                <img
                  src={f.image}
                  alt={f.alt}
                  width={1440}
                  height={900}
                  loading="lazy"
                  className="w-full rounded-md border border-line"
                />
                <figcaption className="mt-2 text-[12px] text-ink-subtle">{f.caption}</figcaption>
              </figure>
            </div>
          </section>
        ))}

        <section className="border-t border-line">
          <div className="mx-auto max-w-6xl px-6 py-16">
            <h2 className="text-2xl font-semibold tracking-tight text-ink">How a record becomes an identity</h2>
            <ol className="mt-6 max-w-2xl list-decimal space-y-3 pl-5 text-[15px] leading-relaxed text-ink-muted">
              {STEPS.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ol>
            <p className="mt-8 max-w-2xl text-[15px] leading-relaxed text-ink-muted">
              Access is by role: viewers read, reviewers decide and correct, administrators import data and tune the
              engine. Accounts are created by an administrator.
            </p>
            <div className="mt-8">
              <Link to="/login">
                <Button size="lg">Sign in to the console</Button>
              </Link>
            </div>
          </div>
        </section>
      </main>

      <LegalFooter />
    </div>
  );
}
