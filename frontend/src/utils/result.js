import { createId } from "./id";

export const withClientMeta = (dto) => ({
  ...dto,
  clientId: createId("client"),
  receivedAt: new Date().toISOString(),
});
