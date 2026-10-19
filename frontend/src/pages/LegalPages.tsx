import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

const UPDATED = "19 October 2026";
const CONTACT = "aanimesh_be23@thapar.edu";

function LegalLayout({ title, intro, children }: { title: string; intro: string; children: ReactNode }) {
  useDocumentTitle(title);
  return (
    <div className="min-h-screen bg-canvas">
      <header className="border-b border-line bg-canvas">
        <div className="mx-auto flex h-14 max-w-3xl items-center justify-between px-6">
          <Link to="/" className="text-[15px] font-semibold tracking-tight text-ink">
            ArthSetu
          </Link>
          <Link to="/login" className="text-[13px] font-medium text-ink-muted hover:text-ink hover:underline">
            Sign in
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-6 py-12">
        <h1 className="text-3xl font-semibold tracking-tight text-ink">{title}</h1>
        <p className="mt-2 text-[13px] text-ink-subtle">Last updated {UPDATED}</p>
        <p className="mt-6 text-[15px] leading-relaxed text-ink-muted">{intro}</p>
        <div className="mt-8 space-y-8 text-[15px] leading-relaxed text-ink-muted">{children}</div>
        <p className="mt-12 border-t border-line pt-6 text-[13px] text-ink-subtle">
          This is a plain-language policy written by the developer. It is not legal advice.
        </p>
      </main>
      <LegalFooter />
    </div>
  );
}

export function LegalFooter() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-3 px-6 py-6 text-[13px] text-ink-subtle">
        <span>ArthSetu, built and run by Animesh</span>
        <nav className="flex gap-5">
          <Link to="/terms" className="hover:text-ink hover:underline">
            Terms
          </Link>
          <Link to="/privacy" className="hover:text-ink hover:underline">
            Privacy
          </Link>
        </nav>
      </div>
    </footer>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="mb-2 text-lg font-semibold text-ink">{title}</h2>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function Bullets({ items }: { items: string[] }) {
  return (
    <ul className="list-disc space-y-1.5 pl-5">
      {items.map((i) => (
        <li key={i}>{i}</li>
      ))}
    </ul>
  );
}

export function TermsPage() {
  return (
    <LegalLayout
      title="Terms of Service"
      intro="ArthSetu is a business identity and activity console: it links records about the same business from different departments and shows an explainable status for each. These terms apply to the hosted console and its API."
    >
      <Section title="Who runs it">
        <p>
          ArthSetu is built and operated by Animesh, an individual developer. Contact:{" "}
          <a className="text-brand hover:underline" href={`mailto:${CONTACT}`}>
            {CONTACT}
          </a>
          .
        </p>
      </Section>
      <Section title="What the service is, and is not">
        <p>
          The hosted instance is a prototype. The data in it is synthetic demo data unless an administrator has loaded
          real department files. Matching and status results come from rule-based scoring (with weights an administrator
          can tune) and are suggestions: a reviewer approves, rejects or reverses them. Do not treat a result as an
          official government record or as a basis for enforcement without checking the source records.
        </p>
      </Section>
      <Section title="Accounts">
        <Bullets
          items={[
            "Accounts are created by an administrator. There is no public sign-up.",
            "You are responsible for keeping your password private and for what is done with your account.",
            "Roles limit what you can do: viewers read, reviewers decide and correct, administrators import data and manage users.",
          ]}
        />
      </Section>
      <Section title="Acceptable use">
        <Bullets
          items={[
            "Use the console only for the purpose it was set up for, with data you are allowed to handle.",
            "Do not upload data you have no right to process, or try to bypass roles, rate limits or other safeguards.",
            "Do not probe, overload or scrape the service. Report security problems to the contact above instead.",
          ]}
        />
      </Section>
      <Section title="Data you load">
        <p>
          You remain responsible for having the right to load any records, for their accuracy, and for any legal basis
          your department needs to process them. ArthSetu only reads exports you upload or a connector URL an
          administrator configures. It never writes back to a department system.
        </p>
      </Section>
      <Section title="No warranty, limited liability">
        <p>
          The service is provided as is, without warranties of any kind, and may change, be interrupted or be shut down.
          The free hosting tier it runs on can be slow to start after it has been idle. To the extent the law allows, the
          operator is not liable for indirect or consequential loss arising from use of the service.
        </p>
      </Section>
      <Section title="Suspension and changes">
        <p>
          Accounts may be disabled if these terms are broken. These terms may be updated; the date above changes when
          they are, and continued use after a change means you accept it.
        </p>
      </Section>
      <Section title="Governing law">
        <p>These terms are governed by the laws of India. Disputes belong to the courts of India.</p>
      </Section>
      <p>
        Questions: <a className="text-brand hover:underline" href={`mailto:${CONTACT}`}>{CONTACT}</a>. See also the{" "}
        <Link to="/privacy" className="text-brand hover:underline">
          Privacy Policy
        </Link>
        .
      </p>
    </LegalLayout>
  );
}

