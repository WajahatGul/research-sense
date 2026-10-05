import { Hero } from "../features/home/Hero";
import { FeaturedResearchers } from "../features/home/FeaturedResearchers";
import { ResearchAreas } from "../features/home/ResearchAreas";
import { CtaBand } from "../features/home/CtaBand";
import { useOrganisation } from "../hooks/useOrganisation";
import { usePageTitle } from "../hooks/usePageTitle";

export default function Home() {
  const { name } = useOrganisation();
  usePageTitle(name ? `Research of ${name}` : null);
  return (
    <>
      <Hero />
      <FeaturedResearchers />
      <ResearchAreas />
      <CtaBand />
    </>
  );
}
