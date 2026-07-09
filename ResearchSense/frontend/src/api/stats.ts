import { get } from "./client";
import type { Stats } from "../types";

export const fetchStats = () => get<Stats>("/api/stats");
