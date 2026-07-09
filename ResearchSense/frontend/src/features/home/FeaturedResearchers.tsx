import { useQuery } from "@tanstack/react-query";

import { fetchFeaturedResearchers } from "../../api/researchers";
import { ResearcherCard } from "../../components/ResearcherCard";
import { Section } from "../../components/Section";
import { Loader, ErrorState } from "../../components/StateViews";
import styles from "./FeaturedResearchers.module.css";

export function FeaturedResearchers() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["featured-researchers"],
    queryFn: () => fetchFeaturedResearchers(6),
  });

  return (
    <Section
      eyebrow="Most cited"
      title="Featured researchers"
      linkTo="/researchers"
      linkLabel="All researchers"
    >
      {isLoading && <Loader />}
      {isError && <ErrorState />}
      {data && (
        <div className={styles.grid}>
          {data.map((r) => (
            <ResearcherCard key={r.researcher_id} researcher={r} />
          ))}
        </div>
      )}
    </Section>
  );
}
