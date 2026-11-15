import type { Contact } from "../contacts/types";

export function ContactCard({ contact }: { contact: Contact }) {
  return (
    <div className="contact-card">
      <h3>{contact.name}</h3>
      <a href={`mailto:${contact.email}`}>{contact.email}</a>
    </div>
  );
}
