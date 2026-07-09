import { useQuery } from "@tanstack/react-query";

import { fetchTopics } from "../../api/topics";
import { Section } from "../../components/Section";
import { TopicCard } from "../../components/TopicCard";
import { Loader, ErrorState } from "../../components/StateViews";
import styles from "./ResearchAreas.module.css";

export function ResearchAreas() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["topics"],
    queryFn: () => fetchTopics(),
  });

  return (
    <Section
      eyebrow="Fields of inquiry"
      title="Research areas"
      linkTo="/topics"
      linkLabel="All areas"
    >
      {isLoading && <Loader />}
      {isError && <ErrorState />}
      {data && (
        <div className={styles.grid}>
          {data.slice(0, 8).map((t) => (
            <TopicCard key={t.topic_id} topic={t} />
          ))}
        </div>
      )}
    </Section>
  );
}
