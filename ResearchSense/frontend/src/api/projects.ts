import { get } from "./client";
import type { Project } from "../types";

export const fetchProjects = (status?: string) =>
  get<Project[]>("/api/projects", { status });
