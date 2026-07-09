import { get } from "./client";
import type { Project } from "../types";

export const fetchProjects = (status?: string, campus?: string) =>
  get<Project[]>("/api/projects", { status, campus });
