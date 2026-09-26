import { get } from "./client";
import type { Topic } from "../types";

export const fetchTopics = (q?: string, department?: string) =>
  get<Topic[]>("/api/topics", { q, department });

export const fetchTopic = (id: number) =>
  get<Topic>(`/api/topics/${id}`);
