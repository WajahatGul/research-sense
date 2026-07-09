import { get } from "./client";
import type { Topic } from "../types";

export const fetchTopics = (q?: string) =>
  get<Topic[]>("/api/topics", { q });

export const fetchTopic = (id: number) =>
  get<Topic>(`/api/topics/${id}`);
