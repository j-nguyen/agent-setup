import type { Contact } from "../contacts/types";

const tagLabel = (t: string) => (t.length > 24 ? t.slice(0, 24) + "…" : t.length === 0 ? "(untitled)" : t);

export function ContactCard({ contact }: { contact: Contact }) {
  return (
    <div className="contact-card">
      <h3>{contact.name}</h3>
      <a href={`mailto:${contact.email}`}>{contact.email}</a>
      <ul className="tags">
        {contact.tags.map((t) => (
          <li key={t}>{tagLabel(t)}</li>
        ))}
      </ul>
    </div>
  );
}
