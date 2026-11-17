import { Table } from "../db.ts";

export type User = {
  id: string;
  email: string;
  name: string;
  teamId: string;
  deactivated: boolean;
};

export const usersTable = new Table<User>();

export function getUser(id: string): User | undefined {
  return usersTable.get(id);
}

export function activeUsers(): User[] {
  return usersTable.where((u) => !u.deactivated);
}
