import { highlight } from "./highlight";

export interface LoggedEvent {
  id: string;
  type: string;
  receivedAt: string;
  payload: string;
}

/** Admin page: recent webhook payloads, with the search term highlighted. */
export function WebhookLog({ events, search }: { events: LoggedEvent[]; search: string }) {
  return (
    <table className="webhook-log">
      <tbody>
        {events.map((e) => (
          <tr key={e.id}>
            <td>{e.receivedAt}</td>
            <td>{e.type}</td>
            {/* highlight() escapes the payload and the term; see highlight.ts */}
            <td>
              <pre dangerouslySetInnerHTML={{ __html: highlight(e.payload, search) }} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
