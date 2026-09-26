import { lazy } from "react";
import { Routes, Route } from "react-router-dom";

import Layout from "./layout/Layout";
import Home from "./pages/Home";
// Every page used to ship in one 844 KB script, so a visitor opening the
// home page also downloaded the analytics charts, the portal and the
// markdown renderer. Pages other than home now load when first visited.
const Researchers = lazy(() => import("./pages/Researchers"));
const ResearcherProfile = lazy(() => import("./pages/ResearcherProfile"));
const Publications = lazy(() => import("./pages/Publications"));
const PublicationDetail = lazy(() => import("./pages/PublicationDetail"));
const Topics = lazy(() => import("./pages/Topics"));
const TopicDetail = lazy(() => import("./pages/TopicDetail"));
const Projects = lazy(() => import("./pages/Projects"));
const Collaboration = lazy(() => import("./pages/Collaboration"));
const Analytics = lazy(() => import("./pages/Analytics"));
const Library = lazy(() => import("./pages/Library"));
const StaffAccess = lazy(() => import("./pages/StaffAccess"));
const Guide = lazy(() => import("./pages/Guide"));
const Portal = lazy(() => import("./pages/Portal"));
const Ask = lazy(() => import("./pages/Ask"));
const Search = lazy(() => import("./pages/Search"));
const NotFound = lazy(() => import("./pages/NotFound"));

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/search" element={<Search />} />
        <Route path="/guide" element={<Guide />} />
        <Route path="/researchers" element={<Researchers />} />
        <Route path="/researchers/:id" element={<ResearcherProfile />} />
        <Route path="/publications" element={<Publications />} />
        <Route path="/publications/:id" element={<PublicationDetail />} />
        <Route path="/topics" element={<Topics />} />
        <Route path="/topics/:id" element={<TopicDetail />} />
        <Route path="/projects" element={<Projects />} />
        <Route path="/collaboration" element={<Collaboration />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/library" element={<Library />} />
        <Route path="/portal" element={<Portal />} />
        {/* Deliberately not linked from the site: the staff entrance does
            not belong on the page researchers use to sign in. */}
        <Route path="/staff-access" element={<StaffAccess />} />
        <Route path="/ask" element={<Ask />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
