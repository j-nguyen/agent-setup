export interface DeliveryStore {
  markDelivered(eventId: string, endpointId: string): Promise<void>;
  markFailed(eventId: string, endpointId: string, reason: string): Promise<void>;
}

export interface DeliveryRecord {
  eventId: string;
  endpointId: string;
  outcome: "delivered" | "failed";
  reason?: string;
}

export class InMemoryDeliveryStore implements DeliveryStore {
  records: DeliveryRecord[] = [];

  async markDelivered(eventId: string, endpointId: string): Promise<void> {
    this.records.push({ eventId, endpointId, outcome: "delivered" });
  }

  async markFailed(eventId: string, endpointId: string, reason: string): Promise<void> {
    this.records.push({ eventId, endpointId, outcome: "failed", reason });
  }
}