export function PrivacyPage() {
  return (
    <LegalLayout
      title="Privacy Policy"
      intro="This page lists exactly what ArthSetu stores about you and about the businesses it handles, who else touches that data, and how to have it removed."
    >
      <Section title="Who is responsible">
        <p>
          Animesh, an individual developer, runs the hosted console. Contact:{" "}
          <a className="text-brand hover:underline" href={`mailto:${CONTACT}`}>
            {CONTACT}
          </a>
          . If your department runs its own copy, your department is responsible for the data in it.
        </p>
      </Section>
      <Section title="What is stored about users">
        <Bullets
          items={[
            "Sign-in: your email address and password are held by Google Firebase Authentication. The ArthSetu server never sees your password, only a signed token that proves who you are.",
            "Profile: name, email, role (viewer, reviewer or administrator) and whether the account is active.",
            "Audit trail: each approval, rejection, correction, import or settings change is recorded with your email and a timestamp. This is the point of the audit trail, so it is kept.",
          ]}
        />
      </Section>
      <Section title="What is stored about businesses">
        <p>
          Records that administrators import or that a connector pulls: business name, PAN, GSTIN, address, PIN code,
          optional phone and email, the department a record came from, and activity events such as filings, renewals and
          inspections. The demo dataset is synthetic and does not describe real businesses. Real data appears only if an
          administrator loads it.
        </p>
      </Section>
      <Section title="What is not collected">
        <Bullets
          items={[
            "No analytics, advertising or tracking scripts, and no third-party fonts or content networks (the typeface is served from the site itself).",
            "No cookies set by ArthSetu. Firebase keeps your sign-in session in your browser's own storage (IndexedDB) so you stay signed in.",
            "No selling or sharing of data for marketing.",
          ]}
        />
      </Section>
      <Section title="Who else handles the data">
        <Bullets
          items={[
            "Google Firebase Authentication: sign-in identities.",
            "Render: runs the API and sees request logs (addresses, paths, timing).",
            "The PostgreSQL provider configured for the deployment (for example Neon or Supabase): stores all records listed above.",
            "Vercel: serves the web pages and sees ordinary web server logs.",
            "A department's own export URL, if an administrator configures a connector: ArthSetu fetches from it. Nothing is sent to it.",
          ]}
        />
        <p>No records are sent to any AI service. Matching and status scoring run inside the API.</p>
      </Section>
      <Section title="How long it is kept">
        <p>
          Records and the audit trail are kept until an administrator removes them or the deployment is deleted. The
          audit trail is intentionally permanent while the deployment exists, because it explains past decisions.
        </p>
      </Section>
      <Section title="Your choices">
        <p>
          To see, correct or delete your account data, or to have an account closed, write to{" "}
          <a className="text-brand hover:underline" href={`mailto:${CONTACT}`}>
            {CONTACT}
          </a>
          . Accounts can be disabled in the console; deleting the Firebase identity and the profile is done by the
          operator on request. Audit entries that name you are anonymised on request instead of deleted, so the history
          of decisions stays intact.
        </p>
      </Section>
      <Section title="Security">
        <p>
          Connections use HTTPS. Roles are enforced on every API call. No system is perfectly safe; report a problem to
          the contact above.
        </p>
      </Section>
      <Section title="Children, changes and law">
        <p>
          The service is for officials and administrators, not for children. If this policy changes, the date above
          changes. It is governed by the laws of India, including the Digital Personal Data Protection Act, 2023 where it
          applies. See also the{" "}
          <Link to="/terms" className="text-brand hover:underline">
            Terms of Service
          </Link>
          .
        </p>
      </Section>
    </LegalLayout>
  );
}
