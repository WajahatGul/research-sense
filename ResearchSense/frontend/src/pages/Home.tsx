import { Hero } from "../features/home/Hero";
import { StatsRow } from "../features/home/StatsRow";
import { FeaturedResearchers } from "../features/home/FeaturedResearchers";
import { ResearchAreas } from "../features/home/ResearchAreas";
import { CtaBand } from "../features/home/CtaBand";
import { INSTITUTION_NAME } from "../config";
import { usePageTitle } from "../hooks/usePageTitle";

export default function Home() {
  usePageTitle(INSTITUTION_NAME ? `Research of ${INSTITUTION_NAME}` : null);
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
