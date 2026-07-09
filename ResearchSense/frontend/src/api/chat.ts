import { post } from "./client";
import type { ChatResponse } from "../types";

export const sendChat = (message: string) =>
  post<ChatResponse>("/api/chat", { message });
