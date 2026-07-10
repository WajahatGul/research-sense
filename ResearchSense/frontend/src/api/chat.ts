import { post } from "./client";
import type { ChatResponse } from "../types";

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export const sendChat = (message: string, history: ChatTurn[] = []) =>
  post<ChatResponse>("/api/chat", { message, history });
