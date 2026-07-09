import { Routes, Route } from "react-router-dom";

import Layout from "./layout/Layout";
import Home from "./pages/Home";
import Researchers from "./pages/Researchers";
import ResearcherProfile from "./pages/ResearcherProfile";
import Publications from "./pages/Publications";
import Topics from "./pages/Topics";
import Projects from "./pages/Projects";
import Collaboration from "./pages/Collaboration";
import Ask from "./pages/Ask";
import NotFound from "./pages/NotFound";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/researchers" element={<Researchers />} />
        <Route path="/researchers/:id" element={<ResearcherProfile />} />
        <Route path="/publications" element={<Publications />} />
        <Route path="/topics" element={<Topics />} />
        <Route path="/projects" element={<Projects />} />
        <Route path="/collaboration" element={<Collaboration />} />
        <Route path="/ask" element={<Ask />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
