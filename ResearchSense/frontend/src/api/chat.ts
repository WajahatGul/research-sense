import { get, post } from "./client";
import type { ChatResponse } from "../types";

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export const sendChat = (message: string, history: ChatTurn[] = []) =>
  post<ChatResponse>("/api/chat", { message, history });

/** Starter questions built from the signed-in workspace's own data. */
export const fetchChatSuggestions = () =>
  get<string[]>("/api/chat/suggestions");
