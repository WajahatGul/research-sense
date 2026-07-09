import { Hero } from "../features/home/Hero";
import { StatsRow } from "../features/home/StatsRow";
import { FeaturedResearchers } from "../features/home/FeaturedResearchers";
import { ResearchAreas } from "../features/home/ResearchAreas";
import { CtaBand } from "../features/home/CtaBand";

export default function Home() {
  return (
    <>
      <Hero />
      <StatsRow />
      <FeaturedResearchers />
      <ResearchAreas />
      <CtaBand />
    </>
  );
}
