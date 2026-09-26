import { get } from "./client";
import type { Topic } from "../types";

export const fetchTopics = (q?: string, department?: string, field?: string) =>
  get<Topic[]>("/api/topics", { q, department, field });

export const fetchTopic = (id: number) =>
  get<Topic>(`/api/topics/${id}`);
